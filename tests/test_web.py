# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.6.0: the web UI. The headless editor session, the local server, and (when Playwright and its
Chromium are installed) the page itself in a real browser."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

import _path  # noqa: F401

from solotrace import demos
from solotrace.board import Board
from solotrace.web import session as websession
from solotrace.web.session import Session
from solotrace.web.server import make_server

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def _no_proxy_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


class HeadlessSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = self.tmp
        websession.CONFIG_FILE = os.path.join(self.tmp, "config.json")
        websession.AUTOSAVE_FILE = os.path.join(self.tmp, "autosave.solotrace")

    def test_session_does_not_need_tkinter(self):
        code = ("import builtins, sys\n"
                "real = builtins.__import__\n"
                "def imp(name, *a, **k):\n"
                "    if name == 'tkinter' or name.startswith('tkinter.') or name == '_tkinter':\n"
                "        raise ImportError('no tkinter here')\n"
                "    return real(name, *a, **k)\n"
                "builtins.__import__ = imp\n"
                "sys.path.insert(0, %r)\n"
                "from solotrace.web.session import Session\n"
                "from solotrace.web.server import make_server\n"
                "from solotrace import demos\n"
                "s = Session(demos.DEMOS['555 LED flasher']())\n"
                "import json; json.dumps(s.state()); json.dumps(s.menu(10, 10)); json.dumps(s.dialog('laser'))\n"
                "print('tk' in ','.join(sorted(sys.modules)), 'OK')\n" % SRC)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK", r.stdout)
        self.assertNotIn("tkinter", r.stdout)

    def test_scene_is_json_and_in_paint_order(self):
        s = Session(demos.DEMOS["555 LED flasher"]())
        st = s.state()
        txt = json.dumps(st)
        self.assertGreater(len(txt), 1000)
        sc = st["scene"]
        self.assertEqual((sc["w"], sc["h"]), (70.0, 50.0))
        self.assertEqual(len(sc["parts"]), 8)
        self.assertTrue(sc["airwires"])
        self.assertTrue(all(s_["k"] in ("c", "p") for s_ in sc["copper"]))
        self.assertEqual(sc["tool"], "select")
        self.assertIn("WORK IN PROGRESS", sc["wip"])
        self.assertEqual(st["panel"][0]["t"], "head")

    def test_place_wire_trace_and_undo(self):
        s = Session(Board(60, 40, "t"))
        s.cmd("arm", {"pid": "R_0.25W_10.16"})
        self.assertEqual(s.tool, "place")
        self.assertIn("ghost", s.scene())
        s.cmd("press", {"x": 10, "y": 20, "scale": 8})
        s.cmd("press", {"x": 40, "y": 20, "scale": 8})
        self.assertEqual(sorted(s.board.parts), ["R1", "R2"])
        s.cmd("tool", {"name": "wire"})
        p1 = s.board.pin_pos("R1.2")
        p2 = s.board.pin_pos("R2.1")
        s.cmd("press", {"x": p1[0], "y": p1[1]})
        s.cmd("press", {"x": p2[0], "y": p2[1]})
        self.assertEqual(len(s.board.nets), 1)
        net = next(iter(s.board.nets))
        s.cmd("tool", {"name": "trace"})
        s.cmd("press", {"x": p1[0], "y": p1[1]})
        s.cmd("press", {"x": p2[0], "y": p2[1]})
        self.assertEqual([t.net for t in s.board.traces], [net])
        self.assertEqual(s.scene()["unrouted"], 0)
        n_undo = len(s.undo)
        s.cmd("undo", {})
        self.assertEqual(len(s.undo), n_undo - 1)
        self.assertEqual(s.board.traces, [])
        s.cmd("redo", {})
        self.assertEqual(len(s.board.traces), 1)
        # select the trace and change its width from the panel
        mid = ((p1[0] + p2[0]) / 2, p1[1])
        s.cmd("tool", {"name": "select"})
        s.cmd("press", {"x": mid[0], "y": mid[1], "scale": 8})
        self.assertIn("trace", s.sel)
        panel = s.panel()
        slider = next(w for w in panel if w["t"] == "slider")
        s.cmd(slider["cmd"], dict(slider["args"], value=1.5, scope="trace"))
        self.assertEqual(s.board.traces[0].widths[0], 1.5)

    def test_drag_moves_a_part_and_menu_matches_the_hit(self):
        s = Session(demos.DEMOS["555 LED flasher"]())
        ref = "R1"
        px = s.board.parts[ref].x
        x0, y0, x1, y1 = s.board.court_rect(ref)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out = s.cmd("press", {"x": cx, "y": cy, "scale": 8})
        self.assertEqual(s.sel, {"part": ref})
        self.assertEqual(out["drag"]["ref"], ref)
        s.cmd("drag_to", {"x": cx + 5.08, "y": cy})
        self.assertAlmostEqual(s.board.parts[ref].x, px + 5.08, places=6)
        m = s.menu(cx + 5.08, cy)
        self.assertTrue(m[0]["head"])
        self.assertIn(ref, m[0]["label"])
        labels = [i.get("label") for i in m]
        self.assertIn("Delete part", labels)
        # nothing under the mouse: the board menu
        m = s.menu(1, 1)
        self.assertIn("Auto-route", [i.get("label") for i in m])

    def test_panels_for_every_kind_of_selection(self):
        b = demos.DEMOS["555 LED flasher"]()
        from solotrace.router import AutoRouter, RouteOptions
        AutoRouter(b, RouteOptions(time_limit=30.0)).route_all()
        s = Session(b)
        kinds = []
        s.sel = {"part": "U1"}; kinds.append(s.panel())
        s.sel = {"part": "U1", "pin": "1"}; kinds.append(s.panel())
        s.sel = {"trace": 0, "seg": 0}; kinds.append(s.panel())
        s.sel = {"net": next(iter(b.nets))}; kinds.append(s.panel())
        if b.jumpers:
            s.sel = {"jumper": 0}; kinds.append(s.panel())
        s.cmd("add_island", {"x": 5, "y": 5}); kinds.append(s.panel())
        s.cmd("via_at", {"x": 8, "y": 8}); kinds.append(s.panel())
        for k in kinds:
            json.dumps(k)
            self.assertEqual(k[0]["t"], "head")
        for name in ("settings", "new", "islands", "backplane", "footprint", "laser"):
            d = s.dialog(name)
            json.dumps(d)
            self.assertTrue(d["fields"])

    def test_dialogs_apply_and_validate(self):
        s = Session(demos.DEMOS["555 LED flasher"]())
        d = s.dialog("settings")
        vals = {f["k"]: f["value"] for f in d["fields"]}
        vals["width"] = 5
        self.assertIn("Width", s.cmd("apply_settings", {"values": vals})["error"])
        vals["width"] = 90
        vals["name"] = "Bigger"
        self.assertIsNone(s.cmd("apply_settings", {"values": vals})["error"])
        self.assertEqual((s.board.width, s.board.name), (90.0, "Bigger"))
        d = s.dialog("backplane")
        vals = {f["k"]: f["value"] for f in d["fields"]}
        vals["on"] = True
        self.assertIsNone(s.cmd("apply_backplane", {"values": vals})["error"])
        self.assertTrue(s.board.settings.backplane)
        self.assertIsNotNone(s.scene()["plane"])
        d = s.dialog("islands")
        vals = {f["k"]: f["value"] for f in d["fields"] if f["type"] != "head"}
        vals["on"] = True
        vals["dead"] = True
        self.assertIsNone(s.cmd("apply_islands", {"values": vals})["error"])
        self.assertTrue(s.board.settings.island_mode)
        sc = s.scene()
        self.assertIsNotNone(sc["fill"])
        self.assertIsNone(s.cmd("new_board", {"values": {"name": "n", "w": 50, "h": 40}})["error"])
        self.assertEqual(s.board.width, 50)

    def test_exports_and_laser_preview(self):
        b = demos.DEMOS["555 LED flasher"]()
        from solotrace.router import AutoRouter, RouteOptions
        AutoRouter(b, RouteOptions(time_limit=30.0)).route_all()
        s = Session(b)
        for kind, head in (("gerber", b"PK"), ("pdf", b"%PDF"), ("svg", b"<"), ("netlist", b""), ("bom", b""), ("board", b"{")):
            name, data, mime = s.export(kind)
            self.assertTrue(data.startswith(head), kind)
            self.assertTrue(name, kind)
        job, o, probs = s.laser_job({"mode": "isolation", "feed": 1500}, "bottom")
        self.assertEqual(probs, [])
        png = s.laser_preview_png(job)
        self.assertTrue(png.startswith(b"\x89PNG"))
        name, data, mime = s.laser_extra("frame", {})
        self.assertIn("G0", data.decode())

    def test_jobs_run_in_the_background(self):
        s = Session(demos.DEMOS["555 LED flasher"]())
        s.cmd("auto_route", {})
        self.assertIsNotNone(s.job)
        t = time.time()
        while s.job is not None and time.time() - t < 120:
            s.state()
            time.sleep(0.1)
        self.assertIsNone(s.job)
        self.assertEqual(s.board.unrouted_count(), 0)
        self.assertTrue(s.undo)

    def test_parts_mode_and_custom_part(self):
        s = Session(Board(50, 50, "x"))
        s.set_parts_mode("tht")
        names = [g["name"] for g in s.library_tree()]
        self.assertIn("Chips (DIP)", names)
        self.assertNotIn("SMD", names)
        s.set_parts_mode("smd")
        self.assertEqual([g["name"] for g in s.library_tree()], ["SMD"])
        self.assertEqual(websession.load_config().get("parts_mode"), "smd")
        self.assertTrue(s.library_tree("sot-23")[0]["subs"])
        s.set_parts_mode("tht")
        import solotrace.library as library
        old = library.user_part_dir
        library.user_part_dir = lambda: os.path.join(self.tmp, "parts")
        try:
            err = s.save_part({"name": "My relay", "prefix": "K", "pads": "1 0 0 round 2 2 1\n2 5.08 0 round 2 2 1"})
            self.assertIsNone(err)
            self.assertIn("USER_My_relay", s.lib)
            self.assertIn("name x y", s.save_part({"name": "bad", "pads": "1 x"}) or "")
            self.assertTrue(s.library_tree("relay"))
        finally:
            library.user_part_dir = old


class LocalServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = cls.tmp
        websession.CONFIG_FILE = os.path.join(cls.tmp, "config.json")
        websession.AUTOSAVE_FILE = os.path.join(cls.tmp, "autosave.solotrace")
        cls.session = Session(demos.DEMOS["555 LED flasher"]())
        cls.srv = make_server(cls.session, 0)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:%d" % cls.port
        cls.opener = _no_proxy_opener()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def get(self, path, headers=None):
        req = urllib.request.Request(self.url + path, headers=headers or {})
        with self.opener.open(req, timeout=30) as r:
            return r.status, r.headers, r.read()

    def post(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with self.opener.open(req, timeout=60) as r:
            return r.status, r.headers, r.read()

    def test_page_and_static_files(self):
        st, h, body = self.get("/")
        self.assertEqual(st, 200)
        self.assertIn(b"WORK IN PROGRESS", body)
        for f in ("app.js", "style.css", "icon.png"):
            st, h, body = self.get("/static/" + f)
            self.assertEqual(st, 200, f)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/static/../session.py")
        self.assertEqual(cm.exception.code, 404)

    def test_only_the_local_page_is_served(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/api/state", {"Host": "evil.example.com"})
        self.assertEqual(cm.exception.code, 403)

    def test_state_cmd_menu_and_export(self):
        st, h, body = self.get("/api/state")
        j = json.loads(body)
        self.assertEqual(j["state"]["scene"]["name"], "555 LED flasher")
        st, h, body = self.post("/api/cmd", {"name": "tool", "args": {"name": "wire"}})
        j = json.loads(body)
        self.assertEqual(j["state"]["scene"]["tool"], "wire")
        st, h, body = self.post("/api/cmd", {"name": "no_such_command", "args": {}})
        self.assertIn("Unknown command", json.loads(body)["out"]["error"])
        st, h, body = self.get("/api/menu?x=1&y=1")
        self.assertIn("Auto-route", [i.get("label") for i in json.loads(body)["menu"]])
        st, h, body = self.get("/api/library?q=dip+8")
        self.assertTrue(json.loads(body)["tree"])
        st, h, body = self.get("/api/part?pid=DIP8_N")
        self.assertEqual(json.loads(body)["pins"], 8)
        st, h, body = self.get("/api/export/gerber")
        self.assertTrue(body.startswith(b"PK"))
        self.assertIn("attachment", h["Content-Disposition"])
        st, h, body = self.post("/api/laser/preview", {"values": {"mode": "negative"}, "layer": "bottom"})
        self.assertIn("png", json.loads(body))
        st, h, body = self.post("/api/laser/gcode", {"kind": "board", "values": {}, "layer": "bottom"})
        self.assertIn(b"G21", body)
        st, h, body = self.get("/api/ping")
        self.assertEqual(json.loads(body), {"ok": True})


class CliFallback(unittest.TestCase):
    """Since 0.8.0 the browser editor is the default; the tkinter window is `main.py desktop`."""

    def _run(self, args):
        code = ("import builtins, sys\n"
                "real = builtins.__import__\n"
                "def imp(name, *a, **k):\n"
                "    if name == 'tkinter' or name.startswith('tkinter.') or name == '_tkinter':\n"
                "        raise ImportError('no tkinter here')\n"
                "    return real(name, *a, **k)\n"
                "builtins.__import__ = imp\n"
                "sys.path.insert(0, %r)\n"
                "import solotrace.web.server as srv\n"
                "srv.serve = lambda session, **kw: print('WEB', session.board.name) or 0\n"
                "from solotrace.cli import main\n"
                "sys.exit(main(%r))\n" % (SRC, args))
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)

    def test_default_is_the_browser_editor_without_touching_tkinter(self):
        r = self._run(["--no-browser"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("WEB Untitled", r.stdout)
        self.assertNotIn("tkinter", r.stderr)

    def test_desktop_falls_back_to_the_browser_without_tkinter(self):
        r = self._run(["desktop", "--no-browser"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("WEB Untitled", r.stdout)
        self.assertIn("tkinter", r.stderr)


class BrowserPage(unittest.TestCase):
    """The real page in Chromium, only when Playwright is installed (it is not a requirement)."""

    def test_page_routes_a_board_in_a_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright is not installed")
        tmp = tempfile.mkdtemp()
        websession.CONFIG_DIR = tmp
        websession.CONFIG_FILE = os.path.join(tmp, "config.json")
        websession.save_config({"accepted": websession.__version__.split("-")[0].rsplit(".", 1)[0]})
        session = Session(demos.DEMOS["555 LED flasher"]())
        srv = make_server(session, 0)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        try:
            with sync_playwright() as p:
                try:
                    b = p.chromium.launch(args=["--no-proxy-server"])
                except Exception as exc:          # noqa: BLE001
                    self.skipTest("no Chromium for Playwright: %s" % exc)
                pg = b.new_page(viewport={"width": 1100, "height": 760})
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto("http://127.0.0.1:%d/" % port)
                pg.wait_for_timeout(800)
                self.assertTrue(pg.evaluate("document.getElementById('modal-back').hidden"))
                pg.click("#btn-route")
                for _ in range(300):
                    pg.wait_for_timeout(300)
                    if pg.evaluate("document.getElementById('job').hidden") and session.job is None:
                        break
                self.assertEqual(session.board.unrouted_count(), 0)
                self.assertEqual(pg.evaluate("document.getElementById('route-badge').textContent"), "all routed")
                pg.click("#mode-btn")
                pg.wait_for_timeout(400)
                self.assertEqual(session.parts_mode, "smd")
                self.assertEqual(pg.evaluate("document.getElementById('mode-text').textContent"), "Through-hole parts")
                pg.mouse.click(550, 400, button="right")
                pg.wait_for_timeout(400)
                self.assertFalse(pg.evaluate("document.getElementById('menu-popup').hidden"))
                self.assertEqual(errors, [])
                b.close()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
