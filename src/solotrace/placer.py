# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Untangle placement by simulated annealing.

The cost is what a person looks at when judging a layout:
  * length of the ratsnest (minimum spanning tree of every net),
  * how many ratsnest lines cross each other (the "tangled string" count),
  * parts overlapping each other or leaving the board.
Locked parts never move. Parts are only moved to the placement grid and turned in 90 degree
steps. Component-side flip is not used (through-hole parts).

Two placers (Board > Auto-place algorithm):

* "anneal": the original, with a fixed cooling curve.
* "routability": the same moves, with two extra cost terms a single copper layer cares about,
  and VPR's adaptive schedule (Betz & Rose 1997; see docs/research/autorouter-options.md):
  - a RUDY-style congestion estimate (Spindler & Johannes 2007): each net's wire area, spread
    over its bounding box, summed on a 5 mm grid and compared with the room the grid cell has
    left once part bodies are taken out; the overflow is the wire that will not fit;
  - boxed pads: a pad hemmed in by other parts on every side has no way out for its trace;
  - the temperature is set from the spread of random move costs and cooled by the acceptance
    rate (fast while nearly everything is accepted, slowly in the useful 15-80 % band), and the
    move range shrinks to keep that rate near 0.44.
"""
from __future__ import annotations

import math
import random
import time
from typing import Callable, Dict, List, Optional, Tuple

from .board import Board
from .geom import Point, dist, place_point, segments_cross


class PlaceResult:
    def __init__(self) -> None:
        self.crossings_before = 0
        self.crossings_after = 0
        self.length_before = 0.0
        self.length_after = 0.0
        self.overlaps_after = 0
        self.iterations = 0
        self.seconds = 0.0

    def summary(self) -> str:
        return ("ratsnest crossings %d -> %d, length %.0f -> %.0f mm, %d overlap(s), %d moves (%.1f s)"
                % (self.crossings_before, self.crossings_after, self.length_before, self.length_after,
                   self.overlaps_after, self.iterations, self.seconds))


def _mst(pts: List[Point]) -> List[Tuple[Point, Point]]:
    n = len(pts)
    if n < 2:
        return []
    in_t = [0]
    best = {j: (dist(pts[0], pts[j]), 0) for j in range(1, n)}
    edges = []
    while best:
        j = min(best, key=lambda k: best[k][0])
        d, i = best.pop(j)
        edges.append((pts[i], pts[j]))
        for k in best:
            dk = dist(pts[j], pts[k])
            if dk < best[k][0]:
                best[k] = (dk, j)
    return edges


RUDY_CELL = 5.0          # mm; the congestion grid
W_RUDY = 2.0             # cost per mm of estimated wire that does not fit its grid cell
W_BOXED = 15.0           # cost per pad hemmed in on every side
FREE_FRACTION = 0.6      # share of a free grid cell usable by copper (clearances, chamfers, pads)


class Placer:
    def __init__(self, board: Board, gap: float = 3.0, margin: float = 2.5, seed: int = 1,
                 progress: Optional[Callable[[str, float], None]] = None,
                 cancel: Optional[Callable[[], bool]] = None, mode: str = "anneal") -> None:
        self.b = board
        self.mode = mode if mode in ("anneal", "routability") else "anneal"
        self.gap = gap              # clear space wanted between parts, mm (room for traces)
        self.margin = margin        # distance kept from the board edge
        self.rnd = random.Random(seed)
        self.progress = progress
        self.cancel = cancel
        self.refs = list(board.parts)
        self.movable = [r for r in self.refs if not board.parts[r].locked and
                        board.get_def(board.parts[r].part_id).kind != "hole"]
        self.net_pins: Dict[str, List[Tuple[str, str]]] = {}
        for n in board.nets.values():
            lst = [board.split_pin(p) for p in n.pins if board.has_pin(p)]
            if len(lst) >= 2:
                self.net_pins[n.name] = lst
        self.part_nets: Dict[str, List[str]] = {r: [] for r in self.refs}
        for nn, lst in self.net_pins.items():
            for ref in {r for r, _ in lst}:
                self.part_nets[ref].append(nn)
        self._off: Dict[Tuple[str, int], Dict[str, Point]] = {}
        self._box: Dict[Tuple[str, int], Tuple[float, float, float, float]] = {}
        self.state: Dict[str, Tuple[float, float, int]] = {r: (p.x, p.y, p.rot) for r, p in board.parts.items()}
        self.edges: Dict[str, List[Tuple[Point, Point]]] = {}
        # routability terms
        self.pitch: Dict[str, float] = {nn: board.net_width(nn) + board.settings.clearance for nn in self.net_pins}
        self.gx = max(1, int(math.ceil(board.width / RUDY_CELL)))
        self.gy = max(1, int(math.ceil(board.height / RUDY_CELL)))
        self.demand = [0.0] * (self.gx * self.gy)
        self.body = [0.0] * (self.gx * self.gy)
        self.net_cells: Dict[str, Dict[int, float]] = {}
        self.part_cells: Dict[str, Dict[int, float]] = {}

    # -- routability: RUDY congestion and boxed pads ----------------------------------------
    def _net_rudy(self, nn: str) -> Dict[int, float]:
        """Wire area of net nn spread over its bounding box: {cell: mm2}."""
        pts = [self._pin(r, p) for r, p in self.net_pins[nn]]
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        hpwl = (x1 - x0) + (y1 - y0)
        area = max(1.0, (x1 - x0 + 1.0) * (y1 - y0 + 1.0))
        dens = hpwl * self.pitch[nn] / area           # mm2 of wire per mm2 of box
        return self._spread(x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5, dens)

    def _spread(self, x0: float, y0: float, x1: float, y1: float, dens: float) -> Dict[int, float]:
        out: Dict[int, float] = {}
        c = RUDY_CELL
        i0, i1 = max(0, int(x0 / c)), min(self.gx - 1, int(x1 / c))
        j0, j1 = max(0, int(y0 / c)), min(self.gy - 1, int(y1 / c))
        for j in range(j0, j1 + 1):
            cy0, cy1 = j * c, (j + 1) * c
            oy = min(y1, cy1) - max(y0, cy0)
            if oy <= 0:
                continue
            for i in range(i0, i1 + 1):
                ox = min(x1, (i + 1) * c) - max(x0, i * c)
                if ox > 0:
                    out[j * self.gx + i] = dens * ox * oy
        return out

    def _part_body(self, ref: str) -> Dict[int, float]:
        r = self._rect(ref)
        return self._spread(r[0] + 1.3, r[1] + 1.3, r[2] - 1.3, r[3] - 1.3, 1.0)

    def _overflow(self, cells) -> float:
        tot = 0.0
        full = RUDY_CELL * RUDY_CELL
        for k in cells:
            supply = max(0.0, full - self.body[k]) * FREE_FRACTION
            tot += max(0.0, self.demand[k] - supply)
        return tot

    def _near(self, refs) -> set:
        """These parts plus every part close enough to box, or be boxed by, one of them (current state)."""
        rects = {r: self._rect(r) for r in self.refs}
        out = set(refs)
        for m in refs:
            rr = rects[m]
            for o, q in rects.items():
                if q[0] - 4 <= rr[2] and q[2] + 4 >= rr[0] and q[1] - 4 <= rr[3] and q[3] + 4 >= rr[1]:
                    out.add(o)
        return out

    def _boxed(self, refs) -> int:
        """Pads of exactly these parts that are hemmed in by other parts (no free side within 1.6 mm)."""
        n = 0
        rects = {r: self._rect(r) for r in self.refs}
        reach = 1.6

        def boxed(ref: str, px: float, py: float) -> bool:
            sides = [True, True, True, True]          # +x, -x, +y, -y still free
            for o, q in rects.items():
                if o == ref:
                    continue
                if q[1] - reach <= py <= q[3] + reach:
                    if 0 <= q[0] - px <= reach:
                        sides[0] = False
                    if 0 <= px - q[2] <= reach:
                        sides[1] = False
                if q[0] - reach <= px <= q[2] + reach:
                    if 0 <= q[1] - py <= reach:
                        sides[2] = False
                    if 0 <= py - q[3] <= reach:
                        sides[3] = False
            return not any(sides)
        for ref in refs:
            d = self.b.get_def(self.b.parts[ref].part_id)
            for pd in d.pads:
                px, py = self._pin(ref, pd.name)
                if boxed(ref, px, py):
                    n += 1
        return n

    def _route_cost(self, refs, nets, count=None) -> float:
        """Routability cost of the current state for these parts and nets (the parts' body cells and
        the nets' RUDY cells are refreshed in place). ``count`` is the set of parts whose boxed pads
        are counted (default: the parts themselves and their neighbours)."""
        if self.mode != "routability":
            return 0.0
        touched = set()
        for nn in nets:
            for k in self.net_cells.get(nn, {}):
                self.demand[k] -= self.net_cells[nn][k]
                touched.add(k)
            cells = self._net_rudy(nn)
            self.net_cells[nn] = cells
            for k, v in cells.items():
                self.demand[k] += v
                touched.add(k)
        for r in refs:
            for k in self.part_cells.get(r, {}):
                self.body[k] -= self.part_cells[r][k]
                touched.add(k)
            cells = self._part_body(r)
            self.part_cells[r] = cells
            for k, v in cells.items():
                self.body[k] += v
                touched.add(k)
        return W_RUDY * self._overflow(touched) + W_BOXED * self._boxed(count if count is not None else self._near(refs))

    # -- cached offsets for a part at a given rotation ------------------------------------
    def _offsets(self, ref: str, rot: int) -> Dict[str, Point]:
        key = (ref, rot)
        o = self._off.get(key)
        if o is None:
            d = self.b.get_def(self.b.parts[ref].part_id)
            o = {p.name: place_point((p.x, p.y), 0.0, 0.0, rot, False) for p in d.pads}
            self._off[key] = o
            xs = [place_point(c, 0, 0, rot, False) for c in
                  ((d.court[0], d.court[1]), (d.court[2], d.court[3]))]
            x0 = min(v[0] for v in list(o.values()) + xs) - 1.3
            x1 = max(v[0] for v in list(o.values()) + xs) + 1.3
            y0 = min(v[1] for v in list(o.values()) + xs) - 1.3
            y1 = max(v[1] for v in list(o.values()) + xs) + 1.3
            self._box[key] = (x0, y0, x1, y1)
        return o

    def _pin(self, ref: str, pad: str) -> Point:
        x, y, rot = self.state[ref]
        o = self._offsets(ref, rot)[pad]
        return (x + o[0], y + o[1])

    def _rect(self, ref: str) -> Tuple[float, float, float, float]:
        x, y, rot = self.state[ref]
        self._offsets(ref, rot)
        b = self._box[(ref, rot)]
        return (x + b[0], y + b[1], x + b[2], y + b[3])

    def _net_edges(self, nn: str) -> List[Tuple[Point, Point]]:
        return _mst([self._pin(r, p) for r, p in self.net_pins[nn]])

    # -- cost pieces ------------------------------------------------------------------------
    @staticmethod
    def _len(edges) -> float:
        return sum(dist(a, b) for a, b in edges)

    def _cross_count(self, nets: List[str]) -> int:
        """Crossings involving any edge of ``nets`` (each pair counted once)."""
        aset = set(nets)
        c = 0
        a_edges = [(nn, e) for nn in nets for e in self.edges[nn]]
        for i, (n1, e1) in enumerate(a_edges):
            for n2, e2 in a_edges[i + 1:]:
                if n1 != n2 and segments_cross(e1[0], e1[1], e2[0], e2[1]):
                    c += 1
            for nn, lst in self.edges.items():
                if nn in aset:
                    continue
                for e2 in lst:
                    if segments_cross(e1[0], e1[1], e2[0], e2[1]):
                        c += 1
        return c

    def _part_pen(self, ref: str) -> float:
        """Overlap and out-of-board penalty for one part against all others."""
        r = self._rect(ref)
        g = self.gap / 2.0
        pen = 0.0
        m = self.margin
        W, H = self.b.width, self.b.height
        dx = max(0.0, m - r[0]) + max(0.0, r[2] - (W - m))
        dy = max(0.0, m - r[1]) + max(0.0, r[3] - (H - m))
        pen += 4.0 * (dx + dy)
        for o in self.refs:
            if o == ref:
                continue
            q = self._rect(o)
            ox = min(r[2] + g, q[2] + g) - max(r[0] - g, q[0] - g)
            oy = min(r[3] + g, q[3] + g) - max(r[1] - g, q[1] - g)
            if ox > 0 and oy > 0:
                pen += 3.0 * min(ox, oy) + 0.2 * ox * oy
        return pen

    def total_cost(self) -> Tuple[float, int, float, float]:
        self.edges = {nn: self._net_edges(nn) for nn in self.net_pins}
        length = sum(self._len(e) for e in self.edges.values())
        names = list(self.edges)
        cross = self._cross_count(names) if names else 0
        pen = sum(self._part_pen(r) for r in self.refs) / 2.0
        rc = 0.0
        if self.mode == "routability":
            self.demand = [0.0] * (self.gx * self.gy)
            self.body = [0.0] * (self.gx * self.gy)
            self.net_cells = {}
            self.part_cells = {}
            self._route_cost(self.refs, list(self.net_pins))
            rc = W_RUDY * self._overflow(range(self.gx * self.gy)) + W_BOXED * self._boxed(self.refs)
        return length + 10.0 * cross + 6.0 * pen + rc, cross, length, pen

    def _count_overlaps(self) -> int:
        n = 0
        for i, a in enumerate(self.refs):
            ra = self._rect(a)
            for b in self.refs[i + 1:]:
                rb = self._rect(b)
                if min(ra[2], rb[2]) - max(ra[0], rb[0]) > 0 and min(ra[3], rb[3]) - max(ra[1], rb[1]) > 0:
                    n += 1
        return n

    # -- annealing -----------------------------------------------------------------------------
    def _propose(self, r1: str, step: float, pg: float):
        """One move: returns (old states dict) and applies the move to self.state (or None to skip)."""
        old = {r1: self.state[r1]}
        kind = self.rnd.random()
        x, y, rot = self.state[r1]
        W, H = self.b.width, self.b.height
        if kind < 0.55:
            nx = x + round(self.rnd.gauss(0, step) / pg) * pg
            ny = y + round(self.rnd.gauss(0, step) / pg) * pg
            self.state[r1] = (min(max(nx, 0.0), W), min(max(ny, 0.0), H), rot)
        elif kind < 0.75:
            self.state[r1] = (x, y, (rot + 90 * self.rnd.choice((1, 2, 3))) % 360)
        else:
            r2 = self.rnd.choice(self.movable)
            if r2 == r1:
                return None
            old[r2] = self.state[r2]
            x2, y2, rot2 = self.state[r2]
            self.state[r1] = (x2, y2, rot)
            self.state[r2] = (x, y, rot2)
        return old

    def _delta(self, old: dict):
        """Cost change of the move already applied to self.state (edges, RUDY caches updated to the
        new state). Returns (delta, new_cross - old_cross, new_len - old_len, new_pen - old_pen, old_edges)."""
        moved = list(old)
        nets = sorted({n for r in moved for n in self.part_nets[r]})
        old_edges = {n: self.edges[n] for n in nets}
        old_len = sum(self._len(e) for e in old_edges.values())
        new_state = {r: self.state[r] for r in moved}
        count = self._near(moved) if self.mode == "routability" else None   # neighbours at the new place
        for r in moved:
            self.state[r] = old[r]
        if count is not None:
            count |= self._near(moved)                                        # ... and at the old place
        old_cross = self._cross_count(nets) if nets else 0
        old_pen = sum(self._part_pen(r) for r in moved)
        old_rc = self._route_cost(moved, nets, count)
        for r in moved:
            self.state[r] = new_state[r]
        for n in nets:
            self.edges[n] = self._net_edges(n)
        new_cross = self._cross_count(nets) if nets else 0
        new_len = sum(self._len(self.edges[n]) for n in nets)
        new_pen = sum(self._part_pen(r) for r in moved)
        new_rc = self._route_cost(moved, nets, count)
        delta = (new_len - old_len) + 10.0 * (new_cross - old_cross) + 6.0 * (new_pen - old_pen) + (new_rc - old_rc)
        return delta, new_cross - old_cross, new_len - old_len, new_pen - old_pen, old_edges, nets

    def _undo(self, old: dict, old_edges: dict, nets) -> None:
        for r in old:
            self.state[r] = old[r]
        for n in nets:
            self.edges[n] = old_edges[n]
        if self.mode == "routability":
            self._route_cost(list(old), nets)

    def run(self, time_limit: float = 20.0, iterations: int = 30000) -> PlaceResult:
        res = PlaceResult()
        t0 = time.time()
        b = self.b
        pg = b.settings.place_grid
        if not self.movable or not self.net_pins:
            res.seconds = 0.0
            return res
        # parts that are far off the board or stacked get scattered first
        cost, cross, length, pen = self.total_cost()
        res.crossings_before, res.length_before = cross, length
        if pen > 0:
            for ref in self.movable:
                if self._part_pen(ref) > 0:
                    self._scatter(ref, pg)
            cost, cross, length, pen = self.total_cost()
        best = (cost, dict(self.state))
        W, H = b.width, b.height
        if self.mode == "routability":
            it = self._run_adaptive(cost, cross, length, pen, best, t0, time_limit, pg)
        else:
            it = self._run_fixed(cost, cross, length, pen, best, t0, time_limit, pg, iterations)
        res.iterations = it
        self.state = dict(self._best_state)
        cost, cross, length, pen = self.total_cost()
        for ref, (x, y, rot) in self.state.items():
            pl = b.parts[ref]
            pl.x, pl.y, pl.rot = x, y, rot
        b.touch()
        res.crossings_after = cross
        res.length_after = length
        res.overlaps_after = self._count_overlaps()
        res.seconds = time.time() - t0
        return res

    def _run_fixed(self, cost, cross, length, pen, best, t0, time_limit, pg, iterations) -> int:
        T0 = max(5.0, cost / max(10, len(self.refs)) * 0.5)
        W, H = self.b.width, self.b.height
        it = 0
        for it in range(iterations):
            if it & 63 == 0:
                if time.time() - t0 > time_limit or (self.cancel and self.cancel()):
                    break
                if self.progress and it & 511 == 0:
                    self.progress("Placing: %d crossings" % cross, it / float(iterations))
            frac = it / float(iterations)
            T = T0 * (1.0 - frac) ** 2 + 0.05
            step = max(pg, (W + H) / 6.0 * (1.0 - frac) ** 1.5)
            old = self._propose(self.rnd.choice(self.movable), step, pg)
            if old is None:
                continue
            delta, dc, dl, dp, old_edges, nets = self._delta(old)
            if delta <= 0 or self.rnd.random() < math.exp(-delta / T):
                cost += delta
                cross += dc
                length += dl
                pen += dp
                if cost < best[0] - 1e-9:
                    best = (cost, dict(self.state))
            else:
                self._undo(old, old_edges, nets)
        self._best_state = best[1]
        return it + 1

    def _run_adaptive(self, cost, cross, length, pen, best, t0, time_limit, pg) -> int:
        """VPR-style schedule: T from the spread of random moves, cooling by acceptance rate, move
        range held so about 44 % of moves are accepted; stops when T is tiny or time is up."""
        W, H = self.b.width, self.b.height
        n = len(self.movable)
        per_t = max(60, int(10 * n ** (4.0 / 3.0)))
        rlim = max(W, H)
        # starting temperature: 20 x the standard deviation of the cost change of random moves
        deltas = []
        for _ in range(min(per_t, 200)):
            old = self._propose(self.rnd.choice(self.movable), rlim / 3.0, pg)
            if old is None:
                continue
            d, dc, dl, dp, old_edges, nets = self._delta(old)
            deltas.append(d)
            self._undo(old, old_edges, nets)
        if deltas:
            mean = sum(deltas) / len(deltas)
            sd = math.sqrt(sum((d - mean) ** 2 for d in deltas) / len(deltas))
        else:
            sd = 1.0
        T = max(1.0, 20.0 * sd)
        it = 0
        n_nets = max(1, len(self.net_pins))
        t_step = None
        while True:
            now = time.time()
            if now - t0 > time_limit or (self.cancel and self.cancel()):
                break
            t_start = now
            if self.progress:
                self.progress("Placing: %d crossings, T %.1f" % (cross, T), min(0.99, 1.0 - min(1.0, T / (20.0 * sd + 1e-9))))
            acc = 0
            step = max(pg, rlim / 3.0)
            for _ in range(per_t):
                it += 1
                old = self._propose(self.rnd.choice(self.movable), step, pg)
                if old is None:
                    continue
                delta, dc, dl, dp, old_edges, nets = self._delta(old)
                if delta <= 0 or self.rnd.random() < math.exp(-delta / T):
                    acc += 1
                    cost += delta
                    cross += dc
                    length += dl
                    pen += dp
                else:
                    self._undo(old, old_edges, nets)
            R = acc / float(per_t)
            if R > 0.96:
                alpha = 0.5
            elif R > 0.8:
                alpha = 0.9
            elif R > 0.15:
                alpha = 0.95
            else:
                alpha = 0.8
            # deadline: if the schedule would not reach its stop temperature before the time limit,
            # cool faster so the run still ends cold (a hot layout is a bad layout)
            t_step = time.time() - t_start
            t_stop = 0.005 * max(cost, 1.0) / n_nets
            remaining = time_limit - (time.time() - t0)
            if T > t_stop and t_step > 0 and remaining > 0:
                steps_left = max(1.0, remaining / t_step) - 1.0
                need = math.exp(math.log(t_stop / T) / max(1.0, steps_left))
                alpha = min(alpha, max(0.3, need))
            T *= alpha
            rlim = min(max(W, H), max(pg * 2, rlim * (1.0 - 0.44 + R)))
            # the best layout is judged on the exactly recomputed cost at the end of every temperature
            # step, so a small drift in the summed deltas can never hide a better layout
            cost, cross, length, pen = self.total_cost()
            if cost < best[0] - 1e-9:
                best = (cost, dict(self.state))
            if T < 0.005 * max(cost, 1.0) / n_nets:
                break
        self._best_state = best[1]
        return it

    def _scatter(self, ref: str, pg: float) -> None:
        W, H, m = self.b.width, self.b.height, self.margin
        best = None
        for _ in range(60):
            x = round(self.rnd.uniform(m, W - m) / pg) * pg
            y = round(self.rnd.uniform(m, H - m) / pg) * pg
            self.state[ref] = (x, y, self.state[ref][2])
            p = self._part_pen(ref)
            if best is None or p < best[0]:
                best = (p, self.state[ref])
            if p == 0:
                return
        self.state[ref] = best[1]  # type: ignore[index]


def auto_place(board: Board, time_limit: float = 20.0, seed: int = 1, **kw) -> PlaceResult:
    return Placer(board, seed=seed, **kw).run(time_limit=time_limit)
