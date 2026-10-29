# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Part definitions: pads, outlines, and how a pad turns into copper.

Pin 1 of every part sits at the part origin (0, 0), like most PCB tools, so the
part snaps to the grid by its first pin. Y points up, so a DIP's pin 1 is the
top-left pad and the rest of the left column runs downwards (negative Y).

Pad styles:
  tht   - normal drilled pad
  dead  - "deadbug": no hole, a longer copper pad that sticks outwards so the
          lead can be bent flat and soldered on the copper surface
  mixed - drilled pad plus the extra deadbug copper tab
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .geom import Cap, Poly, octagon_rect, place_point, place_vec

STYLES = ("tht", "dead", "mixed")
PAD_SHAPES = ("round", "oval", "rect")


@dataclass
class PadDef:
    name: str
    x: float
    y: float
    shape: str = "round"        # round | oval | rect
    w: float = 1.8
    h: float = 1.8
    drill: float = 0.9
    chamfer: float = 0.3        # corner cut for 'rect' pads (no square corners anywhere)

    def to_dict(self) -> dict:
        return {"n": self.name, "x": self.x, "y": self.y, "shape": self.shape,
                "w": self.w, "h": self.h, "drill": self.drill, "chamfer": self.chamfer}

    @staticmethod
    def from_dict(d: dict) -> "PadDef":
        return PadDef(name=str(d["n"]), x=float(d["x"]), y=float(d["y"]),
                      shape=d.get("shape", "round"), w=float(d.get("w", 1.8)),
                      h=float(d.get("h", d.get("w", 1.8))), drill=float(d.get("drill", 0.9)),
                      chamfer=float(d.get("chamfer", 0.3)))


@dataclass
class PartDef:
    id: str
    name: str
    category: str
    prefix: str = "U"
    pads: List[PadDef] = field(default_factory=list)
    # silkscreen / placement outline, part-local coordinates:
    #   ("line", x1, y1, x2, y2)  ("rect", x0, y0, x1, y1)  ("circle", cx, cy, r)
    #   ("arc", cx, cy, r, start_deg, end_deg)   counter-clockwise
    outline: List[tuple] = field(default_factory=list)
    court: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)   # body rectangle x0,y0,x1,y1
    kind: str = "part"          # part | link (wire link) | hole (mounting hole) | pad (solder pad)
    dead_dir: Tuple[float, float] = (0.0, -1.0)   # deadbug direction for pads at the centroid
    note: str = ""

    def centroid(self) -> Tuple[float, float]:
        if not self.pads:
            return (0.0, 0.0)
        return (sum(p.x for p in self.pads) / len(self.pads),
                sum(p.y for p in self.pads) / len(self.pads))

    def pad(self, name: str) -> Optional[PadDef]:
        for p in self.pads:
            if p.name == name:
                return p
        return None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "category": self.category, "prefix": self.prefix,
                "pads": [p.to_dict() for p in self.pads],
                "outline": [list(o) for o in self.outline],
                "court": list(self.court), "kind": self.kind,
                "dead_dir": list(self.dead_dir), "note": self.note}

    @staticmethod
    def from_dict(d: dict) -> "PartDef":
        return PartDef(
            id=d["id"], name=d.get("name", d["id"]), category=d.get("category", "Custom"),
            prefix=d.get("prefix", "U"),
            pads=[PadDef.from_dict(p) for p in d.get("pads", [])],
            outline=[tuple(o) for o in d.get("outline", [])],
            court=tuple(d.get("court", (0, 0, 0, 0))),      # type: ignore[arg-type]
            kind=d.get("kind", "part"),
            dead_dir=tuple(d.get("dead_dir", (0.0, -1.0))),  # type: ignore[arg-type]
            note=d.get("note", ""))


# --------------------------------------------------------------------------
# deadbug geometry
# --------------------------------------------------------------------------
DEAD_EXT = 2.2      # extra copper length beyond the normal pad, mm
DEAD_WIDTH = 1.8    # width of the deadbug pad, mm


def dead_geom(part: PartDef, pad: PadDef, clearance: float = 0.3,
              ext: float = DEAD_EXT, width: float = DEAD_WIDTH) -> Tuple[float, float, float, float]:
    """Deadbug pad as (w, h, dx, dy): size of the oval and offset of its centre from the pad.

    The copper extends away from the part centre so the lead folds outwards. The width
    is clamped so neighbouring deadbug pads keep their clearance.
    """
    cx, cy = part.centroid()
    vx, vy = pad.x - cx, pad.y - cy
    # How many pads share this pad's row (same y) or column (same x)?
    in_row = sum(1 for q in part.pads if abs(q.y - pad.y) < 1e-6)
    in_col = sum(1 for q in part.pads if abs(q.x - pad.x) < 1e-6)
    if in_row >= 3 and in_col < 3:
        # a row of pads: leads must fold across the row, never along it
        horizontal = False
        sgn = vy if abs(vy) > 1e-6 else part.dead_dir[1]
        dx, dy = 0.0, (1.0 if sgn > 0 else -1.0)
    elif in_col >= 3 and in_row < 3:
        horizontal = True
        sgn = vx if abs(vx) > 1e-6 else part.dead_dir[0]
        dx, dy = (1.0 if sgn > 0 else -1.0), 0.0
    elif abs(vx) < 1e-6 and abs(vy) < 1e-6:
        dx, dy = part.dead_dir
        horizontal = abs(dx) > 0.5
    elif abs(vx) >= abs(vy):
        dx, dy = (1.0 if vx > 0 else -1.0), 0.0
        horizontal = True
    else:
        dx, dy = 0.0, (1.0 if vy > 0 else -1.0)
        horizontal = False
    # closest neighbouring pad measured across the outward axis, within reach
    perp_min = 1e9
    for q in part.pads:
        if q is pad:
            continue
        if horizontal:
            along, perp = abs(q.x - pad.x), abs(q.y - pad.y)
        else:
            along, perp = abs(q.y - pad.y), abs(q.x - pad.x)
        if along < ext + 2.0 and perp > 1e-6:
            perp_min = min(perp_min, perp)
    wd = width
    if perp_min < 1e8:
        wd = max(1.0, min(width, perp_min - clearance))
    if horizontal:
        return (pad.w + ext, max(wd, 1.0), dx * ext / 2.0, 0.0)
    return (max(wd, 1.0), pad.h + ext, 0.0, dy * ext / 2.0)


def _shape_from_wh(cx: float, cy: float, w: float, h: float, shape: str, chamfer: float,
                   ox: float, oy: float, rot: int, flip: bool, net, tag):
    """Build a Cap or Poly in board coordinates for a pad of size w x h centred at local (cx,cy)."""
    if shape == "rect":
        pts = octagon_rect(cx, cy, w, h, chamfer)
        pts = [place_point(p, ox, oy, rot, flip) for p in pts]
        return Poly(pts, net, tag)
    if abs(w - h) < 1e-9:
        c = place_point((cx, cy), ox, oy, rot, flip)
        return Cap(c[0], c[1], c[0], c[1], w / 2.0, net, tag)
    if w > h:
        a = place_point((cx - (w - h) / 2.0, cy), ox, oy, rot, flip)
        b = place_point((cx + (w - h) / 2.0, cy), ox, oy, rot, flip)
        return Cap(a[0], a[1], b[0], b[1], h / 2.0, net, tag)
    a = place_point((cx, cy - (h - w) / 2.0), ox, oy, rot, flip)
    b = place_point((cx, cy + (h - w) / 2.0), ox, oy, rot, flip)
    return Cap(a[0], a[1], b[0], b[1], w / 2.0, net, tag)


def pad_copper(part: PartDef, pad: PadDef, style: str, ox: float, oy: float,
               rot: int = 0, flip: bool = False, net: Optional[str] = None,
               tag: Optional[tuple] = None, clearance: float = 0.3):
    """Copper for one placed pad.

    Returns ``(shapes, drill, centre)`` where ``drill`` is ``(x, y, diameter)`` or None
    for a drill-free deadbug pad and ``centre`` is the board position of the pad's pin.
    """
    centre = place_point((pad.x, pad.y), ox, oy, rot, flip)
    shapes = []
    drill = None
    if style in ("tht", "mixed") or part.kind in ("hole",):
        shapes.append(_shape_from_wh(pad.x, pad.y, pad.w, pad.h, pad.shape, pad.chamfer,
                                     ox, oy, rot, flip, net, tag))
        if pad.drill > 0:
            drill = (centre[0], centre[1], pad.drill)
    if style in ("dead", "mixed") and part.kind not in ("hole",):
        w, h, dx, dy = dead_geom(part, pad, clearance)
        shapes.append(_shape_from_wh(pad.x + dx, pad.y + dy, w, h, "oval", 0.0,
                                     ox, oy, rot, flip, net, tag))
    return shapes, drill, centre
