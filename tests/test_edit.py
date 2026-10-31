# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Trace tidy (straight pad exits, centred ends), dragging, trimming, splitting, new parts."""
import unittest

import _path  # noqa: F401

from solotrace import library
from solotrace.board import Board
from solotrace.drc import run_drc
from solotrace.geom import dist, max_turn
from solotrace.router import AutoRouter
from solotrace.tidy import (apply_drag, drag_segment, split_trace, tidy_trace, tidy_traces, trim_segment,
                            violation_set)


def two_transistors():
    """The layout from the user's photo: two TO-92s over two upright resistors."""
    b = Board(45, 35, "photo")
    b.add_part("TO92", 5.08, 27.94, ref="Q1")
    b.add_part("TO92", 30.48, 27.94, ref="Q2")
    b.add_part("R_0.25W_10.16", 5.08, 7.62, rot=90, ref="R1")
    b.add_part("R_0.25W_10.16", 30.48, 7.62, rot=90, ref="R2")
    b.connect("Q1.1", "R1.2", "A")
    b.connect("Q2.1", "R2.2", "B")
    b.connect("Q1.2", "R2.1", "C")
    b.connect("R1.1", "Q2.2", "D")
    return b


def octilinear(pts):
    for i in range(len(pts) - 1):
        dx, dy = abs(pts[i + 1][0] - pts[i][0]), abs(pts[i + 1][1] - pts[i][1])
        if dx > 1e-6 and dy > 1e-6 and abs(dx - dy) > 1e-6:
            return False
    return True


class Tidy(unittest.TestCase):
    def test_wide_trace_leaves_pads_straight_and_lands_centred(self):
        b = two_transistors()
        AutoRouter(b).route_all()
        b.set_net_trace_width("C", 2.0)
        tidy_traces(b)
        t = [t for t in b.traces if t.net == "C"][0]
        q1, r2 = b.pin_pos("Q1.2"), b.pin_pos("R2.1")
        ends = {t.points[0], t.points[-1]}
        self.assertIn(q1, ends)
        self.assertIn(r2, ends)
        for end, nxt in ((t.points[0], t.points[1]), (t.points[-1], t.points[-2])):
            dx, dy = abs(nxt[0] - end[0]), abs(nxt[1] - end[1])
            self.assertTrue(dx < 1e-6 or dy < 1e-6, "exit is not straight: %s -> %s" % (end, nxt))
            self.assertGreaterEqual(dist(end, nxt), 2.0)
        self.assertLessEqual(max_turn(t.points), 46.0)
        self.assertEqual([i for i in run_drc(b) if i.severity == "error"], [])

    def test_tidy_never_adds_new_clearance_problems(self):
        for w in (1.5, 3.0, 5.0):
            b = two_transistors()
            AutoRouter(b).route_all()
            b.set_net_trace_width("C", w)
            before = {t.net: violation_set(b, t.net, t.points, max(t.widths)) for t in b.traces}
            tidy_traces(b)
            for t in b.traces:
                saved = b.traces
                b.traces = [x for x in saved if x is not t]
                b.touch()
                now = violation_set(b, t.net, t.points, max(t.widths))
                b.traces = saved
                b.touch()
                nets_now = {k[0] for k in now}
                nets_before = {k[0] for k in before[t.net]}
                self.assertTrue(nets_now <= nets_before, (w, t.net, now, before[t.net]))
                self.assertLessEqual(max_turn(t.points), 46.0)

    def test_router_output_is_tidy_on_demo(self):
        from solotrace import demos
        b = demos.regulator_7805()
        AutoRouter(b).route_all()
        self.assertEqual([i for i in run_drc(b) if i.severity == "error"], [])


class Editing(unittest.TestCase):
    def test_drag_keeps_45_degree_rules(self):
        pts = [(0.0, 0.0), (10.0, 0.0), (15.0, 5.0), (25.0, 5.0)]
        for off in ((0.0, 3.0), (0.0, -2.5), (4.0, 4.0)):
            for i in range(3):
                new = drag_segment(pts, i, off, 0.635)
                self.assertEqual(new[0], pts[0])
                self.assertEqual(new[-1], pts[-1])
                self.assertTrue(octilinear(new), (i, off, new))
                self.assertLessEqual(max_turn(new), 90.0 + 1e-6)

    def test_apply_drag_chamfers_and_marks_manual(self):
        b = two_transistors()
        AutoRouter(b).route_all()
        t = [t for t in b.traces if t.net == "D"][0]
        ti = b.traces.index(t)
        si = max(range(len(t.points) - 1), key=lambda k: dist(t.points[k], t.points[k + 1]))
        base, basew = list(t.points), list(t.widths)
        apply_drag(b, ti, si, base, basew, (0.0, 2.0))
        t = b.traces[ti]
        self.assertTrue(t.manual)
        self.assertLessEqual(max_turn(t.points), 46.0)
        self.assertEqual(t.points[0], base[0])
        self.assertEqual(t.points[-1], base[-1])
        self.assertEqual(len(t.widths), len(t.points) - 1)

    def test_trim_and_split(self):
        b = two_transistors()
        AutoRouter(b).route_all()
        ti = max(range(len(b.traces)), key=lambda i: len(b.traces[i].points))
        n = len(b.traces)
        t = b.traces[ti]
        si = max(range(len(t.points) - 1), key=lambda k: dist(t.points[k], t.points[k + 1]))
        a, c = t.points[si], t.points[si + 1]
        split_trace(b, ti, si, ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2))
        self.assertEqual(len(b.traces), n + 1)
        self.assertEqual(b.unrouted_count(), 0)
        trim_segment(b, ti, len(b.traces[ti].points) - 2)
        self.assertGreater(b.unrouted_count(), 0)
        b2 = two_transistors()
        AutoRouter(b2).route_all()
        t = [t for t in b2.traces if len(t.points) >= 4][0]
        n2 = len(b2.traces)
        self.assertEqual(trim_segment(b2, b2.traces.index(t), 1), 2)       # a middle section: two pieces stay
        self.assertEqual(len(b2.traces), n2 + 1)

    def test_tidy_single_trace_is_idempotent(self):
        b = two_transistors()
        AutoRouter(b).route_all()
        b.set_net_trace_width("C", 2.0)
        t = [t for t in b.traces if t.net == "C"][0]
        tidy_trace(b, t)
        once = list(t.points)
        tidy_trace(b, t)
        self.assertEqual(once, t.points)


class NewParts(unittest.TestCase):
    def test_standing_resistors_and_groups(self):
        for pid in ("R_V_0.25W_2.54", "R_V_0.5W_5.08", "R_V_1W_5.08"):
            self.assertIn(pid, library.BUILTIN)
            self.assertEqual(library.form_factor(library.BUILTIN[pid]),
                             ("Resistors, diodes & inductors", "Resistors standing"))
        groups = {library.form_factor(d)[0] for d in library.BUILTIN.values()}
        self.assertNotIn("My parts", groups)
        for g in groups:
            self.assertIn(g, library.FORM_GROUPS)
        self.assertIn(("Resistors, diodes & inductors", "Inductors"), {library.form_factor(d) for d in library.BUILTIN.values()})


if __name__ == "__main__":
    unittest.main()


class RigidAndLabels(unittest.TestCase):
    def osc(self, rigid):
        b = Board(60, 45, "osc")
        b.add_part("TERM_5.08_2", 25.4, 38.1, ref="J1")
        b.add_part("C_FILM_5", 15.24, 27.94, rot=90, ref="C1")
        b.add_part("TO220_3", 10.16, 10.16, rot=90, ref="Q1")
        b.add_part("DIP8_N", 30.48, 30.48, ref="U1")
        b.settings.classes["High current"] = 3.0
        b.connect("J1.1", "C1.2", "GND")
        b.connect("C1.2", "Q1.3", "GND")
        b.connect("U1.1", "C1.2", "GND")
        b.set_net_class("GND", "High current")
        if rigid:
            b.set_rigid("Q1.3", "J1.1")
        return b

    def test_rigid_link_is_one_direct_trace_and_others_branch(self):
        b = self.osc(True)
        AutoRouter(b).route_all()
        self.assertEqual(b.unrouted_count(), 0)
        q, j = b.pin_pos("Q1.3"), b.pin_pos("J1.1")
        trunk = [t for t in b.traces if t.rigid]
        self.assertTrue(trunk)
        ends = [t.points[0] for t in trunk] + [t.points[-1] for t in trunk]
        self.assertTrue(any(dist(e, q) < 1.0 for e in ends))      # the trunk starts on Q1's pad
        self.assertTrue(any(dist(e, j) < 1.0 for e in ends))      # and ends on J1's pad
        # no other trace starts at Q1: C1 and U1 join the trunk, not Q1's pad
        self.assertFalse([t for t in b.traces if not t.rigid and
                          min(dist(t.points[0], q), dist(t.points[-1], q)) < 1.0])
        self.assertEqual([i for i in run_drc(b) if i.severity == "error"], [])

    def test_rigid_links_and_labels_survive_save_and_edits(self):
        b = self.osc(True)
        b.parts["Q1"].pin_labels = library.pinout_presets(library.BUILTIN["TO220_3"])[0][1]
        AutoRouter(b).route_all()
        b2 = Board.from_dict(b.to_dict())
        self.assertEqual(b2.nets["GND"].links, [["Q1.3", "J1.1"]])
        self.assertEqual(b2.parts["Q1"].pin_labels, {"1": "B", "2": "C", "3": "E"})
        self.assertTrue(any(t.rigid for t in b2.traces))
        b2.disconnect("J1.1")
        self.assertEqual(b2.nets["GND"].links, [])
        self.assertTrue(b2.airwires())
        b3 = self.osc(True)
        air = b3.airwires()
        self.assertIn(("GND", b3.pin_pos("Q1.3"), b3.pin_pos("J1.1"), "Q1.3", "J1.1"), air)

    def test_presets_and_defaults(self):
        for pid, want in (("TO92", "E B C"), ("TO220_3", "B C E"), ("DIP4_N", "A K E C"), ("TO247", "G D S")):
            names = [" ".join(lab[p.name] for p in library.BUILTIN[pid].pads) for _n, lab in
                     library.pinout_presets(library.BUILTIN[pid])]
            self.assertIn(want, names)
        self.assertEqual(library.default_pin_labels(library.BUILTIN["D_DO41_10.16"]), {"1": "K", "2": "A"})
        self.assertEqual(library.default_pin_labels(library.BUILTIN["C_ELEC_5"]), {"1": "+", "2": "-"})
        self.assertEqual(library.parse_pin_labels(library.BUILTIN["TO92"], "e, b c"), {"1": "e", "2": "b", "3": "c"})
        self.assertEqual(library.parse_pin_labels(library.BUILTIN["TERM_5.08_2"], "+ -"), {"1": "+", "2": "-"})

    def test_to92_is_d_shaped(self):
        from solotrace import render
        b = Board(20, 20)
        b.add_part("TO92", 5, 5, ref="Q1")
        segs = render.part_segments(b, "Q1")
        ys = [y for s in segs for y in (s[1], s[3])]
        flat = [s for s in segs if abs(s[1] - s[3]) < 1e-9 and abs(s[1] - min(ys)) < 1e-9]
        self.assertEqual(len(flat), 1)                       # one straight flat face
        self.assertGreater(len(segs), 10)                    # and a curved back


class CutAndJumpers(unittest.TestCase):
    def test_cut_between_two_points_keeps_the_rest(self):
        from solotrace.board import Trace
        from solotrace.tidy import cut_between
        b = Board(50, 50)
        b.traces.append(Trace("N", [(0.0, 0.0), (10.0, 0.0), (15.0, 5.0), (25.0, 5.0)], [1.0, 2.0, 3.0]))
        b.traces.append(Trace("N", [(0.0, 10.0), (20.0, 10.0)], [1.0]))
        self.assertEqual(cut_between(b, 0, (18.0, 5.1), (4.0, 0.2)), 2)     # order of the clicks does not matter
        pieces = [t for t in b.traces if t.points[0][1] < 9]
        self.assertEqual(pieces[0].points, [(0.0, 0.0), (4.0, 0.0)])
        self.assertEqual(pieces[1].points, [(18.0, 5.0), (25.0, 5.0)])
        self.assertEqual(pieces[1].widths, [3.0])
        self.assertTrue(any(t.points == [(0.0, 10.0), (20.0, 10.0)] for t in b.traces))   # other trace untouched

    def test_jumpers_can_be_switched_off_globally_and_per_net(self):
        from solotrace import demos
        b = demos.regulator_7805()
        AutoRouter(b).route_all()
        self.assertTrue(b.jumpers)                         # this layout needs jumpers
        b2 = demos.regulator_7805()
        b2.settings.allow_jumpers = False
        AutoRouter(b2).route_all()
        self.assertEqual(b2.jumpers, [])
        b3 = demos.regulator_7805()
        for n in b3.nets.values():
            n.jumpers_ok = False
        AutoRouter(b3).route_all()
        self.assertEqual(b3.jumpers, [])
        b4 = Board.from_dict(b3.to_dict())
        self.assertFalse(any(n.jumpers_ok for n in b4.nets.values()))
        self.assertTrue(Board.from_dict(b2.to_dict()).settings.allow_jumpers is False)

    def test_branches_join_existing_copper_instead_of_running_over_it(self):
        """The bug from the 0.3.0 photo: a partly routed net was re-routed over its own copper."""
        from solotrace.geom import segments_cross
        b = Board(70, 60, "user 555")
        b.add_part("DIP8_N", 30.48, 40.64, ref="U1")
        b.add_part("TERM_5.08_2", 31.75, 48.26, ref="J1")
        b.add_part("TERM_5.08_2", 31.75, 20.32, ref="J2")
        b.add_part("C_FILM_5", 26.67, 44.45, rot=270, ref="C1")
        b.add_part("R_V_0.25W_2.54", 24.13, 34.29, ref="R3")
        b.add_part("R_V_0.25W_2.54", 41.91, 40.64, ref="R1")
        b.add_part("R_V_0.25W_2.54", 41.91, 38.1, ref="R2")
        b.add_part("TO220_3", 22.86, 27.94, rot=270, ref="Q2")
        b.connect("J1.1", "Q2.1", rigid=True)
        b.connect("J1.1", "C1.1")
        b.connect("J1.2", "J2.2", rigid=True)
        for a_, c_ in (("J1.2", "U1.8"), ("U1.8", "R1.1"), ("U1.8", "U1.4"), ("C1.2", "U1.2"), ("U1.6", "R2.2"),
                       ("R1.2", "R2.1"), ("U1.7", "R2.1"), ("R3.2", "U1.3"), ("R3.1", "Q2.3"), ("Q2.2", "J2.1")):
            b.connect(a_, c_)
        from solotrace.router import RouteOptions
        AutoRouter(b, RouteOptions(attempts=6)).route_all()        # the retries are part of the fix
        self.assertEqual(b.unrouted_count(), 0)
        self.assertEqual([i for i in run_drc(b) if i.severity == "error"], [])
        segs = [(t.net, t.points[i], t.points[i + 1]) for t in b.traces for i in range(len(t.points) - 1)]
        for x in range(len(segs)):
            for y in range(x + 1, len(segs)):
                n1, a1, b1 = segs[x]
                n2, a2, b2 = segs[y]
                if n1 == n2 and len({a1, b1, a2, b2}) == 4:
                    self.assertFalse(segments_cross(a1, b1, a2, b2), (n1, segs[x], segs[y]))


class KeepJoints(unittest.TestCase):
    def _board(self):
        from solotrace.board import Trace
        b = Board(60, 60)
        b.add_part("PAD_2.5", 10.16, 10.16, ref="P1")
        b.add_part("PAD_2.5", 20.32, 20.32, ref="P2")
        b.add_part("PAD_2.5", 30.48, 30.48, ref="P3")
        b.add_part("PAD_2.5", 17.78, 25.4, ref="P4")
        b.connect("P1.1", "P2.1", "G")
        b.connect("P1.1", "P3.1", "G")
        b.connect("P4.1", "P1.1", "G")
        b.traces.append(Trace("G", [(10.16, 10.16), (30.48, 30.48)], [2.0], False))   # joins P2 by running over it
        b.traces.append(Trace("G", [(17.78, 25.4), (17.78, 17.78)], [1.0], False))     # a branch ending on the trunk
        b.touch()
        return b

    def test_tidy_does_not_pull_a_trunk_off_its_branches_or_pads(self):
        """0.3.1 bug: widening a rigid trunk re-shaped it and left branches hanging / a pad cut off."""
        b = self._board()
        self.assertEqual(b.unrouted_count(), 0)
        tidy_trace(b, b.traces[0])
        self.assertEqual(b.unrouted_count(), 0)
        self.assertEqual(b.traces[1].points[-1], (17.78, 17.78))

    def test_the_guard_is_what_keeps_it_joined(self):
        import solotrace.tidy as T
        orig = T.keeps_joints
        T.keeps_joints = lambda *a, **k: True
        try:
            b = self._board()
            tidy_trace(b, b.traces[0])
            self.assertGreater(b.unrouted_count(), 0)          # without the guard the pad is cut off
        finally:
            T.keeps_joints = orig


class Dangling(unittest.TestCase):
    def test_drc_flags_a_trace_end_left_hanging(self):
        from solotrace.board import Trace
        b = Board(40, 40)
        b.add_part("PAD_2.5", 10.16, 10.16, ref="P1")
        b.add_part("PAD_2.5", 30.48, 10.16, ref="P2")
        b.connect("P1.1", "P2.1", "N")
        b.traces.append(Trace("N", [(10.16, 10.16), (30.48, 10.16)], [1.0], True))
        self.assertFalse([i for i in run_drc(b) if i.kind == "dangling"])
        b.traces.append(Trace("N", [(20.32, 10.16), (20.32, 20.32)], [1.0], True))     # a stub off the trace
        self.assertEqual(len([i for i in run_drc(b) if i.kind == "dangling"]), 1)
        for name, fn in (("555", "flasher_555"), ("reg", "regulator_7805")):
            from solotrace import demos
            d = getattr(demos, fn)()
            AutoRouter(d).route_all()
            self.assertFalse([i for i in run_drc(d) if i.kind == "dangling"], name)


class TrimPiece(unittest.TestCase):
    def _b(self):
        from solotrace.board import Trace
        b = Board(60, 60)
        for r, x, y in (("P1", 10.16, 10.16), ("P2", 40.64, 10.16), ("P3", 25.4, 30.48)):
            b.add_part("PAD_2.5", x, y, ref=r)
        b.connect("P1.1", "P2.1", "G")
        b.connect("P1.1", "P3.1", "G")
        b.traces.append(Trace("G", [(10.16, 10.16), (40.64, 10.16)], [1.0]))   # trunk P1 - P2
        b.traces.append(Trace("G", [(25.4, 30.48), (25.4, 10.16)], [1.0]))     # branch from P3 to the trunk
        b.touch()
        return b

    def test_click_removes_only_the_piece_between_joints(self):
        from solotrace.tidy import trim_piece
        b = self._b()
        self.assertEqual(trim_piece(b, 0, (15.0, 10.16)), 1)       # P1 .. branch goes, branch .. P2 stays
        self.assertEqual(len(b.traces), 2)
        rest = [t for t in b.traces if t.points[-1] == (40.64, 10.16)][0]
        self.assertLess(rest.points[0][0], 25.4)                   # still reaches into the branch
        comps = b.components()["G"]
        self.assertEqual(len(comps), 2)                            # P1 alone; P2 and P3 still joined
        self.assertTrue(any(set(g) == {"P2.1", "P3.1"} for g in comps))

    def test_whole_branch_and_joint_clicks(self):
        from solotrace.tidy import trim_piece
        b = self._b()
        self.assertEqual(trim_piece(b, 1, (25.4, 20.0)), 0)        # the branch has no joint in between
        self.assertEqual(len(b.traces), 1)
        b = self._b()
        self.assertIsNone(trim_piece(b, 0, (25.4, 10.16)))         # right on the joint: nothing happens


class TrunkAffinity(unittest.TestCase):
    def _b(self, wb=2.0, wt=1.0):
        from solotrace.board import Trace
        b = Board(60, 60)
        for r, x, y in (("P1", 5.08, 20.32), ("P2", 45.72, 20.32), ("P3", 25.4, 40.64)):
            b.add_part("PAD_2.5", x, y, ref=r)
        b.connect("P1.1", "P2.1", "G")
        b.connect("P1.1", "P3.1", "G")
        b.traces.append(Trace("G", [(5.08, 20.32), (45.72, 20.32)], [wt], False, True))    # rigid trunk
        b.traces.append(Trace("G", [(25.4, 40.64), (25.4, 20.32)], [wb]))                   # branch to its centre
        b.touch()
        return b

    def test_a_wider_branch_stops_inside_the_trunk(self):
        from solotrace.tidy import settle_branch_ends
        b = self._b()
        self.assertEqual(settle_branch_ends(b), 1)
        end = b.traces[1].points[-1]
        self.assertGreater(end[1], 20.32)                         # pulled back towards its pad
        self.assertLessEqual(end[1] - 1.0, 20.32 + 0.5 + 1e-6)    # its round end does not stick out below
        self.assertEqual(b.unrouted_count(), 0)                   # still joined
        self.assertEqual(settle_branch_ends(b), 0)                # and it is stable

    def test_dragging_a_trunk_takes_its_branches_along(self):
        from solotrace.tidy import apply_drag, attached_ends, follow_trunk
        b = self._b(1.0, 1.0)
        trunk = b.traces[0]
        att = attached_ends(b, trunk)
        self.assertEqual(len(att), 1)
        base, basew = list(trunk.points), list(trunk.widths)
        apply_drag(b, 0, 0, base, basew, (0.0, -5.0))             # move the trunk 5 mm down
        follow_trunk(b, b.traces[0], att)
        self.assertEqual(b.unrouted_count(), 0)
        self.assertLess(b.traces[1].points[-1][1], 20.0)          # the branch end went down with it
        self.assertLessEqual(max_turn(b.traces[1].points), 46.0)
