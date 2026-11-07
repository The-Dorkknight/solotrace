# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.8.0: moving a part after the traces are laid. Traces never follow a part, so a pad can land on
another net's trace; that must be reported at once (live while dragging, and on drop), and Check must
agree with a brute-force comparison of every pair of copper shapes."""
import itertools
import os
import random
import tempfile
import unittest

import _path  # noqa: F401

from solotrace.board import Board
from solotrace.drc import after_part_edit, body_on_traces, part_collisions, run_drc
from solotrace.geom import shape_dist
from solotrace.web import session as websession
from solotrace.web.session import Session

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


def load(name):
    return Board.load(os.path.join(EX, name, name + ".solotrace"))


def brute_force(b):
    """Every pair of copper shapes of different nets closer than the clearance."""
    cu = b.copper()
    clr = b.settings.clearance
    bad = 0
    for x, y in itertools.combinations(cu, 2):
        if x.tag and y.tag and x.tag[0] == "pad" and y.tag[0] == "pad" and x.tag[1:3] == y.tag[1:3]:
            continue
        if x.tag and y.tag and x.tag[0] != "pad" and x.tag[:2] == y.tag[:2]:
            continue
        if x.net is not None and x.net == y.net:
            continue
        if shape_dist(x, y) < clr - 1e-4:
            bad += 1
    return bad


def find_collision_move(b, rnd):
    """Move parts about until one lands on copper of another net; return (ref, old_xy)."""
    for _ in range(200):
        ref = rnd.choice(list(b.parts))
        pl = b.parts[ref]
        old = (pl.x, pl.y)
        b.move_part(ref, pl.x + rnd.choice([-5.08, -2.54, 2.54, 5.08]), pl.y + rnd.choice([-5.08, -2.54, 2.54, 5.08]))
        if part_collisions(b, ref):
            return ref, old
        b.move_part(ref, *old)
    raise AssertionError("no colliding move found")


class MovedParts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = tmp
        websession.CONFIG_FILE = os.path.join(tmp, "config.json")

    def test_check_agrees_with_brute_force_after_random_moves(self):
        rnd = random.Random(7)
        for name in ("555-led-flasher", "5v-regulator", "logic-mix", "xiao-logger-mirrored-oled"):
            for _ in range(4):
                b = load(name)
                for _k in range(3):
                    ref = rnd.choice(list(b.parts))
                    pl = b.parts[ref]
                    b.move_part(ref, pl.x + rnd.uniform(-6, 6), pl.y + rnd.uniform(-6, 6))
                    if rnd.random() < 0.3:
                        b.rotate_part(ref, 90)
                    if rnd.random() < 0.2:
                        b.mirror_part(ref)
                found = [i for i in run_drc(b) if i.kind == "clearance"]
                self.assertEqual(bool(found), bool(brute_force(b)), name)

    def test_a_move_onto_a_trace_is_reported_at_once(self):
        b = load("555-led-flasher")
        ref, _old = find_collision_move(b, random.Random(1))
        issues, msg = after_part_edit(b, ref, "Moved")
        self.assertIn("COLLISION", msg)
        self.assertTrue(any(i.kind == "clearance" and i.severity == "error" for i in issues))
        self.assertIn("Route this part's nets", msg)

    def test_web_drag_reports_and_probe_changes_nothing(self):
        b = load("555-led-flasher")
        rnd = random.Random(2)
        ref, old = find_collision_move(b, rnd)
        target = (b.parts[ref].x, b.parts[ref].y)
        b.move_part(ref, *old)
        s = Session(b)
        rev = s.board.rev
        hits = s.probe_part(ref, *target)
        self.assertTrue(hits)
        self.assertEqual((s.board.parts[ref].x, s.board.parts[ref].y), old)
        self.assertTrue(s.board.rev >= rev)
        x0, y0, x1, y1 = s.board.court_rect(ref)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        s.sel = {"part": ref}
        s.drag = {"ref": ref, "dx": old[0] - cx, "dy": old[1] - cy}
        s.drag_to(cx + target[0] - old[0], cy + target[1] - old[1])
        self.assertAlmostEqual(s.board.parts[ref].x, target[0], places=6)
        self.assertAlmostEqual(s.board.parts[ref].y, target[1], places=6)
        self.assertIn("COLLISION", s.status_text)
        self.assertTrue(s.marks)

    def test_pressing_on_a_trace_with_branches_answers_in_json(self):
        # 0.8.0 fix: the drag description of a trace held Trace objects, so the server could not
        # answer the press and dragging a trace in the web UI did nothing
        import json
        from solotrace.web import api
        b = load("555-led-flasher")
        s = Session(b)
        tr = max(b.traces, key=lambda t: len(t.points))
        i = len(tr.points) // 2
        x = (tr.points[i][0] + tr.points[i - 1][0]) / 2
        y = (tr.points[i][1] + tr.points[i - 1][1]) / 2
        code, data, _t, _n = api.handle(s, "POST", "/api/cmd", None, {"name": "press", "args": {"x": x, "y": y}})
        self.assertEqual(code, 200)
        out = json.loads(data)["out"]
        self.assertIn("trace", out["drag"])

    def test_part_under_the_board_soldered_flat_on_a_trace_is_a_warning(self):
        b = load("xiao-logger-mirrored-oled")
        ref = "DS1"
        self.assertTrue(b.is_mirrored(ref))
        # put the OLED body over a trace of the board, pins clear of it
        t = max(b.traces, key=lambda t: len(t.points))
        a = t.points[len(t.points) // 2]
        x0, y0, x1, y1 = b.court_rect(ref)
        pl = b.parts[ref]
        b.move_part(ref, pl.x + a[0] - (x0 + x1) / 2, pl.y + a[1] - (y0 + y1) / 2)
        on_hdr = body_on_traces(b, ref)
        self.assertTrue(on_hdr)
        self.assertTrue(all(i.severity == "info" for i in on_hdr))     # on header pins: only a note
        b.parts[ref].style = "dead"
        b.touch()
        flat = body_on_traces(b, ref)
        self.assertTrue(any(i.severity == "warn" for i in flat))       # soldered flat: a warning
        self.assertTrue(any(i.kind == "body" for i in run_drc(b)))


if __name__ == "__main__":
    unittest.main()
