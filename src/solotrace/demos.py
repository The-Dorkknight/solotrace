# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Small example boards used by the tests, the screenshots and File > Open example."""
from __future__ import annotations

import random
from typing import Callable, Dict

from .board import Board


def _net(b: Board, name: str, *pins: str, cls: str = "Signal") -> None:
    for p in pins[1:]:
        b.connect(pins[0], p, name)
    b.set_net_class(name, cls)


def flasher_555() -> Board:
    """NE555 astable LED flasher on a 9 V supply (pin numbers as for the standard DIP-8 555)."""
    b = Board(70, 50, "555 LED flasher")
    b.add_part("DIP8_N", 25.4, 38.1, ref="U1", value="NE555")
    b.add_part("TERM_5.08_2", 5.08, 40.64, rot=90, ref="J1", value="9V")
    b.add_part("R_0.25W_10.16", 10.16, 8.89, ref="R1", value="1k")
    b.add_part("R_0.25W_10.16", 25.4, 8.89, ref="R2", value="47k")
    b.add_part("R_0.25W_10.16", 45.72, 8.89, ref="R3", value="470")
    b.add_part("C_ELEC_5", 12.7, 22.86, ref="C1", value="10u")
    b.add_part("C_DISC_5.08", 40.64, 22.86, ref="C2", value="10n")
    b.add_part("LED5", 55.88, 22.86, rot=90, ref="D1", value="LED")
    _net(b, "VCC", "J1.1", "U1.8", "U1.4", "R1.1", cls="Power")
    _net(b, "GND", "J1.2", "U1.1", "C1.2", "C2.2", "D1.2", cls="Power")
    _net(b, "DIS", "R1.2", "R2.1", "U1.7")
    _net(b, "THR", "R2.2", "U1.6", "U1.2", "C1.1")
    _net(b, "CV", "U1.5", "C2.1")
    _net(b, "OUT", "U1.3", "R3.1")
    _net(b, "LEDA", "R3.2", "D1.1")
    return b


def regulator_7805() -> Board:
    """7805 power supply with a wide (high-current) rail, to show wide traces and TO-220 deadbug pads."""
    b = Board(70, 45, "5 V regulator")
    b.settings.classes["High current"] = 3.0
    b.add_part("TERM_5.08_2", 5.08, 30.48, rot=90, ref="J1", value="12V in")
    b.add_part("TO220_3", 25.4, 20.32, ref="U1", value="7805", style="dead")
    b.add_part("C_ELEC_5", 15.24, 8.89, ref="C1", value="470u")
    b.add_part("C_ELEC_5", 38.1, 8.89, ref="C2", value="100u")
    b.add_part("D_DO41_10.16", 12.7, 35.56, ref="D1", value="1N4007")
    b.add_part("TERM_5.08_2", 50.8, 30.48, rot=90, ref="J2", value="5V out")
    _net(b, "VIN", "J1.1", "D1.1", cls="Power")
    _net(b, "VRAW", "D1.2", "C1.1", "U1.1", cls="High current")
    _net(b, "GND", "J1.2", "C1.2", "U1.2", "C2.2", "J2.2", cls="High current")
    _net(b, "V5", "U1.3", "C2.1", "J2.1", cls="High current")
    return b


def power_oscillator() -> Board:
    """555 astable driving a TO-220 power transistor into a coil (a typical high-voltage-driver
    layout). Shows pin labels, standing resistors and a rigid power trunk from Q1 to J1."""
    from .library import BUILTIN, pinout_presets
    b = Board(60, 50, "555 power oscillator")
    # 2 mm: a wider trace cannot leave the middle pin of a TO-220 (2.54 mm pitch) with 0.3 mm clearance
    b.settings.classes["High current"] = 2.0
    b.add_part("DIP8_N", 22.86, 33.02, ref="U1", value="NE555")
    b.add_part("TERM_5.08_2", 20.32, 45.72, ref="J1", value="12V")
    b.add_part("TERM_5.08_2", 43.18, 10.16, ref="J2", value="Coil")
    b.add_part("C_FILM_5", 12.7, 33.02, rot=270, ref="C1", value="10n")
    b.add_part("R_V_0.25W_2.54", 38.1, 33.02, ref="R1", value="1k")
    b.add_part("R_V_0.25W_2.54", 38.1, 27.94, ref="R2", value="10k")
    b.add_part("R_V_0.25W_2.54", 12.7, 20.32, ref="R3", value="220")
    b.add_part("TO220_3", 7.62, 7.62, ref="Q1", value="NPN power")
    b.add_part("D_DO41_10.16", 30.48, 20.32, ref="D1", value="1N4007")
    b.parts["U1"].pin_labels = dict(pinout_presets(BUILTIN["DIP8_N"])[0][1])
    b.parts["Q1"].pin_labels = dict(pinout_presets(BUILTIN["TO220_3"])[0][1])
    b.parts["J1"].pin_labels = {"1": "-", "2": "+"}
    _net(b, "GND", "J1.1", "Q1.3", "C1.2", "U1.1", cls="High current")
    b.set_rigid("Q1.3", "J1.1")
    _net(b, "VCC", "J1.2", "U1.8", "U1.4", "R1.1", "J2.1", "D1.1", cls="Power")
    _net(b, "DIS", "R1.2", "U1.7", "R2.1")
    _net(b, "THR", "R2.2", "U1.6", "U1.2", "C1.1")
    _net(b, "OUT", "U1.3", "R3.1")
    _net(b, "BASE", "R3.2", "Q1.1")
    _net(b, "COIL", "Q1.2", "J2.2", "D1.2", cls="High current")
    return b


def rf_oscillator() -> Board:
    """Colpitts oscillator built deadbug style on islands: ground fill over the board, every other
    net an island, every pad a surface (no-drill) pad. Shows Board > Ground fill."""
    from .library import BUILTIN, pinout_presets
    b = Board(50, 40, "RF oscillator (islands)")
    b.settings.island_mode = True
    b.settings.island_grow = 1.5
    for pid, x, y, rot, ref, val in (
            ("TO92", 25.4, 20.32, 0, "Q1", "2N3904"),
            ("R_V_0.25W_2.54", 12.7, 30.48, 0, "R1", "47k"),
            ("R_V_0.25W_2.54", 12.7, 20.32, 90, "R2", "10k"),
            ("R_V_0.25W_2.54", 22.86, 10.16, 90, "R3", "1k"),
            ("C_DISC_2.54", 12.7, 10.16, 90, "C5", "10n"),
            ("C_DISC_2.54", 31.75, 12.7, 0, "C2", "47p"),
            ("C_DISC_2.54", 31.75, 5.08, 0, "C3", "100p"),
            ("L_RAD_5", 33.02, 30.48, 0, "L1", "1uH"),
            ("C_DISC_2.54", 40.64, 21.59, 90, "C6", "10p"),
            ("C_DISC_2.54", 22.86, 33.02, 0, "C4", "100n"),
            ("HDR_1x2", 5.08, 33.02, 90, "J1", "9V"),
            ("HDR_1x2", 45.72, 10.16, 90, "J2", "RF out")):
        b.add_part(pid, x, y, rot=rot, ref=ref, value=val, style="dead")
    b.parts["Q1"].pin_labels = dict(pinout_presets(BUILTIN["TO92"])[0][1])
    b.parts["J1"].pin_labels = {"1": "-", "2": "+"}
    b.parts["J2"].pin_labels = {"1": "GND", "2": "OUT"}
    _net(b, "GND", "J1.1", "R2.2", "R3.2", "C3.2", "C5.2", "C4.2", "J2.1", cls="Power")
    _net(b, "VCC", "J1.2", "R1.1", "L1.1", "C4.1", cls="Power")
    _net(b, "BASE", "Q1.2", "R1.2", "R2.1", "C5.1")
    _net(b, "EMIT", "Q1.1", "R3.1", "C3.1", "C2.2")
    _net(b, "COLL", "Q1.3", "L1.2", "C2.1", "C6.1")
    _net(b, "OUT", "C6.2", "J2.2")
    return b


def manhattan_amp() -> Board:
    """Common-emitter RF amplifier built Manhattan style: hand-placed copper islands (no traces at all)
    on a ground fill, every pad a surface pad. Shows the Island tool."""
    from .board import Island
    b = Board(60, 36, "Manhattan RF amplifier")
    b.settings.island_mode = True
    b.settings.island_grow = 0.0
    for pid, x, y, rot, ref, val in (
            ("PAD_2.5", 6.35, 11.43, 0, "P1", "RF in"),
            ("C_DISC_5.08", 11.43, 11.43, 0, "C1", "1n"),
            ("R_V_0.25W_5.08", 19.05, 11.43, 90, "R2", "10k"),
            ("R_V_0.25W_5.08", 23.495, 11.43, 270, "R1", "47k"),
            ("TO92", 25.4, 22.86, 0, "Q1", "2N3904"),
            ("L_RAD_5", 40.64, 5.08, 90, "L1", "10uH"),
            ("C_DISC_5.08", 43.18, 27.94, 0, "C2", "1n"),
            ("C_DISC_5.08", 34.29, 5.08, 90, "C3", "100n"),
            ("PAD_2.5", 25.4, 5.08, 0, "P3", "+9V"),
            ("PAD_2.5", 53.34, 27.94, 0, "P2", "RF out"),
            ("PAD_2.5", 8.89, 30.48, 0, "P4", "GND")):
        b.add_part(pid, x, y, rot=rot, ref=ref, value=val, style="dead")
    for x, y, w, h in ((8.89, 11.43, 8.89, 3.81),        # RF in
                       (21.59, 11.43, 11.43, 3.81),      # base
                       (27.94, 17.15, 1.8, 12.7),        # base, up to Q1
                       (31.75, 5.08, 20.32, 3.81),       # +9 V rail
                       (30.48, 25.4, 1.8, 6.35),         # collector, up from Q1
                       (38.1, 27.94, 15.24, 3.81),       # collector
                       (40.64, 18.0, 3.81, 17.0),        # collector, down to L1
                       (51.5, 27.94, 9.0, 3.81)):        # RF out
        b.islands.append(Island(x, y, w, h))
    for name, pins in (("IN", ("P1.1", "C1.1")), ("BASE", ("C1.2", "R2.1", "R1.1", "Q1.2")),
                       ("VCC", ("P3.1", "R1.2", "L1.1", "C3.1")), ("COLL", ("Q1.3", "L1.2", "C2.1")),
                       ("OUT", ("C2.2", "P2.1")), ("GND", ("Q1.1", "R2.2", "C3.2", "P4.1"))):
        for p in pins[1:]:
            b.connect(pins[0], p, name)
    b.touch()
    return b


def logic_dip14(seed: int = 7) -> Board:
    """Two DIP-14 gates, a DIP-8 and a few passives; many signals, so jumpers may appear."""
    b = Board(80, 60, "Logic mix")
    b.add_part("DIP14_N", 10.16, 50.8, ref="U1", value="74HC00")
    b.add_part("DIP14_N", 35.56, 50.8, ref="U2", value="74HC14")
    b.add_part("DIP8_N", 60.96, 50.8, ref="U3", value="NE555")
    for i in range(4):
        b.add_part("R_0.25W_10.16", 10.16 + i * 15.24, 10.16, ref="R%d" % (i + 1), value="10k")
    b.add_part("HDR_1x4", 50.8, 22.86, ref="J1")
    _net(b, "VCC", "U1.14", "U2.14", "U3.8", "U3.4", "J1.1", cls="Power")
    _net(b, "GND", "U1.7", "U2.7", "U3.1", "J1.2", cls="Power")
    _net(b, "A", "U1.3", "U2.1", "R1.1")
    _net(b, "B", "U1.6", "U2.3", "R2.1")
    _net(b, "C", "U2.2", "U3.2", "R3.1")
    _net(b, "D", "U2.4", "U3.3", "J1.3")
    _net(b, "E", "U1.1", "U1.2", "R4.1")
    _net(b, "F", "U1.4", "U1.5", "J1.4")
    _net(b, "G", "U1.9", "U2.5", "R1.2")
    _net(b, "H", "U1.10", "U2.9", "R2.2")
    return b


def random_board(n_parts: int = 12, seed: int = 1, w: float = 120, h: float = 80) -> Board:
    """Stress-test board: random resistors and DIPs with random 2-4 pin nets."""
    rnd = random.Random(seed)
    b = Board(w, h, "Random %d" % n_parts)
    kinds = ["DIP8_N", "DIP14_N", "R_0.25W_10.16", "R_0.25W_10.16", "C_DISC_5.08", "HDR_1x4"]
    placed = []
    tries = 0
    while len(placed) < n_parts and tries < 2000:
        tries += 1
        kid = rnd.choice(kinds)
        x = round(rnd.uniform(8, w - 25) / 1.27) * 1.27
        y = round(rnd.uniform(15, h - 8) / 1.27) * 1.27
        pl = b.add_part(kid, x, y)
        r = b.court_rect(pl.ref)
        ok = r[0] > 2 and r[1] > 2 and r[2] < w - 2 and r[3] < h - 2
        for q in placed:
            r2 = b.court_rect(q)
            if not (r[2] + 2 < r2[0] or r2[2] + 2 < r[0] or r[3] + 2 < r2[1] or r2[3] + 2 < r[1]):
                ok = False
        if ok:
            placed.append(pl.ref)
        else:
            b.remove_part(pl.ref)
    pins = [p for p in b.all_pins()]
    rnd.shuffle(pins)
    n_nets = max(3, len(pins) // 4)
    for i in range(n_nets):
        k = rnd.choice([2, 2, 3])
        grp = [pins.pop() for _ in range(min(k, len(pins)))]
        if len(grp) >= 2:
            _net(b, "S%d" % i, *grp)
    return b


DEMOS: Dict[str, Callable[[], Board]] = {
    "555 LED flasher": flasher_555,
    "5 V regulator": regulator_7805,
    "555 power oscillator": power_oscillator,
    "Logic mix": logic_dip14,
    "RF oscillator (ground fill, routed)": rf_oscillator,
    "Manhattan RF amplifier (copper islands)": manhattan_amp,
}
