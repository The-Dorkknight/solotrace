# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Trace clean-up and editing: straight pad exits, centred ends, dragging, trimming.

Wide traces look wrong when they leave a pad at an angle or end a little off the pad
centre (the copper becomes a blob). ``tidy_trace`` fixes that:

1. an end that lies inside a pad of its own net is moved to the pad centre;
2. a wide trace (``WIDE`` mm or more) gets a straight vertical or horizontal exit from
   the pad, roughly the pad radius plus the trace width long, before it turns;
3. corners are re-cut so a chamfer never eats those exits, then lengthened where there
   is room.

Every change is checked against the real copper and the clearance rule; if a better
shape does not fit, the trace is left as it was.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from .board import Board, Trace
from .geom import (Cap, chamfer_polyline, dist, octi_path, polyline_length, seg_point_dist, shape_dist,
                   simplify_polyline, turn_angle)

Point = Tuple[float, float]
WIDE = 1.2          # traces at least this wide get straight pad exits
AXES = ((0.0, -1.0), (0.0, 1.0), (-1.0, 0.0), (1.0, 0.0))


# --------------------------------------------------------------------------- checks
def path_violations(board: Board, net: str, pts: Sequence[Point], width: float, stop: int = 0) -> int:
    """How many other-net shapes (and edge points) a trace along ``pts`` comes too close to."""
    return len(violation_set(board, net, pts, width, stop))


def violation_set(board: Board, net: str, pts: Sequence[Point], width: float, stop: int = 0) -> set:
    """The other-net shapes (by tag) and edge points a trace along ``pts`` comes too close to."""
    st = board.settings
    clr = st.clearance - 1e-4
    r = width / 2.0
    hit = set()
    for x, y in pts:
        e = st.edge_clearance + r - 1e-4
        if x < e or y < e or x > board.width - e or y > board.height - e:
            hit.add(("edge",))
    shapes = [s for s in board.copper() if s.net != net]
    for i in range(len(pts) - 1):
        cap = Cap(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], r)
        bx0, by0, bx1, by1 = cap.bbox()
        for s in shapes:
            k = (s.net, s.tag)
            if k in hit:
                continue
            sb = s.bbox()
            if sb[0] > bx1 + clr or sb[2] < bx0 - clr or sb[1] > by1 + clr or sb[3] < by0 - clr:
                continue
            if shape_dist(cap, s) < clr:
                hit.add(k)
                if stop and len(hit) >= stop:
                    return hit
    return hit


def path_clear(board: Board, net: str, pts: Sequence[Point], width: float, skip_trace: Optional[Trace] = None) -> bool:
    """True if a trace of ``width`` along ``pts`` keeps clearance to other nets and the edge."""
    return path_violations(board, net, pts, width, stop=1) == 0


def _pad_at(board: Board, net: str, p: Point) -> Optional[Tuple[str, Point, float]]:
    """(pin, centre, pad radius) of a pad of ``net`` that contains ``p``."""
    probe = Cap(p[0], p[1], p[0], p[1], 0.0)
    for s in board.copper():
        if s.tag and s.tag[0] == "pad" and s.net == net and shape_dist(probe, s) <= 1e-6:
            pin = "%s.%s" % (s.tag[1], s.tag[2])
            c = board.pin_pos(pin)
            x0, y0, x1, y1 = s.bbox()
            rad = 0.5 * min(x1 - x0, y1 - y0)
            return pin, c, rad
    return None


def _max_turn(pts: Sequence[Point]) -> float:
    m = 0.0
    for i in range(1, len(pts) - 1):
        m = max(m, turn_angle(pts[i - 1], pts[i], pts[i + 1]))
    return m


def _octi_ok(pts: Sequence[Point]) -> bool:
    for i in range(len(pts) - 1):
        dx, dy = abs(pts[i + 1][0] - pts[i][0]), abs(pts[i + 1][1] - pts[i][1])
        if dx > 1e-6 and dy > 1e-6 and abs(dx - dy) > 1e-6:
            return False
    return True


def _over_body(board: Board, pin: str, a: Point, b: Point) -> bool:
    """Does the exit a->b run over the body of the part it starts from?"""
    ref = pin.split(".")[0]
    if ref not in board.parts:
        return False
    x0, y0, x1, y1 = board.court_rect(ref)
    for k in (0.5, 1.0):
        x, y = a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
        if x0 + 0.2 < x < x1 - 0.2 and y0 + 0.2 < y < y1 - 0.2:
            return True
    return False


# ----------------------------------------------------------------------- the tidy
def _fix_start(board: Board, t: Trace, pts: List[Point], w: float) -> List[Point]:
    """Return ``pts`` with a centred start and, for wide traces, a straight exit."""
    hit = _pad_at(board, t.net, pts[0])
    if hit is None:
        return pts
    pin, c, prad = hit
    wide = w >= WIDE - 1e-9
    orig_len = polyline_length(pts)
    first_ok = False
    if len(pts) >= 2 and dist(pts[0], c) < 1e-6:
        dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        axis = abs(dx) < 1e-6 or abs(dy) < 1e-6
        first_ok = (not wide) or (axis and dist(pts[0], pts[1]) >= prad + 0.6 * w - 1e-6)
    if first_ok:
        return pts
    cands: List[Tuple[float, List[Point]]] = []
    E_full = prad + max(w, 1.0)
    for E in ((E_full, E_full * 0.6) if wide else (0.0,)):
        for j in range(1, min(len(pts), 5) if wide else 2):
            pj = pts[j]
            tail = pts[j + 1:]
            dirs = AXES if wide else ((0.0, 0.0),)
            for d in dirs:
                s = (c[0] + d[0] * E, c[1] + d[1] * E)
                for var in (False, True):
                    head = [c] if not wide else [c, s]
                    mid = octi_path(head[-1], pj, var)
                    new = simplify_polyline(head + mid[1:] + tail)
                    if len(new) < 2 or not _octi_ok(new):
                        continue
                    if _max_turn(new) > 90.0 + 1e-6:
                        continue
                    if wide:
                        f = (new[1][0] - new[0][0], new[1][1] - new[0][1])
                        if abs(f[0]) > 1e-6 and abs(f[1]) > 1e-6:
                            continue
                        if dist(new[0], new[1]) < E - 1e-6:
                            continue
                    L = polyline_length(new)
                    if L > orig_len + 2.5 * max(E, 1.0) + 1.0:
                        continue
                    cost = L + 0.6 * sum(1 for i in range(1, len(new) - 1) if turn_angle(new[i - 1], new[i], new[i + 1]) > 1)
                    if wide and _over_body(board, pin, new[0], new[1]):
                        cost += 25.0
                    if wide and E < E_full:
                        cost += 8.0
                    cands.append((cost, new))
    if wide:
        # last resort for a wide trace: only bring the end onto the pad centre (no straight exit)
        for var in (False, True):
            new = simplify_polyline([c] + octi_path(c, pts[1], var)[1:] + pts[2:])
            if len(new) >= 2 and _octi_ok(new) and _max_turn(new) <= 90.0 + 1e-6:
                cands.append((1e6 + polyline_length(new), new))
    cands.sort(key=lambda kv: kv[0])
    base = violation_set(board, t.net, pts, w)
    old_w = list(t.widths)
    best = None
    for _cost, new in cands[:48]:
        test = chamfer_polyline(new, board.settings.chamfer_len(w), keep_ends=(prad + 0.6 * w) if wide else 0.0)
        v = violation_set(board, t.net, test, w)
        if v and not (wide and best is None and v <= base):
            continue
        # never pull the trace off a branch, pad or jumper that is joined to it
        if not keeps_joints(board, t, pts, _widths_for(t, pts) if len(pts) - 1 != len(old_w) else old_w,
                            test, _widths_for(t, test)):
            continue
        if not v:
            return new
        best = new              # still too wide to fit, but touches nothing new and is neater
    return best if best is not None else pts


# ------------------------------------------------------------ keep joints joined
def _widths_for(t: Trace, pts: Sequence[Point]) -> List[float]:
    tmp = Trace(t.net, list(t.points), list(t.widths), t.manual)
    _set_points(tmp, list(pts), list(t.points))
    return tmp.widths


def _touch_profile(board: Board, t: Trace, pts: Sequence[Point], widths: Sequence[float]):
    """What a trace of this shape touches on its own net, and how deep the other traces'
    ends sit in it. ``board.traces`` must not contain ``t`` itself."""
    caps = [Cap(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], widths[min(i, len(widths) - 1)] / 2.0)
            for i in range(len(pts) - 1)]
    touched = set()
    for s in board.copper():
        if s.net != t.net:
            continue
        if any(shape_dist(c, s) <= 1e-6 for c in caps):
            if s.tag and s.tag[0] == "trace":
                touched.add(("trace", id(board.traces[s.tag[1]])))
            else:
                touched.add(s.tag)
    ends = {}
    for o in board.traces:
        if o.net != t.net:
            continue
        for e in (o.points[0], o.points[-1]):
            d = min(seg_point_dist(e, pts[i], pts[i + 1]) for i in range(len(pts) - 1))
            r = widths[0] / 2.0 if widths else 0.4
            if d <= max(r, 0.05):
                ends[(id(o), e)] = d
    return touched, ends


def keeps_joints(board: Board, t: Trace, old_pts: Sequence[Point], old_w: Sequence[float],
                 new_pts: Sequence[Point], new_w: Sequence[float]) -> bool:
    """True if the reshaped trace still touches every pad, trace and jumper of its net that the old
    one touched, and every other trace that ended on it still ends at least as deep inside it.
    Without this, moving a trunk leaves its branches hanging (or a pad it ran over cut off).
    ``board.traces`` must not contain ``t``."""
    before, ends_b = _touch_profile(board, t, old_pts, old_w)
    after, _ends_a = _touch_profile(board, t, new_pts, new_w)
    if not before <= after:
        return False
    for (oid, e), d0 in ends_b.items():
        d1 = min(seg_point_dist(e, new_pts[i], new_pts[i + 1]) for i in range(len(new_pts) - 1))
        if d1 > d0 + 0.05:
            return False
    return True


def tidy_trace(board: Board, t: Trace) -> bool:
    """Clean one trace in place. Returns True if anything changed."""
    if len(t.points) < 2:
        return False
    w = max(t.widths) if t.widths else board.net_width(t.net)
    old = list(t.points)
    others = [x for x in board.traces if x is not t]
    # judge clearance without the trace itself in the copper list
    saved = board.traces
    board.traces = others
    board.touch()
    try:
        pts = list(t.points)
        pts = _fix_start(board, t, pts, w)
        pts = list(reversed(_fix_start(board, t, list(reversed(pts)), w)))
        ka = _pad_at(board, t.net, pts[0])
        kb = _pad_at(board, t.net, pts[-1])
        keep = 0.0
        if w >= WIDE:
            keep = max(ka[2] if ka else 0.0, kb[2] if kb else 0.0) + 0.6 * w
        pts = chamfer_polyline(pts, board.settings.chamfer_len(w), keep_ends=keep)
        if not violation_set(board, t.net, pts, w) <= violation_set(board, t.net, old, w):
            pts = old
        if pts != old and not keeps_joints(board, t, old, t.widths, pts, _widths_for(t, pts)):
            pts = old                      # something was joined to the old shape: leave it alone
    finally:
        board.traces = saved
        board.touch()
    if pts == old:
        changed = False
    else:
        _set_points(t, pts, old)
        changed = True
    if w >= WIDE:
        from .router import smooth_corners
        changed = smooth_corners(board, None, [t]) > 0 or changed
    board.touch()
    return changed


def tidy_traces(board: Board, traces: Optional[List[Trace]] = None) -> int:
    n = 0
    for t in list(traces if traces is not None else board.traces):
        if t in board.traces and tidy_trace(board, t):
            n += 1
    return n


def _set_points(t: Trace, pts: List[Point], old_pts: Optional[List[Point]] = None) -> None:
    """Replace the points, giving every new segment the width of the nearest old one."""
    old_pts = old_pts if old_pts is not None else t.points
    old_w = list(t.widths) or [0.8]
    new_w = []
    for i in range(len(pts) - 1):
        mid = ((pts[i][0] + pts[i + 1][0]) / 2.0, (pts[i][1] + pts[i + 1][1]) / 2.0)
        if len(old_pts) >= 2:
            k = min(range(len(old_pts) - 1), key=lambda j: seg_point_dist(mid, old_pts[j], old_pts[j + 1]))
            new_w.append(old_w[min(k, len(old_w) - 1)])
        else:
            new_w.append(old_w[0])
    t.points = [(round(p[0], 4), round(p[1], 4)) for p in pts]
    t.widths = new_w


# ------------------------------------------------------------------- dragging
def _line_intersect(p: Point, u: Point, q: Point, v: Point) -> Optional[Point]:
    """Intersection of line p + s*u with line q + t*v."""
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-9:
        return None
    s = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
    return (p[0] + s * u[0], p[1] + s * u[1])


def drag_segment(pts: Sequence[Point], i: int, offset: Point, grid: float = 0.0) -> List[Point]:
    """Move segment ``i`` sideways by ``offset`` (only the part at right angles to it counts).

    The neighbouring segments keep their direction and stretch or shrink, like dragging a
    segment in a normal PCB editor. Ends that sit on pads never move: a short 45 degree
    link is added there instead. The result is octilinear before chamfering.
    """
    pts = [tuple(p) for p in pts]
    a, b = pts[i], pts[i + 1]
    L = dist(a, b)
    if L < 1e-9:
        return list(pts)
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    n = (-u[1], u[0])
    s = offset[0] * n[0] + offset[1] * n[1]
    if grid > 0:
        step = grid if (abs(n[0]) < 1e-6 or abs(n[1]) < 1e-6) else grid * math.sqrt(0.5) * 2
        s = round(s / step) * step
    if abs(s) < 1e-9:
        return list(pts)
    a2 = (a[0] + n[0] * s, a[1] + n[1] * s)
    b2 = (b[0] + n[0] * s, b[1] + n[1] * s)
    out: List[Point] = list(pts[:i])
    # start side
    if i == 0:
        out = [a] + _link(a, a2, u)
    else:
        p = pts[i - 1]
        v = (a[0] - p[0], a[1] - p[1])
        x = _line_intersect(p, v, a2, u)
        if x is not None and (x[0] - p[0]) * v[0] + (x[1] - p[1]) * v[1] > 1e-6:
            out.append(x)
        else:
            out += [a] + _link(a, a2, u)
    # end side
    if i + 1 == len(pts) - 1:
        lk = _link(b, b2, (-u[0], -u[1]))
        out += list(reversed(lk)) + [b]
    else:
        q = pts[i + 2]
        v = (q[0] - b[0], q[1] - b[1])
        x = _line_intersect(q, (-v[0], -v[1]), b2, u)
        if x is not None and (q[0] - x[0]) * v[0] + (q[1] - x[1]) * v[1] > 1e-6:
            out.append(x)
        else:
            lk = _link(b, b2, (-u[0], -u[1]))
            out += list(reversed(lk)) + [b]
        out += list(pts[i + 2:])
    return simplify_polyline(out)


def _link(a: Point, a2: Point, u: Point) -> List[Point]:
    """Points that lead from fixed point ``a`` to the moved point ``a2`` at 45 degrees.

    Returns the points after ``a`` (ending with ``a2``): a diagonal that also moves along
    the segment direction ``u`` so the joint has no 90 degree corner.
    """
    d = dist(a, a2)
    mid = (a[0] + (a2[0] - a[0]) + u[0] * d, a[1] + (a2[1] - a[1]) + u[1] * d)
    return [mid]


# ---------------------------------------------------------------- trim/split
def split_at(t: Trace, seg: int, p: Point) -> Tuple[List[Point], List[Point]]:
    a, b = t.points[seg], t.points[seg + 1]
    L = dist(a, b)
    if L < 1e-9:
        return t.points[:seg + 1], t.points[seg + 1:]
    k = max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)))
    m = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
    return list(t.points[:seg + 1]) + [m], [m] + list(t.points[seg + 1:])


def trim_segment(board: Board, ti: int, seg: int) -> int:
    """Cut section ``seg`` out of trace ``ti``. The pieces either side stay as their own traces.

    Returns how many traces are left from the original (0, 1 or 2).
    """
    t = board.traces[ti]
    left = list(t.points[:seg + 1])
    right = list(t.points[seg + 1:])
    lw = list(t.widths[:seg])
    rw = list(t.widths[seg + 1:])
    del board.traces[ti]
    kept = 0
    for pts, ws in ((left, lw), (right, rw)):
        if len(pts) >= 2 and polyline_length(pts) > 0.05:
            board.traces.insert(ti + kept, Trace(t.net, pts, ws, True, t.rigid))
            kept += 1
    board.touch()
    return kept


def split_trace(board: Board, ti: int, seg: int, p: Point) -> None:
    """Break trace ``ti`` into two traces at point ``p`` on section ``seg``."""
    t = board.traces[ti]
    a, b = split_at(t, seg, p)
    wa = list(t.widths[:seg + 1])
    wb = list(t.widths[seg:])
    del board.traces[ti]
    board.traces.insert(ti, Trace(t.net, b, wb, True, t.rigid))
    board.traces.insert(ti, Trace(t.net, a, wa, True, t.rigid))
    board.touch()


def apply_drag(board: Board, ti: int, seg: int, base_pts: List[Point], base_w: List[float],
               offset: Point) -> None:
    """Set trace ``ti`` to ``base_pts`` with section ``seg`` dragged by ``offset`` (chamfered)."""
    t = board.traces[ti]
    w = max(base_w) if base_w else 0.8
    moved = drag_segment(base_pts, seg, offset, board.settings.grid)
    moved = chamfer_polyline(moved, board.settings.chamfer_len(w), keep_ends=0.0)
    tmp = Trace(t.net, list(base_pts), list(base_w), t.manual)
    _set_points(tmp, moved, list(base_pts))
    t.points, t.widths = tmp.points, tmp.widths
    t.manual = True
    board.touch()


# ------------------------------------------------------------------------ cut
def project_on_trace(t: Trace, p: Point) -> Tuple[int, Point, float]:
    """(section index, nearest point on the trace, distance along the trace) for point ``p``."""
    best = None
    run = 0.0
    for i in range(len(t.points) - 1):
        a, b = t.points[i], t.points[i + 1]
        L = dist(a, b)
        k = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)))
        q = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        d = dist(p, q)
        if best is None or d < best[0]:
            best = (d, i, q, run + L * k)
        run += L
    assert best is not None
    return best[1], best[2], best[3]


def cut_between(board: Board, ti: int, p1: Point, p2: Point) -> int:
    """Remove the copper of trace ``ti`` between two points on it; the rest of the trace stays.

    Returns how many pieces are left (0, 1 or 2). Every other trace of the net is untouched.
    """
    t = board.traces[ti]
    s1, q1, d1 = project_on_trace(t, p1)
    s2, q2, d2 = project_on_trace(t, p2)
    if d2 < d1:
        s1, q1, d1, s2, q2, d2 = s2, q2, d2, s1, q1, d1
    left = list(t.points[:s1 + 1]) + [q1]
    lw = list(t.widths[:s1 + 1])
    right = [q2] + list(t.points[s2 + 1:])
    rw = list(t.widths[s2:])
    del board.traces[ti]
    kept = 0
    for pts, ws in ((left, lw), (right, rw)):
        pts = simplify_polyline(pts)
        if len(pts) >= 2 and polyline_length(pts) > 0.05:
            nt = Trace(t.net, pts, [ws[min(i, len(ws) - 1)] for i in range(len(pts) - 1)], True, t.rigid)
            # keep each section's own width
            nt.widths = []
            for i in range(len(pts) - 1):
                mid = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
                k = min(range(len(t.points) - 1), key=lambda j: seg_point_dist(mid, t.points[j], t.points[j + 1]))
                nt.widths.append(t.widths[k])
            board.traces.insert(ti + kept, nt)
            kept += 1
    board.touch()
    return kept


# --------------------------------------------------------------- trim a piece
def _point_at(pts: Sequence[Point], d: float) -> Tuple[int, Point]:
    """(section index, point) at distance ``d`` along a polyline."""
    run = 0.0
    for i in range(len(pts) - 1):
        L = dist(pts[i], pts[i + 1])
        if d <= run + L or i == len(pts) - 2:
            k = 0.0 if L < 1e-12 else max(0.0, min(1.0, (d - run) / L))
            return i, (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k)
        run += L
    return len(pts) - 2, pts[-1]


def _sub_polyline(pts: Sequence[Point], d0: float, d1: float) -> List[Point]:
    i0, p0 = _point_at(pts, d0)
    i1, p1 = _point_at(pts, d1)
    return simplify_polyline([p0] + list(pts[i0 + 1:i1 + 1]) + [p1])


def piece_bounds(board: Board, ti: int, p: Point, step: float = 0.1) -> Optional[Tuple[float, float, float]]:
    """The stretch of trace ``ti`` around point ``p`` that has no joint on it.

    A joint is anything of the same net that the trace's centre line runs into: a pad, another
    trace, a jumper pad. Returns (start, end, total length) along the trace, measured so that
    what is left either side still reaches into its joint, or None if ``p`` is on a joint.
    """
    t = board.traces[ti]
    pts = t.points
    total = polyline_length(pts)
    if total < 1e-9:
        return None
    others = [s for s in board.copper() if s.net == t.net and not (s.tag and s.tag[0] == "trace" and s.tag[1] == ti)]
    n = max(2, int(total / step) + 1)
    covered = []
    for k in range(n + 1):
        d = total * k / n
        _i, q = _point_at(pts, d)
        probe = Cap(q[0], q[1], q[0], q[1], 0.0)
        covered.append(any(shape_dist(probe, s) <= 1e-6 for s in others))
    _s, _q, dclick = project_on_trace(t, p)
    kc = int(round(dclick / total * n))
    if covered[kc]:
        return None
    lo = kc
    while lo > 0 and not covered[lo - 1]:
        lo -= 1
    hi = kc
    while hi < n and not covered[hi + 1]:
        hi += 1
    # cut inside the joints (one sample in), so the pieces that stay remain joined
    d_lo = total * max(0, lo - 1) / n if lo > 0 else 0.0
    d_hi = total * min(n, hi + 1) / n if hi < n else total
    return d_lo, d_hi, total


def trim_piece(board: Board, ti: int, p: Point) -> Optional[int]:
    """Remove the piece of trace ``ti`` that ``p`` is on, from joint to joint (see piece_bounds).

    Pieces left over that lie completely inside a joint (a stub inside a pad) are dropped too.
    Returns how many pieces of the trace stay, or None if ``p`` is on a joint.
    """
    b = piece_bounds(board, ti, p)
    if b is None:
        return None
    d_lo, d_hi, total = b
    t = board.traces[ti]
    keep = []
    if d_lo > 1e-6:
        keep.append(_sub_polyline(t.points, 0.0, d_lo))
    if d_hi < total - 1e-6:
        keep.append(_sub_polyline(t.points, d_hi, total))
    # a leftover that is only a stub inside its pad or trace is not worth keeping
    others = [s for s in board.copper() if s.net == t.net and not (s.tag and s.tag[0] == "trace" and s.tag[1] == ti)]
    kept_pts = []
    for pts in keep:
        if len(pts) < 2 or polyline_length(pts) < 0.05:
            continue
        L = polyline_length(pts)
        m = max(2, int(L / 0.1))
        free = False
        for k in range(m + 1):
            _i, q = _point_at(pts, L * k / m)
            if not any(shape_dist(Cap(q[0], q[1], q[0], q[1], 0.0), s) <= 1e-6 for s in others):
                free = True
                break
        if free:
            kept_pts.append(pts)
    del board.traces[ti]
    for k, pts in enumerate(kept_pts):
        nt = Trace(t.net, pts, [0.8] * (len(pts) - 1), True, t.rigid)
        nt.widths = []
        for i in range(len(pts) - 1):
            mid = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
            j = min(range(len(t.points) - 1), key=lambda jj: seg_point_dist(mid, t.points[jj], t.points[jj + 1]))
            nt.widths.append(t.widths[j])
        board.traces.insert(ti + k, nt)
    board.touch()
    return len(kept_pts)


# ------------------------------------------------------------ branches on trunks
def _ray_hit(p: Point, d: Point, a: Point, b: Point) -> Optional[float]:
    """Distance t >= 0 along p + t*d (d a unit vector) where it meets segment a-b, or None."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = d[0] * ey - d[1] * ex
    if abs(den) < 1e-12:
        return None
    t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
    u = ((a[0] - p[0]) * d[1] - (a[1] - p[1]) * d[0]) / den
    if t < -1e-9 or u < -1e-9 or u > 1 + 1e-9:
        return None
    return t


def attached_ends(board: Board, trunk: Trace) -> List[Tuple[Trace, int, List[Point]]]:
    """Other traces of the same net with an end on ``trunk`` (a T-joint, not a pad):
    (trace, 0 or -1, copy of its points)."""
    out = []
    hw = max(trunk.widths) / 2.0 if trunk.widths else 0.4
    for o in board.traces:
        if o is trunk or o.net != trunk.net or len(o.points) < 2:
            continue
        for k in (0, -1):
            e = o.points[k]
            if _pad_at(board, o.net, e) is not None:
                continue
            d = min(seg_point_dist(e, trunk.points[i], trunk.points[i + 1]) for i in range(len(trunk.points) - 1))
            if d <= hw + 1e-6:
                out.append((o, k, list(o.points)))
    return out


def follow_trunk(board: Board, trunk: Trace, attached: List[Tuple[Trace, int, List[Point]]]) -> None:
    """After a trunk moved, slide each attached branch end along its own last section until it meets
    the trunk again (or add a 45 degree link to the nearest point), so the branches stay joined."""
    for o, k, base in attached:
        if o not in board.traces:
            continue
        pts = list(base)
        if k == 0:
            pts.reverse()
        e, p = pts[-1], pts[-2]
        L = dist(p, e)
        if L < 1e-9:
            continue
        d = ((e[0] - p[0]) / L, (e[1] - p[1]) / L)
        best = None
        for i in range(len(trunk.points) - 1):
            t = _ray_hit(p, d, trunk.points[i], trunk.points[i + 1])
            if t is not None and t > 0.05 and (best is None or t < best):
                best = t
        if best is not None:
            new = pts[:-1] + [(p[0] + d[0] * best, p[1] + d[1] * best)]
        else:
            q = min((project_on_trace(trunk, p)[1],), key=lambda x: 0)
            new = pts[:-1] + octi_path(p, q)[1:]
        new = simplify_polyline(new)
        if k == 0:
            new.reverse()
        w = max(o.widths) if o.widths else 0.8
        new = chamfer_polyline(new, board.settings.chamfer_len(w))
        tmp = Trace(o.net, list(base), list(o.widths), o.manual)
        _set_points(tmp, new, list(base))
        o.points, o.widths = tmp.points, tmp.widths
        o.manual = True
    board.touch()


def settle_branch_ends(board: Board) -> int:
    """Make T-joints look like one piece of copper: a branch that ends on another trace of its net
    stops on that trace's centre line, pulled back a little when the branch is the wider one, so its
    round end does not poke out of the far side. Returns how many ends moved."""
    moved = 0
    for o in list(board.traces):
        if len(o.points) < 2:
            continue
        for k in (0, -1):
            e = o.points[k]
            p = o.points[1] if k == 0 else o.points[-2]
            if _pad_at(board, o.net, e) is not None:
                continue
            L = dist(p, e)
            if L < 1e-9:
                continue
            d = ((e[0] - p[0]) / L, (e[1] - p[1]) / L)
            wb = o.widths[0] if k == 0 else o.widths[-1]
            hit = None
            for t in board.traces:
                if t is o or t.net != o.net:
                    continue
                for i in range(len(t.points) - 1):
                    if seg_point_dist(e, t.points[i], t.points[i + 1]) > t.widths[i] / 2.0 + 1e-6:
                        continue
                    s = _ray_hit(p, d, t.points[i], t.points[i + 1])
                    if s is not None and (hit is None or s < hit[0]):
                        hit = (s, t.widths[i])
            if hit is None:
                continue
            s, wt = hit
            back = max(0.0, (wb - wt) / 2.0)
            others = [(t.points[i], t.points[i + 1], t.widths[i]) for t in board.traces
                      if t is not o and t.net == o.net for i in range(len(t.points) - 1)]
            done = False
            for f in (1.0, 0.5, 0.0):
                s_new = s - back * f
                if s_new < 0.05:
                    continue
                if abs(s_new - L) < 1e-4:
                    done = True                            # already where it should be
                    break
                ne = (round(p[0] + d[0] * s_new, 4), round(p[1] + d[1] * s_new, 4))
                # the new end must stay inside the other trace's copper, so they stay joined
                if not any(seg_point_dist(ne, a_, b_) <= w_ / 2.0 - 0.05 for a_, b_, w_ in others):
                    continue
                pts = list(o.points)
                pts[k] = ne
                o.points = pts
                board.touch()
                moved += 1
                done = True
                break
            if not done:
                continue
    return moved
