# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""PCB trace antennas with their copper keep-outs, generated from the wavelength.

These are STARTING POINTS, not tuned designs. The trace length is the quarter wavelength worked out with the
usual rule of thumb for a trace on FR4 (effective permittivity (er + 1) / 2 = 2.7 for er = 4.4), plus a trimming
tail (10 % more copper than the formula) with a silk tick every 2 mm, so you can measure the antenna (a NanoVNA is
enough) and scratch the copper back from the tip until it is best at your frequency. Nothing here is from a
manufacturer's drawing: the published designs (TI AN043, DN007, DN024) are tuned for their own board and their
layout drawings are not reproduced; their sizes are listed in docs/research/pcb-antennas.md for comparison.

A monopole needs a ground to work against: put the board's ground copper (or the ground fill) next to the two
ground pads, below the feed. The keep-out above it is where no copper, fill or back-side plane may go.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .parts import PadDef, PartDef

C_LIGHT = 299792458.0
ER_FR4 = 4.4
EPS_EFF = (ER_FR4 + 1.0) / 2.0          # rule of thumb for a trace on FR4 with air above and nothing under it
TRACK = 1.0                              # mm
PITCH = 3.0                              # mm, centre to centre of the meander runs
STUB = 3.0                               # mm from the feed pad to the first run
TRIM = 0.10                              # extra length for trimming
BANDS = {                                # id, MHz, what uses it (common names; not a list of what a given module uses)
    "315": (315.0, "315 MHz ASK key fobs and remotes (US)", 26.0),
    "433": (433.92, "433.92 MHz ASK / FSK modules, key fobs, remote sockets (EU ISM)", 24.0),
    "868": (868.0, "868 MHz LoRa / sub-GHz radios (EU)", 16.0),
    "915": (915.0, "915 MHz LoRa / sub-GHz radios (US, AU)", 16.0),
    "2G4": (2450.0, "2.4 GHz WiFi / Bluetooth / Zigbee / nRF24 (ISM band, centre 2450 MHz)", 6.0),
}


def quarter_wave_mm(f_mhz: float, eps_eff: float = EPS_EFF) -> float:
    """Quarter wavelength in a trace, mm."""
    return C_LIGHT / (f_mhz * 1e6) / math.sqrt(eps_eff) / 4.0 * 1000.0


def free_quarter_wave_mm(f_mhz: float) -> float:
    return C_LIGHT / (f_mhz * 1e6) / 4.0 * 1000.0


def meander_path(total: float, run: float, pitch: float = PITCH, stub: float = STUB) -> List[Tuple[float, float]]:
    """From the feed (0, 0): a stub up, then runs left and right a ``pitch`` apart, ``total`` mm of copper."""
    pts = [(0.0, 0.0), (0.0, stub)]
    left = total - stub
    x, y, d = 0.0, stub, 1.0
    while left > 1e-9:
        step = min(run, left)
        x += d * step
        pts.append((x, y))
        left -= step
        if left <= 1e-9:
            break
        up = min(pitch, left)
        y += up
        pts.append((x, y))
        left -= up
        d = -d
    return pts


def _ticks(path: List[Tuple[float, float]], tail: float, every: float = 2.0, half: float = 1.6) -> List[tuple]:
    """Silk ticks across the copper at 0, 2, 4 ... mm back from the tip (the formula length is ``tail`` back)."""
    segs = []
    for a, b in zip(path, path[1:]):
        segs.append((a, b, math.dist(a, b)))
    out = []
    pos = 0.0
    marks = [k * every for k in range(0, int(tail // every) + 1)]
    if not marks or abs(marks[-1] - tail) > 1e-6:
        marks.append(tail)
    for m in marks:
        pos = m
        for a, b, l in reversed(segs):
            if pos <= l + 1e-9:
                t = 1.0 - pos / l if l > 0 else 0.0
                px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                ux, uy = (b[0] - a[0]) / l, (b[1] - a[1]) / l
                h = half * (1.4 if abs(m - tail) < 1e-6 else 1.0)
                out.append(("line", px - uy * h, py + ux * h, px + uy * h, py - ux * h))
                break
            pos -= l
    return out


def meander_antenna(key: str) -> PartDef:
    f, uses, run = BANDS[key]
    nominal = quarter_wave_mm(f)
    total = nominal * (1.0 + TRIM)
    path = meander_path(total, run)
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    xmin, xmax, ymax = min(xs), max(xs), max(ys)
    margin = 5.0 if f < 1000 else 3.0
    ko = (xmin - margin, 2.0, xmax + margin, ymax + margin)
    pads = [PadDef("1", 0.0, 0.0, "round", 2.0, 2.0, 1.0),
            PadDef("2", -5.08, 0.0, "round", 2.0, 2.0, 1.0), PadDef("3", 5.08, 0.0, "round", 2.0, 2.0, 1.0)]
    court = (min(ko[0], -6.2), -1.2, max(ko[2], 6.2), ko[3])
    outline = [("rect", *ko)] + _ticks(path, total - nominal)
    mhz = "%g" % f
    name = "Meander monopole antenna %s MHz (%.0f x %.0f mm, keep-out %.0f x %.0f)" % (
        mhz, xmax - xmin, ymax, ko[2] - ko[0], ko[3] - ko[1])
    note = ("PCB trace antenna for %s. A STARTING POINT: %.0f mm of 1 mm copper (quarter wave %.0f mm from the FR4 rule of "
            "thumb, effective permittivity %.1f, plus %.0f %% to trim). Pin 1 = feed (the radio's RF pin, through any "
            "matching parts), pins 2 and 3 = ground: put ground copper or the ground fill beside them, never above the feed. "
            "Silk ticks every 2 mm from the tip; the longer tick is the formula length. Measure with a NanoVNA and scratch "
            "the copper back from the tip until it is best at your frequency; if it resonates too high add copper instead. "
            "The box is a keep-out: no copper, fill or back-side plane inside it. Untested on a real board."
            % (uses, total, nominal, EPS_EFF, TRIM * 100))
    part = PartDef("ANT_MEANDER_%s" % key, name, "Board", "ANT", pads, outline, court, "antenna", (0.0, -1.0), note)
    part.strokes = [("1", tuple(path), TRACK)]
    part.keepouts = [ko]
    return part


def wire_whip(key: str) -> PartDef:
    f, uses, _run = BANDS[key]
    q = free_quarter_wave_mm(f)
    pads = [PadDef("1", 0.0, 0.0, "round", 2.2, 2.2, 1.1), PadDef("2", 5.08, 0.0, "round", 2.2, 2.2, 1.1)]
    court = (-1.8, -1.8, 6.9, 1.8)
    name = "Wire whip antenna %s MHz: cut a %.0f mm wire" % ("%g" % f, q)
    note = ("A straight quarter-wave wire for %s: solder one end into pin 1 (the radio's RF pin, through any matching parts) "
            "and stand it up straight, clear of metal. Quarter wavelength in free air = %.1f mm; a common rule of thumb "
            "is to cut it about 5 %% shorter (%.0f mm) and trim while measuring. Pin 2 = ground (put the board's ground "
            "copper next to it). The wire is the part in the parts list."
            % (uses, q, q * 0.95))
    return PartDef("ANT_WIRE_%s" % key, name, "Board", "ANT", pads, [("rect", *court)], court, "part", (0.0, -1.0), note)


def keepout_box(w: float, h: float) -> PartDef:
    """A bare keep-out rectangle: no copper, fill or plane inside. Mark the antenna end of a module with it."""
    ko = (0.0, 0.0, float(w), float(h))
    name = "RF keep-out box %g x %g mm (no copper, fill or plane)" % (w, h)
    note = ("Marks an area that must stay bare: no copper of any part, trace, jumper, via or island, and no ground fill "
            "or back-side plane. Use it where a module's own antenna sits (follow the module's datasheet for the size) "
            "or to protect an antenna you drew yourself. It has no pins and is not in the parts list.")
    pid = "ANT_KEEPOUT_%gx%g" % (w, h)
    part = PartDef(pid, name, "Board", "KO", [], [("rect", *ko)], ko, "antenna", (0.0, -1.0), note)
    part.keepouts = [ko]
    return part


def all_parts() -> Dict[str, PartDef]:
    out: Dict[str, PartDef] = {}
    for k in BANDS:
        p = meander_antenna(k)
        out[p.id] = p
    for k in BANDS:
        p = wire_whip(k)
        out[p.id] = p
    for w, h in ((10, 10), (20, 10), (20, 20), (30, 15), (40, 20)):
        p = keepout_box(w, h)
        out[p.id] = p
    return out
