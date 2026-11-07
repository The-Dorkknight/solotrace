# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.8.0: the router gives the same result every run, and the polish pass never makes a board worse.

Before 0.8.0 the order in which ripped-up nets were rerouted came from a Python set of net names,
whose order changes from one run of Python to the next, so the same board could come out with two
jumpers one time and four the next. These tests run the router in fresh Pythons with different
hash seeds and compare."""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import _path  # noqa: F401

from solotrace import demos
from solotrace.drc import run_drc
from solotrace.router import AutoRouter, RouteOptions

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def copper(b):
    return sum(math.dist(p, q) for t in b.traces for p, q in zip(t.points, t.points[1:]))


def moved_555():
    """The 555 example with three parts moved: a placement that needs rip-up and jumpers."""
    b = demos.DEMOS["555 LED flasher"]()
    b.traces = [t for t in b.traces if t.manual]
    b.jumpers = []
    for ref, dx, dy in (("R1", 5.08, 0), ("C1", -2.54, 5.08), ("U1", 0, 2.54)):
        if ref in b.parts:
            old = (b.parts[ref].x, b.parts[ref].y)
            b.move_part(ref, old[0] + dx, old[1] + dy)
            if any(i.kind in ("edge", "overlap", "courtyard") for i in run_drc(b)):
                b.move_part(ref, *old)
    return b


class Repeatable(unittest.TestCase):
    def test_same_board_same_result_whatever_the_hash_seed(self):
        f = os.path.join(tempfile.mkdtemp(), "b.solotrace")
        moved_555().save(f)
        code = ("import sys, math, json; sys.path.insert(0, %r)\n"
                "from solotrace.board import Board\n"
                "from solotrace.router import AutoRouter, RouteOptions\n"
                "b = Board.load(%r)\n"
                "AutoRouter(b, RouteOptions(attempts=1, algorithm='classic')).route_all()\n"
                "print(json.dumps([len(b.jumpers), round(sum(math.dist(p, q) for t in b.traces "
                "for p, q in zip(t.points, t.points[1:])), 3), b.unrouted_count()]))\n" % (SRC, f))
        seen = set()
        for seed in ("1", "2", "3"):
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                               env=dict(os.environ, PYTHONHASHSEED=seed))
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            seen.add(r.stdout.strip())
        self.assertEqual(len(seen), 1, seen)


class Polish(unittest.TestCase):
    def test_polish_never_adds_jumpers_or_copper_and_stays_clean(self):
        for name in ("555 LED flasher", "Logic mix"):
            res = {}
            for pol in (False, True):
                b = demos.DEMOS[name]() if name != "555 LED flasher" else moved_555()
                b.traces = [t for t in b.traces if t.manual]
                b.jumpers = []
                AutoRouter(b, RouteOptions(attempts=1, algorithm="classic", polish=pol, smooth=False)).route_all()
                res[pol] = (b.unrouted_count(), len(b.jumpers), copper(b))
                if pol:
                    self.assertFalse([i for i in run_drc(b) if i.severity == "error"], name)
            self.assertLessEqual(res[True][0], res[False][0], name)
            self.assertLessEqual(res[True][1], res[False][1], name)
            if res[True][1] == res[False][1]:
                self.assertLessEqual(res[True][2], res[False][2] + 1e-6, name)

    def test_cancel_during_polish_keeps_every_net(self):
        def fresh():
            b = demos.DEMOS["Logic mix"]()
            b.traces = [t for t in b.traces if t.manual]
            b.jumpers = []
            return b
        b0 = fresh()
        AutoRouter(b0, RouteOptions(attempts=1, algorithm="classic", polish=False, smooth=False)).route_all()
        phase = {"polish": False, "n": 0}

        def progress(msg, frac):
            if msg.startswith("Shortening"):
                phase["polish"] = True

        def cancel():
            if phase["polish"]:
                phase["n"] += 1
            return phase["n"] > 5                  # stop a few nets into the polish
        b = fresh()
        AutoRouter(b, RouteOptions(attempts=1, algorithm="classic", smooth=False), progress, cancel).route_all()
        self.assertTrue(phase["polish"])
        self.assertEqual(b.unrouted_count(), b0.unrouted_count())
        self.assertLessEqual(len(b.jumpers), len(b0.jumpers))


if __name__ == "__main__":
    unittest.main()
