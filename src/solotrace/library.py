# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The built-in part library (full-size through-hole parts only) and user parts.

Every part is generated from a few numbers so the library stays small and
consistent. Pitches, DIP spacing and the TO-220 / TO-92 pin layouts are the
well-known standard ones; body outlines are *approximate* and only there to
help placement. Always hold a real part against a 1:1 print before etching.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from .parts import PadDef, PartDef

CATEGORIES = ["Resistors", "Diodes", "Inductors", "Capacitors", "Transistors & LEDs", "Power semiconductors",
              "ICs (DIP)", "Connectors", "Switches & misc", "Board", "Custom"]


def _rect_outline(x0: float, y0: float, x1: float, y1: float) -> tuple:
    return ("rect", x0, y0, x1, y1)


# --------------------------------------------------------------------------
# generators
# --------------------------------------------------------------------------
def axial(pid: str, name: str, cat: str, prefix: str, pitch: float, body_l: float, body_d: float,
          pad: float = 1.8, drill: float = 0.9, band: bool = False, note: str = "") -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "rect" if band else "round", pad, pad, drill),
            PadDef("2", pitch, 0.0, "round", pad, pad, drill)]
    bx0 = (pitch - body_l) / 2.0
    bx1 = bx0 + body_l
    out = [("line", pad / 2.0, 0.0, bx0, 0.0), ("line", bx1, 0.0, pitch - pad / 2.0, 0.0),
           _rect_outline(bx0, -body_d / 2.0, bx1, body_d / 2.0)]
    if band:
        out.append(("line", bx0 + 1.2, -body_d / 2.0, bx0 + 1.2, body_d / 2.0))
    return PartDef(pid, name, cat, prefix, pads, out, (bx0, -body_d / 2.0, bx1, body_d / 2.0), note=note)


def standing(pid: str, name: str, cat: str, prefix: str, pitch: float, body_d: float,
             pad: float = 1.8, drill: float = 0.9, band: bool = False, note: str = "") -> PartDef:
    """An axial part standing on end: the body sits over pin 1, the top lead bends down to pin 2."""
    pads = [PadDef("1", 0.0, 0.0, "rect" if band else "round", pad, pad, drill),
            PadDef("2", pitch, 0.0, "round", pad, pad, drill)]
    r = body_d / 2.0
    out = [("circle", 0.0, 0.0, r), ("line", r, 0.0, pitch - pad / 2.0, 0.0)]
    if band:
        out.append(("circle", 0.0, 0.0, r * 0.55))
    return PartDef(pid, name, cat, prefix, pads, out, (-r, -r, pitch + pad / 2.0, r),
                   note=note or "Standing (vertical) mounting: the body stands on pin 1, the other lead "
                                "folds back down to pin 2. Saves board space.")


def radial2(pid: str, name: str, cat: str, prefix: str, pitch: float, body_w: float,
            body_d: float, round_body: bool, pad: float = 1.8, drill: float = 0.8,
            polar: bool = False, note: str = "") -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "rect" if polar else "round", pad, pad, drill),
            PadDef("2", pitch, 0.0, "round", pad, pad, drill)]
    cx = pitch / 2.0
    if round_body:
        out = [("circle", cx, 0.0, body_w / 2.0)]
        court = (cx - body_w / 2.0, -body_w / 2.0, cx + body_w / 2.0, body_w / 2.0)
    else:
        out = [_rect_outline(cx - body_w / 2.0, -body_d / 2.0, cx + body_w / 2.0, body_d / 2.0)]
        court = (cx - body_w / 2.0, -body_d / 2.0, cx + body_w / 2.0, body_d / 2.0)
    if polar:   # a little plus sign beside pin 1
        px, py = -pad / 2.0 - 1.0, pad / 2.0 + 0.6
        out += [("line", px - 0.5, py, px + 0.5, py), ("line", px, py - 0.5, px, py + 0.5)]
    return PartDef(pid, name, cat, prefix, pads, out, court, note=note)


def dip(n: int, row: float, pad: float = 1.5, drill: float = 0.8) -> PartDef:
    half = n // 2
    pads: List[PadDef] = []
    for k in range(half):
        pads.append(PadDef(str(k + 1), 0.0, -2.54 * k, "rect" if k == 0 else "round", pad, pad, drill))
    for k in range(half):
        pads.append(PadDef(str(half + k + 1), row, -2.54 * (half - 1 - k), "round", pad, pad, drill))
    body_w = 6.35 if row < 10 else 13.0
    x0 = (row - body_w) / 2.0
    y_top = 1.27
    y_bot = -2.54 * (half - 1) - 1.27
    out = [_rect_outline(x0, y_bot, x0 + body_w, y_top),
           ("circle", row / 2.0, y_top, 0.8),            # pin-1 end notch
           ("circle", x0 + 0.9, y_top - 0.9, 0.3)]       # pin-1 dot
    kind = "narrow" if row < 10 else "wide"
    return PartDef("DIP%d_%s" % (n, "N" if row < 10 else "W"), "DIP-%d %s (%.2f mm rows)" % (n, kind, row),
                   "ICs (DIP)", "U", pads, out, (x0, y_bot, x0 + body_w, y_top),
                   note="Pin 1 is the square pad at the top left; pins run down the left side "
                        "and up the right side, viewed from the component side.")


def header(cols: int, rows: int, pitch: float = 2.54, pad: float = 1.7, drill: float = 1.0) -> PartDef:
    pads: List[PadDef] = []
    idx = 1
    for c in range(cols):
        for r in range(rows):
            pads.append(PadDef(str(idx), c * pitch, -r * pitch, "rect" if idx == 1 else "round", pad, pad, drill))
            idx += 1
    x0, x1 = -pitch / 2.0, (cols - 1) * pitch + pitch / 2.0
    y0, y1 = -(rows - 1) * pitch - pitch / 2.0, pitch / 2.0
    pid = "HDR_%dx%d" % (rows, cols)
    return PartDef(pid, "Pin header %dx%d, 2.54 mm" % (rows, cols), "Connectors", "J", pads,
                   [_rect_outline(x0, y0, x1, y1)], (x0, y0, x1, y1),
                   note="2-row headers number across the columns: 1 top, 2 below it, 3 next top...")


def terminal(pitch: float, n: int, pad: float, drill: float, depth: float = 8.0) -> PartDef:
    pads = [PadDef(str(k + 1), k * pitch, 0.0, "rect" if k == 0 else "round", pad, pad, drill) for k in range(n)]
    x0, x1 = -pitch / 2.0, (n - 1) * pitch + pitch / 2.0
    pid = "TERM_%s_%d" % (("%g" % pitch), n)
    return PartDef(pid, "Screw terminal %d-way, %g mm" % (n, pitch), "Connectors", "J", pads,
                   [_rect_outline(x0, -depth / 2.0, x1, depth / 2.0)], (x0, -depth / 2.0, x1, depth / 2.0))


def jst_xh(n: int) -> PartDef:
    pitch = 2.5
    pads = [PadDef(str(k + 1), k * pitch, 0.0, "rect" if k == 0 else "round", 1.9, 1.9, 1.0) for k in range(n)]
    x0, x1 = -2.5, (n - 1) * pitch + 2.5
    return PartDef("JSTXH_%d" % n, "JST-XH header %d-pin, 2.5 mm" % n, "Connectors", "J", pads,
                   [_rect_outline(x0, -3.4, x1, 3.4)], (x0, -3.4, x1, 3.4))


def to92() -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "rect", 1.6, 1.6, 0.8), PadDef("2", 2.54, 0.0, "round", 1.6, 1.6, 0.8),
            PadDef("3", 5.08, 0.0, "round", 1.6, 1.6, 0.8)]
    # D-shaped body seen from above: the flat face (with the printing) at the bottom, towards
    # you, the round back at the top. About 4.5 mm wide and 3.9 mm deep.
    r, cy, flat = 2.6, 0.4, -0.9
    half = (r * r - (cy - flat) ** 2) ** 0.5
    out = [("line", 2.54 - half, flat, 2.54 + half, flat), ("arc", 2.54, cy, r, -30.0, 210.0)]
    return PartDef("TO92", "Transistor TO-92 (3 pins, 2.54 mm)", "Transistors & LEDs", "Q", pads, out,
                   (2.54 - half, flat, 2.54 + half, cy + r),
                   note="Pins are in order 1-2-3 left to right with the flat face towards you. "
                        "Pin names depend on the part (BC547: C-B-E vs 2N3904: E-B-C), check the datasheet.")


def led(dia: float) -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "rect", 1.8, 1.8, 0.9), PadDef("2", 2.54, 0.0, "round", 1.8, 1.8, 0.9)]
    r = dia / 2.0
    out = [("circle", 1.27, 0.0, r), ("line", 1.27 - r, -r * 0.7, 1.27 - r, r * 0.7)]
    return PartDef("LED%d" % int(dia), "LED %d mm, 2.54 mm pitch" % int(dia), "Transistors & LEDs", "LED",
                   pads, out, (1.27 - r, -r, 1.27 + r, r),
                   note="Pin 1 (square pad, flat side of the lens) is the cathode (-), pin 2 the anode (+).")


def to220(pins: int, heatsink: bool = False) -> PartDef:
    if pins == 2:
        xs = [0.0, 5.08]
        names = ["1", "3"]
    else:
        xs = [0.0, 2.54, 5.08]
        names = ["1", "2", "3"]
    pads = [PadDef(nm, x, 0.0, "rect" if nm == "1" else "oval", 2.0, 2.5, 1.1) for nm, x in zip(names, xs)]
    if pins == 2:
        pads[1].shape = "oval"
    x0, x1 = 2.54 - 5.1, 2.54 + 5.1
    out = [_rect_outline(x0, -1.5, x1, 3.0)]
    y1 = 3.0
    if heatsink:
        out += [("line", x0, 3.0, x0, 17.0), ("line", x1, 3.0, x1, 17.0), ("line", x0, 17.0, x1, 17.0)]
        y1 = 17.0
    pid = "TO220_%d%s" % (pins, "_HS" if heatsink else "")
    nm = "TO-220 %d-pin%s" % (pins, " + heatsink outline" if heatsink else "")
    return PartDef(pid, nm, "Power semiconductors", "Q", pads, out, (x0, -1.5, x1, y1),
                   note="Pins 1-2-3 left to right viewed from the front (printed face). "
                        "Pin 1 is square. Standing upright, tab away from you.")


def to247() -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "rect", 2.8, 2.8, 1.5, 0.4), PadDef("2", 5.45, 0.0, "round", 2.8, 2.8, 1.5),
            PadDef("3", 10.9, 0.0, "round", 2.8, 2.8, 1.5)]
    out = [_rect_outline(-2.2, -1.8, 13.1, 3.4)]
    return PartDef("TO247", "TO-247 / TO-3P (3 pins, 5.45 mm pitch)", "Power semiconductors", "Q", pads, out,
                   (-2.2, -1.8, 13.1, 3.4))


def wire_link(pitch: float) -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "round", 2.0, 2.0, 1.0), PadDef("2", pitch, 0.0, "round", 2.0, 2.0, 1.0)]
    return PartDef("LINK_%g" % pitch, "Wire link %g mm" % pitch, "Board", "W", pads,
                   [("line", 1.0, 0.0, pitch - 1.0, 0.0)], (1.0, -0.4, pitch - 1.0, 0.4), kind="link",
                   note="Bare or insulated wire on the component side that hops over other copper.")


def single_pad(pid: str, name: str, prefix: str, w: float, h: float, drill: float, shape: str,
               kind: str = "pad") -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, shape, w, h, drill)]
    return PartDef(pid, name, "Board", prefix, pads, [], (-w / 2.0, -h / 2.0, w / 2.0, h / 2.0), kind=kind)


def mount_hole(dia: float, ring: float) -> PartDef:
    pads = [PadDef("1", 0.0, 0.0, "round", ring, ring, dia)]
    return PartDef("HOLE_M%g" % (dia - 0.2), "Mounting hole M%g (%.1f mm drill)" % (dia - 0.2, dia), "Board",
                   "H", pads, [("circle", 0.0, 0.0, ring / 2.0)], (-ring / 2.0, -ring / 2.0, ring / 2.0, ring / 2.0),
                   kind="hole")


# --------------------------------------------------------------------------
# SMD parts (the "SMD" sidebar mode): sourced land patterns, see docs/research/smd-land-patterns.md
# --------------------------------------------------------------------------
def smd(pid: str, name: str, cat: str, prefix: str, pads, body, note: str = "",
        marks=None) -> PartDef:
    """An SMD part from a list of pads (name, cx, cy, w, h) given about the package centre.

    Everything is shifted so pin 1 sits at the part origin, like every other part. ``body``
    is (w, h) of the outline about the package centre; ``marks`` are extra outline items
    (pin-1 dot, polarity band) in package-centre coordinates.
    """
    ox, oy = pads[0][1], pads[0][2]
    pd = [PadDef(nm, cx - ox, cy - oy, "rect", w, h, 0.0, min(0.25, w * 0.2, h * 0.2)) for nm, cx, cy, w, h in pads]
    bw, bh = body
    out = [_rect_outline(-bw / 2 - ox, -bh / 2 - oy, bw / 2 - ox, bh / 2 - oy)]
    for m in (marks or []):
        if m[0] == "dot":
            out.append(("circle", m[1] - ox, m[2] - oy, 0.3))
        elif m[0] == "line":
            out.append(("line", m[1] - ox, m[2] - oy, m[3] - ox, m[4] - oy))
    xs = [p.x - p.w / 2 for p in pd] + [p.x + p.w / 2 for p in pd] + [-bw / 2 - ox, bw / 2 - ox]
    ys = [p.y - p.h / 2 for p in pd] + [p.y + p.h / 2 for p in pd] + [-bh / 2 - oy, bh / 2 - oy]
    court = (min(xs), min(ys), max(xs), max(ys))
    return PartDef(pid, name, cat, prefix, pd, out, court, kind="smd",
                   note=(note + " " if note else "") + "SMD: sits on the COPPER side, no holes. Pad sizes from the "
                   "maker's land pattern (see docs/research/smd-land-patterns.md); check against your part.")


def _two_pad(pid, name, cat, prefix, gap, length, width, body, note="", polar=False):
    """Two pads ``gap`` apart, each ``length`` along X and ``width`` across; pin 1 on the left."""
    c = gap / 2.0 + length / 2.0
    marks = [("line", -body[0] / 2 + 0.5, -body[1] / 2, -body[0] / 2 + 0.5, body[1] / 2)] if polar else None
    return smd(pid, name, cat, prefix, [("1", -c, 0.0, length, width), ("2", c, 0.0, length, width)], body, note, marks)


def _soic(pid: str, name: str, n: int, pad_l: float, pad_w: float, span: float, body_w: float, note: str = "",
          pitch: float = 1.27) -> PartDef:
    half = n // 2
    body_l = pitch * half + 1.0
    pads = []
    for k in range(half):
        y = ((half - 1) / 2.0 - k) * pitch
        pads.append((str(k + 1), -span / 2.0, y, pad_l, pad_w))
    for k in range(half):
        y = (-(half - 1) / 2.0 + k) * pitch
        pads.append((str(half + k + 1), span / 2.0, y, pad_l, pad_w))
    return smd(pid, name, "SMD", "U", pads, (body_w, body_l), note,
               marks=[("dot", -body_w / 2 + 0.7, body_l / 2 - 0.7)])


def _build_smd(add) -> None:
    S = "SMD"
    # chip resistors / capacitors / inductors: Vishay "wave" (roomier) land patterns: G gap, Y length, X width
    for code, metric, g, y, x, bl, bw in (("0603", "1608", 0.65, 1.10, 1.25, 1.55, 0.85),
                                           ("0805", "2012", 0.90, 1.30, 1.60, 2.0, 1.25),
                                           ("1206", "3216", 1.40, 1.40, 1.95, 3.2, 1.6),
                                           ("1210", "3225", 1.80, 1.45, 2.95, 3.2, 2.5),
                                           ("2010", "5025", 3.40, 1.65, 2.85, 5.0, 2.5),
                                           ("2512", "6432", 4.60, 1.60, 3.65, 6.3, 3.15)):
        add(_two_pad("SMD_CHIP_%s" % code, "Chip %s (%s metric) resistor / capacitor / inductor" % (code, metric), S, "R",
                     g, y, x, (bl, bw), "Vishay wave-solder pattern (roomier than reflow); 0603 is the smallest that "
                     "hand soldering and toner transfer manage." if code == "0603" else
                     "Vishay wave-solder pattern (roomier than the reflow one)."))
    # diodes: Diodes Inc package files; pin 1 = cathode (banded end)
    for pid, name, c, L, w, bl, bw, note in (
            ("SMD_D_SMA", "Diode SMA (DO-214AC)", 4.00, 2.50, 1.70, 4.3, 2.6, ""),
            ("SMD_D_SMB", "Diode SMB (DO-214AA)", 4.30, 2.50, 2.30, 3.6, 4.3, ""),
            ("SMD_D_SMC", "Diode SMC (DO-214AB)", 6.90, 2.50, 3.30, 5.9, 6.9, ""),
            ("SMD_D_SOD123", "Diode SOD-123", 3.15, 0.90, 0.95, 2.65, 1.55, "Pad spacing derived from the overall span."),
            ("SMD_D_SOD123F", "Diode SOD-123F / SOD-123FL", 2.86, 1.34, 1.80, 2.7, 1.8, ""),
            ("SMD_D_MELF", "Diode MELF (DO-213AB)", 4.80, 1.50, 2.70, 5.0, 2.5, "Round body: hold it while the first end cools."),
            ("SMD_D_MINIMELF", "Diode MiniMELF (DO-213AA)", 3.50, 1.30, 1.70, 3.5, 1.45,
             "The maker's own figures differ by 0.1 mm between span and gap; the spacing used is the centre-to-centre one.")):
        add(_two_pad(pid, name, S, "D", c - L, L, w, (bl, bw), note + " Pin 1 is the cathode (band).", polar=True))
    # SOT-23 family: TI DBV pattern, 0.6 mm wide pads on 0.95 mm pitch (0.35 mm gap); the Diodes 0.8 mm pads would not keep 0.3 mm
    add(smd("SMD_SOT23", "SOT-23 (3 pins)", S, "Q", [("1", -0.95, -1.3, 0.6, 1.1), ("2", 0.95, -1.3, 0.6, 1.1), ("3", 0.0, 1.3, 0.6, 1.1)],
            (2.9, 1.3), "TI DBV land pattern. Pins 1 and 2 on one side, 3 alone opposite.", marks=[("dot", -1.2, -0.3)]))
    add(smd("SMD_SOT23_5", "SOT-23-5 (SOT-25 / SC-74A)", S, "U",
            [("1", -0.95, -1.3, 0.6, 1.1), ("2", 0.0, -1.3, 0.6, 1.1), ("3", 0.95, -1.3, 0.6, 1.1),
             ("4", 0.95, 1.3, 0.6, 1.1), ("5", -0.95, 1.3, 0.6, 1.1)], (3.0, 1.6), "TI DBV land pattern.", marks=[("dot", -1.3, -0.4)]))
    add(smd("SMD_SOT23_6", "SOT-23-6 (SOT-26)", S, "U",
            [("1", -0.95, -1.3, 0.6, 1.1), ("2", 0.0, -1.3, 0.6, 1.1), ("3", 0.95, -1.3, 0.6, 1.1),
             ("4", 0.95, 1.3, 0.6, 1.1), ("5", 0.0, 1.3, 0.6, 1.1), ("6", -0.95, 1.3, 0.6, 1.1)], (3.0, 1.6),
            "TI DBV land pattern.", marks=[("dot", -1.3, -0.4)]))
    # SOT-223: Diodes pattern; pin 4 is the tab (internally pin 2)
    add(smd("SMD_SOT223", "SOT-223 (3 pins + tab)", S, "U",
            [("1", -2.3, -3.2, 1.2, 1.6), ("2", 0.0, -3.2, 1.2, 1.6), ("3", 2.3, -3.2, 1.2, 1.6), ("4", 0.0, 3.2, 3.3, 1.6)],
            (6.5, 3.5), "Diodes Inc land pattern; pin 4 is the tab, joined to pin 2 inside the part.", marks=[("dot", -2.9, -1.3)]))
    # DPAK / D2PAK: Diodes patterns; the tab is pin 2 (the middle lead is cut off)
    add(smd("SMD_TO252", "TO-252 DPAK (2 leads + tab)", S, "Q",
            [("1", -2.28, -4.70, 1.5, 2.5), ("2", 0.0, 2.20, 7.0, 7.0), ("3", 2.28, -4.70, 1.5, 2.5)], (6.1, 6.6),
            "Diodes Inc pattern (DMN4040SK3 datasheet). The 7 x 7 mm tab pad is pin 2.", marks=[("dot", -2.8, -2.5)]))
    add(smd("SMD_TO263", "TO-263 D2PAK (3 leads + tab)", S, "Q",
            [("1", -2.54, -6.245, 1.1, 3.5), ("2", 0.0, 4.49, 10.41, 7.01), ("3", 2.54, -6.245, 1.1, 3.5), ("4", 0.0, -6.245, 1.1, 3.5)],
            (9.0, 10.2), "Diodes Inc TO263AB pattern (another revision of the same file gives a 9.1 mm long tab and 2.5 mm "
            "leads). Pin 2 is the tab; pin 4 is the middle lead, cut off on 2-lead parts.", marks=[("dot", -3.4, -3.5)]))
    # SOIC: TI D (narrow) and DW (wide) drawings; Microchip SOIJ
    for n in (8, 14, 16):
        add(_soic("SMD_SOIC%d" % n, "SOIC-%d narrow (3.9 mm body)" % n, n, 1.55, 0.60, 5.4, 3.9,
                  "TI D land pattern (1.55 x 0.6 mm pads, 5.4 mm between rows)." +
                  (" The 16-pin drawing itself was not retrieved; the pattern is the D family's." if n == 16 else "")))
    for n in (16, 18, 20, 24, 28):
        add(_soic("SMD_SOIC%dW" % n, "SOIC-%d wide (7.5 mm body)" % n, n, 2.0, 0.60, 9.3, 7.5,
                  "TI DW land pattern (2.0 x 0.6 mm pads, 9.3 mm between rows)." +
                  ("" if n in (16, 20) else " Verified from the 16 and 20 pin drawings; the same pattern is used for this count.")))
    add(_soic("SMD_SOP8_5.3", "SOP-8 'EIAJ' (5.3 mm body, 208 mil)", 8, 1.70, 0.65, 7.3, 5.3,
              "Microchip SOIJ drawing. Not the same as SOIC-8: a 5.3 mm body does not fit the 3.9 mm pattern."))
    # tantalum (KEMET T491, level A = roomiest); pin 1 = anode (+), the banded end
    for case, code, x, y, c, bl, bw in (("A", "3216", 1.35, 2.15, 1.45, 3.2, 1.6), ("B", "3528", 2.35, 2.15, 1.45, 3.5, 2.8),
                                         ("C", "6032", 2.35, 2.65, 2.60, 6.0, 3.2), ("D", "7343", 2.55, 3.75, 2.70, 7.3, 4.3)):
        add(_two_pad("SMD_TANT_%s" % case, "Tantalum case %s (%s)" % (case, code), S, "C", c, y, x, (bl, bw),
                     "KEMET T491 level-A (roomiest) land. Pin 1 is + (the band marks the ANODE on tantalums)."
                     + (" Re-check the D row against the datasheet." if case == "D" else ""), polar=True))
    # SMD aluminium electrolytic (Nichicon recommended lands; the labels X/Y/a were read off a drawing)
    for size, x, y, a, base in (("4x5.4", 1.6, 2.6, 1.0, 4.3), ("5x5.4", 1.6, 3.0, 1.4, 5.3), ("6.3x5.4", 1.6, 3.5, 2.1, 6.6),
                                ("6.3x7.7", 1.6, 3.5, 2.1, 6.6), ("8x6.2", 2.5, 4.0, 2.1, 8.3), ("8x10", 2.5, 3.5, 3.0, 8.3),
                                ("10x10", 2.5, 4.0, 4.0, 10.3)):
        add(_two_pad("SMD_CELEC_%s" % size, "Electrolytic SMD %s mm" % size.replace("x", " x "), S, "C", a, y, x, (base, base),
                     "Nichicon recommended land (reflow). Pin 1 is +; the dark band on the case marks the NEGATIVE lead: "
                     "check your part.", polar=True))
    # inductors: only patterns whose numbers add up (pad + gap + pad = overall)
    add(_two_pad("SMD_L_CDRH104R", "Inductor 10 x 10 (Sumida CDRH104R type)", S, "L", 7.3, 1.6, 3.2, (10.5, 10.3),
                 "Sumida CDRH104R land. Shielded power inductor lands differ between makers: check the datasheet."))
    add(_two_pad("SMD_L_CDRH6D28", "Inductor 7 x 7 (Sumida CDRH6D28 type)", S, "L", 2.0, 2.65, 6.5, (7.0, 7.0),
                 "Sumida CDRH6D28 land; the pad width (6.5) was read off the drawing without a label: check it."))


# --------------------------------------------------------------------------
# the library
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# microcontroller modules, displays, SD card modules (0.7.0)
# --------------------------------------------------------------------------
# Pin names printed on each module, by pad number; shown as pin labels by default.
MODULE_LABELS: Dict[str, List[str]] = {}
MODULE_GROUP = "Modules & displays"


def module(pid: str, name: str, prefix: str, rows, board: Tuple[float, float, float, float], note: str,
           extra: Optional[list] = None, pad: float = 1.7, drill: float = 1.0) -> PartDef:
    """A module on 2.54 mm headers. ``rows`` is a list of ``(x, y_top, dy, dx, labels)``: one row of
    pins starting at (x, y_top) and stepping (dx, dy) per pin, named in that order. Pads are numbered
    in the order the rows are given; pin 1 (the first pin of the first row) is square and the part is
    moved so pin 1 sits at the origin. ``board`` is the module outline in the same coordinates (Y up),
    ``extra`` more outline items (USB socket, antenna, screen area)."""
    pads: List[PadDef] = []
    labels: List[str] = []
    for x, y, dy, dx, names in rows:
        for k, nm in enumerate(names):
            n = len(pads) + 1
            pads.append(PadDef(str(n), x + dx * k, y + dy * k, "rect" if n == 1 else "round", pad, pad, drill))
            labels.append(nm)
    ox, oy = pads[0].x, pads[0].y
    for p in pads:
        p.x, p.y = round(p.x - ox, 4), round(p.y - oy, 4)

    def sh(o):
        if o[0] == "rect":
            return ("rect", o[1] - ox, o[2] - oy, o[3] - ox, o[4] - oy)
        if o[0] == "line":
            return ("line", o[1] - ox, o[2] - oy, o[3] - ox, o[4] - oy)
        if o[0] in ("circle", "arc"):
            return (o[0], o[1] - ox, o[2] - oy) + tuple(o[3:])
        return o
    x0, y0, x1, y1 = board
    court = (round(x0 - ox, 4), round(y0 - oy, 4), round(x1 - ox, 4), round(y1 - oy, 4))
    out = [("rect",) + court] + [sh(o) for o in (extra or [])]
    out.append(("circle", pads[0].x, pads[0].y, pad / 2 + 0.5))       # pin-1 ring on the outline
    MODULE_LABELS[pid] = labels
    return PartDef(pid, name, "Modules", prefix, pads, out, court, note=note)


def _col(x: float, y_top: float, names, up: bool = False):
    """One header column at x, first pin at y_top, running DOWN (or UP), 2.54 mm pitch."""
    return (x, y_top, 2.54 if up else -2.54, 0.0, list(names))


def _usb(cx: float, y_edge: float, w: float = 8.0, out: float = 1.5, down: bool = False) -> tuple:
    """A marker box for the USB socket at a board edge (a reminder of which end is which, not a size)."""
    y1 = y_edge - out if down else y_edge + out
    return ("rect", cx - w / 2, min(y_edge, y1), cx + w / 2, max(y_edge, y1))


_CASTELLATED = (" Castellated: with deadbug pads (Pads of this part > Deadbug) you can solder it flat on the copper, "
                "or Shift+M to mirror it so it sits on the copper side. ")


def _build_modules(add) -> None:
    """Microcontroller modules, OLED displays and SD card modules on 2.54 mm headers.

    Every pin order, row spacing and board size comes from a text source (makers' KiCad / Eagle files,
    datasheets, vendor wikis); see docs/research/mcu-modules.md. Coordinates: top (component) view,
    Y up, USB or antenna end at the top unless the note says otherwise."""
    # --- ESP32-C3 / S3 "postage stamp" boards -------------------------------------------------
    xiao = [_col(0, 0, ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]),
            _col(15.24, -15.24, ["D7", "D8", "D9", "D10", "3V3", "GND", "5V"], up=True)]
    xiao_board = (-1.28, -18.12, 16.52, 2.88)
    gpio = {"C3": "D0=GPIO2 D1=3 D2=4 D3=5 D4/SDA=6 D5/SCL=7 D6/TX=21 D7/RX=20 D8/SCK=8 D9/MISO=9 D10/MOSI=10",
            "S3": "D0=GPIO1 D1=2 D2=3 D3=4 D4/SDA=5 D5/SCL=6 D6/TX=43 D7/RX=44 D8/SCK=7 D9/MISO=8 D10/MOSI=9",
            "RP2040": "D0=GP26 D1=27 D2=28 D3=29 D4/SDA=6 D5/SCL=7 D6/TX=0 D7/RX=1 D8/SCK=2 D9/MISO=4 D10/MOSI=3"}
    for key, chip in (("C3", "ESP32-C3"), ("S3", "ESP32-S3"), ("RP2040", "RP2040")):
        add(module("MOD_XIAO_%s" % key, "Seeed XIAO %s (21 x 17.8 mm)" % chip, "U", xiao, xiao_board,
                   "Seeed's own footprint: 2 x 7 at 2.54 mm, rows 15.24 mm apart, USB-C at the top (shown as a box). "
                   + gpio[key] + "." + _CASTELLATED + "The pads under the board (battery, JTAG) are not included.",
                   [_usb(7.62, 2.88, 9.0)]))
    add(module("MOD_ESP32C3_SUPERMINI", "ESP32-C3 SuperMini (22.5 x 18 mm)", "U",
               [_col(0, 0, ["IO5", "IO6", "IO7", "IO8", "IO9", "IO10", "IO20", "IO21"]),
                _col(15.24, -17.78, ["IO0", "IO1", "IO2", "IO3", "IO4", "3V3", "GND", "5V"], up=True)],
               (-1.38, -20.15, 16.62, 2.37),
               "2 x 8 at 2.54 mm, rows 15.24 mm apart, USB-C at the top. IO20 = RX, IO21 = TX, IO8 = SDA / LED, IO9 = SCL "
               "/ BOOT. Two independent footprints agree on this order; they disagree by about 1 mm on where the pins "
               "sit along the board, so the outline is drawn with the pins centred. One maker's file (Elecrow) shows a "
               "different order and spacing: check your board's print." + _CASTELLATED,
               [_usb(7.62, 2.37, 9.0)]))
    add(module("MOD_ESP32S3_ZERO", "Waveshare ESP32-S3-Zero (23.5 x 18 mm)", "U",
               [_col(0, 0, ["5V", "GND", "3V3", "IO1", "IO2", "IO3", "IO4", "IO5", "IO6"]),
                _col(15.24, -20.32, ["IO7", "IO8", "IO9", "IO10", "IO11", "IO12", "IO13", "RX", "TX"], up=True)],
               (-1.38, -21.91, 16.62, 1.59),
               "2 x 9 castellated pins at 2.54 mm, rows 15.24 mm apart, USB-C at the top. TX = GPIO43, RX = GPIO44. "
               "Pin order from two community footprints (Waveshare only publishes it as a picture); the outline "
               "is from those footprints. Pads under the board are not included." + _CASTELLATED,
               [_usb(7.62, 1.59, 9.0)]))
    # --- RP2040 ------------------------------------------------------------------------------
    add(module("MOD_RP2040_ZERO", "Waveshare RP2040-Zero (23.5 x 18 mm)", "U",
               [_col(0, 0, ["5V", "GND", "3V3", "GP29", "GP28", "GP27", "GP26", "GP15", "GP14"]),
                _col(15.24, 0, ["GP0", "GP1", "GP2", "GP3", "GP4", "GP5", "GP6", "GP7", "GP8"]),
                (2.54, -20.32, 0.0, 2.54, ["GP13", "GP12", "GP11", "GP10", "GP9"])],
               (-1.38, -21.91, 16.62, 1.59),
               "9 + 9 castellated pins down the sides (rows 15.24 mm apart) and 5 along the bottom edge, all 2.54 mm, "
               "USB-C at the top. From two independent community footprints that agree. The 10 pads under the "
               "board (GP16 to GP25) are not included." + _CASTELLATED, [_usb(7.62, 1.59, 9.0)]))
    pico_l = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7", "GP8", "GP9", "GND", "GP10",
              "GP11", "GP12", "GP13", "GND", "GP14", "GP15"]
    pico_r = ["GP16", "GP17", "GND", "GP18", "GP19", "GP20", "GP21", "GND", "GP22", "RUN", "GP26", "GP27", "AGND",
              "GP28", "VREF", "3V3", "3V3EN", "GND", "VSYS", "VBUS"]
    for pid, nm in (("MOD_PICO", "Raspberry Pi Pico (51 x 21 mm)"), ("MOD_PICO_W", "Raspberry Pi Pico W (51 x 21 mm)")):
        add(module(pid, nm, "U", [_col(0, 0, pico_l), _col(17.78, -48.26, pico_r, up=True)],
                   (-1.61, -49.63, 19.39, 1.37),
                   "2 x 20 at 2.54 mm, rows 17.78 mm apart, 1 mm holes (datasheet), USB at the top, pin 1 = GP0 top left. "
                   "The 3-pin SWD header at the bottom edge and the four 2.1 mm mounting holes are not included."
                   + (" The W uses GP23-25 and GP29 inside for the radio; the LED is on the radio chip." if "W" in pid else "")
                   + _CASTELLATED, [_usb(8.89, 1.37, 8.0)]))
    # --- ESP32 dev boards --------------------------------------------------------------------
    add(module("MOD_ESP32_DOIT30", "ESP32 DOIT DevKit V1, 30 pins", "U",
               [_col(0, 0, ["EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12",
                            "IO13", "GND", "VIN"]),
                _col(25.4, -35.56, ["3V3", "GND", "IO15", "IO2", "IO4", "IO16", "IO17", "IO5", "IO18", "IO19", "IO21",
                                    "RX0", "TX0", "IO22", "IO23"], up=True)],
               (-1.40, -44.65, 26.90, 7.86),
               "2 x 15 at 2.54 mm, rows 25.4 mm apart (1 inch: too wide for one breadboard), antenna at the top, USB at "
               "the bottom. VP = GPIO36, VN = GPIO39, TX0 = GPIO1, RX0 = GPIO3, LED on IO2. From one corrected community "
               "footprint; the outline is that footprint's, not a maker's drawing. Keep copper away from under the "
               "antenna (top end).", [_usb(12.7, -44.65, 8.0, down=True)]))
    j2 = ["3V3", "EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12", "GND",
          "IO13", "IO9", "IO10", "IO11", "5V"]
    j3 = ["GND", "IO23", "IO22", "TX", "RX", "IO21", "GND", "IO19", "IO18", "IO5", "IO17", "IO16", "IO4", "IO0", "IO2",
          "IO15", "IO8", "IO7", "IO6"]
    add(module("MOD_ESP32_DEVKITC38", "Espressif ESP32-DevKitC, 38 pins", "U",
               [_col(0, 0, j2), _col(25.4, -45.72, list(reversed(j3)), up=True)],
               (-1.27, -47.01, 26.67, 1.29),
               "2 x 19 at 2.54 mm, rows 25.4 mm apart, board 27.94 mm wide (Espressif's own footprint and drawing), "
               "antenna at the top, USB at the bottom. VP/VN = GPIO36/39. IO6 to IO11 go to the flash chip: do not use "
               "them. The board's length is not in any text source, so the outline stops 1.29 mm past the pins: the "
               "real board is longer at the antenna end. Keep copper away from there."))
    # --- ESP8266 -----------------------------------------------------------------------------
    right = ["D0", "D1", "D2", "D3", "D4", "3V3", "GND", "D5", "D6", "D7", "D8", "RX", "TX", "GND", "3V3"]
    add(module("MOD_NODEMCU_AMICA", "NodeMCU v2 Amica (ESP8266, narrow)", "U",
               [_col(0, 0, ["A0", "RSV", "RSV", "SD3", "SD2", "SD1", "CMD", "SD0", "CLK", "GND", "3V3", "EN", "RST",
                            "GND", "VIN"]),
                _col(22.86, -35.56, list(reversed(right)), up=True)],
               (-1.57, -42.28, 24.43, 6.72),
               "2 x 15 at 2.54 mm, rows 22.86 mm apart (0.9 inch, two text sources), antenna at the top, USB at the "
               "bottom. D0=GPIO16 D1=5 D2=4 D3=0 D4=2 (LED) D5=14 D6=12 D7=13 D8=15. Board about 49 x 26 mm (one "
               "source); the pin order is from one footprint library. The wide LoLin v3 board is a separate part.",
               [_usb(11.43, -42.28, 8.0, down=True)]))
    add(module("MOD_NODEMCU_LOLIN", "NodeMCU v3 LoLin (ESP8266, wide)", "U",
               [_col(0, 0, ["A0", "GND", "VU", "S3", "S2", "S1", "SC", "SO", "SK", "GND", "3V3", "EN", "RST", "GND",
                            "VIN"]),
                _col(27.94, -35.56, list(reversed(right)), up=True)],
               (-1.53, -46.82, 29.47, 10.18),
               "2 x 15 at 2.54 mm, rows 27.94 mm apart (1.1 inch, two sources), antenna at the top, USB at the bottom, "
               "VU = USB 5 V. Board about 58 x 31 mm. Same D pins as the Amica. Pin order from one footprint library.",
               [_usb(13.97, -46.82, 8.0, down=True)]))
    add(module("MOD_WEMOS_D1MINI", "WEMOS / LOLIN D1 mini (ESP8266)", "U",
               [_col(0, 0, ["RST", "A0", "D0", "D5", "D6", "D7", "D8", "3V3"]),
                _col(22.86, -17.78, ["5V", "GND", "D4", "D3", "D2", "D1", "RX", "TX"], up=True)],
               (-1.37, -25.99, 24.23, 8.21),
               "2 x 8 at 2.54 mm, rows 22.86 mm apart, board 34.2 x 25.6 mm, antenna at the top, USB at the bottom "
               "(KiCad's own footprint + WEMOS). D0=GPIO16 D1/SCL=5 D2/SDA=4 D3=0 D4=2 (LED) D5/SCK=14 D6/MISO=12 "
               "D7/MOSI=13 D8/SS=15. Keep copper out of the antenna area (the box at the top).",
               [("rect", 0.0, 1.4, 22.86, 8.2), _usb(11.43, -25.99, 8.0, down=True)]))
    add(module("MOD_ESP01", "ESP-01 (ESP8266, 2 x 4 header)", "U",
               [(0, 0, -2.54, 0.0, ["TX", "EN", "RST", "VCC"]), (2.54, 0, -2.54, 0.0, ["GND", "IO2", "IO0", "RX"])],
               (-1.78, -10.92, 22.86, 3.30),
               "2 x 4 header at one end, rows 2.54 mm apart, antenna at the far (right) end, board 24.6 x 14.2 mm. "
               "VCC is 3.3 V only. EN = CH_PD. From one footprint library; the ESP-01S is believed to be the same but "
               "no source confirmed it. Plugging it in from the copper side (Shift+M) keeps it flat over the board.",
               pad=1.6))
    # --- Arduino -----------------------------------------------------------------------------
    add(module("MOD_ARDUINO_NANO", "Arduino Nano (and clones)", "U",
               [_col(0, 0, ["TX", "RX", "RST", "GND", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11",
                            "D12"]),
                _col(15.24, -35.56, ["D13", "3V3", "AREF", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "5V", "RST",
                                     "GND", "VIN"], up=True)],
               (-1.27, -39.37, 16.51, 3.81),
               "2 x 15 at 2.54 mm, rows 15.24 mm apart (KiCad's own footprint), USB at the BOTTOM (pins D12 / D13 end). "
               "Arduino gives the board as 45 x 18 mm; the outline is KiCad's slightly smaller one.",
               [("rect", 3.81, -41.91, 11.43, -39.37)]))
    pm_l = ["TXO", "RXI", "RST", "GND", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"]
    pm_r = ["D10", "D11", "D12", "D13", "A0", "A1", "A2", "A3", "VCC", "RST", "GND", "RAW"]
    add(module("MOD_PRO_MINI", "Arduino Pro Mini (side pins)", "U",
               [_col(1.27, 29.21, pm_l), _col(16.51, 1.27, pm_r, up=True)], (0, 0, 17.78, 33.02),
               "2 x 12 at 2.54 mm, rows 15.24 mm apart, board 17.8 x 33 mm (SparkFun's own board file), the FTDI end at "
               "the top. A4 / A5 / A6 / A7 sit off the 2.54 mm grid inside the board and are not included. The version "
               "with the FTDI programming header is a separate part. Clone boards: check yours."))
    add(module("MOD_PRO_MINI_FTDI", "Arduino Pro Mini with FTDI header", "U",
               [_col(1.27, 29.21, pm_l), _col(16.51, 1.27, pm_r, up=True),
                (2.54, 31.75, 0.0, 2.54, ["GND", "GND", "VCC", "RXI", "TXO", "DTR"])], (0, 0, 17.78, 33.02),
               "The Pro Mini's two side rows plus the 6-pin FTDI header along the top (GND GND VCC RXI TXO DTR, left "
               "to right), from SparkFun's own board file. Board 17.8 x 33 mm. A4 to A7 (off grid) not included."))
    add(module("MOD_PRO_MICRO", "Arduino Pro Micro (ATmega32U4)", "U",
               [_col(1.27, 29.21, ["TXO", "RXI", "GND", "GND", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"]),
                _col(16.51, 1.27, ["D10", "D16", "D14", "D15", "A0", "A1", "A2", "A3", "VCC", "RST", "GND", "RAW"], up=True)],
               (0, 0, 17.78, 33.02),
               "2 x 12 at 2.54 mm, rows 15.24 mm apart, board 17.8 x 33 mm, USB at the top (SparkFun's own board file "
               "and pin list agree). D2 = SDA, D3 = SCL, D15 = SCK, D14 = MISO, D16 = MOSI.",
               [_usb(8.89, 33.02, 8.0)]))
    # --- displays ----------------------------------------------------------------------------
    add(module("MOD_OLED096_I2C", "OLED 0.96 inch 128x64, I2C, 4 pins", "DS",
               [(0, 0, 0.0, 2.54, ["GND", "VCC", "SCL", "SDA"])], (-9.84, -26.3, 17.46, 1.5),
               "SSD1306 module, board 27.3 x 27.8 mm, 4-pin header centred on the top edge, pins GND VCC SCL SDA "
               "left to right as you look at the screen. Some sellers swap VCC and GND: read the print on yours and "
               "use Pin labels > VCC GND SCL SDA. Mounted screen-up on the component side it is shown as is; to have "
               "the screen face the other way (under the board), Shift+M. The four mounting holes differ between "
               "sellers and are not included.",
               ))
    add(module("MOD_OLED091_I2C", "OLED 0.91 inch 128x32, I2C, 4 pins", "DS",
               [(0, 0, -2.54, 0.0, ["GND", "VCC", "SCL", "SDA"])], (-36.5, -9.81, 1.5, 2.19),
               "SSD1306 module, board 38 x 12 mm, 4-pin header on the right-hand short edge, GND VCC SCL SDA from the "
               "top as you look at the screen (one footprint + the maker's pin table). No mounting holes. Check the "
               "print on yours."))
    add(module("MOD_OLED096_SPI", "OLED 0.96 inch 128x64, SPI, 7 pins", "DS",
               [(0, 0, 0.0, 2.54, ["GND", "VCC", "D0", "D1", "RES", "DC", "CS"])], (-6.03, -26.3, 21.27, 1.5),
               "SSD1306 module, board 27.3 x 27.8 mm, pins GND VCC D0 (SCK) D1 (MOSI) RES DC CS (maker's manual). "
               "Where the header sits is not in any text source: it is drawn centred on the top edge like the I2C "
               "module. Measure yours. Mounting holes not included.",
               ))
    # --- storage -----------------------------------------------------------------------------
    add(module("MOD_MICROSD_SPI", "Micro SD card module, SPI, 6 pins (42 x 24 mm, 5 V)", "J",
               [(5.47, -3.98, 0.0, 2.54, ["CS", "SCK", "MOSI", "MISO", "VCC", "GND"])], (0, -42.0, 24.0, 0),
               "The common blue module with a regulator and level shifter (runs from 5 V), header on the top short "
               "edge: CS SCK MOSI MISO VCC GND left to right. Pin order and size from one parts file; some sellers "
               "print the pins in another order, so read yours (Pin labels lets you type them). Mounting holes not "
               "included."))
    add(module("MOD_MICROSD_SPI_SMALL", "Micro SD card module, SPI, 6 pins (small, 3.3 V)", "J",
               [(0, 0, -2.54, 0.0, ["3V3", "CS", "MOSI", "CLK", "MISO", "GND"])], (-1.27, -15.24, 29.21, 2.54),
               "The small 3.3 V module without a level shifter, header on the left short edge: 3V3 CS MOSI CLK MISO "
               "GND from the top. From one footprint author only: check the print on yours.",
               ))


def _build() -> Dict[str, PartDef]:
    lib: Dict[str, PartDef] = {}

    def add(p: PartDef) -> None:
        lib[p.id] = p

    # resistors (axial)
    for pw, pitch, bl, bd in [("0.25W", 7.62, 6.3, 2.3), ("0.25W", 10.16, 6.3, 2.3), ("0.25W", 12.7, 6.3, 2.3),
                              ("0.5W", 10.16, 9.0, 3.2), ("0.5W", 12.7, 9.0, 3.2),
                              ("1W", 12.7, 11.0, 4.2), ("1W", 15.24, 11.0, 4.2)]:
        add(axial("R_%s_%g" % (pw, pitch), "Resistor %s, %g mm" % (pw.replace("W", " W"), pitch),
                  "Resistors", "R", pitch, bl, bd, 1.8 if pw != "1W" else 2.0, 0.9 if pw != "1W" else 1.1))
    add(axial("R_2W_15.24", "Resistor 2 W, 15.24 mm", "Resistors", "R", 15.24, 12.0, 5.0, 2.4, 1.2))
    add(axial("R_5W_22.86", "Resistor 5 W ceramic, 22.86 mm", "Resistors", "R", 22.86, 17.0, 8.0, 2.6, 1.3))
    # resistors standing on end (vertical mounting)
    add(standing("R_V_0.25W_2.54", "Resistor 0.25 W standing, 2.54 mm", "Resistors", "R", 2.54, 2.5, 1.6, 0.8))
    add(standing("R_V_0.25W_5.08", "Resistor 0.25 W standing, 5.08 mm", "Resistors", "R", 5.08, 2.5, 1.6, 0.8))
    add(standing("R_V_0.5W_5.08", "Resistor 0.5 W standing, 5.08 mm", "Resistors", "R", 5.08, 3.2, 1.8, 0.9))
    add(standing("R_V_1W_5.08", "Resistor 1 W standing, 5.08 mm", "Resistors", "R", 5.08, 4.2, 2.0, 1.1))
    add(standing("D_V_DO35_2.54", "Diode DO-35 standing, 2.54 mm", "Diodes", "D", 2.54, 2.0, 1.6, 0.8, True,
                 note="Standing diode: pin 1 (square pad, under the body) is the cathode; the band is at the bottom."))
    add(standing("D_V_DO41_5.08", "Diode DO-41 standing, 5.08 mm", "Diodes", "D", 5.08, 2.7, 2.0, 1.0, True,
                 note="Standing diode: pin 1 (square pad, under the body) is the cathode; the band is at the bottom."))
    # inductors
    for pitch, bl, bd in ((10.16, 6.5, 3.5), (12.7, 9.0, 4.5), (15.24, 11.0, 5.5)):
        add(axial("L_AX_%g" % pitch, "Inductor axial, %g mm (body about %g mm)" % (pitch, bl), "Inductors", "L",
                  pitch, bl, bd, 2.0, 1.0, note="Generic axial choke. Measure your part's lead spacing."))
    for pitch, dia in ((2.5, 6.0), (5.0, 10.0), (7.5, 13.0)):
        add(radial2("L_RAD_%g" % pitch, "Inductor radial, %g mm pitch (body up to %g mm)" % (pitch, dia),
                    "Inductors", "L", pitch, dia, dia, True, 1.8, 0.9,
                    note="Generic radial (drum core) inductor. Check the pitch on your part."))
    # diodes (axial, pin 1 = cathode with band)
    add(axial("D_DO35_7.62", "Diode DO-35, 7.62 mm", "Diodes", "D", 7.62, 4.2, 2.0, 1.8, 0.9, True))
    add(axial("D_DO35_10.16", "Diode DO-35, 10.16 mm", "Diodes", "D", 10.16, 4.2, 2.0, 1.8, 0.9, True))
    add(axial("D_DO41_10.16", "Diode DO-41 (1N400x), 10.16 mm", "Diodes", "D", 10.16, 5.2, 2.7, 2.0, 1.0, True))
    add(axial("D_DO41_12.7", "Diode DO-41 (1N400x), 12.7 mm", "Diodes", "D", 12.7, 5.2, 2.7, 2.0, 1.0, True))
    add(axial("D_DO201_15.24", "Diode DO-201 (1N540x), 15.24 mm", "Diodes", "D", 15.24, 9.5, 5.3, 2.8, 1.5, True))
    # capacitors
    for p in (2.54, 5.08):
        add(radial2("C_DISC_%g" % p, "Ceramic disc cap, %g mm" % p, "Capacitors", "C", p, p + 2.0, 3.5, False))
    for p, w, d in [(5.0, 7.0, 3.5), (7.5, 10.0, 4.0), (10.0, 13.0, 5.5), (15.0, 18.0, 7.0), (22.5, 26.0, 11.0)]:
        add(radial2("C_FILM_%g" % p, "Film / box cap, %g mm" % p, "Capacitors", "C", p, w, d, False))
    for p, dia in [(2.0, 5.0), (2.5, 6.3), (3.5, 8.0), (5.0, 10.0), (7.5, 16.0)]:
        add(radial2("C_ELEC_%g" % p, "Electrolytic cap, %g mm pitch (body up to %g mm)" % (p, dia),
                    "Capacitors", "C", p, dia, dia, True, 1.6 if p < 3 else 1.8, 0.8, True,
                    note="Pin 1 (square pad) is the positive lead."))
    # transistors, LEDs
    add(to92())
    add(led(3.0))
    add(led(5.0))
    # power
    add(to220(2))
    add(to220(3))
    add(to220(3, True))
    add(to247())
    # DIP
    for n in (4, 6, 8, 14, 16, 18, 20, 24):
        add(dip(n, 7.62))
    add(dip(28, 7.62))
    add(dip(28, 15.24))
    add(dip(40, 15.24))
    # connectors
    for n in (2, 3, 4, 5, 6, 8, 10):
        add(header(n, 1))
    for n in (3, 4, 5, 8):
        add(header(n, 2))
    add(terminal(5.0, 2, 2.6, 1.3))
    add(terminal(5.08, 2, 2.6, 1.3))
    add(terminal(5.08, 3, 2.6, 1.3))
    add(terminal(7.5, 2, 3.2, 1.6, 10.0))
    add(terminal(7.62, 2, 3.2, 1.6, 10.0))
    for n in (2, 3, 4):
        add(jst_xh(n))
    # switches and misc
    pads = [PadDef("1", 0.0, 0.0, "round", 2.0, 2.0, 1.0), PadDef("2", 6.5, 0.0, "round", 2.0, 2.0, 1.0),
            PadDef("3", 0.0, -4.5, "round", 2.0, 2.0, 1.0), PadDef("4", 6.5, -4.5, "round", 2.0, 2.0, 1.0)]
    add(PartDef("SW_TACT_6", "Tactile switch 6 mm (6.5 x 4.5 mm pins)", "Switches & misc", "SW", pads,
                [_rect_outline(0.25, -4.75, 6.25, 0.25), ("circle", 3.25, -2.25, 1.7)], (0.25, -4.75, 6.25, 0.25),
                note="Pins on the same side are joined inside. Check your switch, sizes vary slightly."))
    pads = [PadDef("1", 0.0, 0.0, "round", 1.8, 1.8, 0.9), PadDef("2", 4.88, 0.0, "round", 1.8, 1.8, 0.9)]
    add(PartDef("XTAL_HC49", "Crystal HC-49 (4.88 mm)", "Switches & misc", "X", pads,
                [("rect", -1.0, -2.3, 5.9, 2.3)], (-1.0, -2.3, 5.9, 2.3)))
    pads = [PadDef("1", 0.0, 0.0, "rect", 1.8, 1.8, 1.0), PadDef("2", 2.54, 0.0, "round", 1.8, 1.8, 1.0),
            PadDef("3", 5.08, 0.0, "round", 1.8, 1.8, 1.0)]
    add(PartDef("POT_3_2.54", "Pot / trimmer, 3 pins 2.54 mm inline", "Switches & misc", "RV", pads,
                [("rect", -1.5, -3.5, 6.6, 3.5)], (-1.5, -3.5, 6.6, 3.5),
                note="Generic inline footprint. Many trimmers use other layouts, use the wizard for those."))
    add(PartDef("POT_3_5.08", "Pot / trimmer, 3 pins 5.08 mm inline", "Switches & misc", "RV",
                [PadDef("1", 0.0, 0.0, "rect", 2.0, 2.0, 1.1), PadDef("2", 5.08, 0.0, "round", 2.0, 2.0, 1.1),
                 PadDef("3", 10.16, 0.0, "round", 2.0, 2.0, 1.1)],
                [("rect", -1.8, -4.0, 11.96, 4.0)], (-1.8, -4.0, 11.96, 4.0),
                note="Generic inline layout for larger pots. Measure your pot; panel pots also need mounting lugs."))
    add(PartDef("TRIM_TRI_5.08", "Trimmer, 3 pins in a triangle (5.08 x 2.54 mm)", "Switches & misc", "RV",
                [PadDef("1", 0.0, 0.0, "rect", 1.8, 1.8, 1.0), PadDef("2", 2.54, 2.54, "round", 1.8, 1.8, 1.0),
                 PadDef("3", 5.08, 0.0, "round", 1.8, 1.8, 1.0)],
                [("rect", -1.6, -1.6, 6.68, 4.2), ("circle", 2.54, 1.0, 1.2)], (-1.6, -1.6, 6.68, 4.2),
                note="Generic triangle layout: wiper (pin 2) in the middle. Many trimmers differ; measure yours."))
    # board items
    for pitch in (5.08, 7.62, 10.16, 12.7, 15.24):
        add(wire_link(pitch))
    add(mount_hole(3.2, 6.0))
    add(mount_hole(4.2, 8.0))
    add(single_pad("PAD_2.5", "Solder pad 2.5 mm with hole", "TP", 2.5, 2.5, 1.0, "round"))
    add(single_pad("SURF_3", "Surface pad 3 mm (no hole)", "TP", 3.0, 3.0, 0.0, "round"))
    add(single_pad("SURF_6x3", "Surface pad 6 x 3 mm (no hole)", "TP", 6.0, 3.0, 0.0, "oval"))
    _build_smd(add)
    _build_modules(add)
    return lib


BUILTIN: Dict[str, PartDef] = _build()


# --------------------------------------------------------------------------
# form-factor groups for the parts panel
# --------------------------------------------------------------------------
SMD_GROUP = "SMD"
FORM_GROUPS = ["Chips (DIP)", "Transistors & regulators", "Resistors, diodes & inductors", "Capacitors",
               "LEDs", "Pots, switches & crystals", "Connectors", MODULE_GROUP, "Board bits", SMD_GROUP, "My parts"]
MODULE_SUBS = ["ESP32-C3 / S3 mini (postage stamp)", "ESP32 dev boards", "ESP8266", "RP2040", "Arduino",
               "OLED displays", "SD card"]
SMD_SUBS = ["Chips (R, C, L)", "Diodes", "Transistors (SOT)", "Power (DPAK, D2PAK)", "ICs (SOIC)",
            "Tantalum caps", "Electrolytic caps", "Inductors"]


_FF_TABLE = [("DIP", "_W", "Chips (DIP)", "Wide (15.24 mm rows)"), ("DIP", "", "Chips (DIP)", "Narrow (7.62 mm rows)"),
             ("TO92", "", "Transistors & regulators", "TO-92 (small plastic)"),
             ("TO220", "", "Transistors & regulators", "TO-220 (power, regulators)"),
             ("TO247", "", "Transistors & regulators", "TO-247 / TO-3P (big power)"),
             ("R_V_", "", "Resistors, diodes & inductors", "Resistors standing"),
             ("R_", "", "Resistors, diodes & inductors", "Resistors lying flat"),
             ("D_V_", "", "Resistors, diodes & inductors", "Diodes standing"),
             ("D_", "", "Resistors, diodes & inductors", "Diodes lying flat"),
             ("L_", "", "Resistors, diodes & inductors", "Inductors"),
             ("C_DISC", "", "Capacitors", "Ceramic disc"), ("C_FILM", "", "Capacitors", "Film / box"),
             ("C_ELEC", "", "Capacitors", "Electrolytic"), ("LED", "", "LEDs", ""),
             ("POT", "", "Pots, switches & crystals", "Pots & trimmers"),
             ("TRIM", "", "Pots, switches & crystals", "Pots & trimmers"),
             ("SW", "", "Pots, switches & crystals", "Switches"), ("XTAL", "", "Pots, switches & crystals", "Crystals"),
             ("HDR", "", "Connectors", "Pin headers"), ("TERM", "", "Connectors", "Screw terminals"),
             ("JSTXH", "", "Connectors", "JST-XH"), ("LINK", "", "Board bits", "Wire links"),
             ("HOLE", "", "Board bits", "Mounting holes"), ("PAD", "", "Board bits", "Pads"),
             ("SURF", "", "Board bits", "Pads"),
             ("SMD_CHIP", "", SMD_GROUP, "Chips (R, C, L)"), ("SMD_D", "", SMD_GROUP, "Diodes"),
             ("SMD_SOT", "", SMD_GROUP, "Transistors (SOT)"), ("SMD_TO", "", SMD_GROUP, "Power (DPAK, D2PAK)"),
             ("SMD_SOIC", "", SMD_GROUP, "ICs (SOIC)"), ("SMD_SOP", "", SMD_GROUP, "ICs (SOIC)"), ("SMD_TANT", "", SMD_GROUP, "Tantalum caps"),
             ("SMD_CELEC", "", SMD_GROUP, "Electrolytic caps"), ("SMD_L", "", SMD_GROUP, "Inductors"),
             ("MOD_XIAO_RP", "", MODULE_GROUP, "RP2040"),
             ("MOD_XIAO", "", MODULE_GROUP, "ESP32-C3 / S3 mini (postage stamp)"),
             ("MOD_ESP32C3", "", MODULE_GROUP, "ESP32-C3 / S3 mini (postage stamp)"),
             ("MOD_ESP32S3", "", MODULE_GROUP, "ESP32-C3 / S3 mini (postage stamp)"),
             ("MOD_ESP32_", "", MODULE_GROUP, "ESP32 dev boards"),
             ("MOD_NODEMCU", "", MODULE_GROUP, "ESP8266"), ("MOD_WEMOS", "", MODULE_GROUP, "ESP8266"),
             ("MOD_ESP01", "", MODULE_GROUP, "ESP8266"),
             ("MOD_RP2040", "", MODULE_GROUP, "RP2040"), ("MOD_PICO", "", MODULE_GROUP, "RP2040"),
             ("MOD_ARDUINO", "", MODULE_GROUP, "Arduino"), ("MOD_PRO_", "", MODULE_GROUP, "Arduino"),
             ("MOD_OLED", "", MODULE_GROUP, "OLED displays"), ("MOD_MICROSD", "", MODULE_GROUP, "SD card")]
SUB_ORDER = ["Narrow (7.62 mm rows)", "Wide (15.24 mm rows)", "TO-92 (small plastic)", "TO-220 (power, regulators)",
             "TO-247 / TO-3P (big power)", "Resistors lying flat", "Resistors standing", "Diodes lying flat",
             "Diodes standing", "Inductors", "Ceramic disc", "Film / box", "Electrolytic", "Pots & trimmers",
             "Switches", "Crystals", "Pin headers", "Screw terminals", "JST-XH", "Wire links", "Mounting holes", "Pads"] \
    + SMD_SUBS + MODULE_SUBS


def form_factor(part: PartDef) -> tuple:
    """(group, sub-group or "") used to sort the parts panel by shape rather than by maker code."""
    pid = part.id
    if pid in BUILTIN:
        for pre, suf, grp, sub in _FF_TABLE:
            if pid.startswith(pre) and pid.endswith(suf):
                return grp, sub
    return "My parts", ""


def user_part_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".solotrace", "parts")


def load_user_parts(path: Optional[str] = None) -> Dict[str, PartDef]:
    path = path or user_part_dir()
    out: Dict[str, PartDef] = {}
    if not os.path.isdir(path):
        return out
    for fn in sorted(os.listdir(path)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(path, fn), "r", encoding="utf-8") as fh:
                p = PartDef.from_dict(json.load(fh))
            p.category = p.category or "Custom"
            out[p.id] = p
        except (OSError, ValueError, KeyError):
            continue
    return out


def save_user_part(part: PartDef, path: Optional[str] = None) -> str:
    path = path or user_part_dir()
    os.makedirs(path, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", part.id)
    fn = os.path.join(path, safe + ".json")
    with open(fn, "w", encoding="utf-8") as fh:
        json.dump(part.to_dict(), fh, indent=1)
    return fn


def all_parts(include_user: bool = True) -> Dict[str, PartDef]:
    lib = dict(BUILTIN)
    if include_user:
        lib.update(load_user_parts())
    return lib


# --------------------------------------------------------------------------
# KiCad footprint import (.kicad_mod, a plain text S-expression file)
# --------------------------------------------------------------------------
def _tokenize(text: str) -> list:
    toks: list = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            toks.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            toks.append(text[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in "() \t\r\n":
                j += 1
            toks.append(text[i:j])
            i = j
    return toks


def _parse(toks: list, pos: int = 0):
    if toks[pos] != "(":
        return toks[pos], pos + 1
    pos += 1
    lst = []
    while toks[pos] != ")":
        item, pos = _parse(toks, pos)
        lst.append(item)
    return lst, pos + 1


def _find(node: list, key: str) -> list:
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def import_kicad_mod(text: str, category: str = "Custom") -> PartDef:
    """Read pads (through-hole only) and simple outline lines from a KiCad footprint.

    KiCad has Y pointing down and its origin at the part centre. We flip Y and move
    the origin to pad 1. Check the licence of any footprint before sharing it.
    """
    root, _ = _parse(_tokenize(text))
    if not root or root[0] != "footprint" and root[0] != "module":
        raise ValueError("not a KiCad footprint file")
    name = str(root[1]) if len(root) > 1 and not isinstance(root[1], list) else "imported"
    raw_pads = []
    for pd in _find(root, "pad"):
        if len(pd) < 4:
            continue
        pname, ptype, pshape = str(pd[1]), str(pd[2]), str(pd[3])
        if ptype not in ("thru_hole", "np_thru_hole"):
            continue
        at = _find(pd, "at")
        size = _find(pd, "size")
        drill = _find(pd, "drill")
        if not at or not size:
            continue
        x, y = float(at[0][1]), -float(at[0][2])
        w, h = float(size[0][1]), float(size[0][2])
        dr = 0.0
        if drill:
            vals = [v for v in drill[0][1:] if re.match(r"^-?\d+(\.\d+)?$", str(v))]
            dr = min(float(v) for v in vals) if vals else 0.0
        shape = {"circle": "round", "oval": "oval", "rect": "rect", "roundrect": "rect"}.get(pshape, "round")
        raw_pads.append((pname, x, y, shape, w, h, dr))
    if not raw_pads:
        raise ValueError("no through-hole pads found")
    ox, oy = raw_pads[0][1], raw_pads[0][2]
    pads = [PadDef(n, round(x - ox, 4), round(y - oy, 4), s, w, h, d) for n, x, y, s, w, h, d in raw_pads]
    outline: list = []
    for key in ("fp_line",):
        for ln in _find(root, key):
            st, en = _find(ln, "start"), _find(ln, "end")
            if st and en:
                outline.append(("line", float(st[0][1]) - ox, -float(st[0][2]) - oy,
                                float(en[0][1]) - ox, -float(en[0][2]) - oy))
    for cc in _find(root, "fp_circle"):
        ce, en = _find(cc, "center"), _find(cc, "end")
        if ce and en:
            cx, cy = float(ce[0][1]), -float(ce[0][2])
            r = ((float(en[0][1]) - float(ce[0][1])) ** 2 + (float(en[0][2]) - float(ce[0][2])) ** 2) ** 0.5
            outline.append(("circle", cx - ox, cy - oy, r))
    xs = [p.x for p in pads]
    ys = [p.y for p in pads]
    court = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
    pid = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return PartDef("KI_" + pid, name, category, "U", pads, outline, court,
                   note="Imported from a KiCad footprint. Check its licence before sharing.")


# --------------------------------------------------------------------------
# pin-function labels: common layouts for each form factor (not specific part numbers)
# --------------------------------------------------------------------------
_BJT_FET_92 = [("E B C", "E B C"), ("C B E", "C B E"), ("B C E", "B C E"), ("D G S", "D G S"),
               ("G D S", "G D S"), ("S G D", "S G D"),
               ("Small regulator, OUT GND IN", "OUT GND IN"), ("Small regulator, IN GND OUT", "IN GND OUT")]
_TO220_3 = [("Power transistor, B C E", "B C E"), ("MOSFET, G D S", "G D S"), ("IGBT, G C E", "G C E"),
            ("Regulator, IN GND OUT", "IN GND OUT"), ("Adjustable regulator, ADJ OUT IN", "ADJ OUT IN"),
            ("Negative regulator, GND IN OUT", "GND IN OUT"), ("Triac, MT1 MT2 G", "MT1 MT2 G"),
            ("Dual diode, A K A", "A K A")]
PINOUTS = {
    "TO92": _BJT_FET_92,
    "TO220_3": _TO220_3,
    "TO220_3_HS": _TO220_3,
    "TO220_2": [("Diode, K A", "K A"), ("Diode, A K", "A K")],
    "TO247": [("MOSFET, G D S", "G D S"), ("IGBT, G C E", "G C E"), ("Power transistor, B C E", "B C E")],
    "DIP4_N": [("Optocoupler, A K E C", "A K E C")],
    "DIP6_N": [("Optocoupler with base pin, A K NC E C B", "A K NC E C B"),
               ("Opto-triac, A K NC MT NC MT", "A K NC MT NC MT")],
    "DIP8_N": [("555-style timer", "GND TRIG OUT RST CV THR DIS VCC"),
               ("Dual op-amp", "OUT1 IN1- IN1+ V- IN2+ IN2- OUT2 V+"),
               ("Single op-amp", "NUL IN- IN+ V- NUL OUT V+ NC"),
               ("Dual optocoupler", "A1 K1 K2 A2 E2 C2 E1 C1")],
    "DIP14_N": [("Logic, GND 7 VCC 14", ". . . . . . GND . . . . . . VCC"),
                ("Quad op-amp", "OUT1 IN1- IN1+ V+ IN2+ IN2- OUT2 OUT3 IN3- IN3+ V- IN4+ IN4- OUT4")],
    "DIP16_N": [("Logic, GND 8 VCC 16", ". . . . . . . GND . . . . . . . VCC")],
    "DIP20_N": [("Logic, GND 10 VCC 20", ". . . . . . . . . GND . . . . . . . . . VCC")],
    "SMD_SOT23": [("Transistor, B E C", "B E C"), ("MOSFET, G S D", "G S D"), ("Dual diode, A K K (common cathode)", "A A K"),
                  ("Diode, A K", "A . K")],
    "SMD_SOT23_5": [("Regulator, IN GND EN NC OUT", "IN GND EN NC OUT"), ("Op-amp, IN+ V- IN- OUT V+", "IN+ V- IN- OUT V+")],
    "SMD_SOT23_6": [("Dual diode / MOSFET: check datasheet", ". . . . . ."), ("Regulator, IN GND EN . FB OUT", "IN GND EN . FB OUT")],
    "SMD_SOT223": [("Regulator 1117: GND OUT IN, tab OUT", "GND OUT IN OUT"), ("LM317: ADJ OUT IN, tab OUT", "ADJ OUT IN OUT"),
                   ("Transistor, B C E, tab C", "B C E C")],
    "SMD_TO252": [("MOSFET, G D S (tab D)", "G D S"), ("Transistor, B C E (tab C)", "B C E"), ("Regulator, IN GND OUT (tab GND)", "IN GND OUT")],
    "SMD_TO263": [("MOSFET, G D S (tab D)", "G D S ."), ("Transistor, B C E (tab C)", "B C E ."), ("Regulator, IN GND OUT (tab GND)", "IN GND OUT .")],
}
_TWO_PIN_POWER = [("+ -", "+ -"), ("- +", "- +"), ("AC AC", "AC AC"), ("IN OUT", "IN OUT")]
_THREE_PIN_POWER = [("V+ GND V-", "V+ GND V-"), ("IN GND OUT", "IN GND OUT"), ("+ - S", "+ - S")]
_POT = [("End, wiper, end (1 W 3)", "1 W 3"), ("CCW W CW", "CCW W CW")]


def default_pin_labels(part: PartDef) -> Dict[str, str]:
    """Labels that are true for every part of that shape (polarity of diodes, LEDs, electrolytics)."""
    pid = part.id
    if pid.startswith(("D_", "LED")) and len(part.pads) == 2:
        return {part.pads[0].name: "K", part.pads[1].name: "A"}
    if pid.startswith(("C_ELEC", "SMD_CELEC", "SMD_TANT")) and len(part.pads) == 2:
        return {part.pads[0].name: "+", part.pads[1].name: "-"}
    if pid.startswith("SMD_D_") and len(part.pads) == 2:
        return {part.pads[0].name: "K", part.pads[1].name: "A"}
    if pid in MODULE_LABELS and len(MODULE_LABELS[pid]) == len(part.pads):
        return {p.name: t for p, t in zip(part.pads, MODULE_LABELS[pid]) if t and t != "."}
    return {}


_SMD_ALIAS = {"SMD_SOIC8": "DIP8_N", "SMD_SOP8_5.3": "DIP8_N", "SMD_SOIC14": "DIP14_N", "SMD_SOIC16": "DIP16_N",
              "SMD_SOIC16W": "DIP16_N", "SMD_SOIC20W": "DIP20_N"}


def pinout_presets(part: PartDef) -> List[tuple]:
    """(menu name, {pad name: label}) for the layouts that are common for this form factor."""
    pid = part.id
    raw = list(PINOUTS.get(pid, PINOUTS.get(_SMD_ALIAS.get(pid, ""), [])))
    n = len(part.pads)
    if pid.startswith(("TERM", "JSTXH", "HDR_1x")) and n == 2:
        raw = _TWO_PIN_POWER
    elif pid.startswith(("TERM", "JSTXH", "HDR_1x")) and n == 3:
        raw = _THREE_PIN_POWER
    elif pid.startswith(("POT", "TRIM")):
        raw = _POT
    elif pid.startswith(("D_", "LED", "SMD_D_")) and n == 2:
        raw = [("K A (cathode is pin 1)", "K A")]
    elif pid.startswith(("C_ELEC", "SMD_CELEC", "SMD_TANT")) and n == 2:
        raw = [("+ - (positive is pin 1)", "+ -")]
    elif pid in MODULE_LABELS:
        raw = [("As printed on the module", " ".join(MODULE_LABELS[pid]))]
        if pid.startswith("MOD_OLED") and n == 4:
            raw.append(("VCC GND SCL SDA (some sellers swap them)", "VCC GND SCL SDA"))
    out = []
    for name, labels in raw:
        toks = labels.split()
        if len(toks) != n:
            continue
        out.append((name, {p.name: t for p, t in zip(part.pads, toks) if t != "."}))
    return out


def parse_pin_labels(part: PartDef, text: str) -> Dict[str, str]:
    """Labels typed by the user, separated by spaces or commas, in pin order; '.' skips a pin."""
    toks = [t for t in text.replace(",", " ").split()]
    return {p.name: t[:6] for p, t in zip(part.pads, toks) if t != "."}


# --------------------------------------------------------------------------
# names in the parts panel
# --------------------------------------------------------------------------
_SHORT = (("Resistor ", ""), (" standing", ""), ("Diode ", ""), ("Inductor ", ""), ("Electrolytic cap, ", ""),
          ("Film / box cap, ", ""), ("Ceramic disc cap, ", ""), ("Pin header ", ""), ("Screw terminal ", ""),
          ("JST-XH header ", ""), ("Wire link ", ""))


def short_name(name: str, sub: str) -> str:
    """Shorter tree label: the sub-group already says what kind of part it is."""
    if not sub:
        return name
    out = name
    for a, b in _SHORT:
        out = out.replace(a, b)
    if out.startswith("DIP-") and "(" in out:
        out = out.split(" ")[0]
    return out[:1].upper() + out[1:] if out else name


def _natural(s: str):
    """Sort key so DIP-8 comes before DIP-14 and 2.54 mm before 10.16 mm."""
    import re
    return [float(t) if t.replace(".", "", 1).isdigit() else t.lower() for t in re.findall(r"\d+\.?\d*|\D+", s)]
