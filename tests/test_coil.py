# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.10.0: the parametric PCB coil generator (inductance engine, both design modes, the placeable part)."""
import math
import unittest

import _path  # noqa: F401

from solotrace import coil
from solotrace.board import Board
from solotrace.drc import run_drc
from solotrace.parts import PartDef
from solotrace.router import AutoRouter, RouteOptions

MU0 = 4e-7 * math.pi


def mohan_uH(dout, din, n):
    """Square spiral, the current-sheet formula of Mohan et al. 1999 (IEEE JSSC 34): the cross-check."""
    davg = (dout + din) / 2.0
    rho = (dout - din) / (dout + din)
    return 1e6 * MU0 * n * n * davg * 1e-3 * (1.27 / 2.0) * (math.log(2.07 / rho) + 0.18 * rho + 0.13 * rho * rho)


class Engine(unittest.TestCase):
    def test_single_bar_matches_rosa(self):
        # a 10 mm bar, 1 mm wide, 35 um thick: Rosa's formula
        l, wt = 10e-3, 1.035e-3
        want = MU0 / (2 * math.pi) * l * (math.log(2 * l / wt) + 0.50049 + wt / (3 * l))
        got = coil.inductance([(0.0, 0.0), (10.0, 0.0)], 1.0, 35.0)
        self.assertAlmostEqual(got / want, 1.0, delta=0.01)

    def test_agrees_with_mohan_on_a_square_coil(self):
        # the shorter side bounds the turns; compare several square coils with the published formula
        for size, n, pitch, track in ((30.0, 6, 1.5, 0.5), (20.0, 5, 1.2, 0.4), (40.0, 8, 2.0, 0.6)):
            pts = coil.spiral_points(size - track, size - track, n, pitch)
            ours = coil.inductance(pts, track, 35.0) * 1e6
            din = size - 2 * (n * pitch - (pitch - track))
            ref = mohan_uH(size, din, n)
            self.assertAlmostEqual(ours / ref, 1.0, delta=0.08, msg="%s %s" % (size, n))

    def test_more_turns_more_inductance(self):
        a = coil.design(30, 20, turns=4)
        b = coil.design(30, 20, turns=8)
        self.assertTrue(a.ok and b.ok)
        self.assertGreater(b.inductance_uH, a.inductance_uH)


class Modes(unittest.TestCase):
    def test_find_turns_for_inductance(self):
        r = coil.design(30, 20, want_uH=1.5)
        self.assertTrue(r.ok)
        self.assertAlmostEqual(r.inductance_uH / 1.5, 1.0, delta=0.05)
        self.assertGreaterEqual(r.gap, 0.4 - 1e-9)

    def test_inductance_for_turns(self):
        r = coil.design(30, 20, turns=6)
        self.assertTrue(r.ok)
        self.assertEqual(r.turns, 6)
        self.assertGreaterEqual(r.gap, 0.4 - 1e-9)
        self.assertGreater(r.inductance_uH, 0.1)

    def test_resonance_capacitor(self):
        r = coil.design(30, 20, want_uH=2.0, freq_MHz=13.56)
        c = 1.0 / ((2 * math.pi * 13.56e6) ** 2 * r.inductance_uH * 1e-6) * 1e12
        self.assertAlmostEqual(r.cap_pF, c, places=3)

    def test_errors_are_sentences(self):
        self.assertFalse(coil.design(5, 5, turns=3).ok)
        self.assertIn("too small", coil.design(5, 5, turns=3).summary())
        self.assertFalse(coil.design(30, 20, turns=200).ok)
        self.assertFalse(coil.design(30, 20).ok)
        with self.assertRaises(ValueError):
            coil.design_from_values({"mode": "uh", "width": "abc", "height": "20", "uh": "1"})
        with self.assertRaises(ValueError):
            coil.design_from_values({"mode": "turns", "width": "30", "height": "20", "turns": "2.5"})

    def test_values_helper_both_modes(self):
        a = coil.design_from_values({"mode": "uh", "width": "30", "height": "20", "uh": "1,5"})
        b = coil.design_from_values({"mode": "turns", "width": "30", "height": "20", "turns": "6"})
        self.assertTrue(a.ok and b.ok)
        self.assertEqual(b.turns, 6)


class Cli(unittest.TestCase):
    def test_cli_both_modes_and_the_error(self):
        import contextlib
        import io
        from solotrace import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["coil", "--width", "30", "--height", "20", "--uh", "1.5"]), 0)
            self.assertEqual(cli.main(["coil", "--width", "30", "--height", "20", "--turns", "6"]), 0)
            self.assertEqual(cli.main(["coil", "--width", "30", "--height", "20"]), 2)
        self.assertIn("estimated inductance", out.getvalue())


class Part(unittest.TestCase):
    def part(self):
        return coil.coil_part(coil.design(30, 20, want_uH=1.5))

    def test_part_shape(self):
        p = self.part()
        self.assertEqual(p.kind, "antenna")
        self.assertEqual(p.ties, [("2", "3")])
        self.assertEqual(len(p.keepouts), 1)
        self.assertEqual(sorted(x.name for x in p.pads), ["1", "2", "3"])
        q = PartDef.from_dict(p.to_dict())
        self.assertEqual(q.ties, p.ties)
        self.assertEqual(q.keepouts, p.keepouts)

    def test_pins_two_and_three_count_as_joined(self):
        from solotrace import library
        p = self.part()
        library.BUILTIN[p.id] = p
        try:
            b = Board(70, 70, "coil")
            b.add_part(p.id, 15, 10, ref="L1")
            b.add_part("DIP8_N", 8, 58, ref="U1")
            b.connect("L1.1", "U1.1", "TXA")
            b.connect("L1.3", "U1.2")
            AutoRouter(b, RouteOptions()).route_all()
            self.assertEqual(b.unrouted_count(), 0)
            self.assertEqual([i for i in run_drc(b) if i.severity == "error"], [])
        finally:
            library.BUILTIN.pop(p.id, None)


if __name__ == "__main__":
    unittest.main()
