# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Geometry, library, board model, DRC, placer and router."""
import json
import math
import unittest

import _path  # noqa: F401
from solotrace import demos, library
from solotrace.board import Board, MAX_WIDTH, MIN_WIDTH, clamp_width, current_capacity
from solotrace.drc import run_drc
from solotrace.geom import Cap, chamfer_polyline, merge_intervals, octi_path, shape_dist, subtract_intervals, turn_angle
from solotrace.placer import auto_place
from solotrace.router import AutoRouter


def corners_ok(board, limit=46.0):
    for t in board.traces:
        for i in range(1, len(t.points) - 1):
            if turn_angle(t.points[i - 1], t.points[i], t.points[i + 1]) > limit:
                return False
    return True


class Geometry(unittest.TestCase):
    def test_chamfer_removes_right_angles(self):
        pts = chamfer_polyline([(0, 0), (10, 0), (10, 10), (0, 10)], 1.5)
        for i in range(1, len(pts) - 1):
            self.assertLessEqual(turn_angle(pts[i - 1], pts[i], pts[i + 1]), 46.0)

    def test_octi_path_only_45_steps(self):
        for p0, p1 in (((0, 0), (7, 3)), ((0, 0), (-4, 9)), ((2, 2), (2, 9))):
            path = octi_path(p0, p1, True)
            for a, b in zip(path, path[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                self.assertTrue(abs(dx) < 1e-9 or abs(dy) < 1e-9 or abs(abs(dx) - abs(dy)) < 1e-9)

    def test_intervals(self):
        self.assertEqual(merge_intervals([(0, 1), (1, 2), (3, 4)]), [(0, 2), (3, 4)])
        self.assertEqual(subtract_intervals([(0, 10)], [(2, 3), (5, 6)]), [(0, 2), (3, 5), (6, 10)])

    def test_shape_dist(self):
        a = Cap(0, 0, 0, 0, 1.0)
        b = Cap(5, 0, 5, 0, 1.0)
        self.assertAlmostEqual(shape_dist(a, b), 3.0, places=6)


class Library(unittest.TestCase):
    def test_count_and_ids(self):
        n = len(library.BUILTIN)
        self.assertTrue(30 <= n <= 100, n)  # the brief: about 30 to 100 parts
        self.assertEqual(len({d.id for d in library.BUILTIN.values()}), n)

    def test_required_parts_exist(self):
        for pid in ("DIP4_N", "DIP8_N", "DIP16_N", "TO220_3", "TO92", "C_ELEC_5", "R_0.25W_10.16"):
            self.assertIn(pid, library.BUILTIN)

    def test_pads_keep_clearance_in_every_style(self):
        for pid, d in library.BUILTIN.items():
            for style in ("tht", "dead", "mixed"):
                b = Board(300, 300)
                b.defs[pid] = d
                pl = b.add_part(pid, 100, 100, style=style)
                shapes = []
                for p in d.pads:
                    sh, _dr, _c = b.pad_copper(pl.ref, p.name)
                    shapes.extend((p.name, s) for s in sh)
                for i, (na, a) in enumerate(shapes):
                    for nb, c in shapes[i + 1:]:
                        if na != nb:
                            self.assertGreaterEqual(shape_dist(a, c), 0.25, "%s %s pads %s/%s" % (pid, style, na, nb))

    def test_deadbug_has_no_hole_and_more_copper(self):
        b = Board(100, 100)
        b.add_part("DIP8_N", 20, 50, ref="U1")
        b.add_part("DIP8_N", 60, 50, ref="U2", style="dead")
        sh1, dr1, _ = b.pad_copper("U1", "1")
        sh2, dr2, _ = b.pad_copper("U2", "1")
        self.assertIsNotNone(dr1)
        self.assertIsNone(dr2)
        def area(shapes):
            tot = 0.0
            for s in shapes:
                if s.kind == "cap":
                    tot += math.pi * s.r ** 2 + 2 * s.r * math.hypot(s.x2 - s.x1, s.y2 - s.y1)
                else:
                    p = s.pts
                    tot += abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1]
                                   for i in range(len(p)))) / 2.0
            return tot

        a1, a2 = area(sh1), area(sh2)
        self.assertGreater(a2, a1 * 1.5)

    def test_kicad_import(self):
        text = '''(footprint "Test" (pad "1" thru_hole circle (at 0 0) (size 1.7 1.7) (drill 1.0) (layers *.Cu))
                  (pad "2" thru_hole oval (at 2.54 0) (size 1.7 2.4) (drill 1.0) (layers *.Cu))
                  (pad "3" smd rect (at 5 0) (size 1 1) (layers F.Cu)))'''
        d = library.import_kicad_mod(text)
        self.assertEqual([p.name for p in d.pads], ["1", "2"])


class BoardModel(unittest.TestCase):
    def test_width_limits(self):
        self.assertEqual(clamp_width(0.01), MIN_WIDTH)
        self.assertEqual(clamp_width(99), MAX_WIDTH)
        self.assertEqual(MAX_WIDTH, 10.0)
        self.assertGreater(current_capacity(10.0), current_capacity(1.0))

    def test_no_90_degree_trace_possible(self):
        b = Board(100, 100)
        b.add_part("R_0.25W_10.16", 10, 10, ref="R1")
        b.add_part("R_0.25W_10.16", 10, 40, ref="R2")
        b.connect("R1.1", "R2.1", "A")
        t = b.add_trace("A", [(10, 10), (30, 10), (30, 40), (10, 40)], 1.0)
        self.assertTrue(corners_ok(b))
        self.assertGreater(len(t.points), 4)

    def test_per_segment_width(self):
        b = demos.flasher_555()
        AutoRouter(b).route_all()
        t = b.traces[0]
        b.set_segment_width(t, 0, 7.5)
        self.assertEqual(t.widths[0], 7.5)
        b.set_segment_width(t, 0, 50)
        self.assertEqual(t.widths[0], 10.0)

    def test_save_load_roundtrip(self):
        b = demos.regulator_7805()
        AutoRouter(b).route_all()
        c = Board.from_dict(json.loads(json.dumps(b.to_dict())))
        self.assertEqual(c.to_dict(), b.to_dict())

    def test_netlist_roundtrip(self):
        b = demos.flasher_555()
        c = Board()
        c.import_netlist(b.export_netlist())
        self.assertEqual(sorted(c.nets), sorted(b.nets))
        self.assertEqual(sorted(c.parts), sorted(b.parts))
        b2 = demos.regulator_7805()
        c2 = Board()
        c2.import_netlist(b2.export_netlist())
        self.assertEqual(c2.nets["VRAW"].cls, "High current")

    def test_connect_merges_nets(self):
        b = Board(100, 100)
        for i, x in enumerate((10, 30, 50, 70)):
            b.add_part("R_0.25W_10.16", x, 10, ref="R%d" % (i + 1))
        b.connect("R1.1", "R2.1")
        b.connect("R3.1", "R4.1")
        n = b.connect("R2.1", "R3.1")
        self.assertEqual(len([x for x in b.nets.values() if len(x.pins) > 1]), 1)
        self.assertEqual(len(n.pins), 4)


class Drc(unittest.TestCase):
    def test_detects_sharp_corner(self):
        b = Board(100, 100)
        b.add_part("R_0.25W_10.16", 10, 10, ref="R1")
        b.add_part("R_0.25W_10.16", 10, 40, ref="R2")
        b.connect("R1.1", "R2.1", "A")
        b.add_trace("A", [(10, 10), (30, 10), (30, 40), (10, 40)], 1.0, chamfer=False)
        kinds = {i.kind for i in run_drc(b)}
        self.assertIn("corner", kinds)

    def test_detects_clearance(self):
        b = Board(100, 100)
        b.add_part("R_0.25W_10.16", 10, 10, ref="R1")
        b.add_part("R_0.25W_10.16", 10, 20, ref="R2")
        b.connect("R1.1", "R1.2", "A")
        b.connect("R2.1", "R2.2", "B")
        b.add_trace("A", [(10, 10), (10, 14)], 1.0)
        b.add_trace("B", [(10, 20), (10, 14.4)], 1.0)
        self.assertIn("clearance", {i.kind for i in run_drc(b)})

    def test_flags_unrouted(self):
        self.assertIn("unrouted", {i.kind for i in run_drc(demos.flasher_555())})


class PlaceAndRoute(unittest.TestCase):
    def check_routed(self, b):
        res = AutoRouter(b).route_all()
        self.assertTrue(res.complete, res.summary())
        errs = [i for i in run_drc(b) if i.severity == "error"]
        self.assertEqual(errs, [], [str(e) for e in errs])
        self.assertTrue(corners_ok(b))
        self.assertTrue(b.is_fully_routed())
        return res

    def test_555(self):
        self.check_routed(demos.flasher_555())

    def test_regulator_with_wide_traces_and_deadbug(self):
        b = demos.regulator_7805()
        res = self.check_routed(b)
        self.assertTrue(any(w >= 3.0 for t in b.traces for w in t.widths))
        self.assertGreater(res.routed_nets, 0)

    def test_placer_reduces_crossings_and_does_not_overlap(self):
        import random
        b = demos.flasher_555()
        rnd = random.Random(5)
        for pl in b.parts.values():
            pl.x = round(rnd.uniform(8, 50) / 1.27) * 1.27
            pl.y = round(rnd.uniform(8, 40) / 1.27) * 1.27
        r = auto_place(b, time_limit=15)
        self.assertLessEqual(r.crossings_after, r.crossings_before)
        self.assertEqual(r.overlaps_after, 0)

    def test_locked_parts_do_not_move(self):
        b = demos.flasher_555()
        b.parts["U1"].locked = True
        before = (b.parts["U1"].x, b.parts["U1"].y, b.parts["U1"].rot)
        auto_place(b, time_limit=3)
        self.assertEqual(before, (b.parts["U1"].x, b.parts["U1"].y, b.parts["U1"].rot))

    def test_manual_traces_survive_autoroute(self):
        b = demos.flasher_555()
        t = b.add_trace("GND", [b.pin_pos("C1.2"), (b.pin_pos("C1.2")[0], b.pin_pos("C1.2")[1] + 3)], 1.2, manual=True)
        AutoRouter(b).route_all()
        self.assertIn(t, b.traces)


if __name__ == "__main__":
    unittest.main()
