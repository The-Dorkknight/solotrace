# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Geometry kernel for SoloTrace: points, shapes, distances, 45-degree helpers.

Everything is millimetres, Y pointing up (maths convention). Pure Python,
standard library only, so it runs on a 7th-gen Core i3 without extras.

Two copper shape kinds exist:

* ``Cap``  - a capsule: a segment with a round radius (a round pad is a capsule
  whose two ends coincide, a trace segment is a capsule with ``r = width / 2``).
* ``Poly`` - a simple polygon (chamfered rectangular pads, odd shapes).

A trace drawn with a round aperture is exactly a union of capsules, which is
also exactly how Gerber strokes it, so the model and the output agree.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]

EPS = 1e-9
SQ2 = math.sqrt(2.0)

# Eight compass headings, index 0 = East, counter-clockwise in 45 degree steps.
HEADINGS: List[Tuple[int, int]] = [
    (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1),
]


# --------------------------------------------------------------------------
# basic vector helpers
# --------------------------------------------------------------------------
def dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def mul(a: Point, k: float) -> Point:
    return (a[0] * k, a[1] * k)


def rnd(p: Point, nd: int = 4) -> Point:
    return (round(p[0], nd), round(p[1], nd))


def orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    """True when segments ab and cd cross strictly (shared endpoints do not count)."""
    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    return o1 * o2 < -EPS and o3 * o4 < -EPS


def segments_touch(a: Point, b: Point, c: Point, d: Point) -> bool:
    """True when the segments share at least one point (inclusive)."""
    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 * o2 < -EPS and o3 * o4 < -EPS:
        return True

    def on_seg(p: Point, q: Point, r: Point) -> bool:
        return (min(p[0], q[0]) - 1e-9 <= r[0] <= max(p[0], q[0]) + 1e-9 and
                min(p[1], q[1]) - 1e-9 <= r[1] <= max(p[1], q[1]) + 1e-9)

    if abs(o1) <= 1e-12 and on_seg(a, b, c):
        return True
    if abs(o2) <= 1e-12 and on_seg(a, b, d):
        return True
    if abs(o3) <= 1e-12 and on_seg(c, d, a):
        return True
    if abs(o4) <= 1e-12 and on_seg(c, d, b):
        return True
    return False


def seg_point_dist(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-18:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def seg_seg_dist(a: Point, b: Point, c: Point, d: Point) -> float:
    if segments_touch(a, b, c, d):
        return 0.0
    return min(seg_point_dist(a, c, d), seg_point_dist(b, c, d),
               seg_point_dist(c, a, b), seg_point_dist(d, a, b))


def point_in_poly(p: Point, pts: Sequence[Point]) -> bool:
    x, y = p
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            xc = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xc:
                inside = not inside
        j = i
    return inside


def poly_bbox(pts: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def poly_seg_dist(pts: Sequence[Point], a: Point, b: Point) -> float:
    if point_in_poly(a, pts) or point_in_poly(b, pts):
        return 0.0
    best = 1e18
    n = len(pts)
    for i in range(n):
        d = seg_seg_dist(pts[i], pts[(i + 1) % n], a, b)
        if d < best:
            best = d
            if best <= 0.0:
                return 0.0
    return best


def poly_poly_dist(p: Sequence[Point], q: Sequence[Point]) -> float:
    if point_in_poly(p[0], q) or point_in_poly(q[0], p):
        return 0.0
    best = 1e18
    n, m = len(p), len(q)
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        for j in range(m):
            d = seg_seg_dist(a, b, q[j], q[(j + 1) % m])
            if d < best:
                best = d
                if best <= 0.0:
                    return 0.0
    return best


def rotate_point(p: Point, rot: int) -> Point:
    """Rotate by a multiple of 90 degrees (exact, no float drift)."""
    r = rot % 360
    x, y = p
    if r == 0:
        return (x, y)
    if r == 90:
        return (-y, x)
    if r == 180:
        return (-x, -y)
    if r == 270:
        return (y, -x)
    a = math.radians(rot)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def place_point(p: Point, ox: float, oy: float, rot: int = 0, flip: bool = False) -> Point:
    """Part-local point -> board point: mirror (flip) in X, rotate, translate."""
    x, y = p
    if flip:
        x = -x
    x, y = rotate_point((x, y), rot)
    return (x + ox, y + oy)


def place_vec(v: Point, rot: int = 0, flip: bool = False) -> Point:
    x, y = v
    if flip:
        x = -x
    return rotate_point((x, y), rot)


# --------------------------------------------------------------------------
# shapes
# --------------------------------------------------------------------------
class Cap:
    """Capsule: segment (x1,y1)-(x2,y2) grown by radius r. A circle if the ends coincide."""
    __slots__ = ("x1", "y1", "x2", "y2", "r", "net", "tag")
    kind = "cap"

    def __init__(self, x1: float, y1: float, x2: float, y2: float, r: float,
                 net: Optional[str] = None, tag: Optional[tuple] = None) -> None:
        self.x1, self.y1, self.x2, self.y2, self.r = x1, y1, x2, y2, r
        self.net = net
        self.tag = tag

    def bbox(self) -> Tuple[float, float, float, float]:
        r = self.r
        return (min(self.x1, self.x2) - r, min(self.y1, self.y2) - r,
                max(self.x1, self.x2) + r, max(self.y1, self.y2) + r)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "Cap(%.3f,%.3f,%.3f,%.3f r=%.3f net=%s)" % (self.x1, self.y1, self.x2, self.y2, self.r, self.net)


class Poly:
    """Simple polygon (counter-clockwise or clockwise, both accepted)."""
    __slots__ = ("pts", "net", "tag", "_bb")
    kind = "poly"

    def __init__(self, pts: Sequence[Point], net: Optional[str] = None, tag: Optional[tuple] = None) -> None:
        self.pts = [(float(x), float(y)) for x, y in pts]
        self.net = net
        self.tag = tag
        self._bb = poly_bbox(self.pts)

    def bbox(self) -> Tuple[float, float, float, float]:
        return self._bb


Shape = object  # Cap or Poly


def shape_dist(a, b) -> float:
    """Minimum distance between two shapes; 0 when they touch or overlap."""
    if a.kind == "cap":
        if b.kind == "cap":
            d = seg_seg_dist((a.x1, a.y1), (a.x2, a.y2), (b.x1, b.y1), (b.x2, b.y2)) - a.r - b.r
            return d if d > 0.0 else 0.0
        d = poly_seg_dist(b.pts, (a.x1, a.y1), (a.x2, a.y2)) - a.r
        return d if d > 0.0 else 0.0
    if b.kind == "cap":
        return shape_dist(b, a)
    return poly_poly_dist(a.pts, b.pts)


def bbox_gap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def octagon_rect(cx: float, cy: float, w: float, h: float, ch: float) -> List[Point]:
    """Rectangle with every corner cut at 45 degrees (chamfer ch)."""
    hw, hh = w / 2.0, h / 2.0
    ch = max(0.0, min(ch, hw * 0.9, hh * 0.9))
    if ch <= 0:
        return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    return [
        (cx - hw + ch, cy - hh), (cx + hw - ch, cy - hh),
        (cx + hw, cy - hh + ch), (cx + hw, cy + hh - ch),
        (cx + hw - ch, cy + hh), (cx - hw + ch, cy + hh),
        (cx - hw, cy + hh - ch), (cx - hw, cy - hh + ch),
    ]


# --------------------------------------------------------------------------
# scanline intervals (used by the laser fill engine)
# --------------------------------------------------------------------------
def _convex_poly_interval(pts: Sequence[Point], y: float) -> Optional[Tuple[float, float]]:
    lo, hi = 1e18, -1e18
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 <= y <= y2) or (y2 <= y <= y1):
            if abs(y2 - y1) < 1e-12:
                lo = min(lo, x1, x2)
                hi = max(hi, x1, x2)
            else:
                t = (y - y1) / (y2 - y1)
                x = x1 + t * (x2 - x1)
                lo = min(lo, x)
                hi = max(hi, x)
    if lo > hi:
        return None
    return (lo, hi)


def cap_interval(c: Cap, y: float, grow: float = 0.0) -> Optional[Tuple[float, float]]:
    """x-interval of the capsule (grown by ``grow``) on the horizontal line at y."""
    r = c.r + grow
    if r <= 0:
        return None
    ymin = min(c.y1, c.y2) - r
    ymax = max(c.y1, c.y2) + r
    if y < ymin or y > ymax:
        return None
    lo, hi = 1e18, -1e18
    for (px, py) in ((c.x1, c.y1), (c.x2, c.y2)):
        dy = y - py
        if abs(dy) <= r:
            h = math.sqrt(max(0.0, r * r - dy * dy))
            lo = min(lo, px - h)
            hi = max(hi, px + h)
    dx, dy = c.x2 - c.x1, c.y2 - c.y1
    L = math.hypot(dx, dy)
    if L > 1e-9:
        nx, ny = -dy / L * r, dx / L * r
        quad = [(c.x1 + nx, c.y1 + ny), (c.x2 + nx, c.y2 + ny),
                (c.x2 - nx, c.y2 - ny), (c.x1 - nx, c.y1 - ny)]
        iv = _convex_poly_interval(quad, y)
        if iv is not None:
            lo = min(lo, iv[0])
            hi = max(hi, iv[1])
    if lo > hi:
        return None
    return (lo, hi)


def poly_intervals(pts: Sequence[Point], y: float) -> List[Tuple[float, float]]:
    """Even-odd x-intervals of a polygon on the scanline at y (half-open rule)."""
    xs: List[float] = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 <= y < y2) or (y2 <= y < y1):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    xs.sort()
    out: List[Tuple[float, float]] = []
    for i in range(0, len(xs) - 1, 2):
        out.append((xs[i], xs[i + 1]))
    return out


def shape_intervals(sh, y: float, grow: float = 0.0) -> List[Tuple[float, float]]:
    """Intervals of ``sh`` grown by ``grow`` (a disc offset) on the scanline at y.

    A polygon grown by a disc is the polygon plus a capsule around each edge,
    which is exact for outward offsets, so no polygon clipping is needed.
    ``grow`` may be negative for capsules (shrinks the radius), polygons ignore
    negative values (they are only used for small pad shapes).
    """
    if sh.kind == "cap":
        iv = cap_interval(sh, y, grow)
        return [iv] if iv else []
    out = poly_intervals(sh.pts, y)
    if grow > 0:
        n = len(sh.pts)
        for i in range(n):
            a, b = sh.pts[i], sh.pts[(i + 1) % n]
            iv = cap_interval(Cap(a[0], a[1], b[0], b[1], 0.0), y, grow)
            if iv:
                out.append(iv)
    return out


def merge_intervals(ivs: List[Tuple[float, float]], join: float = 1e-9) -> List[Tuple[float, float]]:
    if not ivs:
        return []
    ivs = sorted(ivs)
    out = [ivs[0]]
    for lo, hi in ivs[1:]:
        if lo <= out[-1][1] + join:
            if hi > out[-1][1]:
                out[-1] = (out[-1][0], hi)
        else:
            out.append((lo, hi))
    return out


def subtract_intervals(base: List[Tuple[float, float]],
                       cut: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """base minus cut; both must be sorted and merged."""
    out: List[Tuple[float, float]] = []
    for lo, hi in base:
        cur = lo
        for clo, chi in cut:
            if chi <= cur:
                continue
            if clo >= hi:
                break
            if clo > cur:
                out.append((cur, clo))
            cur = max(cur, chi)
            if cur >= hi:
                break
        if cur < hi:
            out.append((cur, hi))
    return out


# --------------------------------------------------------------------------
# 45-degree (octilinear) helpers and chamfering
# --------------------------------------------------------------------------
def heading_of(dx: float, dy: float, tol: float = 1e-6) -> Optional[int]:
    """Index 0..7 of an octilinear direction, or None if not a multiple of 45 degrees."""
    if abs(dx) < tol and abs(dy) < tol:
        return None
    ang = math.atan2(dy, dx)
    k = round(ang / (math.pi / 4.0))
    if abs(ang - k * math.pi / 4.0) > 1e-4:
        return None
    return int(k) % 8


def turn_angle(a: Point, b: Point, c: Point) -> float:
    """Turning angle in degrees at b going a->b->c (0 = straight on, 180 = U-turn)."""
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < EPS or n2 < EPS:
        return 0.0
    cosv = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))


def polyline_length(pts: Sequence[Point]) -> float:
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def simplify_polyline(pts: Sequence[Point], tol: float = 1e-6) -> List[Point]:
    """Drop duplicate points and collinear interior points that continue straight on."""
    out: List[Point] = []
    for p in pts:
        if out and dist(out[-1], p) < tol:
            continue
        out.append((p[0], p[1]))
    i = 1
    while i < len(out) - 1:
        if turn_angle(out[i - 1], out[i], out[i + 1]) < 1e-4 and \
                (out[i + 1][0] - out[i][0]) * (out[i][0] - out[i - 1][0]) + \
                (out[i + 1][1] - out[i][1]) * (out[i][1] - out[i - 1][1]) > 0:
            del out[i]
        else:
            i += 1
    return out


def octi_path(p0: Point, p1: Point, diag_first: bool = False) -> List[Point]:
    """Path from p0 to p1 using only 0/45/90 degree moves and at most one 45 degree turn."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ax, ay = abs(dx), abs(dy)
    if ax < 1e-9 or ay < 1e-9 or abs(ax - ay) < 1e-9:
        return [p0, p1]
    m = min(ax, ay)
    sx = 1.0 if dx > 0 else -1.0
    sy = 1.0 if dy > 0 else -1.0
    diag = (sx * m, sy * m)
    if diag_first:
        mid = (p0[0] + diag[0], p0[1] + diag[1])
    else:
        mid = (p1[0] - diag[0], p1[1] - diag[1])
    return [p0, mid, p1]


def chamfer_polyline(pts: Sequence[Point], c: float, min_turn: float = 60.0, keep_ends: float = 0.0) -> List[Point]:
    """Cut every sharp corner (turn >= ``min_turn`` degrees) with a chamfer of leg ``c``.

    A 90 degree turn becomes two 45 degree turns joined by a diagonal. The cut
    length is limited to half of each neighbouring segment so cuts never overlap.
    Gentle 45 degree bends are left alone. The end points never move.
    ``keep_ends`` keeps at least that much straight copper on the first and last
    segment (the pad exits of wide traces) when the corner next to them is cut,
    unless that would leave the corner uncut.
    """
    pts = simplify_polyline(pts)
    if len(pts) < 3:
        return list(pts)
    out: List[Point] = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, d = pts[i - 1], pts[i], pts[i + 1]
        if turn_angle(a, b, d) < min_turn:
            out.append(b)
            continue
        l1 = dist(a, b)
        l2 = dist(b, d)
        # each segment may lose at most half its length to each end, so the
        # cuts of neighbouring corners can never overlap
        lim1, lim2 = 0.5 * l1, 0.5 * l2
        if keep_ends > 0:
            if i - 1 == 0:
                lim1 = l1 - keep_ends        # the first segment only has this one corner
            if i + 1 == len(pts) - 1:
                lim2 = l2 - keep_ends
        t = min(c, lim1, lim2)
        if t < 0.3 and keep_ends > 0:
            t = min(c, 0.5 * l1, 0.5 * l2)      # never leave a sharp corner behind
        if t < 1e-6:
            out.append(b)
            continue
        u1 = ((a[0] - b[0]) / l1, (a[1] - b[1]) / l1)
        u2 = ((d[0] - b[0]) / l2, (d[1] - b[1]) / l2)
        out.append((b[0] + u1[0] * t, b[1] + u1[1] * t))
        out.append((b[0] + u2[0] * t, b[1] + u2[1] * t))
    out.append(pts[-1])
    return simplify_polyline(out)


def max_turn(pts: Sequence[Point]) -> float:
    """Largest turn angle (degrees) along a polyline; 0 for fewer than 3 points."""
    best = 0.0
    for i in range(1, len(pts) - 1):
        t = turn_angle(pts[i - 1], pts[i], pts[i + 1])
        if t > best:
            best = t
    return best
