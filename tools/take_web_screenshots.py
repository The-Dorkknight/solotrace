# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Screenshots of the web UI for the README and the project page (needs Playwright + Chromium).

    python3 tools/take_web_screenshots.py          writes docs/images/web-ui*.webp

It starts the local server on a free port with a throwaway HOME, drives the page in headless
Chromium and saves lossless WebP. Playwright is a development tool only; SoloTrace itself needs
nothing beyond Python.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
OUT = os.path.join(ROOT, "docs", "images")

for k in list(os.environ):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy"):
        del os.environ[k]
home = tempfile.mkdtemp(prefix="solotrace-home-")
os.environ["HOME"] = home
from solotrace import __version__  # noqa: E402
from solotrace.web import session as websession  # noqa: E402
from solotrace.web.session import Session  # noqa: E402
from solotrace.web.server import make_server  # noqa: E402
from solotrace.board import Board  # noqa: E402

websession.CONFIG_DIR = os.path.join(home, ".solotrace")
websession.CONFIG_FILE = os.path.join(websession.CONFIG_DIR, "config.json")
websession.AUTOSAVE_FILE = os.path.join(websession.CONFIG_DIR, "autosave.solotrace")
websession.save_config({"accepted": __version__.split("-")[0].rsplit(".", 1)[0], "parts_mode": "tht"})

from playwright.sync_api import sync_playwright  # noqa: E402


def webp(png_path, out_name):
    subprocess.run(["convert", png_path, "-define", "webp:lossless=true", os.path.join(OUT, out_name)], check=True)
    os.remove(png_path)


def run():
    ex = os.path.join(ROOT, "examples")
    session = Session(Board.load(os.path.join(ex, "555-led-flasher", "555-led-flasher.solotrace")),
                      "/home/matthew/Desktop/solotrace/examples/555-led-flasher/555-led-flasher.solotrace")
    srv = make_server(session, 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-proxy-server"])
        pg = b.new_page(viewport={"width": 1280, "height": 840}, device_scale_factor=1)
        pg.goto("http://127.0.0.1:%d/" % port)
        pg.wait_for_timeout(1200)

        def wait_job():
            for _ in range(400):
                pg.wait_for_timeout(250)
                if pg.evaluate("document.getElementById('job').hidden") and session.job is None:
                    break
        # 1. the routed 555 with a trace selected
        pg.click("#btn-route")
        wait_job()
        pg.wait_for_timeout(300)
        tr = pg.evaluate("(() => { const s = S.copper.filter(q => q.tag && q.tag[0]==='trace' && q.k==='c')[3]; "
                         "const [sx,sy] = w2s((s.a[0]+s.b[0])/2,(s.a[1]+s.b[1])/2); const r = canvas.getBoundingClientRect(); "
                         "return [sx + r.left, sy + r.top]; })()")
        pg.mouse.click(tr[0], tr[1])
        pg.wait_for_timeout(500)
        pg.screenshot(path="/tmp/web-ui.png")
        webp("/tmp/web-ui.png", "web-ui.webp")
        # 2. the right-click menu on a pin
        pg.keyboard.press("Escape")
        pin = pg.evaluate("(() => { const s = S.copper.find(q => q.tag && q.tag[0]==='pad' && q.tag[1]==='U1' && q.tag[2]==='3'); "
                          "const c = s.k==='c' ? s.a : s.pts[0]; const [sx,sy] = w2s(c[0], c[1]); const r = canvas.getBoundingClientRect(); "
                          "return [sx + r.left, sy + r.top]; })()")
        pg.mouse.click(pin[0], pin[1], button="right")
        pg.wait_for_timeout(500)
        pg.screenshot(path="/tmp/web-ui-menu.png")
        webp("/tmp/web-ui-menu.png", "web-ui-menu.webp")
        pg.keyboard.press("Escape")
        # 3. SMD mode on the SMD regulator, copper-side view, a SOT-23 armed
        with session.lock:
            session.load_board(Board.load(os.path.join(ex, "smd-regulator-pro", "smd-regulator-pro.solotrace")),
                               "/home/matthew/Desktop/solotrace/examples/smd-regulator-pro/smd-regulator-pro.solotrace")
        pg.evaluate("getState()")
        pg.wait_for_timeout(600)
        pg.click("#mode-btn")
        pg.wait_for_timeout(500)
        pg.locator("#tree .grp > .row", has_text="SMD").click()
        pg.wait_for_timeout(200)
        pg.locator("#tree .sub > .row", has_text="Transistors").click()
        pg.wait_for_timeout(200)
        pg.locator("#tree .part:visible").first.click()
        pg.wait_for_timeout(400)
        pg.keyboard.press("m")
        pg.wait_for_timeout(300)
        pg.mouse.move(640, 620)
        pg.wait_for_timeout(300)
        pg.screenshot(path="/tmp/web-ui-smd.png")
        webp("/tmp/web-ui-smd.png", "web-ui-smd.webp")
        pg.keyboard.press("Escape")
        pg.keyboard.press("m")
        # 4. modules: the XIAO logger, its OLED mirrored under the board and selected
        with session.lock:
            session.load_board(Board.load(os.path.join(ex, "xiao-logger-mirrored-oled", "xiao-logger-mirrored-oled.solotrace")),
                               "/home/matthew/Desktop/solotrace/examples/xiao-logger-mirrored-oled/xiao-logger-mirrored-oled.solotrace")
            session.sel = {"part": "DS1"}
        pg.click("#mode-btn")
        pg.wait_for_timeout(400)
        pg.evaluate("getState()")
        pg.wait_for_timeout(600)
        pg.locator("#tree .grp > .row", has_text="Modules").click()
        pg.wait_for_timeout(200)
        pg.locator("#tree .sub > .row", has_text="postage").click()
        pg.wait_for_timeout(300)
        pg.locator("#tree .part:visible", has_text="XIAO ESP32-S3").click()
        pg.wait_for_timeout(500)
        with session.lock:
            session.escape()
            session.sel = {"part": "DS1"}
        pg.evaluate("getState()")
        pg.wait_for_timeout(500)
        pg.mouse.move(5, 5)
        pg.screenshot(path="/tmp/web-ui-modules.png")
        webp("/tmp/web-ui-modules.png", "web-ui-modules.webp")
        # 5. the laser dialog
        pg.click('.menu[data-menu="export"]')
        pg.wait_for_timeout(200)
        pg.click("text=Laser G-code (Elegoo Phecda)...")
        pg.wait_for_timeout(3000)
        pg.screenshot(path="/tmp/web-ui-laser.png")
        webp("/tmp/web-ui-laser.png", "web-ui-laser.webp")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        # 6. a part dragged onto another net's trace after routing: red ghost and rings, status line
        from solotrace.drc import part_collisions
        with session.lock:
            session.load_board(Board.load(os.path.join(ex, "555-led-flasher", "555-led-flasher.solotrace")),
                               "/home/matthew/Desktop/solotrace/examples/555-led-flasher/555-led-flasher.solotrace")
            bd = session.board
            ref, off = None, None
            for r in ("R1", "R2", "C1", "D1"):
                if r not in bd.parts:
                    continue
                pl = bd.parts[r]
                old = (pl.x, pl.y)
                for dx, dy in ((2.54, 0), (-2.54, 0), (0, 2.54), (0, -2.54), (5.08, 0), (0, 5.08)):
                    bd.move_part(r, old[0] + dx, old[1] + dy)
                    hit = part_collisions(bd, r)
                    bd.move_part(r, *old)
                    if hit:
                        ref, off = r, (dx, dy)
                        break
                if ref:
                    break
            x0, y0, x1, y1 = bd.court_rect(ref)
        pg.evaluate("getState()")
        pg.wait_for_timeout(600)
        pts = pg.evaluate("(a) => { const r = canvas.getBoundingClientRect(); const p = w2s(a[0], a[1]); const q = w2s(a[0] + a[2], a[1] + a[3]);"
                          " return [p[0] + r.left, p[1] + r.top, q[0] + r.left, q[1] + r.top]; }",
                          [(x0 + x1) / 2, (y0 + y1) / 2, off[0], off[1]])
        pg.mouse.move(pts[0], pts[1])
        pg.mouse.down()
        for k in range(1, 9):
            pg.mouse.move(pts[0] + (pts[2] - pts[0]) * k / 8, pts[1] + (pts[3] - pts[1]) * k / 8)
            pg.wait_for_timeout(60)
        pg.wait_for_timeout(700)
        pg.screenshot(path="/tmp/web-ui-collision.png")
        webp("/tmp/web-ui-collision.png", "web-ui-collision.webp")
        pg.mouse.up()
        pg.wait_for_timeout(400)
        # 7. the breakout board (XIAO ESP32-S3 / C3), then 8. the green lock circle while wiring on it
        bo = os.path.join(ex, "breakout-xiao-esp32-s3-c3", "breakout-xiao-esp32-s3-c3.solotrace")
        with session.lock:
            session.load_board(Board.load(bo), "/home/matthew/Desktop/solotrace/examples/breakout-xiao-esp32-s3-c3/breakout-xiao-esp32-s3-c3.solotrace")
            session.sel = {}
            session.status("Breakout: XIAO ESP32-S3 / C3. Every pin has a strip with 4 holes; 3V3, GND and 5V rails; power in on the screw terminal or the header.")
            bd = session.board
        pg.evaluate("getState()")
        pg.wait_for_timeout(500)
        pg.keyboard.press("f")
        pg.wait_for_timeout(600)
        pg.mouse.move(5, 5)
        pg.screenshot(path="/tmp/web-ui-breakout.png")
        webp("/tmp/web-ui-breakout.png", "web-ui-breakout.webp")

        def scr(x, y):
            return pg.evaluate("(a) => { const r = canvas.getBoundingClientRect(); const p = w2s(a[0], a[1]);"
                               " return [p[0] + r.left, p[1] + r.top]; }", [x, y])
        # wire from a GPIO pad of the module towards the rail; the cursor is a little off the target hole
        a1 = bd.pin_pos("U1.7")
        tx, ty = bd.pin_pos("RL1.1")
        pg.keyboard.press("w")
        pg.wait_for_timeout(200)
        p1 = scr(*a1)
        pg.mouse.click(p1[0], p1[1])
        pg.wait_for_timeout(300)
        q = scr(tx, ty - 1.0)
        pg.mouse.move(q[0] - 30, q[1] - 20)
        pg.mouse.move(q[0], q[1], steps=6)
        pg.wait_for_timeout(900)
        pg.screenshot(path="/tmp/web-ui-wire-lock.png")
        webp("/tmp/web-ui-wire-lock.png", "web-ui-wire-lock.webp")
        pg.keyboard.press("Escape")
        # 9. the 433 MHz meander antenna with its keep-out, 10. the coil generator dialog, 11. a generated coil
        for folder, shot, msg in (("antenna-433mhz-meander", "web-ui-antenna", "433.92 MHz meander antenna: the orange hatched box is the keep-out, the ground fill stops at it. A starting point, never measured."),):
            fp = os.path.join(ex, folder, folder + ".solotrace")
            with session.lock:
                session.load_board(Board.load(fp), "/home/matthew/Desktop/solotrace/examples/%s/%s.solotrace" % (folder, folder))
                session.sel = {}
                session.status(msg)
            pg.evaluate("getState()")
            pg.wait_for_timeout(1500)
            pg.keyboard.press("f")
            pg.wait_for_timeout(600)
            pg.mouse.move(5, 5)
            pg.screenshot(path="/tmp/%s.png" % shot)
            webp("/tmp/%s.png" % shot, shot + ".webp")
        fp = os.path.join(ex, "pcb-coil-1u5-13m56", "pcb-coil-1u5-13m56.solotrace")
        with session.lock:
            session.load_board(Board.load(fp), "/home/matthew/Desktop/solotrace/examples/pcb-coil-1u5-13m56/pcb-coil-1u5-13m56.solotrace")
            session.sel = {}
            session.status("A 30 x 20 mm coil from the generator (1.5 uH wanted). Pins 2 and 3 of the coil are joined by an insulated wire you solder over the turns.")
        pg.evaluate("getState()")
        pg.wait_for_timeout(1200)
        pg.keyboard.press("f")
        pg.wait_for_timeout(500)
        pg.evaluate("runCmd('dialog', { name: 'coil' })")
        pg.wait_for_timeout(700)
        pg.get_by_role("button", name="Calculate").click()
        pg.wait_for_timeout(700)
        pg.mouse.move(5, 5)
        pg.screenshot(path="/tmp/web-ui-coil-dialog.png")
        webp("/tmp/web-ui-coil-dialog.png", "web-ui-coil-dialog.webp")
        pg.get_by_role("button", name="Cancel").click()
        pg.wait_for_timeout(400)
        pg.mouse.move(5, 5)
        pg.screenshot(path="/tmp/web-ui-coil.png")
        webp("/tmp/web-ui-coil.png", "web-ui-coil.webp")
        b.close()
    srv.shutdown()
    srv.server_close()
    print("wrote web-ui.webp, web-ui-menu.webp, web-ui-smd.webp, web-ui-modules.webp, web-ui-laser.webp, web-ui-collision.webp, web-ui-breakout.webp, web-ui-wire-lock.webp, web-ui-antenna.webp, web-ui-coil-dialog.webp, web-ui-coil.webp")


def run_browser_app():
    """The no-install version from docs/app/, with a local copy of Pyodide (SOLOTRACE_PYODIDE_DIR)."""
    pyo = os.environ.get("SOLOTRACE_PYODIDE_DIR")
    if not pyo:
        print("SOLOTRACE_PYODIDE_DIR not set: no screenshot of the in-browser version")
        return
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    site = tempfile.mkdtemp()
    os.makedirs(os.path.join(site, "solotrace"))
    os.symlink(os.path.join(ROOT, "docs", "app"), os.path.join(site, "solotrace", "app"))
    os.symlink(pyo, os.path.join(site, "pyodide"))

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-proxy-server"])
        pg = b.new_page(viewport={"width": 1280, "height": 840}, device_scale_factor=1)
        pg.goto("http://127.0.0.1:%d/solotrace/app/?pyodide=/pyodide/" % srv.server_address[1])
        for _ in range(300):
            pg.wait_for_timeout(200)
            if pg.evaluate("!document.getElementById('loading') && typeof S !== 'undefined' && S !== null"):
                break
        pg.check("#dc-chk")
        pg.click("#dc-ok")
        pg.wait_for_timeout(300)
        pg.evaluate("api('demo', {name: 'XIAO ESP32-C3 logger (OLED mirrored under the board)'})")
        pg.wait_for_timeout(1500)
        pg.mouse.move(5, 5)
        pg.screenshot(path="/tmp/web-app.png")
        webp("/tmp/web-app.png", "web-app.webp")
        b.close()
    srv.shutdown()
    print("wrote web-app.webp")


if __name__ == "__main__":
    run()
    run_browser_app()
