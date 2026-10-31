# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The board model: parts, nets, traces, jumpers, settings, save/load.

Design view convention: you look at the board from the component side, through
the board, with Y up. The copper is on the far side. Gerber files use the same
view; laser and toner exports mirror it where needed (see render.py / laser.py).
"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from . import library
from .geom import (Cap, Poly, bbox_gap, chamfer_polyline, dist, max_turn, octagon_rect, place_point,
                   seg_point_dist, shape_dist, simplify_polyline)
from .parts import PartDef, STYLES, pad_copper

FORMAT = "solotrace"
FORMAT_VERSION = 1

MIN_WIDTH = 0.4
MAX_WIDTH = 10.0
WIDTH_STEPS = [0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.5, 10.0]

Point = Tuple[float, float]


def clamp_width(w: float) -> float:
    return max(MIN_WIDTH, min(MAX_WIDTH, w))


def snap_width(w: float) -> float:
    """Nearest step of the slider (0.4 ... 10 mm)."""
    w = clamp_width(w)
    return min(WIDTH_STEPS, key=lambda s: abs(s - w))


@dataclass
class Settings:
    clearance: float = 0.3          # copper to copper, mm
    min_trace: float = 0.4
    edge_clearance: float = 0.5     # copper to board edge
    grid: float = 0.635             # routing grid (25 mil) so DIP pins and 2.54 parts line up
    place_grid: float = 1.27
    chamfer_factor: float = 1.5     # chamfer leg = factor * trace width ...
    chamfer_min: float = 0.9        # ... but never less than this
    jumper_pad: float = 2.0
    jumper_drill: float = 1.0
    jumper_min: float = 5.08
    jumper_max: float = 15.24
    jumper_step: float = 2.54
    copper_oz: float = 1.0
    temp_rise: float = 10.0
    allow_jumpers: bool = True      # the router may add wire-link jumpers (each net can also say no)
    keep_out_under_parts: bool = False   # make the router go round part bodies unless there is no other way
    island_mode: bool = False       # deadbug islands: ground fill over the board, every other net an island
    island_net: str = ""            # ground net for island mode ("" = guess: GND, 0V, VSS..., else the biggest net)
    island_gap: float = 0.6         # bare board between an island and the ground fill, mm
    island_grow: float = 1.0        # how much islands are fattened beyond their pads and traces, mm
    island_drop_floating: bool = True   # cut away pieces of fill that no ground pin sits on
    classes: Dict[str, float] = field(default_factory=lambda: {"Signal": 0.8, "Power": 2.0, "High current": 5.0})

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "classes"}
        d["classes"] = dict(self.classes)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Settings":
        s = Settings()
        for k, v in d.items():
            if k == "classes":
                s.classes = {str(a): float(b) for a, b in v.items()}
            elif k in s.__dataclass_fields__:
                setattr(s, k, v)
        return s

    def chamfer_len(self, width: float) -> float:
        return max(self.chamfer_min, self.chamfer_factor * width)


@dataclass
class Placed:
    ref: str
    part_id: str
    x: float
    y: float
    rot: int = 0
    flip: bool = False
    value: str = ""
    style: str = "tht"                       # tht | dead | mixed
    pad_styles: Dict[str, str] = field(default_factory=dict)
    locked: bool = False
    pin_labels: Dict[str, str] = field(default_factory=dict)   # pad name -> function, e.g. "1": "E"

    def to_dict(self) -> dict:
        d = {"ref": self.ref, "part": self.part_id, "x": self.x, "y": self.y, "rot": self.rot,
             "flip": self.flip, "value": self.value, "style": self.style, "locked": self.locked}
        if self.pad_styles:
            d["pad_styles"] = dict(self.pad_styles)
        if self.pin_labels:
            d["pin_labels"] = dict(self.pin_labels)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Placed":
        return Placed(ref=d["ref"], part_id=d["part"], x=float(d["x"]), y=float(d["y"]),
                      rot=int(d.get("rot", 0)), flip=bool(d.get("flip", False)),
                      value=d.get("value", ""), style=d.get("style", "tht"),
                      pad_styles=dict(d.get("pad_styles", {})), locked=bool(d.get("locked", False)),
                      pin_labels={str(k): str(v) for k, v in d.get("pin_labels", {}).items()})


@dataclass
class Net:
    name: str
    cls: str = "Signal"
    pins: List[str] = field(default_factory=list)
    # "rigid" pin pairs (Shift + Wire): the router joins each pair with its own direct trace
    # before anything else, so the rest of the net branches off that trunk
    links: List[List[str]] = field(default_factory=list)
    jumpers_ok: bool = True                  # may the router use wire-link jumpers on this net?


@dataclass
class Trace:
    net: str
    points: List[Point]
    widths: List[float]                      # one width per segment
    manual: bool = False                     # drawn by hand: the autorouter never removes it
    rigid: bool = False                      # routed from a rigid (Shift + Wire) link

    def to_dict(self) -> dict:
        d = {"net": self.net, "points": [[round(x, 4), round(y, 4)] for x, y in self.points],
             "widths": [round(w, 3) for w in self.widths], "manual": self.manual}
        if self.rigid:
            d["rigid"] = True
        return d

    @staticmethod
    def from_dict(d: dict) -> "Trace":
        pts = [(float(x), float(y)) for x, y in d["points"]]
        w = [float(v) for v in d.get("widths", [])]
        if len(w) != max(0, len(pts) - 1):
            w = [w[0] if w else 0.8] * max(0, len(pts) - 1)
        return Trace(d["net"], pts, w, bool(d.get("manual", False)), bool(d.get("rigid", False)))


@dataclass
class Jumper:
    net: str
    a: Point
    b: Point
    auto: bool = True

    def length(self) -> float:
        return dist(self.a, self.b)

    def to_dict(self) -> dict:
        return {"net": self.net, "a": [round(self.a[0], 4), round(self.a[1], 4)],
                "b": [round(self.b[0], 4), round(self.b[1], 4)], "auto": self.auto}

    @staticmethod
    def from_dict(d: dict) -> "Jumper":
        return Jumper(d["net"], (float(d["a"][0]), float(d["a"][1])),
                      (float(d["b"][0]), float(d["b"][1])), bool(d.get("auto", True)))


ISLAND_SHAPES = ("rect", "round")
ISLAND_MIN, ISLAND_MAX = 1.0, 60.0


@dataclass
class Island:
    """A free-standing copper pad (Manhattan / deadbug style): a round or rectangular patch of copper.

    It has no net of its own: it joins whatever net's pin, trace or jumper pad touches it (or
    another island it touches). Rectangles get their corners cut at 45 degrees like every
    other corner on the board; "round" is a circle, or an oval (a stadium) when w and h differ.
    """
    x: float
    y: float
    w: float = 5.08
    h: float = 5.08
    shape: str = "rect"
    corner: float = 0.5

    def copper(self, net: Optional[str] = None, tag: Optional[tuple] = None):
        w = clamp_island(self.w)
        h = clamp_island(self.h)
        if self.shape == "round":
            r = min(w, h) / 2.0
            if w >= h:
                d = (w - h) / 2.0
                return Cap(self.x - d, self.y, self.x + d, self.y, r, net, tag)
            d = (h - w) / 2.0
            return Cap(self.x, self.y - d, self.x, self.y + d, r, net, tag)
        return Poly(octagon_rect(self.x, self.y, w, h, max(0.0, self.corner)), net, tag)

    def bbox(self) -> Tuple[float, float, float, float]:
        return (self.x - self.w / 2, self.y - self.h / 2, self.x + self.w / 2, self.y + self.h / 2)

    def to_dict(self) -> dict:
        return {"x": round(self.x, 4), "y": round(self.y, 4), "w": round(self.w, 4), "h": round(self.h, 4),
                "shape": self.shape, "corner": round(self.corner, 4)}

    @staticmethod
    def from_dict(d: dict) -> "Island":
        shape = d.get("shape", "rect")
        return Island(float(d["x"]), float(d["y"]), clamp_island(float(d.get("w", 5.08))),
                      clamp_island(float(d.get("h", 5.08))), shape if shape in ISLAND_SHAPES else "rect",
                      float(d.get("corner", 0.5)))


def clamp_island(v: float) -> float:
    return max(ISLAND_MIN, min(ISLAND_MAX, float(v)))


class Board:
    def __init__(self, width: float = 100.0, height: float = 80.0, name: str = "Untitled") -> None:
        self.name = name
        self.width = float(width)
        self.height = float(height)
        self.settings = Settings()
        self.parts: Dict[str, Placed] = {}
        self.nets: Dict[str, Net] = {}
        self.traces: List[Trace] = []
        self.jumpers: List[Jumper] = []
        self.islands: List[Island] = []
        self.defs: Dict[str, PartDef] = {}
        self.rev = 0
        self._cu_cache: Optional[tuple] = None
        self._net_counter = 0

    # ------------------------------------------------------------------ basics
    def touch(self) -> None:
        self.rev += 1

    def get_def(self, part_id: str) -> PartDef:
        d = self.defs.get(part_id)
        if d is None:
            d = library.all_parts().get(part_id)
            if d is None:
                raise KeyError("unknown part %s" % part_id)
            self.defs[part_id] = d
        return d

    def next_ref(self, prefix: str) -> str:
        n = 1
        while "%s%d" % (prefix, n) in self.parts:
            n += 1
        return "%s%d" % (prefix, n)

    def add_part(self, part_id: str, x: float, y: float, rot: int = 0, flip: bool = False,
                 ref: Optional[str] = None, value: str = "", style: str = "tht") -> Placed:
        d = self.get_def(part_id)
        ref = ref or self.next_ref(d.prefix)
        if ref in self.parts:
            raise ValueError("reference %s already used" % ref)
        p = Placed(ref, part_id, float(x), float(y), rot % 360, flip, value, style)
        self.parts[ref] = p
        self.touch()
        return p

    def remove_part(self, ref: str) -> None:
        if ref not in self.parts:
            return
        del self.parts[ref]
        prefix = ref + "."
        for n in list(self.nets.values()):
            n.pins = [p for p in n.pins if not p.startswith(prefix)]
            n.links = [lk for lk in n.links if not (lk[0].startswith(prefix) or lk[1].startswith(prefix))]
            if len(n.pins) < 2:
                self.drop_net(n.name)
        self.clear_auto_routes()
        self.touch()

    def move_part(self, ref: str, x: float, y: float) -> None:
        p = self.parts[ref]
        p.x, p.y = float(x), float(y)
        self.touch()

    def rotate_part(self, ref: str, step: int = 90) -> None:
        p = self.parts[ref]
        p.rot = (p.rot + step) % 360
        self.touch()

    def flip_part(self, ref: str) -> None:
        p = self.parts[ref]
        p.flip = not p.flip
        self.touch()

    # -------------------------------------------------------------------- pins
    def split_pin(self, pin: str) -> Tuple[str, str]:
        ref, _, name = pin.rpartition(".")
        return ref, name

    def pad_copper(self, ref: str, padname: str, net: Optional[str] = None):
        pl = self.parts[ref]
        d = self.get_def(pl.part_id)
        pad = d.pad(padname)
        if pad is None:
            raise KeyError("%s has no pad %s" % (ref, padname))
        style = pl.pad_styles.get(padname, pl.style)
        if style not in STYLES:
            style = "tht"
        return pad_copper(d, pad, style, pl.x, pl.y, pl.rot, pl.flip, net, ("pad", ref, padname),
                          self.settings.clearance)

    def pin_labels_of(self, ref: str) -> Dict[str, str]:
        """Pin-function labels to show for a part: the user's, else the ones every part of that
        shape has (diode K/A, electrolytic +/-)."""
        pl = self.parts[ref]
        if pl.pin_labels:
            return {k: v for k, v in pl.pin_labels.items() if k != "_"}
        from .library import default_pin_labels
        return default_pin_labels(self.get_def(pl.part_id))

    def pin_pos(self, pin: str) -> Point:
        ref, name = self.split_pin(pin)
        return self.pad_copper(ref, name)[2]

    def has_pin(self, pin: str) -> bool:
        ref, name = self.split_pin(pin)
        if ref not in self.parts:
            return False
        return self.get_def(self.parts[ref].part_id).pad(name) is not None

    def all_pins(self) -> List[str]:
        out = []
        for ref, pl in self.parts.items():
            for pad in self.get_def(pl.part_id).pads:
                out.append("%s.%s" % (ref, pad.name))
        return out

    def court_rect(self, ref: str) -> Tuple[float, float, float, float]:
        pl = self.parts[ref]
        d = self.get_def(pl.part_id)
        x0, y0, x1, y1 = d.court
        pts = [place_point(p, pl.x, pl.y, pl.rot, pl.flip) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    # -------------------------------------------------------------------- nets
    def net_of(self, pin: str) -> Optional[Net]:
        for n in self.nets.values():
            if pin in n.pins:
                return n
        return None

    def new_net_name(self) -> str:
        while True:
            self._net_counter += 1
            nm = "N%d" % self._net_counter
            if nm not in self.nets:
                return nm

    def drop_net(self, name: str) -> None:
        self.nets.pop(name, None)
        self.traces = [t for t in self.traces if t.net != name]
        self.jumpers = [j for j in self.jumpers if j.net != name]
        self.touch()

    def connect(self, a: str, b: str, net: Optional[str] = None, rigid: bool = False) -> Net:
        """Join two pins into one net, merging nets if both already have one.

        ``rigid``: also remember the pair as a link the router must join directly.
        """
        if a == b:
            raise ValueError("cannot connect a pin to itself")
        for p in (a, b):
            if not self.has_pin(p):
                raise KeyError("no such pin %s" % p)
        na, nb = self.net_of(a), self.net_of(b)
        if na and nb and na is not nb:
            keep, gone = (na, nb)
            if net and nb.name == net:
                keep, gone = nb, na
            elif re.match(r"^N\d+$", na.name) and not re.match(r"^N\d+$", nb.name):
                keep, gone = nb, na
            for t in self.traces:
                if t.net == gone.name:
                    t.net = keep.name
            for j in self.jumpers:
                if j.net == gone.name:
                    j.net = keep.name
            keep.pins.extend(p for p in gone.pins if p not in keep.pins)
            keep.links.extend(lk for lk in gone.links if lk not in keep.links)
            del self.nets[gone.name]
            result = keep
        elif na or nb:
            result = na or nb          # type: ignore[assignment]
            for p in (a, b):
                if p not in result.pins:
                    result.pins.append(p)
        else:
            name = net or self.new_net_name()
            result = self.nets.get(name) or Net(name)
            self.nets[name] = result
            result.pins.extend([a, b])
        if rigid:
            self.set_rigid(a, b, True)
        self.touch()
        return result

    def set_rigid(self, a: str, b: str, on: bool = True) -> None:
        """Mark (or unmark) the pins ``a`` and ``b`` of one net as a rigid, directly routed pair."""
        n = self.net_of(a)
        if n is None or b not in n.pins:
            raise ValueError("%s and %s are not on the same net" % (a, b))
        n.links = [lk for lk in n.links if set(lk) != {a, b}]
        if on:
            n.links.append([a, b])
        self.touch()

    def rigid_links(self, name: str) -> List[List[str]]:
        n = self.nets.get(name)
        if n is None:
            return []
        return [lk for lk in n.links if lk[0] in n.pins and lk[1] in n.pins
                and self.has_pin(lk[0]) and self.has_pin(lk[1])]

    def disconnect(self, pin: str) -> None:
        n = self.net_of(pin)
        if not n:
            return
        n.pins.remove(pin)
        n.links = [lk for lk in n.links if pin not in lk]
        if len(n.pins) < 2:
            self.drop_net(n.name)
        self.clear_auto_routes()
        self.touch()

    def rename_net(self, old: str, new: str) -> None:
        if old == new or old not in self.nets:
            return
        if new in self.nets:
            raise ValueError("net %s already exists" % new)
        n = self.nets.pop(old)
        n.name = new
        self.nets[new] = n
        for t in self.traces:
            if t.net == old:
                t.net = new
        for j in self.jumpers:
            if j.net == old:
                j.net = new
        self.touch()

    def set_net_class(self, name: str, cls: str) -> None:
        if cls not in self.settings.classes:
            raise ValueError("unknown net class %s" % cls)
        self.nets[name].cls = cls
        self.touch()

    def net_width(self, name: str) -> float:
        n = self.nets.get(name)
        if n is None:
            return self.settings.classes.get("Signal", 0.8)
        return clamp_width(self.settings.classes.get(n.cls, 0.8))

    # ------------------------------------------------------------ traces/jumpers
    def add_trace(self, net: str, points: List[Point], width: Optional[float] = None,
                  manual: bool = False, chamfer: bool = True) -> Optional[Trace]:
        """Add a trace. Sharp corners are chamfered, so a 90 degree trace cannot exist."""
        pts = simplify_polyline(points)
        if len(pts) < 2:
            return None
        w = clamp_width(width if width is not None else self.net_width(net))
        if chamfer:
            pts = chamfer_polyline(pts, self.settings.chamfer_len(w))
        t = Trace(net, pts, [w] * (len(pts) - 1), manual)
        self.traces.append(t)
        self.touch()
        return t

    def set_segment_width(self, trace: Trace, seg: int, width: float) -> None:
        trace.widths[seg] = clamp_width(width)
        self.touch()

    def set_trace_width(self, trace: Trace, width: float) -> None:
        trace.widths = [clamp_width(width)] * len(trace.widths)
        self.touch()

    def set_net_trace_width(self, net: str, width: float) -> None:
        for t in self.traces:
            if t.net == net:
                t.widths = [clamp_width(width)] * len(t.widths)
        self.touch()

    def rechamfer(self, trace: Trace) -> None:
        """Re-cut the corners of a trace, keeping the width of the nearest old segment."""
        old_pts, old_w = trace.points, trace.widths
        wmax = max(old_w) if old_w else 0.8
        new_pts = chamfer_polyline(old_pts, self.settings.chamfer_len(wmax))
        new_w = []
        for i in range(len(new_pts) - 1):
            mid = ((new_pts[i][0] + new_pts[i + 1][0]) / 2.0, (new_pts[i][1] + new_pts[i + 1][1]) / 2.0)
            k = min(range(len(old_pts) - 1), key=lambda j: seg_point_dist(mid, old_pts[j], old_pts[j + 1]))
            new_w.append(old_w[k])
        trace.points, trace.widths = new_pts, new_w
        self.touch()

    def clear_auto_routes(self) -> None:
        self.traces = [t for t in self.traces if t.manual]
        self.jumpers = [j for j in self.jumpers if not j.auto]
        self.touch()

    def clear_all_routes(self) -> None:
        self.traces = []
        self.jumpers = []
        self.touch()

    def add_jumper(self, net: str, a: Point, b: Point, auto: bool = True) -> Jumper:
        j = Jumper(net, a, b, auto)
        self.jumpers.append(j)
        self.touch()
        return j

    # ------------------------------------------------------------------ copper
    def copper(self) -> List:
        """All copper shapes with .net and .tag, cached until the board changes."""
        if self._cu_cache and self._cu_cache[0] == self.rev:
            return self._cu_cache[1]
        net_of_pin = {}
        for n in self.nets.values():
            for p in n.pins:
                net_of_pin[p] = n.name
        shapes: List = []
        for ref, pl in self.parts.items():
            d = self.get_def(pl.part_id)
            for pad in d.pads:
                nm = net_of_pin.get("%s.%s" % (ref, pad.name))
                sh, _dr, _c = self.pad_copper(ref, pad.name, nm)
                if nm is None:
                    # unconnected pads still count as copper owned by their own pad
                    for s in sh:
                        s.net = "~%s.%s" % (ref, pad.name)
                shapes.extend(sh)
        for ti, t in enumerate(self.traces):
            for si in range(len(t.points) - 1):
                a, b = t.points[si], t.points[si + 1]
                shapes.append(Cap(a[0], a[1], b[0], b[1], t.widths[si] / 2.0, t.net, ("trace", ti, si)))
        r = self.settings.jumper_pad / 2.0
        for ji, j in enumerate(self.jumpers):
            shapes.append(Cap(j.a[0], j.a[1], j.a[0], j.a[1], r, j.net, ("jpad", ji, 0)))
            shapes.append(Cap(j.b[0], j.b[1], j.b[0], j.b[1], r, j.net, ("jpad", ji, 1)))
        shapes.extend(self._island_copper(shapes))
        self._cu_cache = (self.rev, shapes)
        return shapes

    def _island_copper(self, others: List) -> List:
        """Copper of the islands, each with the net of what touches it (islands that touch share one)."""
        n = len(self.islands)
        if not n:
            return []
        raw = [isl.copper() for isl in self.islands]
        bbs = [s.bbox() for s in raw]
        parent = list(range(n))

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i in range(n):
            for j in range(i + 1, n):
                if bbox_gap(bbs[i], bbs[j]) <= 1e-6 and shape_dist(raw[i], raw[j]) <= 1e-6:
                    parent[find(i)] = find(j)
        nets: Dict[int, set] = {}
        for i in range(n):
            for o in others:
                if o.net and bbox_gap(bbs[i], o.bbox()) <= 1e-6 and shape_dist(raw[i], o) <= 1e-6:
                    nets.setdefault(find(i), set()).add(o.net)
        out = []
        for i in range(n):
            ns = nets.get(find(i), set())
            real = sorted(x for x in ns if not x.startswith("~"))
            loose = sorted(ns - set(real))
            net = real[0] if real else (loose[0] if loose else "~island%d" % find(i))
            out.append(self.islands[i].copper(net, ("isl", i)))
        return out

    def island_net(self, i: int) -> Optional[str]:
        """The net island i belongs to (None when nothing real touches it)."""
        for s in self.copper():
            if s.tag and s.tag[0] == "isl" and s.tag[1] == i:
                return None if (s.net or "~").startswith("~") else s.net
        return None

    def drills(self) -> List[Tuple[float, float, float]]:
        out = []
        for ref, pl in self.parts.items():
            d = self.get_def(pl.part_id)
            for pad in d.pads:
                _sh, dr, _c = self.pad_copper(ref, pad.name)
                if dr:
                    out.append(dr)
        for j in self.jumpers:
            out.append((j.a[0], j.a[1], self.settings.jumper_drill))
            out.append((j.b[0], j.b[1], self.settings.jumper_drill))
        return out

    # ------------------------------------------------------------ connectivity
    def components(self) -> Dict[str, List[List[str]]]:
        """For every net, the groups of its pins that are already joined by copper."""
        shapes = self.copper()
        by_net: Dict[str, List[int]] = {}
        for i, s in enumerate(shapes):
            if s.net and not s.net.startswith("~"):
                by_net.setdefault(s.net, []).append(i)
        out: Dict[str, List[List[str]]] = {}
        for net, idxs in by_net.items():
            parent = {i: i for i in idxs}

            def find(i: int) -> int:
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            def union(i: int, j: int) -> None:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj

            idxs_sorted = sorted(idxs, key=lambda i: shapes[i].bbox()[0])
            bbs = {i: shapes[i].bbox() for i in idxs}
            for a_pos, i in enumerate(idxs_sorted):
                bi = bbs[i]
                for j in idxs_sorted[a_pos + 1:]:
                    bj = bbs[j]
                    if bj[0] > bi[2] + 1e-6:
                        break
                    if bj[1] > bi[3] + 1e-6 or bj[3] < bi[1] - 1e-6:
                        continue
                    if find(i) != find(j) and shape_dist(shapes[i], shapes[j]) <= 1e-6:
                        union(i, j)
            # a jumper joins its two end pads
            jp: Dict[int, Dict[int, int]] = {}
            for i in idxs:
                tg = shapes[i].tag
                if tg and tg[0] == "jpad":
                    jp.setdefault(tg[1], {})[tg[2]] = i
            for ends in jp.values():
                if 0 in ends and 1 in ends:
                    union(ends[0], ends[1])
            groups: Dict[int, List[str]] = {}
            for i in idxs:
                tg = shapes[i].tag
                if tg and tg[0] == "pad":
                    pin = "%s.%s" % (tg[1], tg[2])
                    root = find(i)
                    if pin not in groups.setdefault(root, []):
                        groups[root].append(pin)
            out[net] = [g for g in groups.values() if g]
        return out

    def airwires(self) -> List[Tuple[str, Point, Point, str, str]]:
        """Straight 'rubber-band' lines for connections that are not yet copper.

        Each item is ``(net, p1, p2, pin1, pin2)``. Uses a minimum spanning tree
        between the groups of already-joined pins.
        """
        st = self.settings
        key = (self.rev, tuple((n, tuple(v.pins), tuple(tuple(lk) for lk in v.links)) for n, v in self.nets.items()),
               st.island_mode, st.island_net, st.island_gap, st.island_grow, st.island_drop_floating,
               st.clearance, st.edge_clearance,
               self.width, self.height)
        cache = getattr(self, "_air_cache", None)
        if cache and cache[0] == key:
            return list(cache[1])
        comps = self.components()
        gnd = None
        if st.island_mode:
            from .islands import ground_net
            gnd = ground_net(self)
        wires = []
        for name, net in self.nets.items():
            groups = comps.get(name, [])
            if name == gnd:
                # in island mode the ground fill joins every ground pin on the same piece of fill
                from .islands import ground_groups
                groups = ground_groups(self, groups)
            joined = {p for g in groups for p in g}
            groups = [list(g) for g in groups] + [[p] for p in net.pins if p not in joined and self.has_pin(p)]
            if len(groups) < 2:
                continue
            pos = {p: self.pin_pos(p) for g in groups for p in g}
            # rigid links are shown as they were drawn, and their groups count as joined
            for la, lb in self.rigid_links(name):
                ga = next((g for g in groups if la in g), None)
                gb = next((g for g in groups if lb in g), None)
                if ga is None or gb is None or ga is gb:
                    continue
                wires.append((name, pos[la], pos[lb], la, lb))
                groups.remove(gb)
                ga.extend(gb)
            if len(groups) < 2:
                continue

            def gdist(g1: List[str], g2: List[str]):
                best = (1e18, "", "")
                for p in g1:
                    for q in g2:
                        d = dist(pos[p], pos[q])
                        if d < best[0]:
                            best = (d, p, q)
                return best

            in_tree = [0]
            rest = list(range(1, len(groups)))
            while rest:
                best = None
                for i in in_tree:
                    for j in rest:
                        d, p, q = gdist(groups[i], groups[j])
                        if best is None or d < best[0]:
                            best = (d, p, q, j)
                assert best is not None
                _d, p, q, j = best
                wires.append((name, pos[p], pos[q], p, q))
                in_tree.append(j)
                rest.remove(j)
        self._air_cache = (key, list(wires))
        return wires

    def unrouted_count(self) -> int:
        return len(self.airwires())

    def is_fully_routed(self) -> bool:
        return bool(self.nets) and self.unrouted_count() == 0

    # --------------------------------------------------------------- save/load
    def to_dict(self) -> dict:
        used = {pl.part_id for pl in self.parts.values()}
        return {
            "format": FORMAT, "version": FORMAT_VERSION, "name": self.name,
            "width": self.width, "height": self.height,
            "settings": self.settings.to_dict(),
            "parts": [self.parts[r].to_dict() for r in sorted(self.parts, key=_ref_key)],
            "nets": [dict({"name": n.name, "class": n.cls, "pins": list(n.pins)},
                          **({"links": [list(lk) for lk in n.links]} if n.links else {}),
                          **({"no_jumpers": True} if not n.jumpers_ok else {}))
                     for n in self.nets.values()],
            "traces": [t.to_dict() for t in self.traces],
            "jumpers": [j.to_dict() for j in self.jumpers],
            "islands": [i.to_dict() for i in self.islands],
            "defs": {pid: self.get_def(pid).to_dict() for pid in sorted(used)},
        }

    @staticmethod
    def from_dict(d: dict) -> "Board":
        if d.get("format") != FORMAT:
            raise ValueError("not a SoloTrace file")
        b = Board(d.get("width", 100.0), d.get("height", 80.0), d.get("name", "Untitled"))
        b.settings = Settings.from_dict(d.get("settings", {}))
        for pid, pd in d.get("defs", {}).items():
            b.defs[pid] = PartDef.from_dict(pd)
        for pd in d.get("parts", []):
            pl = Placed.from_dict(pd)
            b.parts[pl.ref] = pl
        for nd in d.get("nets", []):
            b.nets[nd["name"]] = Net(nd["name"], nd.get("class", "Signal"), list(nd.get("pins", [])),
                                     [list(lk) for lk in nd.get("links", []) if len(lk) == 2],
                                     not nd.get("no_jumpers", False))
        b.traces = [Trace.from_dict(t) for t in d.get("traces", [])]
        b.jumpers = [Jumper.from_dict(j) for j in d.get("jumpers", [])]
        b.islands = [Island.from_dict(i) for i in d.get("islands", [])]
        b._net_counter = max([int(m.group(1)) for n in b.nets for m in [re.match(r"^N(\d+)$", n)] if m] + [0])
        b.touch()
        return b

    def clone(self) -> "Board":
        return Board.from_dict(copy.deepcopy(self.to_dict()))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=1)

    @staticmethod
    def load(path: str) -> "Board":
        with open(path, "r", encoding="utf-8") as fh:
            return Board.from_dict(json.load(fh))

    # ---------------------------------------------------------------- netlist
    def export_netlist(self) -> str:
        lines = ["# SoloTrace netlist", "BOARD %g %g" % (self.width, self.height)]
        for ref in sorted(self.parts, key=_ref_key):
            p = self.parts[ref]
            lines.append("PART %s %s %g %g rot=%d%s%s value=%s" % (
                ref, p.part_id, p.x, p.y, p.rot, " flip" if p.flip else "",
                " style=" + p.style if p.style != "tht" else "", p.value or "-"))
        for n in self.nets.values():
            lines.append("NET %s class=%s : %s" % (n.name, n.cls.replace(" ", "_"), " ".join(n.pins)))
        return "\n".join(lines) + "\n"

    def import_netlist(self, text: str) -> None:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            tok = line.split()
            if tok[0] == "BOARD" and len(tok) >= 3:
                self.width, self.height = float(tok[1]), float(tok[2])
            elif tok[0] == "PART" and len(tok) >= 5:
                kw = {t.split("=")[0]: t.split("=", 1)[1] for t in tok[5:] if "=" in t}
                self.add_part(tok[2], float(tok[3]), float(tok[4]), int(kw.get("rot", 0)),
                              "flip" in tok[5:], ref=tok[1],
                              value="" if kw.get("value", "-") == "-" else kw["value"],
                              style=kw.get("style", "tht"))
            elif tok[0] == "NET":
                head, _, pins = line.partition(":")
                ht = head.split()
                name = ht[1]
                cls = "Signal"
                for t in ht[2:]:
                    if t.startswith("class="):
                        cls = t.split("=", 1)[1].replace("_", " ")
                pl = pins.split()
                if len(pl) < 2:
                    continue
                if cls not in self.settings.classes:
                    cls = "Signal"
                for p in pl[1:]:
                    self.connect(pl[0], p, net=name)
                self.nets[name].cls = cls
        self.touch()


def _ref_key(ref: str):
    m = re.match(r"^([A-Za-z]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


# ----------------------------------------------------------------------------
# helpers used by several modules
# ----------------------------------------------------------------------------
def trace_corner_ok(points: List[Point], limit: float = 46.0) -> bool:
    """True when no corner turns more than ``limit`` degrees (so no 90 degree corner)."""
    return max_turn(points) <= limit


def current_capacity(width_mm: float, oz: float = 1.0, temp_rise: float = 10.0) -> float:
    """Approximate current in amps for an outer-layer trace (IPC-2221 formula).

    A guide only: real boards depend on airflow, nearby copper and the etch quality.
    """
    thick_mil = 1.378 * oz                      # 1 oz copper is about 1.378 mil (35 um)
    area_mil2 = (width_mm / 0.0254) * thick_mil
    return 0.048 * (temp_rise ** 0.44) * (area_mil2 ** 0.725)
