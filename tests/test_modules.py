# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.7.0: microcontroller modules, OLED displays, the SD card module, and mirrored parts."""
import os
import tempfile
import unittest

import _path  # noqa: F401

from solotrace import gerber, library, render
from solotrace.board import Board
from solotrace.drc import run_drc, summarize
from solotrace.web import session as websession
from solotrace.web.session import Session


class MirroredParts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = tmp
        websession.CONFIG_FILE = os.path.join(tmp, "config.json")

    def _board(self, pid="HDR_1x4"):
        b = Board(60, 40, "m")
        b.defs[pid] = library.BUILTIN[pid]
        b.add_part(pid, 20, 20)
        return b, next(iter(b.parts))

    def test_mirror_swaps_the_pins_and_marks_the_part(self):
        b, ref = self._board("DIP8_N")
        p1 = b.pin_pos(ref + ".1")
        p8 = b.pin_pos(ref + ".8")
        self.assertFalse(b.is_mirrored(ref))
        self.assertTrue(b.mirror_part(ref))
        self.assertTrue(b.is_mirrored(ref))
        self.assertTrue(b.on_copper_side(ref))
        self.assertEqual(b.pin_pos(ref + ".1"), p1)          # mirrored about pin 1
        q8 = b.pin_pos(ref + ".8")
        self.assertAlmostEqual(q8[0], 2 * p1[0] - p8[0])     # the other row is now on the other side
        self.assertAlmostEqual(q8[1], p8[1])
        self.assertFalse(b.mirror_part(ref))
        self.assertEqual(b.pin_pos(ref + ".8"), p8)

    def test_smd_is_not_mirrored_on_the_copper_side(self):
        b, ref = self._board("SMD_SOT23")
        self.assertTrue(b.on_copper_side(ref))
        self.assertFalse(b.is_mirrored(ref))
        b.mirror_part(ref)
        self.assertTrue(b.is_mirrored(ref))
        self.assertFalse(b.on_copper_side(ref))

    def test_mirrored_part_goes_to_the_bottom_silkscreen_bom_and_drc(self):
        b, ref = self._board("DIP8_N")
        self.assertNotIn("Silkscreen_Bottom", " ".join(gerber.make_files(b)))
        b.mirror_part(ref)
        files = gerber.make_files(b)
        self.assertTrue(any("Silkscreen_Bottom" in n for n in files))
        self.assertTrue(render.silk_segments(b, "bottom"))
        self.assertFalse(render.silk_segments(b, "top"))
        self.assertIn("MIRRORED", render.to_bom_csv(b))
        iss = run_drc(b)
        self.assertTrue(any(i.kind == "mirrored" and i.severity == "info" for i in iss))
        self.assertNotIn("mirrored", summarize(iss).lower())     # a note, not a problem

    def test_web_session_places_mirrored_and_highlights(self):
        s = Session(Board(60, 40, "w"))
        s.cmd("arm", {"pid": "DIP8_N"})
        s.cmd("mirror", {})
        self.assertTrue(s.scene()["arm_mirror"])
        s.cmd("press", {"x": 20, "y": 20, "scale": 8})
        ref = next(iter(s.board.parts))
        self.assertTrue(s.board.is_mirrored(ref))
        part = next(p for p in s.scene()["parts"] if p["ref"] == ref)
        self.assertTrue(part["mirrored"] and part["under"])
        s.cmd("escape", {})
        s.sel = {"part": ref}
        self.assertTrue(any(w.get("mirror") for w in s.panel()))
        s.cmd("mirror", {})
        self.assertFalse(s.board.is_mirrored(ref))
        s.cmd("undo", {})
        self.assertTrue(s.board.is_mirrored(ref))
        labels = [i.get("label", "") for i in s.menu(*s.board.pin_pos(ref + ".1"))]
        self.assertTrue(any(l.startswith("Mirrored") for l in labels))


class Modules(unittest.TestCase):
    """Spot checks against the sourced data in docs/research/mcu-modules.md."""

    def labels(self, pid):
        d = library.BUILTIN[pid]
        return d, {p.name: (p.x, p.y) for p in d.pads}, library.default_pin_labels(d)

    def at(self, pid, label):
        d, pos, lab = self.labels(pid)
        return next(pos[k] for k, v in lab.items() if v == label)

    def test_all_modules_are_grouped_labelled_and_drc_clean(self):
        mods = [k for k in library.BUILTIN if k.startswith("MOD_")]
        self.assertGreaterEqual(len(mods), 20)
        for pid in mods:
            d = library.BUILTIN[pid]
            self.assertEqual(library.form_factor(d)[0], library.MODULE_GROUP, pid)
            self.assertEqual(len(library.default_pin_labels(d)), len(d.pads), pid)
            for style in ("tht", "dead"):
                b = Board(150, 150, "t")
                b.defs[pid] = d
                b.add_part(pid, 70, 70, style=style)
                errs = [i for i in run_drc(b) if i.severity == "error"]
                self.assertEqual(errs, [], (pid, style))

    def test_row_spacings_from_the_sources(self):
        for pid, a, b, gap in (("MOD_XIAO_C3", "D0", "5V", 15.24), ("MOD_ESP32C3_SUPERMINI", "IO5", "5V", 15.24),
                               ("MOD_PICO", "GP0", "VBUS", 17.78), ("MOD_ESP32_DEVKITC38", "EN", "IO23", 25.4),
                               ("MOD_ESP32_DOIT30", "EN", "IO23", 25.4), ("MOD_NODEMCU_AMICA", "A0", "D0", 22.86),
                               ("MOD_NODEMCU_LOLIN", "A0", "D0", 27.94), ("MOD_WEMOS_D1MINI", "RST", "TX", 22.86),
                               ("MOD_ARDUINO_NANO", "TX", "VIN", 15.24), ("MOD_PRO_MICRO", "TXO", "RAW", 15.24)):
            pa, pb = self.at(pid, a), self.at(pid, b)
            self.assertAlmostEqual(pb[0] - pa[0], gap, places=3, msg=pid)
            self.assertAlmostEqual(pb[1], pa[1], places=3, msg=pid)     # the two are opposite each other

    def test_pin_orders(self):
        _d, pos, lab = self.labels("MOD_XIAO_S3")
        right = sorted((p for k, p in pos.items() if p[0] > 1), key=lambda p: -p[1])
        names = {pos[k]: v for k, v in lab.items()}
        self.assertEqual([names[p] for p in right], ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"])
        _d, pos, lab = self.labels("MOD_RP2040_ZERO")
        names = {pos[k]: v for k, v in lab.items()}
        bottom = sorted((p for p in pos.values() if 1 < p[0] < 14), key=lambda p: p[0])
        self.assertEqual([names[p] for p in bottom], ["GP13", "GP12", "GP11", "GP10", "GP9"])
        self.assertEqual(self.at("MOD_OLED096_I2C", "GND")[0] + 2.54, self.at("MOD_OLED096_I2C", "VCC")[0])
        presets = [n for n, _l in library.pinout_presets(library.BUILTIN["MOD_OLED096_I2C"])]
        self.assertTrue(any("swap" in n for n in presets))


if __name__ == "__main__":
    unittest.main()
