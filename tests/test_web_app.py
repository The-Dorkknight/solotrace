# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""0.8.0: the in-browser SoloTrace in docs/app/ (Pyodide, nothing to install).

- docs/app/ must match the source (tools/build_web_app.py --check), so the published page never
  runs older code than the repo;
- the Python in solotrace-py.zip must import and work without tkinter, threads or a server, the
  way it runs in the browser;
- with Playwright, Chromium and a local copy of Pyodide (the npm package, path in the environment
  variable SOLOTRACE_PYODIDE_DIR), the real page is loaded, routes a board and saves it.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import _path  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "docs", "app")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_web_app  # noqa: E402


class BuiltApp(unittest.TestCase):
    def test_docs_app_is_up_to_date(self):
        want = build_web_app.files()
        for name, data in want.items():
            path = os.path.join(APP, name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), data, "docs/app/%s is stale: run python3 tools/build_web_app.py" % name)

    def test_page_loads_pyodide_from_a_pinned_cdn_and_only_same_site_overrides(self):
        html = build_web_app.page().decode()
        self.assertIn("https://cdn.jsdelivr.net/npm/pyodide@0.29.5/", html)
        self.assertIn('p.charAt(0) === "/" && p.charAt(1) !== "/"', html)     # no ?pyodide=//evil.example
        self.assertNotIn("/static/", html)

    def test_zip_runs_without_tkinter_threads_or_a_server(self):
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(io.BytesIO(build_web_app.code_zip())) as z:
            names = z.namelist()
            self.assertNotIn("solotrace/app.py", names)
            self.assertIn("solotrace/web/api.py", names)
            z.extractall(tmp)
        code = ("import builtins, sys, threading\n"
                "real = builtins.__import__\n"
                "def imp(name, *a, **k):\n"
                "    if name.split('.')[0] in ('tkinter', '_tkinter', 'socket', 'http'):\n"
                "        raise ImportError('not in the browser: ' + name)\n"
                "    return real(name, *a, **k)\n"
                "builtins.__import__ = imp\n"
                "def no_threads(self): raise RuntimeError(\"can't start new thread\")\n"
                "threading.Thread.start = no_threads\n"
                "sys.path.insert(0, %r)\n"
                "import os; os.environ['HOME'] = %r\n"
                "from solotrace.web.session import Session\n"
                "from solotrace.web import api\n"
                "from solotrace import demos\n"
                "s = Session(demos.DEMOS['555 LED flasher'](), sync_mode=True)\n"
                "seen = []\n"
                "s.progress_hook = lambda l, m, f: seen.append(m)\n"
                "c, d, t, n = api.handle(s, 'POST', '/api/cmd', None, {'name': 'auto_route', 'args': {}})\n"
                "import json; st = json.loads(d)['state']\n"
                "assert st['scene']['unrouted'] == 0 and st['job'] is None, st['scene']['status']\n"
                "assert seen, 'no progress reported'\n"
                "c, d, t, n = api.handle(s, 'GET', '/api/export/gerber', {}, None)\n"
                "assert d[:2] == b'PK' and n.endswith('.zip')\n"
                "s.cmd('demo', {'name': 'RF oscillator (ground fill)'})\n"
                "c, d, t, n = api.handle(s, 'GET', '/api/state', {}, None)\n"
                "assert json.loads(d)['state']['scene']['fill_ready'] and json.loads(d)['browser_only']\n"
                "print('OK', len(seen))\n" % (tmp, tmp))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                           env=dict(os.environ, SOLOTRACE_ROUTE_ATTEMPTS="1"))
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("OK", r.stdout)


class InTheBrowser(unittest.TestCase):
    def test_the_real_page_in_chromium(self):
        pyo = os.environ.get("SOLOTRACE_PYODIDE_DIR")
        if not pyo or not os.path.exists(os.path.join(pyo, "pyodide.js")):
            self.skipTest("set SOLOTRACE_PYODIDE_DIR to an unpacked npm pyodide@0.29.5 package")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright is not installed")
        site = tempfile.mkdtemp()
        os.makedirs(os.path.join(site, "solotrace"))
        os.symlink(APP, os.path.join(site, "solotrace", "app"))
        os.symlink(pyo, os.path.join(site, "pyodide"))

        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=site))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d/solotrace/app/?pyodide=/pyodide/" % srv.server_address[1]
        try:
            with sync_playwright() as p:
                try:
                    b = p.chromium.launch(args=["--no-proxy-server"])
                except Exception as exc:          # noqa: BLE001
                    self.skipTest("no Chromium for Playwright: %s" % exc)
                pg = b.new_page(viewport={"width": 1200, "height": 800})
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto(url)
                for _ in range(300):
                    pg.wait_for_timeout(200)
                    if pg.evaluate("!document.getElementById('loading') && typeof S !== 'undefined' && S !== null"):
                        break
                self.assertTrue(pg.evaluate("S !== null"))
                self.assertIn("in your browser", pg.evaluate("document.getElementById('wip').textContent"))
                pg.check("#dc-chk")
                pg.click("#dc-ok")
                pg.wait_for_timeout(300)
                pg.evaluate("api('demo', {name: '555 LED flasher'})")
                pg.wait_for_timeout(800)
                pg.click("#btn-route")
                for _ in range(600):
                    pg.wait_for_timeout(300)
                    if pg.evaluate("S && S.unrouted === 0 && document.getElementById('job').hidden"):
                        break
                self.assertEqual(pg.evaluate("S.unrouted"), 0)
                with pg.expect_download() as dl:
                    pg.keyboard.press("Control+s")
                self.assertTrue(dl.value.suggested_filename.endswith(".solotrace"))
                self.assertEqual(errors, [])
                b.close()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
