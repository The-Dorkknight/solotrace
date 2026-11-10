# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.9.0: the wire tool locks onto the pin nearest the cursor (solid green circle in the UI), counting
the whole pad copper, so a long hole strip can be wired from any hole."""
import json
import os
import tempfile
import unittest

import _path  # noqa: F401

from solotrace.board import Board
from solotrace.web import api, session as websession
from solotrace.web.session import Session


def small():
    b = Board(60, 30, "lock")
    b.add_part("DIP8_N", 10.0, 20.0, ref="U1")
    b.add_part("BRK_STRIP4", 40.0, 10.0, ref="TP1")
    b.add_part("BRK_STRIP4_LEAD", 40.0, 20.0, ref="TP2")
    return b


class PinLock(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = tmp
        websession.CONFIG_FILE = os.path.join(tmp, "config.json")

    def test_locks_on_the_nearest_pad_not_only_within_1_6_mm_of_its_centre(self):
        b = small()
        px, py = b.pin_pos("U1.3")
        # 2 mm from the centre of a 1.7 mm pad is just outside the pad: the old test (1.6 mm from the
        # centre) missed it, the new one (distance to the copper) finds it
        lk = b.pin_lock(px + 1.6, py + 0.9, 1.4)
        self.assertEqual(lk[0], "U1.3")
        self.assertEqual(lk[1], (px, py))
        self.assertIsNone(b.pin_lock(px + 1.27, py + 1.27 + 6, 1.4))          # nothing there

    def test_between_two_pads_the_nearer_one_wins(self):
        b = small()
        a, c = b.pin_pos("U1.1"), b.pin_pos("U1.2")
        mid = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
        near_a = (mid[0] + (a[0] - c[0]) * 0.2, mid[1] + (a[1] - c[1]) * 0.2)
        self.assertEqual(b.pin_lock(near_a[0], near_a[1], 2.0)[0], "U1.1")
        near_c = (mid[0] - (a[0] - c[0]) * 0.2, mid[1] - (a[1] - c[1]) * 0.2)
        self.assertEqual(b.pin_lock(near_c[0], near_c[1], 2.0)[0], "U1.2")

    def test_a_hole_strip_is_picked_from_any_hole_and_the_lock_sits_on_that_hole(self):
        b = small()
        holes = b.pad_holes("TP1.1")
        self.assertEqual(len(holes), 4)
        for hx, hy in holes:
            lk = b.pin_lock(hx + 0.2, hy - 0.3, 1.4)
            self.assertEqual(lk[0], "TP1.1")
            self.assertAlmostEqual(lk[1][0], hx, places=3)
            self.assertAlmostEqual(lk[1][1], hy, places=3)

    def test_web_hover_reports_the_lock_and_a_click_places_the_wire(self):
        b = small()
        s = Session(b)
        s.tool = "wire"
        h = s.board.pad_holes("TP1.1")[3]
        code, data, _t, _n = api.handle(s, "POST", "/api/cmd", None, {"name": "hover", "args": {"x": h[0] + 0.3, "y": h[1], "scale": 10}})
        lock = json.loads(data)["out"]["lock"]
        self.assertEqual(lock["pin"], "TP1.1")
        self.assertTrue(lock["ok"])
        self.assertAlmostEqual(lock["x"], h[0], places=2)
        u = s.board.pin_pos("U1.4")
        for x, y in ((u[0] + 0.2, u[1] + 0.2), (h[0], h[1])):
            api.handle(s, "POST", "/api/cmd", None, {"name": "press", "args": {"x": x, "y": y, "scale": 10}})
        self.assertIsNotNone(s.board.net_of("U1.4"))
        self.assertEqual(s.board.net_of("U1.4").name, s.board.net_of("TP1.1").name)
        # the pin it started from is shown as the start, not as a place to click
        code, data, _t, _n = api.handle(s, "POST", "/api/cmd", None, {"name": "hover", "args": {"x": h[0], "y": h[1], "scale": 10}})
        self.assertFalse(json.loads(data)["out"]["lock"]["ok"])

    def test_the_lock_radius_follows_the_zoom(self):
        s = Session(small())
        s.scale = 30.0
        near = s.lock_radius()
        s.scale = 5.0
        far = s.lock_radius()
        self.assertLess(near, far)
        self.assertGreaterEqual(near, 1.4)
        self.assertLessEqual(far, 3.0)


class StripParts(unittest.TestCase):
    def test_strip_holes_in_drill_list_and_round_trip(self):
        b = small()
        d = b.drills()
        self.assertEqual(len([x for x in d if abs(x[1] - 10.0) < 1e-6]), 4)          # TP1: 4 holes, none at the bar's middle
        self.assertFalse(any(abs(x[0] - 40.0) < 1e-6 and abs(x[1] - 10.0) < 1e-6 for x in d))
        f = os.path.join(tempfile.mkdtemp(), "s.solotrace")
        b.save(f)
        b2 = Board.load(f)
        self.assertEqual(sorted(b2.drills()), sorted(d))

    def test_strip_ignores_the_deadbug_choice_and_stays_out_of_the_bom(self):
        from solotrace import render
        b = small()
        b.parts["TP1"].style = "dead"
        b.touch()
        self.assertEqual(len(b.drills()), len(small().drills()))
        self.assertFalse(any("TP1" in r[0] for r in render.bom_rows(b)))

    def test_strip_is_one_net_for_every_hole(self):
        b = small()
        b.connect("U1.1", "TP1.1", "SIG")
        b.touch()
        self.assertEqual(b.unrouted_count(), 1)       # one connection to make; the 4 holes are not 4 pins


if __name__ == "__main__":
    unittest.main()
