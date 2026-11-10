# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.10.0: PCB trace antennas with copper keep-outs. The formula, the keep-out in DRC / fill / plane / router,
and the save and load round trip."""
import math
import os
import tempfile
import unittest

import _path  # noqa: F401

from solotrace import antennas, gerber, library, render
from solotrace.board import Board
from solotrace.drc import run_drc
from solotrace.geom import Cap
from solotrace.parts import PartDef
from solotrace.router import AutoRouter, RouteOptions


def kinds(board):
    return [i.kind for i in run_drc(board)]


class Parts(unittest.TestCase):
    def test_library_has_them(self):
        for k in antennas.BANDS:
            self.assertIn("ANT_MEANDER_" + k, library.BUILTIN)
            self.assertIn("ANT_WIRE_" + k, library.BUILTIN)
        self.assertIn("ANT_KEEPOUT_20x10", library.BUILTIN)
        self.assertEqual(library.form_factor(library.BUILTIN["ANT_MEANDER_433"]), ("Board bits", "Antennas and keep-outs"))

    def test_copper_length_is_the_formula(self):
        for k, (f, _u, run) in antennas.BANDS.items():
            p = library.BUILTIN["ANT_MEANDER_" + k]
            name, pts, w = p.strokes[0]
            self.assertEqual(name, "1")
            length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            want = antennas.quarter_wave_mm(f) * (1.0 + antennas.TRIM)
            self.assertAlmostEqual(length, want, places=3)
            self.assertAlmostEqual(w, 1.0)

    def test_quarter_wave_numbers(self):
        # free-space quarter wave at 433.92 MHz is 172.8 mm; on FR4 the rule of thumb (eps_eff 2.7) shortens it by sqrt(2.7)
        self.assertAlmostEqual(antennas.free_quarter_wave_mm(433.92), 172.8, delta=0.2)
        self.assertAlmostEqual(antennas.quarter_wave_mm(433.92), 172.8 / math.sqrt(2.7), delta=0.2)

    def test_name_shows_the_real_frequency(self):
        self.assertIn("433.92", library.BUILTIN["ANT_MEANDER_433"].name)

    def test_round_trip(self):
        p = library.BUILTIN["ANT_MEANDER_868"]
        q = PartDef.from_dict(p.to_dict())
        self.assertEqual(len(q.strokes), 1)
        self.assertEqual(q.keepouts, p.keepouts)
        self.assertEqual(q.kind, "antenna")

    def test_not_in_bom_for_keepout_only_whip_is(self):
        b = Board(60, 40, "bom")
        b.add_part("ANT_KEEPOUT_10x10", 10, 10, ref="KO1")
        b.add_part("ANT_MEANDER_433", 30, 5, ref="ANT1")
        b.add_part("ANT_WIRE_433", 50, 30, ref="W1")
        refs = " ".join(" ".join(r) for r in render.bom_rows(b))
        self.assertIn("W1", refs)
        self.assertNotIn("KO1", refs)
        self.assertNotIn("ANT1", refs)


class KeepOut(unittest.TestCase):
    def board(self):
        b = Board(70, 60, "ko")
        b.add_part("ANT_KEEPOUT_20x10", 10, 20, ref="KO1")
        return b

    def test_copper_inside_is_an_error(self):
        b = self.board()
        b.add_part("PAD_2.5", 20, 25, ref="TP1")
        self.assertIn("keepout", kinds(b))

    def test_copper_outside_is_fine(self):
        b = self.board()
        b.add_part("PAD_2.5", 50, 25, ref="TP1")
        self.assertNotIn("keepout", kinds(b))

    def test_fill_and_plane_leave_it_bare(self):
        from solotrace import islands, plane
        b = self.board()
        b.add_part("PAD_2.5", 50, 25, ref="TP1")
        b.settings.island_mode = True
        ip = islands.plan(b, full=True)
        self.assertTrue(any(getattr(c, "tag", None) == ("cut", "keepout") for c in ip.cut))
        b.settings.island_mode = False
        b.settings.backplane = True
        pp = plane.plan(b)
        self.assertTrue(any(getattr(c, "tag", None) == ("cut", "keepout") for c in pp.cut))

    def test_router_keeps_out(self):
        b = Board(80, 60, "route")
        b.add_part("ANT_MEANDER_433", 40, 8, ref="ANT1")
        b.add_part("DIP8_N", 10, 40, ref="U1")
        b.connect("ANT1.1", "U1.1", "RF")
        AutoRouter(b, RouteOptions()).route_all()
        self.assertEqual(b.unrouted_count(), 0)
        self.assertEqual([i for i in run_drc(b) if i.severity == "error"], [])

    def test_save_load(self):
        b = Board(80, 60, "save")
        b.add_part("ANT_MEANDER_2G4", 40, 8, ref="ANT1")
        d = tempfile.mkdtemp()
        fn = os.path.join(d, "a.solotrace")
        b.save(fn)
        c = Board.load(fn)
        self.assertEqual(len(c.keepouts()), 1)
        self.assertTrue(any(s.tag[:2] == ("pad", "ANT1") for s in c.copper()))

    def test_exports_run(self):
        b = Board(80, 60, "exp")
        b.add_part("ANT_MEANDER_868", 40, 8, ref="ANT1")
        self.assertIn("<svg", render.to_svg(b))
        self.assertTrue(render.to_pdf(b).startswith(b"%PDF"))
        self.assertTrue(len(gerber.copper_layer(b)) > 100)


class WebDialogs(unittest.TestCase):
    def setUp(self):
        import json
        from solotrace.web import api, session as websession
        self.json, self.api = json, api
        tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = tmp
        websession.CONFIG_FILE = os.path.join(tmp, "config.json")
        self._parts = library.user_part_dir
        library.user_part_dir = lambda: os.path.join(tmp, "parts")
        self.s = websession.Session(Board(80, 60, "web"))

    def tearDown(self):
        library.user_part_dir = self._parts

    def cmd(self, name, args):
        code, data, _t, _n = self.api.handle(self.s, "POST", "/api/cmd", None, {"name": name, "args": args})
        return self.json.loads(data)["out"]

    def test_coil_dialog_calculate_and_save(self):
        d = self.cmd("dialog", {"name": "coil"})["dialog"]
        self.assertEqual(d["submit"], "save_coil")
        vals = {f["k"]: f["value"] for f in d["fields"] if "k" in f}
        out = self.cmd("coil_calc", {"values": vals})
        self.assertTrue(out["ok"])
        self.assertIn("uH", out["report"])
        out = self.cmd("coil_calc", {"values": dict(vals, width="abc")})
        self.assertFalse(out["ok"])
        out = self.cmd("save_coil", {"values": vals})
        self.assertFalse(out.get("error"))
        self.assertTrue(self.s.armed.startswith("COIL_"))
        self.assertIn(self.s.armed, self.s.lib)

    def test_page_has_resizable_panels_and_the_coil_button(self):
        here = os.path.dirname(os.path.abspath(__file__))
        html = open(os.path.join(here, "..", "src", "solotrace", "web", "static", "index.html"), encoding="utf-8").read()
        for ident in ("split-left", "split-right", "split-prev", "btn-coil", "btn-newfp"):
            self.assertIn('id="%s"' % ident, html)

    def test_scene_carries_the_keep_outs(self):
        self.s.board.add_part("ANT_MEANDER_433", 40, 8, ref="ANT1")
        self.s.board.touch()
        code, data, _t, _n = self.api.handle(self.s, "GET", "/api/state", None, None)
        st = self.json.loads(data)
        scene = st["state"]["scene"]
        self.assertEqual(len(scene["keepouts"]), 1)
        self.assertEqual(scene["keepouts"][0]["ref"], "ANT1")
        self.assertGreater(len(scene["keepouts"][0]["hatch"]), 5)


if __name__ == "__main__":
    unittest.main()
