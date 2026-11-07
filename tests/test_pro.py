# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.5.0: SMD (Pro) parts, thermal reliefs, the back-side ground plane with vias, and the new
router / placer options."""
import unittest

import _path  # noqa: F401

from solotrace import demos, drc, gerber, islands, laser, plane, render
from solotrace.board import Board, Island, Settings, Via, current_capacity, width_for_current
from solotrace.geom import shape_dist
from solotrace.library import BUILTIN, SMD_GROUP, form_factor, pinout_presets
from solotrace.parts import pad_copper
from solotrace.placer import auto_place
from solotrace.router import AutoRouter, RouteOptions


class SmdLibrary(unittest.TestCase):
    def test_every_smd_part_keeps_the_copper_gap(self):
        smd = [p for p in BUILTIN.values() if p.kind == "smd"]
        self.assertGreaterEqual(len(smd), 40)
        for p in smd:
            shapes = [pad_copper(p, pd, "tht", 0.0, 0.0)[0][0] for pd in p.pads]
            for i in range(len(shapes)):
                for j in range(i + 1, len(shapes)):
                    self.assertGreaterEqual(shape_dist(shapes[i], shapes[j]), 0.3 - 1e-9, "%s pads %s/%s" % (
                        p.id, p.pads[i].name, p.pads[j].name))
            self.assertEqual(form_factor(p)[0], SMD_GROUP)
            self.assertTrue(form_factor(p)[1], p.id)
            self.assertAlmostEqual(p.pads[0].x, 0.0)                     # pin 1 at the origin
            self.assertAlmostEqual(p.pads[0].y, 0.0)
            # no drill, whatever the pad style says
            for pd in p.pads:
                for style in ("tht", "dead", "mixed"):
                    self.assertIsNone(pad_copper(p, pd, style, 0.0, 0.0)[1])

    def test_sourced_dimensions_spot_check(self):
        soic = BUILTIN["SMD_SOIC8"]
        xs = sorted({round(pd.x, 3) for pd in soic.pads})
        self.assertAlmostEqual(xs[1] - xs[0], 5.4)                        # TI D: 5.4 mm between rows
        self.assertEqual((soic.pads[0].w, soic.pads[0].h), (1.55, 0.6))
        sot = BUILTIN["SMD_SOT23"]
        self.assertAlmostEqual(abs(sot.pads[1].x - sot.pads[0].x), 1.9)   # 0.95 mm pitch, pins 1 and 2
        chip = BUILTIN["SMD_CHIP_0805"]
        self.assertAlmostEqual(chip.pads[1].x - chip.pads[0].x, 0.9 + 1.3)  # Vishay wave: gap 0.9, pad 1.3 long
        self.assertEqual([n for n, _ in pinout_presets(BUILTIN["SMD_SOIC8"])][0], "555-style timer")

    def test_smd_parts_sit_on_the_copper_side(self):
        b = Board(40, 30)
        pl = b.add_part("SMD_SOIC8", 15.24, 15.24, ref="U1")
        self.assertTrue(pl.flip)                                          # mirrored in the component-side view
        tht = b.add_part("R_0.25W_10.16", 5.08, 5.08, ref="R1")
        self.assertFalse(tht.flip)
        self.assertEqual(b.drills(), [(5.08, 5.08, 0.9), (15.24, 5.08, 0.9)])   # only the resistor has holes
        files = gerber.make_files(b)
        self.assertTrue(any(k.endswith("Silkscreen_Bottom.gbo") for k in files))
        top = [k for k in files if k.endswith("Silkscreen_Top.gto")][0]
        self.assertNotIn("Legend,Bot", files[top])
        self.assertIn("Legend,Bot", files[[k for k in files if k.endswith(".gbo")][0]])
        # an SMD board routes and passes DRC with the default router setting
        bb = demos.smd_regulator()
        r = AutoRouter(bb, RouteOptions(algorithm=bb.settings.router)).route_all()
        self.assertEqual(r.failed_nets, [])
        self.assertEqual(drc.summarize(drc.run_drc(bb)), "No problems found.")
        c = Board.from_dict(bb.to_dict())
        self.assertTrue(all(c.parts[r].flip for r in c.parts if c.is_smd(r)))


class ThermalReliefs(unittest.TestCase):
    def test_reliefs_ring_and_spokes_on_every_ground_pad(self):
        b = demos.rf_oscillator()
        AutoRouter(b).route_all()
        p = islands.plan(b, full=True)
        gnd_pads = [s for s in b.copper() if s.tag and s.tag[0] == "pad" and s.net == "GND"]
        self.assertEqual(p.reliefs, len(gnd_pads))
        rings = [c for c in p.cut if c.tag and c.tag[0] == "relief"]
        spokes = [c for c in p.fat if c.tag and c.tag[0] == "spoke"]
        self.assertEqual(len(rings), len(gnd_pads))
        self.assertGreaterEqual(len(spokes), 2 * len(gnd_pads))
        self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.")
        # every ground pin still counts as on the fill (through its spokes)
        self.assertEqual([w for w in b.airwires() if w[0] == "GND"], [])
        # deadbug ovals get their spokes on the sides and ends, never diagonal
        for sp in spokes:
            dx, dy = sp.x2 - sp.x1, sp.y2 - sp.y1
            self.assertTrue(abs(dx) < 1e-6 or abs(dy) < 1e-6, "spoke %s is diagonal" % (sp.tag,))

    def test_solid_and_heavy_overrides_and_current_sizing(self):
        b = demos.manhattan_amp()
        b.parts["C3"].ground_contact = "solid"
        b.parts["R2"].ground_contact = "heavy"
        b.touch()
        p = islands.plan(b, full=True)
        tags = {c.tag[1] for c in p.cut if c.tag and c.tag[0] == "relief"}
        cu = b.copper()
        self.assertFalse(any(cu[i].tag[:2] == ("pad", "C3") for i in tags))
        heavy = [c for c in p.fat if c.tag and c.tag[0] == "spoke" and cu[c.tag[1]].tag[:2] == ("pad", "R2")]
        normal = [c for c in p.fat if c.tag and c.tag[0] == "spoke" and cu[c.tag[1]].tag[:2] == ("pad", "Q1")]
        self.assertAlmostEqual(heavy[0].r, 2 * normal[0].r)
        s = Settings()
        self.assertAlmostEqual(islands.relief_current(s), 4 * current_capacity(0.8), places=6)
        s.relief_amps = 20.0
        self.assertGreaterEqual(islands.relief_current(s), 20.0)
        self.assertAlmostEqual(current_capacity(width_for_current(3.0)), 3.0, delta=0.15)
        b.settings.relief_amps = 20.0
        b.touch()
        self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.")
        # a ground net wider than its reliefs can carry gets a warning
        b.settings.relief_amps = 0.0
        b.settings.relief_width = 0.3
        b.set_net_class("GND", "High current")                            # 5 mm: about 15 A
        b.touch()
        self.assertTrue(any(i.kind == "relief" for i in drc.run_drc(b)))

    def test_reliefs_in_every_output(self):
        b = demos.manhattan_amp()
        g = gerber.copper_layer(b)
        self.assertIn("%LPC*%", g)
        svg = render.to_svg(b)
        self.assertIn('fill="#ffffff"', svg)
        job = laser.generate(b, laser.LaserOptions(mode="negative"))
        b2 = Board.from_dict(b.to_dict())
        b2.settings.relief = False
        b2.touch()
        job2 = laser.generate(b2, laser.LaserOptions(mode="negative"))
        self.assertGreater(job.burn_length, job2.burn_length)            # the rings are burned too


class BackPlane(unittest.TestCase):
    def test_plane_joins_drilled_ground_pins_and_vias(self):
        b = demos.flasher_555()
        b.settings.backplane = True
        b.parts["C1"].style = "dead"
        b.touch()
        self.assertEqual([w[3:] for w in b.airwires() if w[0] == "GND"], [("U1.1", "C1.2")])
        b.vias.append(Via(17.78 + 5.0, 22.86))                            # near C1 but not touching its pad
        b.touch()
        self.assertEqual(len([w for w in b.airwires() if w[0] == "GND"]), 1)
        AutoRouter(b).route_all()
        self.assertEqual([w for w in b.airwires()], [])
        self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.")
        c = Board.from_dict(b.to_dict())
        self.assertEqual(len(c.vias), 1)
        self.assertTrue(c.settings.backplane)

    def test_plane_outputs_and_checks(self):
        b = demos.flasher_555()
        b.settings.backplane = True
        b.touch()
        p = plane.plan(b)
        gnd_holes = [h for h in plane.holes(b) if h[3] == "GND"]
        self.assertEqual(p.reliefs, len(gnd_holes))
        self.assertEqual(p.antipads, len(plane.holes(b)) - len(gnd_holes))
        files = gerber.make_files(b)
        top = [k for k in files if k.endswith("Copper_Top.gtl")][0]
        self.assertIn("Copper,L1,Top", files[top])
        self.assertIn("%LPC*%", files[top])
        self.assertIn("Copper,L2,Bot", files[[k for k in files if k.endswith(".gbl")][0]])
        self.assertIn("<svg", render.to_svg(b, layer="top"))
        self.assertTrue(render.to_pdf(b, layer="top").startswith(b"%PDF"))
        job = laser.generate(b, laser.LaserOptions(mirror=True), layer="top")
        self.assertIn("Not mirrored", job.gcode)
        self.assertEqual(len(plane.countersink_list(b)), p.antipads)
        self.assertEqual(plane.fmt_freq(plane.stitch_frequency(10.0)), "715 MHz")
        # a via inside a non-ground hole's clearance ring is an error
        x, y = b.pin_pos("R1.2")
        b.vias.append(Via(x + 1.27, y))
        b.touch()
        self.assertTrue(any(i.kind == "plane" and i.severity == "error" for i in drc.run_drc(b)))

    def test_stitching_and_pin_vias(self):
        b = demos.rf_oscillator()
        b.settings.backplane = True
        b.touch()
        AutoRouter(b).route_all()
        pins = plane.via_at_ground_pins(b)
        self.assertTrue(pins)
        for x, y in pins:
            self.assertTrue(plane.via_fits(b, x, y, join_pad=True))
            b.vias.append(Via(x, y))
        b.touch()
        self.assertEqual([w for w in b.airwires() if w[0] == "GND"], [])
        pts = plane.stitch_points(b, 10.0)
        self.assertGreater(len(pts), 5)
        for x, y in pts:
            self.assertTrue(plane.via_fits(b, x, y))
            b.vias.append(Via(x, y))
        b.touch()
        self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.")
        self.assertEqual(len(b.drills()), len(b.vias))                    # deadbug board: only the vias are drilled


class RouterOptions(unittest.TestCase):
    def test_negotiated_router_converges_without_errors(self):
        for fn in (demos.flasher_555, demos.power_oscillator, demos.rf_oscillator):
            b = fn()
            r = AutoRouter(b, RouteOptions(algorithm="negotiated")).route_all()
            self.assertEqual(r.failed_nets, [], fn.__name__)
            self.assertEqual(b.unrouted_count(), 0, fn.__name__)
            self.assertEqual(drc.summarize(drc.run_drc(b)), "No problems found.", fn.__name__)
            self.assertTrue(any("negotiated" in m for m in r.messages) or r.jumpers >= 0)

    def test_auto_tries_negotiated_first_and_keeps_the_best(self):
        b = demos.power_oscillator()
        r = AutoRouter(b, RouteOptions(algorithm="auto")).route_all()
        self.assertEqual(b.unrouted_count(), 0)
        self.assertTrue(any("best of the tries" in m for m in r.messages))

    def test_routability_placer_runs_and_overlaps_nothing(self):
        b = demos.logic_dip14()
        r = auto_place(b, time_limit=6, seed=3, mode="routability")
        self.assertEqual(r.overlaps_after, 0)
        self.assertLess(r.crossings_after, r.crossings_before)
        for ref in b.parts:
            x0, y0, x1, y1 = b.court_rect(ref)
            self.assertTrue(x0 >= 0 and y0 >= 0 and x1 <= b.width and y1 <= b.height, ref)


if __name__ == "__main__":
    unittest.main()
