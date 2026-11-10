# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Parametric PCB coil: a rectangular spiral on one copper layer.

Give the outer size and EITHER the inductance you want (the generator finds the number of turns and the
track pitch) OR the number of turns (it works out the inductance).

How the inductance is estimated: the spiral is a chain of straight rectangular conductors. Each one has the
self inductance of a straight flat bar (Rosa / Grover) and every pair of parallel bars has a mutual
inductance (Grover), positive when the currents run the same way and negative when they run opposite ways;
bars at right angles do not couple. That is a standard textbook method for a flat coil and it does not need a
fitted table of coefficients. It is checked in tests/test_coil.py against the published spiral formula of
Mohan, Hershenson, Boyd and Lee (IEEE J. Solid-State Circuits 34, 1999) for a square coil. It is an
ESTIMATE for a single layer coil in air: a ground fill, a ground plane, ferrite, metal or a case nearby will
change it. Measure the real coil (LCR meter or NanoVNA) and trim.

Single-sided boards: the inner end of a spiral has to cross the turns, so it is brought out with a wire
wire (pin 2 to pin 3 of the generated part; the part ties them to one net and counts them as joined, so you
solder an insulated wire between them over the turns).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .parts import PadDef, PartDef

MU0 = 4e-7 * math.pi
RHO_CU = 1.68e-8            # ohm metre, copper at 20 C
PAD = 1.8                   # terminal pad diameter, mm
DRILL = 0.9
Point = Tuple[float, float]


def spiral_points(width: float, height: float, turns: int, pitch: float) -> List[Point]:
    """Centre line of an inward rectangular spiral whose outer centre line is ``width`` x ``height`` from (0, 0).

    It starts at the outer corner (0, 0), runs counter-clockwise inwards for ``turns`` turns and ends at the
    point where the next turn would start. Every turn is ``pitch`` smaller on each side."""
    pts: List[Point] = [(0.0, 0.0)]
    xl, yl, xh, yh = 0.0, 0.0, float(width), float(height)
    for _ in range(turns):
        pts += [(xh, yl), (xh, yh), (xl, yh), (xl, yl + pitch)]
        xl, yl, xh, yh = xl + pitch, yl + pitch, xh - pitch, yh - pitch
    return pts


def _f(z: float, d: float) -> float:
    return z * math.asinh(z / d) - math.sqrt(z * z + d * d)


def _mutual(a1: float, a2: float, b1: float, b2: float, d: float) -> float:
    """Mutual inductance (H) of two parallel filaments on axes d apart: A from a1 to a2, B from b1 to b2 (m),
    both taken in the positive direction (Grover)."""
    return MU0 / (4 * math.pi) * (_f(a2 - b1, d) - _f(a2 - b2, d) - _f(a1 - b1, d) + _f(a1 - b2, d))


def _self(l: float, w: float, t: float) -> float:
    """Self inductance (H) of a straight flat bar of length l, width w, thickness t (m) (Rosa)."""
    wt = w + t
    return MU0 / (2 * math.pi) * l * (math.log(2 * l / wt) + 0.50049 + wt / (3 * l))


def inductance(points: List[Point], w_mm: float, t_um: float = 35.0) -> float:
    """Estimated inductance in henries of a conductor through ``points`` (mm), track width ``w_mm``."""
    segs = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if abs(y1 - y2) < 1e-9:
            segs.append(("h", y1 * 1e-3, x1 * 1e-3, x2 * 1e-3))       # axis position, start, end (signed)
        else:
            segs.append(("v", x1 * 1e-3, y1 * 1e-3, y2 * 1e-3))
    w, t = w_mm * 1e-3, t_um * 1e-6
    total = 0.0
    for k in segs:
        total += _self(abs(k[3] - k[2]), w, t)
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if a[0] != b[0]:
                continue                                              # at right angles: no coupling
            d = abs(a[1] - b[1])
            if d < 1e-9:
                continue
            sgn = 1.0 if (a[3] - a[2]) * (b[3] - b[2]) > 0 else -1.0
            lo_a, hi_a = min(a[2], a[3]), max(a[2], a[3])
            lo_b, hi_b = min(b[2], b[3]), max(b[2], b[3])
            total += 2.0 * sgn * _mutual(lo_a, hi_a, lo_b, hi_b, max(d, 0.2223 * (w + t)))
    return total


def length_mm(points: List[Point]) -> float:
    return sum(math.dist(p, q) for p, q in zip(points, points[1:]))


@dataclass
class CoilResult:
    ok: bool
    turns: int = 0
    pitch: float = 0.0          # mm, centre to centre
    gap: float = 0.0            # mm, copper to copper
    width: float = 0.0          # mm, track width
    outer_w: float = 0.0        # mm, outer copper size
    outer_h: float = 0.0
    inductance_uH: float = 0.0
    wanted_uH: float = 0.0
    length_mm: float = 0.0
    r_dc_mohm: float = 0.0
    cap_pF: float = 0.0         # capacitor that resonates the coil at ``freq_MHz``
    freq_MHz: float = 0.0
    messages: List[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.ok:
            return "\n".join(self.messages)
        lines = ["%d turns, track %.2f mm, gap %.2f mm (pitch %.2f mm)" % (self.turns, self.width, self.gap, self.pitch),
                 "outer size %.1f x %.1f mm, track length %.0f mm" % (self.outer_w, self.outer_h, self.length_mm),
                 "estimated inductance %.3f uH%s" % (self.inductance_uH,
                                                    (" (wanted %.3f uH, %+.1f %%)" % (
                                                        self.wanted_uH, 100 * (self.inductance_uH / self.wanted_uH - 1)))
                                                    if self.wanted_uH else ""),
                 "DC resistance about %.0f mOhm" % self.r_dc_mohm]
        if self.cap_pF:
            lines.append("to resonate at %g MHz: about %.0f pF in parallel (the coil's own capacitance and the "
                         "chip's pins are extra)" % (self.freq_MHz, self.cap_pF))
        lines += self.messages
        return "\n".join(lines)


def _inner_ok(w_out: float, h_out: float, n: int, pitch: float, track: float, gap_min: float) -> bool:
    """Is the hollow in the middle big enough for the inner terminal pad and its clearance?"""
    half = min(w_out, h_out) / 2.0 - (n - 1) * pitch - track / 2.0
    return half >= PAD / 2.0 + gap_min


def _eval(outer_w: float, outer_h: float, n: int, pitch: float, track: float, thick_um: float):
    cw, ch = outer_w - track, outer_h - track           # centre-line size
    pts = spiral_points(cw, ch, n, pitch)
    return pts, inductance(pts, track, thick_um)


def design(outer_w: float, outer_h: float, track: float = 0.5, gap_min: float = 0.4,
           turns: Optional[int] = None, want_uH: Optional[float] = None, thick_um: float = 35.0,
           freq_MHz: float = 0.0) -> CoilResult:
    """The coil for an outer area. Give ``turns`` (the inductance is worked out) or ``want_uH`` (the turns and
    the track pitch that come closest are found, never closer than ``gap_min`` between tracks)."""
    r = CoilResult(False, width=track, outer_w=outer_w, outer_h=outer_h, wanted_uH=want_uH or 0.0, freq_MHz=freq_MHz)
    if min(outer_w, outer_h) < 8.0:
        r.messages.append("The coil is too small: the shorter side must be at least 8 mm (room for the inner terminal).")
        return r
    if track <= 0 or gap_min <= 0:
        r.messages.append("Track width and gap must be above zero.")
        return r
    pmin = track + gap_min
    cands = []
    if turns is not None:
        if turns < 1:
            r.messages.append("Turns must be 1 or more.")
            return r
        ns = [int(turns)]
    else:
        if not want_uH or want_uH <= 0:
            r.messages.append("Give the inductance wanted (uH).")
            return r
        ns = list(range(1, 80))
    for n in ns:
        pmax = (min(outer_w, outer_h) - track) / 2.0 / max(1, n) if n > 0 else pmin
        if pmax < pmin - 1e-9:
            continue
        steps = 40
        for k in range(steps + 1):
            p = pmin + (pmax - pmin) * k / steps if steps else pmin
            if not _inner_ok(outer_w - track, outer_h - track, n, p, track, gap_min):
                continue
            pts, L = _eval(outer_w, outer_h, n, p, track, thick_um)
            cands.append((n, p, L, pts))
    if not cands:
        r.messages.append("No coil with these numbers fits in %.1f x %.1f mm. Use fewer turns, a thinner track or "
                          "a smaller gap." % (outer_w, outer_h))
        return r
    if turns is not None:
        # for a fixed number of turns: spread the turns over the area (the widest pitch that still fits)
        n, p, L, pts = max(cands, key=lambda c: c[1])
    else:
        want = want_uH * 1e-6
        best = min(cands, key=lambda c: (abs(c[2] - want) / want, c[0]))
        err = abs(best[2] - want) / want
        # among the coils inside 1 % of the best error prefer the fewest turns, then the widest gap
        near = [c for c in cands if abs(c[2] - want) / want <= max(err, 0.01)]
        n, p, L, pts = min(near, key=lambda c: (c[0], -c[1]))
        if err > 0.05:
            r.messages.append("The closest coil in this area is %+.0f %% off the inductance wanted: %s" % (
                100 * (L / want - 1), "a bigger area, or a thinner track / smaller gap, reaches more inductance."
                if L < want else "a smaller target, or a larger gap, gives less."))
    r.ok = True
    r.turns, r.pitch, r.gap = n, p, p - track
    r.inductance_uH = L * 1e6
    r.length_mm = length_mm(pts)
    r.r_dc_mohm = 1000.0 * RHO_CU * (r.length_mm * 1e-3) / (track * 1e-3 * thick_um * 1e-6)
    if freq_MHz > 0 and L > 0:
        r.cap_pF = 1e12 / ((2 * math.pi * freq_MHz * 1e6) ** 2 * L)
    r.messages.append("An estimate for a single-layer coil in air: a ground fill or plane, metal or ferrite nearby "
                      "changes it. Measure the real coil and trim.")
    return r


def coil_part(res: CoilResult, name: str = "", keepout: float = 2.0, part_id: str = "") -> PartDef:
    """The generated coil as a placeable part: pin 1 the outer end, pin 2 the inner end, pin 3 a landing for
    the wire that brings the inner end out (the part ties pins 2 and 3 into one net)."""
    track = res.width
    cw, ch = res.outer_w - track, res.outer_h - track
    n, p = res.turns, res.pitch
    y0 = 1.6                                    # the keep-out box starts this far above the terminal pads
    lead = y0 + keepout + track / 2.0           # from pin 1 up to where the spiral starts (just inside the box)
    pts = [(x, y + lead) for x, y in spiral_points(cw, ch, n, p)]
    # the inner end: along to the middle of the hollow, then to its centre (inside the last turn)
    ex, ey = pts[-1]
    cx, cy = cw / 2.0, ch / 2.0 + lead
    tail = [(ex, ey), (cx, ey), (cx, cy)] if abs(ey - cy) > 1e-6 else [(ex, ey), (cx, cy)]
    path = pts + tail[1:]
    # origin = pin 1 (outside the box); a short lead brings the outer end of the spiral out to it
    pad3 = (-2.9, 0.0)
    pads = [PadDef("1", 0.0, 0.0, "round", PAD, PAD, DRILL),
            PadDef("2", cx, cy, "round", PAD, PAD, DRILL),
            PadDef("3", pad3[0], pad3[1], "round", PAD, PAD, DRILL)]
    x0, x1 = -track / 2.0 - keepout, cw + track / 2.0 + keepout
    y1 = ch + lead + track / 2.0 + keepout
    ko = (x0, y0, x1, y1)
    court = (min(x0, pad3[0] - PAD / 2.0 - 0.5), -PAD / 2.0 - 0.5, x1, y1)
    pid = part_id or "COIL_%gx%g_%dT_%gmm" % (res.outer_w, res.outer_h, n, track)
    nm = name or "PCB coil %.3g uH (%dT, %g x %g mm)" % (res.inductance_uH, n, res.outer_w, res.outer_h)
    note = ("Generated coil, %d turns, track %.2f mm, gap %.2f mm, estimated %.3f uH (single layer in air; "
            "measure it). Pin 1 = outer end, pin 2 = inner end, pin 3 = landing for the wire that carries the inner "
            "end out over the turns; pins 2 and 3 are tied into one net and count as joined: solder an INSULATED wire (enamelled or sleeved) "
            "between them over the turns. No copper or fill inside the keep-out box."
            % (n, track, res.gap, res.inductance_uH))
    outline = [("rect",) + ko, ("line", cx, cy, pad3[0], pad3[1])]
    part = PartDef(pid, nm, "Board", "L", pads, outline, court, "antenna", (0.0, -1.0), note)
    part.strokes = [("*", tuple(path), track), ("1", ((0.0, 0.0), (0.0, lead)), track)]
    part.keepouts = [ko]
    part.ties = [("2", "3")]
    return part


def _num(v: dict, key: str, label: str, default: Optional[float] = None, minimum: Optional[float] = None) -> float:
    raw = str(v.get(key, "")).strip().replace(",", ".")
    if not raw:
        if default is None:
            raise ValueError("Fill in %s." % label)
        return default
    try:
        x = float(raw)
    except ValueError:
        raise ValueError("%s must be a number (you typed %r)." % (label, raw))
    if minimum is not None and x < minimum:
        raise ValueError("%s must be at least %g." % (label, minimum))
    return x


def design_from_values(v: dict) -> CoilResult:
    """The same coil designer for both user interfaces. ``v['mode']`` is "uh" (area + inductance wanted ->
    turns found) or "turns" (area + turns wanted -> inductance worked out). Bad numbers raise ValueError with
    a sentence meant for the person."""
    w = _num(v, "width", "The coil width", minimum=1.0)
    h = _num(v, "height", "The coil height", minimum=1.0)
    track = _num(v, "track", "The track width", 0.5, 0.1)
    gap = _num(v, "gap", "The smallest gap", 0.4, 0.1)
    thick = _num(v, "thick", "The copper thickness (um)", 35.0, 5.0)
    freq = _num(v, "freq", "The frequency (MHz)", 0.0, 0.0)
    if str(v.get("mode", "uh")) == "turns":
        n = _num(v, "turns", "The number of turns", minimum=1.0)
        if abs(n - round(n)) > 1e-9:
            raise ValueError("The number of turns must be a whole number.")
        return design(w, h, track, gap, turns=int(round(n)), thick_um=thick, freq_MHz=freq)
    want = _num(v, "uh", "The inductance wanted (uH)", minimum=0.001)
    return design(w, h, track, gap, want_uH=want, thick_um=thick, freq_MHz=freq)
