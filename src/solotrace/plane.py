# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Back-side ground plane for a double-clad board.

All traces stay on the copper (bottom) side as usual; the component (top) side is left as
one sheet of copper used as ground. Ground leads that pass through the board are soldered on
both sides; "vias" (a hole with a wire soldered both sides) join the bottom ground copper,
the ground fill or ground islands to the plane; every other hole gets a bare ring (antipad)
in the plane so its lead does not short to ground.

Like the ground fill (islands.py) the plane is a *paint order*, never polygon clipping:

1. the plane rectangle (board inset by the edge clearance), copper;
2. antipads round every non-ground hole, and thermal-relief rings round ground leads and
   vias, bare;
3. the relief spokes, copper.

Two ways to make it (see docs/research/back-side-ground-plane.md):

* **Etch or burn the plane** from the exported top-copper layer: it needs front-to-back
  registration within the antipad allowance.
* **Leave the back solid and countersink** every non-ground hole with a 2 to 2.5 mm drill
  tip: no registration at all. ``countersink_list`` gives the holes to countersink.

Why many connections are better than one: two copper sheets joined at a single point form
a resonant cavity (about 700 MHz for a 100 mm FR4 board); joined at every ground pin plus a
loose grid of stitching vias they are a low-impedance mesh, which is how multilayer boards
are built. ``stitch_frequency`` says up to what frequency a spacing keeps the lambda/20 rule.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .geom import Cap, Poly, bbox_gap, shape_dist
from .islands import ground_net

C_LIGHT = 299792458.0
FR4_ER = 4.4


class PlanePlan:
    def __init__(self, rect, cut: List, fat: List, ground: Optional[str]) -> None:
        self.rect = rect
        self.cut = cut          # antipads and relief rings (bare board)
        self.fat = fat          # relief spokes (copper)
        self.ground = ground
        self.antipads = 0
        self.reliefs = 0
        self.solid = 0          # ground leads joined solidly (no relief)

    def rect_poly(self) -> Poly:
        x0, y0, x1, y1 = self.rect
        return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], self.ground, ("plane",))

    def paint(self) -> List[Tuple[object, bool]]:
        out: List[Tuple[object, bool]] = [(self.rect_poly(), True)]
        out += [(s, False) for s in self.cut]
        out += [(s, True) for s in self.fat]
        return out


def holes(board) -> List[Tuple[float, float, float, Optional[str], tuple]]:
    """Every hole as (x, y, drill, net or None, tag): part pads, jumper pads, vias."""
    out = []
    gnd = ground_net(board)
    for ref, pl in board.parts.items():
        d = board.get_def(pl.part_id)
        for pad in d.pads:
            _sh, dr, _c = board.pad_copper(ref, pad.name)
            if dr:
                n = board.net_of("%s.%s" % (ref, pad.name))
                out.append((dr[0], dr[1], dr[2], n.name if n else None, ("pad", ref, pad.name)))
    for ji, j in enumerate(board.jumpers):
        out.append((j.a[0], j.a[1], board.settings.jumper_drill, j.net, ("jpad", ji, 0)))
        out.append((j.b[0], j.b[1], board.settings.jumper_drill, j.net, ("jpad", ji, 1)))
    for vi, v in enumerate(board.vias):
        out.append((v.x, v.y, board.settings.via_drill, gnd, ("via", vi)))
    return out


def plan(board) -> Optional[PlanePlan]:
    """The plane's paint plan, or None when the back-side plane is off. Cached per change."""
    s = board.settings
    if not s.backplane:
        return None
    key = (board.rev, s.backplane_clearance, s.backplane_relief, s.relief_spokes, s.relief_width,
           s.relief_gap, s.relief_diag, s.via_drill, s.via_pad, s.edge_clearance, s.island_net,
           board.width, board.height, tuple(board.nets))
    cache = getattr(board, "_plane_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    gnd = ground_net(board)
    border = s.edge_clearance
    rect = (border, border, board.width - border, board.height - border)
    p = PlanePlan(rect, [], [], gnd)
    hs = holes(board)
    clr = s.clearance
    n_sp = max(1, min(8, int(s.relief_spokes)))
    w = max(0.2, float(s.relief_width))
    ring = max(0.2, float(s.relief_gap))
    base = 45.0 if s.relief_diag else 0.0
    angles = [math.radians(base + 360.0 * k / n_sp) for k in range(n_sp)]
    anti = []           # antipad discs, to keep spokes clear of them
    for x, y, dr, net, tag in hs:
        if gnd is None or net != gnd:
            r = dr / 2.0 + s.backplane_clearance
            a = Cap(x, y, x, y, r, None, ("antipad",) + tuple(tag))
            p.cut.append(a)
            anti.append(a)
            p.antipads += 1
    for x, y, dr, net, tag in hs:
        if gnd is None or net != gnd:
            continue
        solid = False
        if tag[0] == "pad":
            pl = board.parts.get(tag[1])
            solid = bool(pl and pl.solid_ground)
        if not s.backplane_relief or solid:
            p.solid += 1
            continue
        # the lead's "pad" on the plane: a disc the size of the trace-side pad, relieved
        rp = s.via_pad / 2.0 if tag[0] == "via" else max(dr / 2.0 + 0.5, _pad_radius(board, tag))
        spokes = []
        for a in angles:
            dx, dy = math.cos(a), math.sin(a)
            L = rp + ring + w * 0.5 + 0.35
            sp = Cap(x + dx * max(0.0, rp - 0.3), y + dy * max(0.0, rp - 0.3), x + dx * L, y + dy * L,
                     w / 2.0, gnd, ("pspoke",) + tuple(tag))
            if all(shape_dist(sp, o) >= clr - 1e-6 for o in anti if bbox_gap(sp.bbox(), o.bbox()) < clr):
                spokes.append(sp)
        if not spokes:
            p.solid += 1
            continue
        p.cut.append(Cap(x, y, x, y, rp + ring, gnd, ("prelief",) + tuple(tag)))
        p.fat.extend(spokes)
        p.reliefs += 1
    board._plane_cache = (key, p)
    return p


def _pad_radius(board, tag) -> float:
    if tag[0] != "pad":
        return board.settings.jumper_pad / 2.0
    pl = board.parts[tag[1]]
    pd = board.get_def(pl.part_id).pad(tag[2])
    return max(pd.w, pd.h) / 2.0 if pd else 0.9


def countersink_list(board) -> List[Tuple[float, float, float, str]]:
    """Holes to countersink when the back is left solid: (x, y, drill, what). Every hole whose
    lead is not ground. Ground leads are soldered to the plane instead."""
    gnd = ground_net(board)
    out = []
    for x, y, dr, net, tag in holes(board):
        if gnd is not None and net == gnd:
            continue
        what = "%s.%s" % (tag[1], tag[2]) if tag[0] == "pad" else ("jumper #%d" % (tag[1] + 1) if tag[0] == "jpad" else "via")
        out.append((x, y, dr, what))
    return out


def stitch_frequency(spacing_mm: float, er: float = FR4_ER, fraction: float = 20.0) -> float:
    """Highest frequency (Hz) for which this via spacing is lambda/``fraction`` in the board."""
    if spacing_mm <= 0:
        return 0.0
    return C_LIGHT / (fraction * spacing_mm * 1e-3 * math.sqrt(er))


def fmt_freq(f: float) -> str:
    if f >= 1e9:
        return "%.1f GHz" % (f / 1e9)
    if f >= 1e6:
        return "%.0f MHz" % (f / 1e6)
    return "%.0f kHz" % (f / 1e3)


def via_fits(board, x: float, y: float, cu=None, cuts=None, join_pad: bool = False) -> bool:
    """A via here keeps the clearance from other nets' copper, sits inside the board edge, is not
    under a part body (you must solder it on both sides), and touches ground copper or the fill."""
    s = board.settings
    gnd = ground_net(board)
    r = s.via_pad / 2.0
    ec = s.edge_clearance
    if x - r < ec or y - r < ec or x + r > board.width - ec or y + r > board.height - ec:
        return False
    for ref in board.parts:
        x0, y0, x1, y1 = board.court_rect(ref)
        if x0 - r <= x <= x1 + r and y0 - r <= y <= y1 + r:
            return False
    pad = Cap(x, y, x, y, r)
    cu = board.copper() if cu is None else cu
    touches = False
    for o in cu:
        if bbox_gap(pad.bbox(), o.bbox()) > s.clearance:
            continue
        d = shape_dist(pad, o)
        if o.net == gnd:
            if d <= 1e-6:
                touches = True
        elif d < s.clearance:
            return False
    # the plane's antipads must not cut the via's back connection
    for hx, hy, dr, net, _tag in holes(board):
        if net != gnd and math.hypot(hx - x, hy - y) < dr / 2.0 + s.backplane_clearance + r + s.clearance:
            return False
    if s.island_mode:
        from .islands import plan as fill_plan
        fp = fill_plan(board, full=True)
        if fp is not None:
            x0, y0, x1, y1 = fp.rect
            if x - r < x0 or y - r < y0 or x + r > x1 or y + r > y1:
                return False
            cuts = fp.cut if cuts is None else cuts
            for c in cuts:
                if join_pad and c.tag and c.tag[0] == "relief":
                    continue          # a via beside a ground pad may sit inside that pad's relief ring
                if bbox_gap(pad.bbox(), c.bbox()) <= 0 and shape_dist(pad, c) <= 1e-6:
                    return False
            return True
    return touches


def stitch_points(board, spacing: Optional[float] = None) -> List[Tuple[float, float]]:
    """Grid positions for stitching vias that fit (see via_fits), at least the spacing apart
    from each other and from existing vias. Snapped to 0.635 mm."""
    s = board.settings
    sp = float(spacing or s.stitch_spacing)
    if sp < 2.0:
        sp = 2.0
    g = 0.635
    out: List[Tuple[float, float]] = []
    have = [(v.x, v.y) for v in board.vias]
    cu = board.copper()
    cuts = None
    if s.island_mode:
        from .islands import plan as fill_plan
        fp = fill_plan(board, full=True)
        cuts = fp.cut if fp is not None else []
    nx = int(board.width / sp)
    ny = int(board.height / sp)
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = round((board.width - nx * sp) / 2.0 / g + i * sp / g) * g
            y = round((board.height - ny * sp) / 2.0 / g + j * sp / g) * g
            # try the grid point and a few neighbours, so a part body does not lose the whole cell
            for dx, dy in ((0, 0), (g * 2, 0), (-g * 2, 0), (0, g * 2), (0, -g * 2), (g * 4, 0), (-g * 4, 0),
                           (0, g * 4), (0, -g * 4)):
                px, py = x + dx, y + dy
                if any(math.hypot(px - hx, py - hy) < sp * 0.6 for hx, hy in have + out):
                    continue
                if via_fits(board, px, py, cu, cuts):
                    out.append((px, py))
                    break
    return out


def via_at_ground_pins(board) -> List[Tuple[float, float]]:
    """A via beside every ground pin that has no hole (deadbug or SMD pads): at the far end of
    the pad, so the via pad overlaps the pad copper and the lead folds over it."""
    s = board.settings
    gnd = ground_net(board)
    if gnd is None:
        return []
    net = board.nets[gnd]
    out: List[Tuple[float, float]] = []
    cu = board.copper()
    comps = board.components(with_vias=True).get(gnd, [])
    on_plane = set()
    for g in comps:
        if any(q.startswith("via:") or (not q.startswith("via:") and board.pin_drilled(q)) for q in g):
            on_plane.update(q for q in g if not q.startswith("via:"))
    r = s.via_pad / 2.0
    for pin in net.pins:
        if not board.has_pin(pin) or board.pin_drilled(pin) or pin in on_plane:
            continue
        ref, nm = board.split_pin(pin)
        shapes, _d, (cx, cy) = board.pad_copper(ref, nm, gnd)
        best = None
        for sh in shapes:
            bb = sh.bbox()
            cands = []
            if sh.kind == "cap":
                cands = [(sh.x1, sh.y1), (sh.x2, sh.y2)]
            cands += [((bb[0] + bb[2]) / 2, bb[1]), ((bb[0] + bb[2]) / 2, bb[3]),
                      (bb[0], (bb[1] + bb[3]) / 2), (bb[2], (bb[1] + bb[3]) / 2)]
            for px, py in cands:
                # push outward a little so the hole is at the pad's end, pad still overlapping
                vx, vy = px - cx, py - cy
                L = math.hypot(vx, vy)
                if L > 1e-9:
                    px, py = px + vx / L * r * 0.6, py + vy / L * r * 0.6
                px, py = round(px / 0.635) * 0.635, round(py / 0.635) * 0.635
                d = math.hypot(px - cx, py - cy)
                if via_fits(board, px, py, cu, join_pad=True) and (best is None or d > best[0]):
                    best = (d, px, py)
        if best:
            out.append((best[1], best[2]))
            cu = cu + [Cap(best[1], best[2], best[1], best[2], r, gnd, ("via", -1))]
    return out
