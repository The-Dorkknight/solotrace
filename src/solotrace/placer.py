# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Untangle placement by simulated annealing.

The cost is what a person looks at when judging a layout:
  * length of the ratsnest (minimum spanning tree of every net),
  * how many ratsnest lines cross each other (the "tangled string" count),
  * parts overlapping each other or leaving the board.
Locked parts never move. Parts are only moved to the placement grid and turned in 90 degree
steps. Component-side flip is not used (through-hole parts).
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


class Placer:
    def __init__(self, board: Board, gap: float = 3.0, margin: float = 2.5, seed: int = 1,
                 progress: Optional[Callable[[str, float], None]] = None,
                 cancel: Optional[Callable[[], bool]] = None) -> None:
        self.b = board
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
        return length + 10.0 * cross + 6.0 * pen, cross, length, pen

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
        T0 = max(5.0, cost / max(10, len(self.refs)) * 0.5)
        T = T0
        W, H = b.width, b.height
        for it in range(iterations):
            if it & 63 == 0:
                if time.time() - t0 > time_limit or (self.cancel and self.cancel()):
                    break
                if self.progress and it & 511 == 0:
                    self.progress("Placing: %d crossings" % cross, it / float(iterations))
            frac = it / float(iterations)
            T = T0 * (1.0 - frac) ** 2 + 0.05
            r1 = self.rnd.choice(self.movable)
            old = {r1: self.state[r1]}
            kind = self.rnd.random()
            x, y, rot = self.state[r1]
            if kind < 0.55:
                step = max(pg, (W + H) / 6.0 * (1.0 - frac) ** 1.5)
                nx = x + round(self.rnd.gauss(0, step) / pg) * pg
                ny = y + round(self.rnd.gauss(0, step) / pg) * pg
                self.state[r1] = (min(max(nx, 0.0), W), min(max(ny, 0.0), H), rot)
            elif kind < 0.75:
                self.state[r1] = (x, y, (rot + 90 * self.rnd.choice((1, 2, 3))) % 360)
            else:
                r2 = self.rnd.choice(self.movable)
                if r2 == r1:
                    continue
                old[r2] = self.state[r2]
                x2, y2, rot2 = self.state[r2]
                self.state[r1] = (x2, y2, rot)
                self.state[r2] = (x, y, rot2)
            moved = list(old)
            nets = sorted({n for r in moved for n in self.part_nets[r]})
            # cost before is cached; compute only the delta
            old_edges = {n: self.edges[n] for n in nets}
            old_len = sum(self._len(e) for e in old_edges.values())
            # evaluate "before" with the old positions (edges of the old layout are cached)
            new_state = {r: self.state[r] for r in moved}
            for r in moved:
                self.state[r] = old[r]
            old_cross = self._cross_count(nets) if nets else 0
            old_pen = sum(self._part_pen(r) for r in moved)
            for r in moved:
                self.state[r] = new_state[r]
            for n in nets:
                self.edges[n] = self._net_edges(n)
            new_cross = self._cross_count(nets) if nets else 0
            new_len = sum(self._len(self.edges[n]) for n in nets)
            new_pen = sum(self._part_pen(r) for r in moved)
            delta = (new_len - old_len) + 10.0 * (new_cross - old_cross) + 6.0 * (new_pen - old_pen)
            if delta <= 0 or self.rnd.random() < math.exp(-delta / T):
                cost += delta
                cross += new_cross - old_cross
                length += new_len - old_len
                pen += new_pen - old_pen
                if cost < best[0] - 1e-9:
                    best = (cost, dict(self.state))
            else:
                for r in moved:
                    self.state[r] = old[r]
                for n in nets:
                    self.edges[n] = old_edges[n]
            res.iterations = it + 1
        self.state = dict(best[1])
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
