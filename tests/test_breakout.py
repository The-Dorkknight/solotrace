# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.9.0: the generated breakout boards (XIAO, C3 SuperMini, S3-Zero) come out complete and clean."""
import unittest

import _path  # noqa: F401

from solotrace import demos, gerber
from solotrace.drc import run_drc
from solotrace.library import BUILTIN
from solotrace.router import AutoRouter, RouteOptions

MAKERS = (("xiao", demos.breakout_xiao, "MOD_XIAO_S3", 14),
          ("supermini", demos.breakout_supermini, "MOD_ESP32C3_SUPERMINI", 16),
          ("s3zero", demos.breakout_s3zero, "MOD_ESP32S3_ZERO", 18))


def routed(fn):
    b = fn()
    AutoRouter(b, RouteOptions(algorithm=b.settings.router)).route_all()
    return b


class Breakouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boards = {n: (routed(fn), mid, npins) for n, fn, mid, npins in MAKERS}

    def test_every_connection_is_made_without_jumpers(self):
        for n, (b, _, _) in self.boards.items():
            self.assertEqual(b.unrouted_count(), 0, n)
            self.assertEqual(len(b.jumpers), 0, n)

    def test_no_drc_errors(self):
        for n, (b, _, _) in self.boards.items():
            bad = [i for i in run_drc(b) if i.severity == "error"]
            self.assertFalse(bad, (n, [(i.kind, getattr(i, "msg", "")) for i in bad[:5]]))

    def test_one_strip_per_module_pin_with_four_extra_holes(self):
        for n, (b, mid, npins) in self.boards.items():
            strips = [p for p in b.parts.values() if p.part_id.startswith("BRK_STRIP4_LEAD")]
            self.assertEqual(len(strips), npins, n)
            for p in strips:
                self.assertEqual(len(BUILTIN[p.part_id].pads[0].holes), 4, n)
            # 4 strip holes + the module's own pad hole = 5 places per pin, plus the rails and connectors
            self.assertGreaterEqual(len(b.drills()), npins * 5, n)

    def test_power_in_reaches_both_rails_from_screw_terminal_and_header(self):
        for n, (b, _, _) in self.boards.items():
            plus, gnd = set(b.nets["+5V"].pins), set(b.nets["GND"].pins)
            self.assertTrue({"J1.1", "J2.1"} <= plus, n)
            self.assertTrue({"J1.2", "J2.2"} <= gnd, n)
            rails = [p for p in b.parts.values() if p.part_id == "BRK_STRIP6"]
            self.assertEqual(len(rails), 3, n)
            self.assertEqual(sorted(set(r.pin_labels["1"] for r in rails)), ["3V3", "5V", "GND"], n)

    def test_no_copper_under_the_module_body(self):
        for n, (b, mid, _) in self.boards.items():
            u = b.parts["U1"]
            x0, y0, x1, y1 = BUILTIN[mid].court
            for t in b.traces:
                for x, y in t.points:
                    inside = u.x + x0 < x < u.x + x1 and u.y + y0 < y < u.y + y1
                    self.assertFalse(inside, (n, t.net, x, y))
            for ref in ("J1", "J2"):
                self.assertLess(b.parts[ref].y, u.y + y0, (n, ref))

    def test_gerber_drill_file_lists_every_hole(self):
        for n, (b, _, _) in self.boards.items():
            text = gerber.drill_file(b)
            self.assertEqual(sum(1 for ln in text.splitlines() if ln.startswith("X")), len(b.drills()), n)


if __name__ == "__main__":
    unittest.main()
