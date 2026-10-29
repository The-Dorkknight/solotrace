# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Single-sided autorouter with wire-link jumpers.

Why it should look tidy instead of like tangled string:

* Moves are only 0 / 45 / 90 degrees and the search state includes the heading, so a
  turn of more than 45 degrees in one step is impossible. A 90 degree bend is therefore
  always two 45 degree turns: chamfered by construction.
* Every turn costs a little, so routes run straight and bend only where needed.
* Nets are routed power-first, then short-to-long, against hard obstacles, so the copper
  that exists is always legal.
* When a connection is blocked, a "soft" search finds the cheapest path through other
  routes, rips up only the nets it crosses, routes the blocked net, and reroutes the
  victims (rip-up and reroute with a budget).
* Only when that fails is a jumper used: a straight wire link on the component side that
  hops over copper. A jumper costs more than a long detour, so you get as few as possible.
* Every finished path is checked against the exact copper geometry before it is kept.

Pure Python, standard library only.
"""
from __future__ import annotations

import heapq
import math
import os
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from .board import Board, Jumper, Trace, clamp_width
from .geom import (Cap, Poly, bbox_gap, dist, point_in_poly, poly_seg_dist, segments_cross,
                   segments_touch, seg_point_dist, shape_dist, simplify_polyline)

SQ2 = math.sqrt(2.0)
DIRS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
HARD = 254      # blocked for every net
MULTI = 255     # blocked by two or more nets


class RoutingCancelled(Exception):
    pass


KEEP_OUT_FACTOR = 60.0     # "keep traces out from under parts": body cells cost this many times more


class RouteOptions:
    def __init__(self, **kw) -> None:
        self.jumper_cost = 35.0       # in grid cells of trace; higher = fewer jumpers, longer detours
        self.use_jumpers = True
        self.turn_cost = 0.7          # cost of each 45 degree turn, grid cells
        self.soft_penalty = 18.0      # cost of passing through another net while looking for rip-ups
        self.max_ripups = 40
        self.max_rounds = 3
        self.margin = 10.0            # search window margin around a connection, mm
        self.max_expansions = 250000
        self.smooth = True            # enlarge chamfers on wide traces where there is room
        self.under_part_cost = 0.3    # extra cost per grid step under a part's body (keeps the area
                                      # between DIP rows free unless going round costs much more)
        self.time_limit = 120.0
        # try several net orders and keep the best result (the tests set SOLOTRACE_ROUTE_ATTEMPTS=1
        # so they run quickly; the tests of the retries themselves ask for more)
        self.attempts = int(os.environ.get("SOLOTRACE_ROUTE_ATTEMPTS", "6"))
        self.time_budget = 12.0       # ... but start no new try after this many seconds
        self.order_seed = None        # internal: shuffles the net order a little for one try
        for k, v in kw.items():
            if not hasattr(self, k):
                raise TypeError("unknown option %s" % k)
            setattr(self, k, v)


class RouteResult:
    def __init__(self) -> None:
        self.routed_nets = 0
        self.failed_nets: List[str] = []
        self.jumpers = 0
        self.ripups = 0
        self.seconds = 0.0
        self.messages: List[str] = []

    @property
    def complete(self) -> bool:
        return not self.failed_nets

    def summary(self) -> str:
        s = "%d net(s) routed" % self.routed_nets
        if self.jumpers:
            s += ", %d jumper(s)" % self.jumpers
        if self.ripups:
            s += ", %d rip-up(s)" % self.ripups
        if self.failed_nets:
            s += ", NOT routed: %s" % ", ".join(self.failed_nets)
        return s + " (%.1f s)" % self.seconds


class _Group:
    __slots__ = ("pins", "nodes")

    def __init__(self) -> None:
        self.pins: Set[str] = set()
        self.nodes: Dict[int, float] = {}


class _Index:
    """Tiny spatial hash of copper shapes for exact clearance checks."""

    def __init__(self, cell: float = 4.0) -> None:
        self.cell = cell
        self.cells: Dict[Tuple[int, int], Set[int]] = {}
        self.items: Dict[int, object] = {}
        self._next = 1

    def _range(self, bb, pad):
        c = self.cell
        return (int(math.floor((bb[0] - pad) / c)), int(math.floor((bb[1] - pad) / c)),
                int(math.floor((bb[2] + pad) / c)), int(math.floor((bb[3] + pad) / c)))

    def add(self, shape) -> int:
        sid = self._next
        self._next += 1
        self.items[sid] = shape
        x0, y0, x1, y1 = self._range(shape.bbox(), 0.0)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                self.cells.setdefault((cx, cy), set()).add(sid)
        return sid

    def remove(self, sid: int) -> None:
        shape = self.items.pop(sid, None)
        if shape is None:
            return
        x0, y0, x1, y1 = self._range(shape.bbox(), 0.0)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                s = self.cells.get((cx, cy))
                if s:
                    s.discard(sid)

    def near(self, bb, pad: float):
        x0, y0, x1, y1 = self._range(bb, pad)
        out: Set[int] = set()
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                s = self.cells.get((cx, cy))
                if s:
                    out |= s
        return [self.items[i] for i in out if i in self.items]


class AutoRouter:
    def __init__(self, board: Board, options: Optional[RouteOptions] = None,
                 progress: Optional[Callable[[str, float], None]] = None,
                 cancel: Optional[Callable[[], bool]] = None) -> None:
        self.board = board
        self.opt = options or RouteOptions()
        self.progress = progress
        self.cancel = cancel
        st = board.settings
        self.g = st.grid
        self.clr = st.clearance
        self.nx = int(board.width / self.g + 1e-9) + 1
        self.ny = int(board.height / self.g + 1e-9) + 1
        self.N = self.nx * self.ny
        self._t0 = time.time()

    # ------------------------------------------------------------------ helpers
    def _check(self) -> None:
        if self.cancel and self.cancel():
            raise RoutingCancelled()
        if time.time() - self._t0 > self.opt.time_limit:
            raise RoutingCancelled()

    def _say(self, msg: str, frac: float = 0.0) -> None:
        if self.progress:
            self.progress(msg, frac)

    def _xy(self, k: int) -> Tuple[float, float]:
        return ((k % self.nx) * self.g, (k // self.nx) * self.g)

    def _node_at(self, x: float, y: float) -> int:
        i = min(self.nx - 1, max(0, int(round(x / self.g))))
        j = min(self.ny - 1, max(0, int(round(y / self.g))))
        return j * self.nx + i

    # ------------------------------------------------------------------- setup
    def _setup(self, rip_nets: Set[str]) -> None:
        """Build width classes, obstacle maps and the exact-geometry index."""
        b = self.board
        self.names = sorted(b.nets)
        self.nid: Dict[str, int] = {n: min(250, i + 1) for i, n in enumerate(self.names)}
        self.width = {n: clamp_width(b.net_width(n)) for n in self.names}
        widths = sorted({round(w, 3) for w in self.width.values()} | {round(b.settings.jumper_pad, 3)})
        self.classes = widths
        self.cidx = {w: i for i, w in enumerate(widths)}
        self.hw = [w / 2.0 for w in widths]
        K = len(widths)
        N = self.N
        self.static = [bytearray(N) for _ in range(K)]
        self.dcnt = [[0] * N for _ in range(K)]
        self.dsid = [[0] * N for _ in range(K)]
        self.dssq = [[0] * N for _ in range(K)]
        self.hist = [0.0] * N
        self.index = _Index()
        self._stencils: Dict[Tuple[int, float], List[Tuple[int, int]]] = {}
        # copper that stays: everything except auto routes of the nets being (re)routed
        keep_auto = [t for t in b.traces if not t.manual and t.net not in rip_nets]
        keep_jump = [j for j in b.jumpers if j.auto and j.net not in rip_nets]
        shapes = []
        for ref, pl in b.parts.items():
            d = b.get_def(pl.part_id)
            for pad in d.pads:
                nm = None
                n = b.net_of("%s.%s" % (ref, pad.name))
                if n:
                    nm = n.name
                sh, _dr, _c = b.pad_copper(ref, pad.name, nm)
                shapes.extend(sh)
        for t in b.traces:
            if t.manual or t in keep_auto:
                for i in range(len(t.points) - 1):
                    a, c = t.points[i], t.points[i + 1]
                    shapes.append(Cap(a[0], a[1], c[0], c[1], t.widths[i] / 2.0, t.net, ("fixed",)))
        r = b.settings.jumper_pad / 2.0
        for j in b.jumpers:
            if (not j.auto) or j in keep_jump:
                shapes.append(Cap(j.a[0], j.a[1], j.a[0], j.a[1], r, j.net, ("fixed",)))
                shapes.append(Cap(j.b[0], j.b[1], j.b[0], j.b[1], r, j.net, ("fixed",)))
        for s in shapes:
            self.index.add(s)
            nm = s.net
            nid = self.nid.get(nm, HARD) if nm and not nm.startswith("~") else HARD
            self._stamp_static(s, nid)
        self._stamp_edges()
        # fixed jumper wires (top side) for crossing tests
        self.wires: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        for j in b.jumpers:
            if (not j.auto) or j in keep_jump:
                self.wires.append((j.a, j.b))
        # component bodies stop jumper wires and jumper pads
        self.court = bytearray(N)
        for ref, pl in b.parts.items():
            x0, y0, x1, y1 = b.court_rect(ref)
            x0 -= 0.25
            y0 -= 0.25
            x1 += 0.25
            y1 += 0.25
            i0 = max(0, int(math.ceil(x0 / self.g - 1e-9)))
            i1 = min(self.nx - 1, int(math.floor(x1 / self.g + 1e-9)))
            j0 = max(0, int(math.ceil(y0 / self.g - 1e-9)))
            j1 = min(self.ny - 1, int(math.floor(y1 / self.g + 1e-9)))
            for jj in range(j0, j1 + 1):
                base = jj * self.nx
                for ii in range(i0, i1 + 1):
                    self.court[base + ii] = 1
        # "body" cells: under a part but not right next to one of its pins; routing through them
        # costs extra (see RouteOptions.under_part_cost), so pins stay reachable
        self.body = bytearray(self.court)
        for pin in b.all_pins():
            px, py = b.pin_pos(pin)
            ref, nm = b.split_pin(pin)
            pd = next((q for q in b.get_def(b.parts[ref].part_id).pads if q.name == nm), None)
            clear = (max(pd.w, pd.h) / 2.0 if pd else 0.9) + 0.4
            rc = int(math.ceil(clear / self.g))
            ci, cj = int(round(px / self.g)), int(round(py / self.g))
            for jj in range(max(0, cj - rc), min(self.ny - 1, cj + rc) + 1):
                for ii in range(max(0, ci - rc), min(self.nx - 1, ci + rc) + 1):
                    if (ii * self.g - px) ** 2 + (jj * self.g - py) ** 2 <= clear * clear:
                        self.body[jj * self.nx + ii] = 0
        nx, ny = self.nx, self.ny
        # prefix sums along rows and columns so a straight jump can be checked in O(1)
        self.rowpre = []
        for j in range(ny):
            acc = 0
            row = [0] * (nx + 1)
            for i in range(nx):
                acc += self.court[j * nx + i]
                row[i + 1] = acc
            self.rowpre.append(row)
        self.colpre = []
        for i in range(nx):
            acc = 0
            col = [0] * (ny + 1)
            for j in range(ny):
                acc += self.court[j * nx + i]
                col[j + 1] = acc
            self.colpre.append(col)
        self.records: Dict[str, List[dict]] = {}     # net -> committed auto routes
        self.groups: Dict[str, List[_Group]] = {}
        self.ripped: Dict[str, int] = {}

    def _stamp_static(self, s, nid: int) -> None:
        g = self.g
        bb = s.bbox()
        for c, hw in enumerate(self.hw):
            R = hw + self.clr
            i0 = max(0, int(math.ceil((bb[0] - R) / g - 1e-9)))
            i1 = min(self.nx - 1, int(math.floor((bb[2] + R) / g + 1e-9)))
            j0 = max(0, int(math.ceil((bb[1] - R) / g - 1e-9)))
            j1 = min(self.ny - 1, int(math.floor((bb[3] + R) / g + 1e-9)))
            S = self.static[c]
            nx = self.nx
            if s.kind == "cap":
                x1, y1, x2, y2, r = s.x1, s.y1, s.x2, s.y2, s.r
                lim = r + R - 1e-9
                dx, dy = x2 - x1, y2 - y1
                l2 = dx * dx + dy * dy
                for j in range(j0, j1 + 1):
                    py = j * g
                    for i in range(i0, i1 + 1):
                        px = i * g
                        if l2 < 1e-18:
                            d = math.hypot(px - x1, py - y1)
                        else:
                            t = ((px - x1) * dx + (py - y1) * dy) / l2
                            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                            d = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
                        if d < lim:
                            k = j * nx + i
                            v = S[k]
                            if v == 0:
                                S[k] = nid
                            elif v != nid:
                                S[k] = HARD if (v == HARD or nid == HARD) else MULTI
            else:
                pts = s.pts
                for j in range(j0, j1 + 1):
                    py = j * g
                    for i in range(i0, i1 + 1):
                        p = (i * g, py)
                        d = poly_seg_dist(pts, p, p)
                        if d < R - 1e-9:
                            k = j * nx + i
                            v = S[k]
                            if v == 0:
                                S[k] = nid
                            elif v != nid:
                                S[k] = HARD if (v == HARD or nid == HARD) else MULTI

    def _stamp_edges(self) -> None:
        ec = self.board.settings.edge_clearance
        W, H, g, nx, ny = self.board.width, self.board.height, self.g, self.nx, self.ny
        for c, hw in enumerate(self.hw):
            S = self.static[c]
            lim = ec + hw - 1e-9
            for j in range(ny):
                y = j * g
                for i in range(nx):
                    x = i * g
                    if x < lim or y < lim or x > W - lim or y > H - lim:
                        S[j * nx + i] = HARD

    def _stencil(self, cls: int, blocker_hw: float) -> List[Tuple[int, int]]:
        key = (cls, round(blocker_hw, 3))
        st = self._stencils.get(key)
        if st is None:
            R = self.hw[cls] + self.clr + blocker_hw + 0.05
            m = int(math.ceil(R / self.g))
            st = [(di, dj) for dj in range(-m, m + 1) for di in range(-m, m + 1)
                  if math.hypot(di, dj) * self.g < R]
            self._stencils[key] = st
        return st

    def _stamp_dyn(self, nodes: List[int], nid: int, blocker_hw: float, sign: int) -> None:
        nx, ny = self.nx, self.ny
        for c in range(len(self.classes)):
            st = self._stencil(c, blocker_hw)
            cnt, sid, ssq = self.dcnt[c], self.dsid[c], self.dssq[c]
            for k in nodes:
                i, j = k % nx, k // nx
                for di, dj in st:
                    i2, j2 = i + di, j + dj
                    if 0 <= i2 < nx and 0 <= j2 < ny:
                        k2 = j2 * nx + i2
                        cnt[k2] += sign
                        sid[k2] += sign * nid
                        ssq[k2] += sign * nid * nid

    # ------------------------------------------------------------ pins & groups
    def _shape_nodes(self, s) -> List[int]:
        g = self.g
        bb = s.bbox()
        i0 = max(0, int(math.ceil(bb[0] / g - 1e-9)))
        i1 = min(self.nx - 1, int(math.floor(bb[2] / g + 1e-9)))
        j0 = max(0, int(math.ceil(bb[1] / g - 1e-9)))
        j1 = min(self.ny - 1, int(math.floor(bb[3] / g + 1e-9)))
        out = []
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                p = (i * g, j * g)
                if s.kind == "cap":
                    d = seg_point_dist(p, (s.x1, s.y1), (s.x2, s.y2)) - s.r
                else:
                    d = poly_seg_dist(s.pts, p, p)
                if d <= 1e-9:
                    out.append(j * self.nx + i)
        return out

    def _pin_nodes(self, pin: str) -> Dict[int, float]:
        ref, name = self.board.split_pin(pin)
        shapes, _dr, centre = self.board.pad_copper(ref, name)
        nodes: Dict[int, float] = {}
        for s in shapes:
            for k in self._shape_nodes(s):
                x, y = self._xy(k)
                nodes[k] = 0.7 * dist((x, y), centre) / self.g
        if not nodes:
            nodes[self._node_at(*centre)] = 0.0
        return nodes

    def _build_groups(self, name: str) -> List[_Group]:
        b = self.board
        comps = b.components().get(name, [])
        net = b.nets[name]
        joined = {p for g in comps for p in g}
        lists = [list(g) for g in comps] + [[p] for p in net.pins if p not in joined and b.has_pin(p)]
        groups: List[_Group] = []
        for pl in lists:
            grp = _Group()
            for p in pl:
                grp.pins.add(p)
                for k, c in self._pin_nodes(p).items():
                    if k not in grp.nodes or c < grp.nodes[k]:
                        grp.nodes[k] = c
            groups.append(grp)
        # every trace of this net that is on the board (hand-drawn, or routed earlier in this run
        # and kept) joins the group it is connected to, through pads or through other traces, so
        # new copper connects to it instead of running over it
        pending = [t for t in b.traces if t.net == name and len(t.points) >= 2]
        tsh = {id(t): [Cap(t.points[i][0], t.points[i][1], t.points[i + 1][0], t.points[i + 1][1],
                           t.widths[i] / 2.0) for i in range(len(t.points) - 1)] for t in pending}
        owned: Dict[int, _Group] = {}
        pad_sh = {}
        for grp in groups:
            for p in grp.pins:
                ref, nm = b.split_pin(p)
                pad_sh[p] = b.pad_copper(ref, nm)[0]
        changed = True
        while changed and pending:
            changed = False
            for t in list(pending):
                mine = tsh[id(t)]
                owner = None
                for grp in groups:
                    if any(shape_dist(a, q) <= 1e-6 for p in grp.pins for a in mine for q in pad_sh[p]):
                        owner = grp
                        break
                if owner is None:
                    for t2, g2 in [(x, owned[id(x)]) for x in b.traces if id(x) in owned]:
                        if any(shape_dist(a, q) <= 1e-6 for a in mine for q in tsh[id(t2)]):
                            owner = g2
                            break
                if owner is None:
                    continue
                owned[id(t)] = owner
                pending.remove(t)
                changed = True
                for sh in mine:
                    for k in self._shape_nodes(Cap(sh.x1, sh.y1, sh.x2, sh.y2, 0.01)):
                        owner.nodes.setdefault(k, 0.0)
        return groups

    # ----------------------------------------------------------------- A* core
    def _search(self, nid: int, cls: int, srcs: Dict[int, float], tgts: Dict[int, float],
                soft: bool = False, jumps: bool = False, forbid_nodes: Optional[Set[int]] = None,
                forbid_edges: Optional[Set[Tuple[int, int]]] = None, margin: Optional[float] = None):
        """Return a list of (node, heading, via_jump) from a source to a target, or None."""
        nx, ny = self.nx, self.ny
        g = self.g
        opt = self.opt
        S = self.static[cls]
        cnt, sid, ssq = self.dcnt[cls], self.dsid[cls], self.dssq[cls]
        hist = self.hist
        jcls = self.cidx[round(self.board.settings.jumper_pad, 3)]
        JS = self.static[jcls]
        jcnt, jsid, jssq = self.dcnt[jcls], self.dsid[jcls], self.dssq[jcls]
        if margin is None:
            margin = opt.margin
        m = int(math.ceil(margin / g))
        allk = list(srcs) + list(tgts)
        ii = [k % nx for k in allk]
        jj = [k // nx for k in allk]
        i_lo, i_hi = max(0, min(ii) - m), min(nx - 1, max(ii) + m)
        j_lo, j_hi = max(0, min(jj) - m), min(ny - 1, max(jj) + m)
        ti = [k % nx for k in tgts]
        tj = [k // nx for k in tgts]
        ti0, ti1, tj0, tj1 = min(ti), max(ti), min(tj), max(tj)
        turn = opt.turn_cost
        soft_pen = opt.soft_penalty
        jmin = int(round(self.board.settings.jumper_min / g))
        jmax = int(round(self.board.settings.jumper_max / g))
        jstep = max(1, int(round(self.board.settings.jumper_step / g)))
        jcost = opt.jumper_cost
        jlens = list(range(jmin, jmax + 1, jstep))
        court = self.court
        body = self.body
        upc = opt.under_part_cost * (KEEP_OUT_FACTOR if self.board.settings.keep_out_under_parts else 1.0)
        rowpre, colpre = self.rowpre, self.colpre
        nid2 = nid * nid
        fnodes = forbid_nodes or None
        fedges = forbid_edges or None
        heap: List[tuple] = []
        best: Dict[int, float] = {}
        parent: Dict[int, int] = {}
        jumped: Set[int] = set()
        counter = 0
        hw_w = 1.0

        def hfun(i: int, j: int) -> float:
            dx = ti0 - i if i < ti0 else (i - ti1 if i > ti1 else 0)
            dy = tj0 - j if j < tj0 else (j - tj1 if j > tj1 else 0)
            return (dx + dy - 0.5858 * min(dx, dy)) * hw_w

        for k, c0 in srcs.items():
            if k % nx < i_lo or k % nx > i_hi or k // nx < j_lo or k // nx > j_hi:
                continue
            st = k * 9 + 8
            if c0 < best.get(st, 1e30):
                best[st] = c0
                counter += 1
                heapq.heappush(heap, (c0 + hfun(k % nx, k // nx), counter, c0, k, 8))
        expansions = 0
        goal_state = -1
        while heap:
            f, _c, gc, k, h = heapq.heappop(heap)
            st = k * 9 + h
            if gc > best.get(st, 1e30) + 1e-12:
                continue
            if k in tgts:
                goal_state = st
                break
            expansions += 1
            if expansions > opt.max_expansions:
                break
            if expansions & 0x3FF == 0:
                self._check()
            j, i = divmod(k, nx)
            if h == 8:
                cand = ((0, 0.0), (1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0), (5, 0.0), (6, 0.0), (7, 0.0))
            else:
                cand = ((h, 0.0), ((h + 1) & 7, turn), ((h + 7) & 7, turn))
            for nh, tc in cand:
                dx, dy = DIRS[nh]
                i2, j2 = i + dx, j + dy
                if i2 < i_lo or i2 > i_hi or j2 < j_lo or j2 > j_hi:
                    continue
                k2 = j2 * nx + i2
                s = S[k2]
                if s and s != nid:
                    continue
                if fnodes is not None and k2 in fnodes:
                    continue
                extra = 0.0
                cn = cnt[k2]
                if cn and not (sid[k2] == cn * nid and ssq[k2] == cn * nid2):
                    if not soft:
                        continue
                    extra = soft_pen
                if nh & 1:
                    ka = j * nx + i2
                    kb = j2 * nx + i
                    sa, sb = S[ka], S[kb]
                    if (sa and sa != nid) or (sb and sb != nid):
                        continue
                    if not soft:
                        ca, cb = cnt[ka], cnt[kb]
                        if (ca and not (sid[ka] == ca * nid and ssq[ka] == ca * nid2)) or \
                                (cb and not (sid[kb] == cb * nid and ssq[kb] == cb * nid2)):
                            continue
                    step = SQ2
                else:
                    step = 1.0
                if fedges is not None and (k, k2) in fedges:
                    continue
                ng = gc + step + tc + extra + hist[k2]
                if body[k2]:
                    ng += upc
                st2 = k2 * 9 + nh
                if ng < best.get(st2, 1e30) - 1e-12:
                    best[st2] = ng
                    parent[st2] = st
                    counter += 1
                    heapq.heappush(heap, (ng + hfun(i2, j2), counter, ng, k2, nh))
            # wire-link jumps: straight, orthogonal, over copper but not over parts
            if jumps and not (i & 1) and not (j & 1) and not court[k]:
                s0 = JS[k]
                if (s0 and s0 != nid) or (jcnt[k] and not (jsid[k] == jcnt[k] * nid and jssq[k] == jcnt[k] * nid2)):
                    continue
                for dxj, dyj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    for L in jlens:
                        i2, j2 = i + dxj * L, j + dyj * L
                        if i2 < i_lo or i2 > i_hi or j2 < j_lo or j2 > j_hi:
                            break
                        k2 = j2 * nx + i2
                        if court[k2]:
                            continue
                        if dyj == 0:
                            lo, hi = (i, i2) if i < i2 else (i2, i)
                            if rowpre[j][hi + 1] - rowpre[j][lo] > 0:
                                break
                        else:
                            lo, hi = (j, j2) if j < j2 else (j2, j)
                            if colpre[i][hi + 1] - colpre[i][lo] > 0:
                                break
                        s2 = JS[k2]
                        if s2 and s2 != nid:
                            continue
                        if jcnt[k2] and not (jsid[k2] == jcnt[k2] * nid and jssq[k2] == jcnt[k2] * nid2):
                            continue
                        if fnodes is not None and k2 in fnodes:
                            continue
                        a = (i * g, j * g)
                        bpt = (i2 * g, j2 * g)
                        bad = False
                        for wa, wb in self.wires:
                            if segments_touch(a, bpt, wa, wb):
                                bad = True
                                break
                        if bad:
                            continue
                        ng = gc + jcost + 0.2 * L
                        st2 = k2 * 9 + 8
                        if ng < best.get(st2, 1e30) - 1e-12:
                            best[st2] = ng
                            parent[st2] = st
                            jumped.add(st2)
                            counter += 1
                            heapq.heappush(heap, (ng + hfun(i2, j2), counter, ng, k2, 8))
        if goal_state < 0:
            return None
        path = []
        st = goal_state
        while True:
            path.append((st // 9, st % 9, st in jumped))
            if st not in parent:
                break
            st = parent[st]
        path.reverse()
        return path

    # ------------------------------------------------------------- path -> copper
    def _split_path(self, path) -> Tuple[List[List[int]], List[Tuple[int, int]]]:
        runs: List[List[int]] = []
        jumps: List[Tuple[int, int]] = []
        run = [path[0][0]]
        for idx in range(1, len(path)):
            k, _h, via_jump = path[idx]
            if via_jump:
                if len(run) > 1:
                    runs.append(run)
                jumps.append((run[-1], k))
                run = [k]
            else:
                run.append(k)
        if len(run) > 1:
            runs.append(run)
        return runs, jumps

    def _verify(self, net: str, runs: List[List[int]], jumps: List[Tuple[int, int]],
                width: float) -> Tuple[Set[int], Set[Tuple[int, int]]]:
        """Exact clearance check. Returns (bad nodes, bad edges)."""
        bad_nodes: Set[int] = set()
        bad_edges: Set[Tuple[int, int]] = set()
        clr = self.clr - 1e-4
        ec = self.board.settings.edge_clearance - 1e-4
        W, H = self.board.width, self.board.height
        for run in runs:
            for a, c in zip(run, run[1:]):
                pa, pc = self._xy(a), self._xy(c)
                cap = Cap(pa[0], pa[1], pc[0], pc[1], width / 2.0)
                bb = cap.bbox()
                if bb[0] < ec or bb[1] < ec or bb[2] > W - ec or bb[3] > H - ec:
                    bad_edges.add((a, c))
                    bad_edges.add((c, a))
                    continue
                for s in self.index.near(bb, self.clr):
                    if s.net == net:
                        continue
                    if bbox_gap(bb, s.bbox()) >= clr:
                        continue
                    if shape_dist(cap, s) < clr:
                        bad_edges.add((a, c))
                        bad_edges.add((c, a))
                        break
        r = self.board.settings.jumper_pad / 2.0
        for a, c in jumps:
            for k in (a, c):
                p = self._xy(k)
                cap = Cap(p[0], p[1], p[0], p[1], r)
                for s in self.index.near(cap.bbox(), self.clr):
                    if s.net != net and shape_dist(cap, s) < clr:
                        bad_nodes.add(k)
                        break
        return bad_nodes, bad_edges

    def _commit(self, net: str, runs: List[List[int]], jumps: List[Tuple[int, int]], width: float,
                rigid: bool = False) -> None:
        b = self.board
        nid = self.nid[net]
        recs = self.records.setdefault(net, [])
        for run in runs:
            pts = simplify_polyline([self._xy(k) for k in run])
            if len(pts) < 2:
                continue
            t = Trace(net, pts, [width] * (len(pts) - 1), False, rigid)
            b.traces.append(t)
            shape_ids = []
            for i in range(len(pts) - 1):
                shape_ids.append(self.index.add(Cap(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                                    width / 2.0, net, ("auto", net))))
            self._stamp_dyn(run, nid, width / 2.0, +1)
            recs.append({"kind": "trace", "obj": t, "nodes": run, "hw": width / 2.0, "shapes": shape_ids})
        r = b.settings.jumper_pad / 2.0
        for a, c in jumps:
            pa, pc = self._xy(a), self._xy(c)
            j = Jumper(net, pa, pc, True)
            b.jumpers.append(j)
            sids = [self.index.add(Cap(pa[0], pa[1], pa[0], pa[1], r, net, ("auto", net))),
                    self.index.add(Cap(pc[0], pc[1], pc[0], pc[1], r, net, ("auto", net)))]
            self._stamp_dyn([a, c], nid, r, +1)
            self.wires.append((pa, pc))
            recs.append({"kind": "jumper", "obj": j, "nodes": [a, c], "hw": r, "shapes": sids})
        b.touch()

    def _rip(self, net: str) -> None:
        b = self.board
        nid = self.nid[net]
        for rec in self.records.get(net, []):
            self._stamp_dyn(rec["nodes"], nid, rec["hw"], -1)
            for sid in rec["shapes"]:
                self.index.remove(sid)
            if rec["kind"] == "trace":
                if rec["obj"] in b.traces:
                    b.traces.remove(rec["obj"])
            else:
                j = rec["obj"]
                if j in b.jumpers:
                    b.jumpers.remove(j)
                w = (j.a, j.b)
                if w in self.wires:
                    self.wires.remove(w)
        self.records[net] = []
        b.touch()

    # ----------------------------------------------------------- one connection
    def _pick_pair(self, groups: List[_Group]) -> Optional[Tuple[_Group, _Group]]:
        best = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                d = 1e18
                for p in groups[i].pins:
                    pp = self.board.pin_pos(p)
                    for q in groups[j].pins:
                        d = min(d, dist(pp, self.board.pin_pos(q)))
                if best is None or d < best[0]:
                    best = (d, groups[i], groups[j])
        return (best[1], best[2]) if best else None

    def _route_pair(self, net: str, X: _Group, Y: _Group, soft: bool = False,
                    jumps: bool = False) -> Optional[Tuple[List[List[int]], List[Tuple[int, int]]]]:
        nid = self.nid[net]
        width = self.width[net]
        cls = self.cidx[round(width, 3)]
        fnodes: Set[int] = set()
        fedges: Set[Tuple[int, int]] = set()
        margins = [self.opt.margin, self.opt.margin * 3.0, max(self.board.width, self.board.height)]
        for attempt in range(8):
            path = None
            for mg in margins:
                path = self._search(nid, cls, X.nodes, Y.nodes, soft, jumps, fnodes, fedges, mg)
                if path is not None:
                    break
            if path is None:
                return None
            runs, jps = self._split_path(path)
            if soft:
                return runs, jps
            bn, be = self._verify(net, runs, jps, width)
            if not bn and not be:
                return runs, jps
            fnodes |= bn
            fedges |= be
        return None

    def _route_net(self, name: str, jumps: bool = False) -> bool:
        groups = self.groups.get(name)
        if groups is None:
            groups = self._build_groups(name)
            self.groups[name] = groups
        width = self.width[name]
        # rigid links first: each is routed pin to pin as its own trunk, so the other
        # pins of the net then branch off it instead of being chained through
        for la, lb in self.board.rigid_links(name):
            X = next((g for g in groups if la in g.pins), None)
            Y = next((g for g in groups if lb in g.pins), None)
            if X is None or Y is None or X is Y:
                continue
            self._check()
            res = self._route_pair(name, X, Y, False, False)
            if res is None and jumps:
                res = self._route_pair(name, X, Y, False, True)
            if res is None:
                return False
            self._join(name, X, Y, res, width, groups, rigid=True)
        guard = 0
        while len(groups) > 1:
            guard += 1
            if guard > 40:
                return False
            self._check()
            pair = self._pick_pair(groups)
            if pair is None:
                return False
            X, Y = pair
            res = self._route_pair(name, X, Y, False, False)
            if res is None and jumps:
                res = self._route_pair(name, X, Y, False, True)
            if res is None:
                return False
            self._join(name, X, Y, res, width, groups)
        return True

    def _join(self, name: str, X: "_Group", Y: "_Group", res, width: float, groups: List["_Group"],
              rigid: bool = False) -> None:
        runs, jps = res
        self._commit(name, runs, jps, width, rigid)
        for run in runs:
            for k in run:
                X.nodes.setdefault(k, 0.0)
        for a, c in jps:
            X.nodes.setdefault(a, 0.0)
            X.nodes.setdefault(c, 0.0)
        X.pins |= Y.pins
        for k, c in Y.nodes.items():
            X.nodes.setdefault(k, c)
        groups.remove(Y)

    # ----------------------------------------------------------------- ordering
    def _order(self, names: List[str]) -> List[str]:
        b = self.board

        def span(n: str) -> float:
            pts = [b.pin_pos(p) for p in b.nets[n].pins if b.has_pin(p)]
            if len(pts) < 2:
                return 0.0
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (max(xs) - min(xs)) + (max(ys) - min(ys))

        if self.opt.order_seed is None:
            return sorted(names, key=lambda n: (-self.width[n], span(n), n))
        import random as _random
        rnd = _random.Random(self.opt.order_seed)
        jitter = {n: 0.5 + rnd.random() for n in names}
        return sorted(names, key=lambda n: (-self.width[n], span(n) * jitter[n], n))

    # ------------------------------------------------------------------ rip-up
    def _crossed_nets(self, net: str, runs: List[List[int]], width: float) -> Optional[Set[str]]:
        """Nets (auto routes only) that a soft path runs through; None if it hits fixed copper."""
        crossed: Set[str] = set()
        clr = self.clr - 1e-4
        for run in runs:
            for a, c in zip(run, run[1:]):
                pa, pc = self._xy(a), self._xy(c)
                cap = Cap(pa[0], pa[1], pc[0], pc[1], width / 2.0)
                for s in self.index.near(cap.bbox(), self.clr):
                    if s.net == net:
                        continue
                    if shape_dist(cap, s) < clr:
                        if s.tag and s.tag[0] == "auto":
                            crossed.add(s.tag[1])
                        else:
                            return None
        return crossed

    def _ripup_route(self, name: str, result: RouteResult, order_front: List[str]) -> bool:
        groups = self.groups.get(name) or self._build_groups(name)
        self.groups[name] = groups
        if len(groups) < 2:
            return True
        pair = self._pick_pair(groups)
        if pair is None:
            return False
        X, Y = pair
        res = self._route_pair(name, X, Y, True, False)
        if res is None:
            return False
        runs, _j = res
        crossed = self._crossed_nets(name, runs, self.width[name])
        if crossed is None or not crossed:
            return False
        if any(self.ripped.get(n, 0) >= 3 for n in crossed):
            return False
        if result.ripups + len(crossed) > self.opt.max_ripups:
            return False
        for n in crossed:
            self._rip(n)
            self.groups.pop(n, None)
            self.ripped[n] = self.ripped.get(n, 0) + 1
            result.ripups += 1
            for rec in runs:                       # discourage the victim from the same corridor
                for k in rec:
                    self.hist[k] += 0.0
        self.groups[name] = groups
        ok = self._route_net(name)
        for n in crossed:
            order_front.append(n)
        return ok

    # ------------------------------------------------------------------- public
    def route_all(self) -> RouteResult:
        if self.opt.attempts > 1:
            return self._best_of(lambda r: r.route_all())
        b = self.board
        b.clear_auto_routes()
        names = [n for n in b.nets if len(b.nets[n].pins) >= 2]
        return self._route(names, set(names))

    def route_net(self, name: str) -> RouteResult:
        return self.route_nets([name])

    def _best_of(self, run) -> RouteResult:
        """Route several times with different net orders on copies of the board; keep the best.

        Best = fewest unrouted connections, then fewest jumpers, then the shortest copper.
        A single unlucky order can box a pin in; another order usually does not.
        """
        import copy as _copy
        t0 = time.time()
        base = self.opt.under_part_cost
        keep_out = self.board.settings.keep_out_under_parts
        low = base if keep_out else 0.0           # with "keep out" every try avoids part bodies
        variants = [(None, base), (1, base), (None, low), (2, low), (3, base * 2), (4, base),
                    (5, low), (6, base * 2)][:max(1, self.opt.attempts)]
        under_w = 50.0 if keep_out else 3.0
        best = None
        for idx, (seed, upc) in enumerate(variants):
            if idx and (time.time() - t0 > self.opt.time_budget or (self.cancel and self.cancel())):
                break
            o = _copy.copy(self.opt)
            o.attempts, o.order_seed, o.under_part_cost = 1, seed, upc
            work = self.board.clone()

            def prog(msg: str, frac: float, idx=idx) -> None:
                if self.progress:
                    self.progress("Try %d of %d: %s" % (idx + 1, len(variants), msg),
                                  (idx + min(1.0, frac)) / len(variants))
            res = run(AutoRouter(work, o, prog, self.cancel))
            length = sum(dist(t.points[i], t.points[i + 1]) for t in work.traces for i in range(len(t.points) - 1))
            # copper under part bodies counts extra: it is legal, but it blocks the pins of that part
            # and is what people dislike most (a fat trace straight through the middle of a chip)
            under = _under_parts_length(work)
            score = (work.unrouted_count(), res.jumpers, round(length + under_w * under, 1))
            if best is None or score < best[0]:
                best = (score, work, res, idx + 1)
            if score[0] == 0 and score[1] == 0:
                break
        assert best is not None
        _score, work, res, which = best
        self.board.traces = work.traces
        self.board.jumpers = work.jumpers
        self.board.touch()
        res.seconds = time.time() - t0
        if len(variants) > 1:
            res.messages.append("best of the tries: number %d" % which)
        return res

    def route_nets(self, names: List[str]) -> RouteResult:
        """Re-route only these nets (their automatic copper is removed first; hand-drawn copper stays)."""
        if self.opt.attempts > 1:
            return self._best_of(lambda r: r.route_nets(list(names)))
        b = self.board
        names = [n for n in names if n in b.nets and len(b.nets[n].pins) >= 2]
        ns = set(names)
        b.traces = [t for t in b.traces if t.manual or t.net not in ns]
        b.jumpers = [j for j in b.jumpers if (not j.auto) or j.net not in ns]
        b.touch()
        return self._route(names, ns)

    def _route(self, names: List[str], rip_set: Set[str]) -> RouteResult:
        result = RouteResult()
        t0 = time.time()
        self._t0 = t0
        self._rip_set = rip_set
        try:
            self._setup(rip_set)
            todo = self._order(names)
            failed: List[str] = []
            total = max(1, len(todo))
            for n, name in enumerate(todo):
                self._say("Routing %s (%d/%d)" % (name, n + 1, total), 0.7 * n / total)
                if not self._route_net(name):
                    failed.append(name)
                    self.groups.pop(name, None)
            # rip-up and reroute rounds
            rounds = 0
            while failed and rounds < self.opt.max_rounds:
                rounds += 1
                self._say("Rip-up and reroute, round %d" % rounds, 0.75)
                front: List[str] = []
                still: List[str] = []
                for name in failed:
                    self._check()
                    if not self._ripup_route(name, result, front):
                        still.append(name)
                for n in front:
                    if n not in self.groups:
                        self.groups[n] = self._build_groups(n)
                    if not self._route_net(n):
                        if n not in still:
                            still.append(n)
                if len(still) >= len(failed) and rounds >= 2:
                    failed = still
                    break
                failed = still
            if failed and self.opt.use_jumpers and self.board.settings.allow_jumpers:
                self._say("Adding jumpers", 0.9)
                still = []
                for name in failed:
                    if not self.board.nets[name].jumpers_ok:
                        still.append(name)
                        continue
                    self._check()
                    self.groups.pop(name, None)
                    self._rip(name)
                    if not self._route_net(name, jumps=True):
                        still.append(name)
                failed = still
            result.failed_nets = failed
            result.routed_nets = len(todo) - len(failed)
            result.jumpers = sum(1 for j in b_jumpers(self.board) if j.auto)
            if self.opt.smooth:
                self._say("Smoothing corners", 0.97)
                smooth_corners(self.board, self.index, [t for t in self.board.traces if not t.manual])
                self._say("Straightening pad exits", 0.98)
                from .tidy import tidy_traces
                tidy_traces(self.board, [t for t in self.board.traces if not t.manual])
        except RoutingCancelled:
            result.messages.append("Routing was stopped early; partial result kept.")
            result.failed_nets = [n for n in names if self.board.nets.get(n) and
                                  self.board.unrouted_count() > 0 and n in self._unrouted_nets()]
        result.seconds = time.time() - t0
        self.board.touch()
        return result

    def _unrouted_nets(self) -> Set[str]:
        return {w[0] for w in self.board.airwires()}


def _under_parts_length(board: Board) -> float:
    """Length (mm) of trace centre line that runs under the body of a part it does not belong to,
    weighted by trace width."""
    rects = [(ref, board.court_rect(ref)) for ref in board.parts]
    total = 0.0
    for t in board.traces:
        for i in range(len(t.points) - 1):
            a, c = t.points[i], t.points[i + 1]
            L = dist(a, c)
            n = max(1, int(L / 0.5))
            inside = 0
            for k in range(n):
                x = a[0] + (c[0] - a[0]) * (k + 0.5) / n
                y = a[1] + (c[1] - a[1]) * (k + 0.5) / n
                for _ref, (x0, y0, x1, y1) in rects:
                    if x0 + 0.3 < x < x1 - 0.3 and y0 + 0.3 < y < y1 - 0.3:
                        inside += 1
                        break
            total += L * inside / n * max(1.0, t.widths[i])
    return total


def b_jumpers(board: Board):
    return board.jumpers


# ----------------------------------------------------------------------------
# corner smoothing: make the 45 degree diagonal of a chamfered corner longer on wide traces
# ----------------------------------------------------------------------------
def smooth_corners(board: Board, index: Optional[_Index], traces: List[Trace]) -> int:
    """Lengthen chamfers where there is room, checking exact clearance. Returns #changes."""
    st = board.settings
    shapes = None
    changed = 0
    for t in traces:
        wmax = max(t.widths) if t.widths else 0.0
        target = st.chamfer_len(wmax)
        pts = t.points
        if len(pts) < 4 or wmax < 1.0:
            continue
        i = 1
        while i < len(pts) - 2:
            a, p1, p2, d = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
            u1 = (p1[0] - a[0], p1[1] - a[1])
            u2 = (d[0] - p2[0], d[1] - p2[1])
            l1 = math.hypot(*u1)
            l2 = math.hypot(*u2)
            ld = dist(p1, p2)
            if l1 < 1e-6 or l2 < 1e-6 or ld >= target:
                i += 1
                continue
            e1 = (u1[0] / l1, u1[1] / l1)
            e2 = (u2[0] / l2, u2[1] / l2)
            # the two outer runs must be orthogonal to each other for a clean 90 degree corner
            if abs(e1[0] * e2[0] + e1[1] * e2[1]) > 1e-6:
                i += 1
                continue
            want = (target - ld) / SQ2
            room = min(0.45 * l1, 0.45 * l2)
            delta = min(want, room)
            if delta < 0.05:
                i += 1
                continue
            for f in (1.0, 0.75, 0.5, 0.25):
                dl = delta * f
                n1 = (p1[0] - e1[0] * dl, p1[1] - e1[1] * dl)
                n2 = (p2[0] + e2[0] * dl, p2[1] + e2[1] * dl)
                if _ok_clear(board, index, t, [n1, n2], pts, i, wmax) and \
                        _joints_ok(board, t, pts, pts[:i] + [n1, n2] + pts[i + 2:]):
                    pts[i] = n1
                    pts[i + 1] = n2
                    changed += 1
                    break
            i += 1
        t.points = pts
    if changed:
        board.touch()
    return changed


def _joints_ok(board: Board, t: Trace, old_pts, new_pts) -> bool:
    """A bigger chamfer must not pull the trace off a branch, pad or jumper joined to it."""
    from .tidy import keeps_joints
    saved = board.traces
    board.traces = [x for x in saved if x is not t]
    board.touch()
    try:
        return keeps_joints(board, t, old_pts, t.widths, new_pts, t.widths)
    finally:
        board.traces = saved
        board.touch()


def _ok_clear(board: Board, index: Optional[_Index], trace: Trace, newp, pts, i: int, w: float) -> bool:
    clr = board.settings.clearance - 1e-4
    segs = [(pts[i - 1], newp[0]), (newp[0], newp[1]), (newp[1], pts[i + 2])]
    if index is None:
        shapes = board.copper()
    for a, c in segs:
        cap = Cap(a[0], a[1], c[0], c[1], w / 2.0)
        bb = cap.bbox()
        cand = index.near(bb, board.settings.clearance) if index is not None else shapes
        for s in cand:
            if s.net == trace.net:
                continue
            if bbox_gap(bb, s.bbox()) >= clr:
                continue
            if shape_dist(cap, s) < clr:
                return False
    return True
