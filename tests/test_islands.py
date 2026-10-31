# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Copper islands (free-standing round / rectangular pads) and the ground-fill island mode."""
import unittest

import _path  # noqa: F401

from solotrace import demos, drc, gerber, islands, laser, render
from solotrace.board import Board, Island
from solotrace.geom import shape_dist
from solotrace.router import AutoRouter


def two_resistors():
    b = Board(40, 30, "islands")
    b.add_part("R_V_0.25W_2.54", 10.16, 15.24, ref="R1", style="dead")
    b.add_part("R_V_0.25W_2.54", 25.4, 15.24, ref="R2", style="dead")
    b.connect("R1.1", "R2.1", "A")
    b.connect("R1.2", "R2.2", "GND")
    return b


class CopperIslands(unittest.TestCase):
    def test_island_takes_the_net_of_the_pin_on_it_and_joins_pins(self):
        b = two_resistors()
        x1, y1 = b.pin_pos("R1.1")
        x2, y2 = b.pin_pos("R2.1")
        # one long island under both "A" pins (below the GND pins' row would short; keep it on y of A pins only)
        b.islands.append(Island((x1 + x2) / 2, y1 - 1.27, x2 - x1 + 2.0, 2.0))
        b.touch()
        self.assertEqual(b.island_net(0), "A")
        joined = b.components()["A"]
        self.assertTrue(any({"R1.1", "R2.1"} <= set(g) for g in joined))
        self.assertNotIn("A", {w[0] for w in b.airwires()})

    def test_island_bridging_two_nets_is_a_drc_error(self):
        b = two_resistors()
        x, y = b.pin_pos("R1.1")
        b.islands.append(Island(x + 1.27, y, 5.08, 5.08))      # covers R1.1 and R1.2
        b.touch()
        errs = [i for i in drc.run_drc(b) if i.severity == "error"]
        self.assertTrue(any("island #1" in i.message for i in errs))

    def test_round_and_oval_shapes_and_save(self):
        b = Board(30, 30)
        b.islands = [Island(10, 10, 4, 4, "round"), Island(20, 10, 6, 3, "round"), Island(15, 20, 6, 3, "rect")]
        b.touch()
        cu = [s for s in b.copper() if s.tag[0] == "isl"]
        self.assertEqual(cu[0].kind, "cap")
        self.assertAlmostEqual(cu[0].r, 2.0)
        self.assertAlmostEqual(cu[1].r, 1.5)
        self.assertAlmostEqual(abs(cu[1].x2 - cu[1].x1), 3.0)
        self.assertEqual(cu[2].kind, "poly")
        self.assertEqual(len(cu[2].pts), 8)                    # corners cut at 45 degrees
        self.assertTrue(all(s.net.startswith("~") for s in cu))   # nothing touches them
        c = Board.from_dict(b.to_dict())
        self.assertEqual([i.to_dict() for i in c.islands], [i.to_dict() for i in b.islands])

    def test_router_treats_islands_as_copper(self):
        b = two_resistors()
        b.islands.append(Island(17.78, 15.24, 3.0, 12.0))      # a wall between the two parts
        b.touch()
        AutoRouter(b).route_all()
        for t in b.traces:
            for i in range(len(t.points) - 1):
                from solotrace.geom import Cap
                seg = Cap(t.points[i][0], t.points[i][1], t.points[i + 1][0], t.points[i + 1][1], t.widths[i] / 2)
                self.assertGreaterEqual(shape_dist(seg, b.islands[0].copper()), b.settings.clearance - 1e-6)

    def test_islands_in_gerber_svg_and_laser(self):
        b = two_resistors()
        b.islands.append(Island(30, 25, 4, 4, "round"))
        b.touch()
        self.assertIn("X30000000Y25000000D03", gerber.copper_layer(b))
        self.assertIn('stroke-width="4.0000"', render.to_svg(b))
        job = laser.generate(b, laser.LaserOptions(mode="positive"))
        hit = [s for s in job.segments if abs(s[1] - 25) < 0.05]
        self.assertTrue(any(s[0] < 29 and s[2] > 31 for s in hit))


    def test_manhattan_example_needs_no_traces(self):
        b = demos.manhattan_amp()
        self.assertEqual(b.traces, [])
        self.assertEqual(b.airwires(), [])                       # every net is joined by islands or the fill
        self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.")
        self.assertEqual(b.drills(), [])                         # deadbug: nothing to drill


class GroundFill(unittest.TestCase):
    def test_islands_keep_the_gap_and_ground_is_not_routed(self):
        b = demos.rf_oscillator()
        p = islands.plan(b)
        self.assertEqual(p.ground, "GND")
        cu = b.copper()
        for i, g in p.grow.items():
            s = cu[i]
            for j, o in enumerate(cu):
                if o.net == s.net:
                    continue
                d = shape_dist(s, o)
                if o.net == "GND":
                    self.assertGreaterEqual(d - g, p.gap - 1e-6)
                elif j in p.grow:
                    self.assertGreaterEqual(d - g - p.grow[j], p.gap - 1e-6)
        r = AutoRouter(b).route_all()
        self.assertFalse(any(t.net == "GND" for t in b.traces))
        self.assertNotIn("GND", r.failed_nets)
        self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.")

    def test_cut_off_ground_pin_shows_a_rubber_band_and_floating_fill_is_removed(self):
        b = demos.flasher_555()
        b.settings.island_mode = True
        islands.make_pads_deadbug(b)
        AutoRouter(b).route_all()
        p = islands.plan(b)
        self.assertGreater(p.dropped, 0)
        self.assertEqual(islands.floating_fill(b), [])
        b.settings.island_drop_floating = False
        b.touch()
        self.assertTrue(islands.floating_fill(b))
        self.assertTrue(any(i.kind == "islands" for i in drc.run_drc(b)))

    def test_fill_in_every_output(self):
        b = demos.rf_oscillator()
        AutoRouter(b).route_all()
        g = gerber.copper_layer(b)
        self.assertIn("%LPC*%", g)
        self.assertIn("%LPD*%", g)
        svg = render.to_svg(b)
        self.assertIn('fill="#ffffff"', svg)            # the cuts are drawn in board colour
        pdf = render.to_pdf(b)
        self.assertTrue(pdf.startswith(b"%PDF"))
        job = laser.generate(b, laser.LaserOptions(mode="negative"))
        self.assertIn("Ground fill on net GND", job.gcode)
        # negative mode on a filled board burns far less than on the same board without the fill
        b2 = Board.from_dict(b.to_dict())
        b2.settings.island_mode = False
        b2.touch()
        self.assertLess(job.burn_length, laser.generate(b2, laser.LaserOptions(mode="negative")).burn_length / 2)
        iso = laser.generate(b, laser.LaserOptions(mode="isolation"))
        self.assertAlmostEqual(iso.burn_length, job.burn_length, delta=1.0)

    def test_gerber_reads_back_with_independent_reader(self):
        try:
            import gerbonara  # noqa: F401
        except Exception:
            self.skipTest("gerbonara is not installed")
        from gerbonara import GerberFile
        b = demos.rf_oscillator()
        GerberFile.from_string(gerber.copper_layer(b))

    def test_off_by_default_and_saved(self):
        b = demos.flasher_555()
        self.assertIsNone(islands.plan(b))
        b.settings.island_mode = True
        b.settings.island_net = "VCC"
        c = Board.from_dict(b.to_dict())
        self.assertEqual(islands.ground_net(c), "VCC")


if __name__ == "__main__":
    unittest.main()
