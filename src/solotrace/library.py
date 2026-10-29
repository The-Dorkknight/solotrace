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
# the library
# --------------------------------------------------------------------------
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
    return lib


BUILTIN: Dict[str, PartDef] = _build()


# --------------------------------------------------------------------------
# form-factor groups for the parts panel
# --------------------------------------------------------------------------
FORM_GROUPS = ["Chips (DIP)", "Transistors & regulators", "Resistors, diodes & inductors", "Capacitors",
               "LEDs", "Pots, switches & crystals", "Connectors", "Board bits", "My parts"]


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
             ("SURF", "", "Board bits", "Pads")]
SUB_ORDER = ["Narrow (7.62 mm rows)", "Wide (15.24 mm rows)", "TO-92 (small plastic)", "TO-220 (power, regulators)",
             "TO-247 / TO-3P (big power)", "Resistors lying flat", "Resistors standing", "Diodes lying flat",
             "Diodes standing", "Inductors", "Ceramic disc", "Film / box", "Electrolytic", "Pots & trimmers",
             "Switches", "Crystals", "Pin headers", "Screw terminals", "JST-XH", "Wire links", "Mounting holes", "Pads"]


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
}
_TWO_PIN_POWER = [("+ -", "+ -"), ("- +", "- +"), ("AC AC", "AC AC"), ("IN OUT", "IN OUT")]
_THREE_PIN_POWER = [("V+ GND V-", "V+ GND V-"), ("IN GND OUT", "IN GND OUT"), ("+ - S", "+ - S")]
_POT = [("End, wiper, end (1 W 3)", "1 W 3"), ("CCW W CW", "CCW W CW")]


def default_pin_labels(part: PartDef) -> Dict[str, str]:
    """Labels that are true for every part of that shape (polarity of diodes, LEDs, electrolytics)."""
    pid = part.id
    if pid.startswith(("D_", "LED")) and len(part.pads) == 2:
        return {part.pads[0].name: "K", part.pads[1].name: "A"}
    if pid.startswith("C_ELEC") and len(part.pads) == 2:
        return {part.pads[0].name: "+", part.pads[1].name: "-"}
    return {}


def pinout_presets(part: PartDef) -> List[tuple]:
    """(menu name, {pad name: label}) for the layouts that are common for this form factor."""
    pid = part.id
    raw = list(PINOUTS.get(pid, []))
    n = len(part.pads)
    if pid.startswith(("TERM", "JSTXH", "HDR_1x")) and n == 2:
        raw = _TWO_PIN_POWER
    elif pid.startswith(("TERM", "JSTXH", "HDR_1x")) and n == 3:
        raw = _THREE_PIN_POWER
    elif pid.startswith(("POT", "TRIM")):
        raw = _POT
    elif pid.startswith(("D_", "LED")) and n == 2:
        raw = [("K A (cathode is pin 1)", "K A")]
    elif pid.startswith("C_ELEC") and n == 2:
        raw = [("+ - (positive is pin 1)", "+ -")]
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
