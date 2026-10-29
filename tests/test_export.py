# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Gerber, drill, SVG, PDF, BOM and laser G-code."""
import os
import re
import tempfile
import unittest
import zipfile

import _path  # noqa: F401
from solotrace import demos, gerber, laser, render
from solotrace.geom import Cap, shape_dist
from solotrace.router import AutoRouter


def routed():
    b = demos.flasher_555()
    AutoRouter(b).route_all()
    return b


def burn_segments(gcode, width, mirror=True):
    """Re-read burn moves (G1 with S>0) from G-code, back in design coordinates."""
    x = y = 0.0
    s = 0
    segs = []
    for ln in gcode.splitlines():
        ln = ln.split(";")[0].strip()
        m = re.match(r"G([01])\b", ln)
        if not m:
            continue
        nx = re.search(r"X(-?[\d.]+)", ln)
        ny = re.search(r"Y(-?[\d.]+)", ln)
        ns = re.search(r"S(\d+)", ln)
        if ns:
            s = int(ns.group(1))
        x2 = float(nx.group(1)) if nx else x
        y2 = float(ny.group(1)) if ny else y
        if m.group(1) == "1" and s > 0:
            segs.append(((width - x) if mirror else x, y, (width - x2) if mirror else x2, y2))
        x, y = x2, y2
    return segs


class Files(unittest.TestCase):
    def test_render(self):
        b = routed()
        svg = render.to_svg(b, mirror=True)
        self.assertIn('width="70mm"', svg)
        pdf = render.to_pdf(b, mirror=True)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"198.425", pdf)         # 70 mm in points
        csv_text = render.to_bom_csv(b)
        self.assertIn("NE555", csv_text)
        self.assertIn("47k", csv_text)

    def test_gerber_and_drill(self):
        b = routed()
        files = gerber.make_files(b)
        self.assertEqual(len(files), 4)
        cu = [t for n, t in files.items() if n.endswith(".gbl")][0]
        self.assertIn("%TF.FileFunction,Copper,L1,Bot*%", cu)
        self.assertIn("%MOMM*%", cu)
        self.assertTrue(cu.rstrip().endswith("M02*"))
        drl = [t for n, t in files.items() if n.endswith(".drl")][0]
        self.assertEqual(len(re.findall(r"^X[\d.]+Y[\d.]+$", drl, re.M)), len(b.drills()))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "g.zip")
            gerber.write_zip(b, p)
            self.assertEqual(len(zipfile.ZipFile(p).namelist()), 4)

    def test_gerbonara_can_read_if_installed(self):
        try:
            from gerbonara import ExcellonFile, GerberFile
        except ImportError:
            self.skipTest("gerbonara not installed")
        b = routed()
        with tempfile.TemporaryDirectory() as d:
            for name, text in gerber.make_files(b).items():
                path = os.path.join(d, name)
                with open(path, "w") as fh:
                    fh.write(text)
                if name.endswith(".drl"):
                    self.assertEqual(len(ExcellonFile.open(path).objects), len(b.drills()))
                else:
                    g = GerberFile.open(path)
                    self.assertGreater(len(g.objects), 0)
                    if name.endswith(".gbl"):
                        (x0, y0), (x1, y1) = g.bounding_box("mm")
                        self.assertGreaterEqual(x0, 0)
                        self.assertLessEqual(x1, b.width)


class Laser(unittest.TestCase):
    def burned(self, segs, px, py, interval):
        for x1, y1, x2, y2 in segs:
            if abs(y1 - py) <= interval / 2 + 1e-6 and min(x1, x2) <= px <= max(x1, x2):
                return True
        return False

    def check_mode(self, mode, comp, dynamic):
        b = routed()
        o = laser.LaserOptions(mode=mode, trace_comp=comp, dynamic=dynamic, gap=0.6, drill_dots=False)
        job = laser.generate(b, o)
        segs = burn_segments(job.gcode, b.width)
        ys = sorted({round(s[1], 4) for s in segs})
        cu = b.copper()
        import random
        rnd = random.Random(3)
        checked = bad = 0
        for _ in range(2500):
            px, py = rnd.uniform(1, b.width - 1), rnd.uniform(1, b.height - 1)
            near = min(ys, key=lambda v: abs(v - py))
            if abs(near - py) > o.line_interval / 2:
                continue
            d = min(shape_dist(Cap(px, py, px, py, 0), s) for s in cu) - comp
            if abs(d) < 0.12 or (mode == "isolation" and abs(d - o.gap) < 0.12):
                continue
            want = d > 0 if mode == "negative" else (d < 0 if mode == "positive" else 0 < d < o.gap)
            checked += 1
            bad += self.burned(segs, px, near, o.line_interval) != want
        self.assertGreater(checked, 500)
        self.assertEqual(bad, 0, "%s comp=%s dynamic=%s" % (mode, comp, dynamic))

    def test_modes_match_geometry(self):
        for mode in laser.MODES:
            self.check_mode(mode, 0.0, True)
        self.check_mode("negative", -0.1, True)       # thinner copper = wider gaps
        self.check_mode("negative", 0.1, False)       # M3 with run-in/out

    def test_negative_is_bigger_than_isolation(self):
        b = routed()
        neg = laser.generate(b, laser.LaserOptions(mode="negative"))
        iso = laser.generate(b, laser.LaserOptions(mode="isolation"))
        self.assertGreater(neg.burn_length, 3 * iso.burn_length)

    def test_negative_comp_widens_gaps(self):
        b = routed()
        a = laser.generate(b, laser.LaserOptions(mode="negative", trace_comp=0.0))
        c = laser.generate(b, laser.LaserOptions(mode="negative", trace_comp=-0.1))
        self.assertGreater(c.burn_length, a.burn_length)

    def test_gcode_is_sane(self):
        b = routed()
        g = laser.generate(b, laser.LaserOptions(power=50, smax=1000, feed=1200)).gcode
        self.assertIn("G21", g)
        self.assertIn("M4 S0", g)
        self.assertTrue(g.rstrip().endswith("M2 ; end of job"))
        self.assertIn("S500", g)
        self.assertIn("F1200", g)
        self.assertNotIn("S1001", g)
        xs = [float(m) for m in re.findall(r"X(-?[\d.]+)", g)]
        self.assertGreaterEqual(min(xs), -1e-6)
        self.assertLessEqual(max(xs), b.width + 1e-6)
        m3 = laser.generate(b, laser.LaserOptions(dynamic=False)).gcode
        self.assertIn("M3 S0", m3)

    def test_mirror_flag(self):
        b = routed()
        m = laser.generate(b, laser.LaserOptions(mode="isolation", mirror=True))
        n = laser.generate(b, laser.LaserOptions(mode="isolation", mirror=False))
        self.assertNotEqual(m.gcode, n.gcode)
        self.assertAlmostEqual(m.burn_length, n.burn_length, places=3)

    def test_warnings(self):
        b = routed()
        w = laser.validate(b, laser.LaserOptions(feed=20000, power=120))
        self.assertTrue(any("160 mm/s" in x for x in w))
        self.assertTrue(any("Power" in x for x in w))
        big = demos.flasher_555()
        big.width = 500
        self.assertTrue(any("400" in x for x in laser.validate(big, laser.LaserOptions())))

    def test_test_cards_and_frame(self):
        self.assertIn("SPEED/POWER TEST CARD", laser.speed_power_card().gcode)
        self.assertGreater(laser.trace_ladder_card().burn_length, 100)
        f = laser.frame_gcode(routed(), laser.LaserOptions(frame_power=0))
        self.assertIn("S0", f)

    def test_crosshatch_doubles_work(self):
        b = routed()
        one = laser.generate(b, laser.LaserOptions(mode="isolation"))
        two = laser.generate(b, laser.LaserOptions(mode="isolation", crosshatch=True))
        self.assertGreater(two.burn_length, 1.6 * one.burn_length)


if __name__ == "__main__":
    unittest.main()
