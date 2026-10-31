# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Deadbug island mode: a ground fill over the whole board with every other net as an island.

This is the quick-and-dirty way RF and fast analogue circuits are often built: the board
stays almost all copper (a big, low-inductance ground), and each signal net is a patch of
copper cut free from it, with the parts soldered straight onto the copper ("deadbug" or
"Manhattan" style).

Nothing here uses polygon clipping. The copper of the board is described as a paint order
that every output can follow:

1. the **fill rectangle** (the board inset by the edge clearance) in copper,
2. the **cut shapes** (every non-ground island grown by its own growth plus the gap) in
   bare board, then
3. the **island shapes** (every non-ground copper shape grown by its growth) and all
   the ordinary copper, in copper.

Gerber does the same with clear polarity (``%LPC*%``), the laser engine with interval
arithmetic on each scan line, and the canvas, SVG and PDF by drawing in that order.

Growth is worked out per shape so islands of two different nets always keep at least
``gap`` between them and from ground copper, and stay inside the edge clearance.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .geom import Cap, Poly, bbox_gap, merge_intervals, shape_dist, shape_intervals, subtract_intervals

GROUND_NAMES = re.compile(r"^(gnd|ground|0v|vss|agnd|dgnd|com|earth|v-)$", re.I)


def guess_ground(board) -> Optional[str]:
    """The net called GND (or 0V, VSS, ground...), else the net with the most pins."""
    names = [n for n in board.nets if board.nets[n].pins]
    for n in names:
        if GROUND_NAMES.match(n.strip()):
            return n
    for n in names:
        if "gnd" in n.lower() or "ground" in n.lower():
            return n
    if not names:
        return None
    return max(names, key=lambda n: (len(board.nets[n].pins), n))


def ground_net(board) -> Optional[str]:
    """The ground net of an island-mode board (None when island mode is off or there are no nets)."""
    s = board.settings
    if not s.island_mode:
        return None
    if s.island_net and s.island_net in board.nets:
        return s.island_net
    return guess_ground(board)


def gap_of(board) -> float:
    s = board.settings
    return max(float(s.island_gap), s.clearance)


def _grown(sh, g: float, net, tag) -> List:
    """A shape grown by g as plain shapes (a polygon grown by a disc = polygon + edge capsules)."""
    if sh.kind == "cap":
        return [Cap(sh.x1, sh.y1, sh.x2, sh.y2, sh.r + g, net, tag)]
    out: List = [Poly(list(sh.pts), net, tag)]
    if g > 1e-9:
        n = len(sh.pts)
        for i in range(n):
            a, b = sh.pts[i], sh.pts[(i + 1) % n]
            out.append(Cap(a[0], a[1], b[0], b[1], g, net, tag))
    return out


class IslandPlan:
    """What island mode adds to the copper of a board."""

    def __init__(self, rect: Tuple[float, float, float, float], cut: List, fat: List,
                 ground: Optional[str], gap: float, grow: Dict[int, float]) -> None:
        self.rect = rect            # x0, y0, x1, y1 of the ground fill
        self.cut = cut              # shapes cut out of the fill (islands + gap)
        self.fat = fat              # the islands' extra copper
        self.ground = ground
        self.gap = gap
        self.grow = grow            # copper shape index -> growth used (mm)
        self.pins: Dict[str, int] = {}      # ground pin -> piece of fill it sits on
        self.floating: List = []            # pieces of fill no ground pin sits on (when kept)
        self.dropped = 0                    # pieces of floating fill cut away

    def rect_poly(self) -> Poly:
        x0, y0, x1, y1 = self.rect
        return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], self.ground, ("fill",))

    def paint(self, copper: Sequence) -> List[Tuple[object, bool]]:
        """(shape, is_copper) in drawing order: fill, cuts (bare board), islands and copper."""
        out: List[Tuple[object, bool]] = [(self.rect_poly(), True)]
        out += [(s, False) for s in self.cut]
        out += [(s, True) for s in self.fat]
        out += [(s, True) for s in copper]
        return out

    def fill_intervals(self, y: float, comp: float = 0.0) -> List[Tuple[float, float]]:
        """x-intervals of the ground fill on the line at y (copper grown by comp, which shrinks the cuts)."""
        x0, y0, x1, y1 = self.rect
        if y < y0 or y > y1:
            return []
        cuts: List[Tuple[float, float]] = []
        for s in self.cut:
            bb = s.bbox()
            if bb[1] - 1 <= y <= bb[3] + 1:
                cuts.extend(shape_intervals(s, y, -comp) if s.kind == "cap" else _poly_ivals(s, y, -comp))
        return subtract_intervals([(x0, x1)], merge_intervals(cuts))


def _poly_ivals(s, y: float, grow: float) -> List[Tuple[float, float]]:
    if grow >= 0:
        return shape_intervals(s, y, grow)
    # an eroded cut polygon only ever sits inside its own edge capsules, so leaving it whole is safe:
    # those capsules (radius growth + gap) are eroded correctly and cover the polygon's edges
    return shape_intervals(s, y, 0.0)


def plan(board) -> Optional[IslandPlan]:
    """The island layout of the board, or None when island mode is off. Cached per board change."""
    s = board.settings
    if not s.island_mode:
        return None
    fast = bool(getattr(board, "_island_fast", False))     # set by the editor while you drag something
    key = (board.rev, fast, s.island_net, s.island_gap, s.island_grow, s.island_drop_floating, s.clearance,
           s.edge_clearance,
           board.width, board.height, tuple(board.nets))
    cache = getattr(board, "_island_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    gnd = ground_net(board)
    gap = gap_of(board)
    want = max(0.0, float(s.island_grow))
    border = s.edge_clearance
    W, H = board.width, board.height
    cu = board.copper()
    bbs = [sh.bbox() for sh in cu]
    reach = 2 * want + gap + 0.01
    cell = max(2.0, reach)
    grid: Dict[Tuple[int, int], List[int]] = {}
    for i, bb in enumerate(bbs):
        for cx in range(int(math.floor(bb[0] / cell)), int(math.floor(bb[2] / cell)) + 1):
            for cy in range(int(math.floor(bb[1] / cell)), int(math.floor(bb[3] / cell)) + 1):
                grid.setdefault((cx, cy), []).append(i)
    grow: Dict[int, float] = {}
    for i, sh in enumerate(cu):
        if sh.net == gnd:
            continue
        bb = bbs[i]
        if sh.tag and sh.tag[0] == "isl":
            grow[i] = 0.0               # copper islands keep the size you gave them
            continue
        g = min(want, bb[0] - border, bb[1] - border, W - border - bb[2], H - border - bb[3])
        if g > 1e-6:
            seen = set()
            for cx in range(int(math.floor((bb[0] - reach) / cell)), int(math.floor((bb[2] + reach) / cell)) + 1):
                for cy in range(int(math.floor((bb[1] - reach) / cell)), int(math.floor((bb[3] + reach) / cell)) + 1):
                    for j in grid.get((cx, cy), ()):
                        if j in seen or j == i:
                            continue
                        seen.add(j)
                        o = cu[j]
                        if o.net == sh.net or bbox_gap(bb, bbs[j]) > reach:
                            continue
                        d = shape_dist(sh, o)
                        # ground copper does not grow; another island grows as much as this one may
                        lim = d - gap if o.net == gnd else (d - gap) / 2.0
                        if lim < g:
                            g = lim
        grow[i] = max(0.0, g)
    cut: List = []
    fat: List = []
    for i, g in grow.items():
        sh = cu[i]
        if g > 1e-6:
            fat.extend(_grown(sh, g, sh.net, ("island", i)))
        cut.extend(_grown(sh, g + gap, sh.net, ("cut", i)))
    rect = (border, border, W - border, H - border)
    p = IslandPlan(rect, cut, fat, gnd, gap, grow)
    if fast:
        # keep which ground pins share the fill from the last full check, so rubber bands do not flicker
        p.pins = dict(cache[1].pins) if cache else {}
        board._island_cache = (key, p)
        return p
    p.pins, p.floating = _analyse(board, p)
    if s.island_drop_floating and p.floating and gnd is not None:
        # cut away fill that no ground pin sits on: floating copper next to RF islands does harm
        step = (rect[3] - rect[1]) / max(1, int((rect[3] - rect[1]) / 0.05))
        for _x, _y, _a, rws in p.floating:
            p.cut.extend(_strips(rws, step, gnd))
        p.dropped = len(p.floating)
        p.floating = []
    if s.island_drop_floating and gnd is not None:
        # second pass along the other axis: slivers thinner than the row step show up as columns
        sw = _Swapped(board, p)
        _pins, more = _analyse(sw, sw)
        if more:
            stepx = (rect[2] - rect[0]) / max(1, int((rect[2] - rect[0]) / 0.05))
            for _x, _y, _a, rws in more:
                p.cut.extend(_swap(_strips(rws, stepx, gnd)))
            p.dropped += len(more)
    board._island_cache = (key, p)
    return p


def _swap(shapes) -> List:
    """The same shapes with x and y swapped (to scan along the other axis)."""
    out: List = []
    for s in shapes:
        if s.kind == "cap":
            out.append(Cap(s.y1, s.x1, s.y2, s.x2, s.r, s.net, s.tag))
        else:
            out.append(Poly([(y, x) for x, y in s.pts], s.net, s.tag))
    return out


class _Swapped:
    """A view of a plan and board with x and y swapped, for the second (column) pass."""

    def __init__(self, board, p) -> None:
        x0, y0, x1, y1 = p.rect
        self.rect = (y0, x0, y1, x1)
        self.cut = _swap(p.cut)
        self.ground = p.ground
        self.nets = board.nets
        self._b = board

    def has_pin(self, pin: str) -> bool:
        return self._b.has_pin(pin)

    def pin_pos(self, pin: str):
        x, y = self._b.pin_pos(pin)
        return (y, x)


def _analyse(board, p, step: float = 0.05):
    """Split the fill into pieces by sampling it on scan lines ``step`` apart.

    Overlapping intervals on neighbouring lines are joined (union-find), so a piece of fill
    cut off by islands gets its own number. Returns (pin -> piece number, floating pieces),
    where each floating piece is (x, y, area mm², [(y, lo, hi) rows]).
    """
    x0, y0, x1, y1 = p.rect
    if y1 <= y0 or x1 <= x0:
        return {}, []
    n = max(1, int((y1 - y0) / step))
    dy = (y1 - y0) / n
    cuts = sorted(((c.bbox()[1], c.bbox()[3], c) for c in p.cut), key=lambda t: t[0])
    active: List[tuple] = []
    nxt = 0
    rows: List[Tuple[float, List[Tuple[float, float]]]] = []
    for k in range(n + 1):
        y = y0 + k * dy
        while nxt < len(cuts) and cuts[nxt][0] <= y:
            active.append(cuts[nxt])
            nxt += 1
        active = [t for t in active if t[1] >= y]
        cv: List[Tuple[float, float]] = []
        for _a, _b, c in active:
            cv.extend(shape_intervals(c, y, 0.0))
        rows.append((y, subtract_intervals([(x0, x1)], merge_intervals(cv))))
    parent: List[int] = []
    ids: List[List[int]] = []

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for r, (_y, ivs) in enumerate(rows):
        row_ids = []
        for _iv in ivs:
            parent.append(len(parent))
            row_ids.append(len(parent) - 1)
        ids.append(row_ids)
        if r:
            prev, cur = rows[r - 1][1], ivs
            i = j = 0
            while i < len(prev) and j < len(cur):
                if prev[i][1] > cur[j][0] + 1e-9 and cur[j][1] > prev[i][0] + 1e-9:
                    ra, rb = find(ids[r - 1][i]), find(row_ids[j])
                    if ra != rb:
                        parent[ra] = rb
                if prev[i][1] < cur[j][1]:
                    i += 1
                else:
                    j += 1
    pins: Dict[str, int] = {}
    roots: Dict[int, int] = {}
    net = board.nets.get(p.ground) if p.ground else None
    for pin in (net.pins if net else []):
        if not board.has_pin(pin):
            continue
        x, y = board.pin_pos(pin)
        if not (y0 <= y <= y1):
            continue
        r = int(round((y - y0) / dy))
        for idx, (lo, hi) in enumerate(rows[r][1]):
            if lo - 1e-6 <= x <= hi + 1e-6:
                root = find(ids[r][idx])
                pins[pin] = roots.setdefault(root, len(roots))
                break
    loose: Dict[int, list] = {}
    for r, (y, ivs) in enumerate(rows):
        for idx, (lo, hi) in enumerate(ivs):
            root = find(ids[r][idx])
            if root not in roots:
                loose.setdefault(root, []).append((y, lo, hi))
    floating = []
    for rws in loose.values():
        area = sum(hi - lo for _y, lo, hi in rws) * dy
        y, lo, hi = max(rws, key=lambda t: t[2] - t[1])
        floating.append(((lo + hi) / 2, y, area, rws))
    return pins, floating


def _strips(rows, dy: float, net) -> List:
    """Polygons that cover a piece of fill sampled as rows (to cut it away).

    Intervals on neighbouring rows that overlap are chained, and each chain becomes one
    polygon (its left ends going up, its right ends coming back down), a little larger than
    the piece, so prints show no seams and diagonal edges do not need a shape per row.
    """
    # a little extra all round (well inside the gap round the islands, which is at least the
    # copper clearance): neighbouring chains overlap by a whole row, so no sliver of fill is left
    e = 0.15
    h = dy + 0.02
    by_y: Dict[float, List[Tuple[float, float]]] = {}
    for y, lo, hi in rows:
        by_y.setdefault(y, []).append((lo, hi))
    chains: List[List[Tuple[float, float, float]]] = []
    live: List[List[Tuple[float, float, float]]] = []
    for y in sorted(by_y):
        nxt = []
        for lo, hi in sorted(by_y[y]):
            hit = None
            for ch in live:
                ly, llo, lhi = ch[-1]
                if y - ly < dy * 1.5 and llo < hi and lo < lhi and ch not in nxt:
                    hit = ch
                    break
            if hit is None:
                hit = []
                chains.append(hit)
            hit.append((y, lo, hi))
            nxt.append(hit)
        live = nxt
    out: List = []
    for ch in chains:
        left = [(ch[0][1] - e, ch[0][0] - h)] + [(lo - e, y) for y, lo, _hi in ch] + [(ch[-1][1] - e, ch[-1][0] + h)]
        right = [(ch[-1][2] + e, ch[-1][0] + h)] + [(hi + e, y) for y, _lo, hi in reversed(ch)] + \
                [(ch[0][2] + e, ch[0][0] - h)]
        out.append(Poly(left + right, net, ("floating",)))
    return out


def fill_groups(board) -> Tuple[Dict[str, int], int]:
    """Which piece of ground fill each ground pin sits on: ({pin: piece}, number of pieces)."""
    p = plan(board)
    if p is None or p.ground is None:
        return {}, 0
    return dict(p.pins), len(set(p.pins.values()))


def floating_fill(board) -> List[Tuple[float, float, float]]:
    """Pieces of ground fill (at least 0.5 mm²) that no ground pin sits on and that were kept: (x, y, area)."""
    p = plan(board)
    if p is None:
        return []
    return [(x, y, a) for x, y, a, _r in p.floating if a >= 0.5]


def ground_groups(board, copper_groups: List[List[str]]) -> List[List[str]]:
    """Groups of ground pins joined by copper OR by the same piece of ground fill."""
    pieces, _n = fill_groups(board)
    groups = [list(g) for g in copper_groups]
    joined = {q for g in groups for q in g}
    net = board.nets.get(ground_net(board) or "")
    for pin in (net.pins if net else []):
        if pin not in joined and board.has_pin(pin):
            groups.append([pin])
    parent = list(range(len(groups)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    first: Dict[int, int] = {}
    for gi, g in enumerate(groups):
        for q in g:
            if q in pieces:
                pc = pieces[q]
                if pc in first:
                    ra, rb = find(first[pc]), find(gi)
                    if ra != rb:
                        parent[ra] = rb
                else:
                    first[pc] = gi
    out: Dict[int, List[str]] = {}
    for gi, g in enumerate(groups):
        out.setdefault(find(gi), []).extend(g)
    return [g for g in out.values() if g]


def make_pads_deadbug(board) -> int:
    """Set every part's pads to deadbug (surface, no drill). Returns how many parts changed."""
    n = 0
    for pl in board.parts.values():
        if pl.style != "dead" or pl.pad_styles:
            pl.style = "dead"
            pl.pad_styles = {}
            n += 1
    if n:
        board.touch()
    return n
