# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""A small local web server for the SoloTrace web UI (standard library only).

It listens on 127.0.0.1 (never on the network), serves the page in ``static/`` and turns
``POST /api/cmd`` requests into ``Session.cmd`` calls. It stops by itself when the page has
gone (no heartbeat for a while), when the page asks it to (File > Quit) or on Ctrl+C.

    python3 src/main.py web [board.solotrace] [--port N] [--no-browser]

WORK IN PROGRESS: many features may be broken.
"""
from __future__ import annotations

import json
import mimetypes
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from .. import APP_NAME
from ..board import Board
from . import api
from .session import Session

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HEARTBEAT_GRACE = 90.0      # seconds without a ping (after the first) before the server stops itself


class State:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.last_ping = 0.0
        self.seen_page = False
        self.quit = False


class Handler(BaseHTTPRequestHandler):
    state: State = None       # type: ignore[assignment]
    server_version = "SoloTrace/0"

    def log_message(self, fmt, *args) -> None:      # quiet unless asked
        if os.environ.get("SOLOTRACE_WEB_LOG"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------- helpers
    def _send(self, code: int, body: bytes, ctype: str = "application/json", download: Optional[str] = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % download.replace('"', ""))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _reply(self, r) -> None:
        code, data, ctype, name = r
        if ctype.startswith("text/") or ctype == "application/json":
            ctype += "; charset=utf-8"
        self._send(code, data, ctype, download=name)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            d = json.loads(raw.decode("utf-8"))
            return d if isinstance(d, dict) else {}
        except ValueError:
            return {}

    def _local(self) -> bool:
        """Only the browser on this computer may talk to the server."""
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "[::1]", "::1"):
            self._send(403, b"forbidden", "text/plain")
            return False
        return True

    # ------------------------------------------------------------- GET
    def do_GET(self) -> None:      # noqa: N802
        if not self._local():
            return
        u = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(u.query).items()}
        p = u.path
        st = self.state
        se = st.session
        if p in ("/", "/index.html"):
            return self._static("index.html")
        if p.startswith("/static/"):
            return self._static(p[len("/static/"):])
        if p.startswith("/api/") and p not in ("/api/ping", "/api/quit"):
            return self._reply(api.handle(se, "GET", p, q))
        if p == "/api/ping":
            st.last_ping = time.time()
            st.seen_page = True
            return self._json({"ok": True})
        if p == "/api/quit":
            st.quit = True
            return self._json({"ok": True})
        self._send(404, b"not found", "text/plain")

    def _static(self, name: str) -> None:
        name = os.path.normpath(name).replace("\\", "/")
        if name.startswith("..") or name.startswith("/"):
            return self._send(404, b"not found", "text/plain")
        fn = os.path.join(STATIC, name)
        if not os.path.isfile(fn):
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(fn, "rb") as fh:
            self._send(200, fh.read(), ctype)

    # ------------------------------------------------------------- POST
    def do_POST(self) -> None:      # noqa: N802
        if not self._local():
            return
        p = urlparse(self.path).path
        se = self.state.session
        body = self._body()
        if p.startswith("/api/"):
            return self._reply(api.handle(se, "POST", p, None, body))
        self._send(404, b"not found", "text/plain")


def free_port(preferred: int = 0) -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", preferred))
        return s.getsockname()[1]
    except OSError:
        s.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def make_server(session: Session, port: int = 0) -> ThreadingHTTPServer:
    st = State(session)

    class H(Handler):
        pass
    H.state = st
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    srv.solotrace_state = st       # type: ignore[attr-defined]
    return srv


def serve(session: Session, port: int = 0, open_browser: bool = True, watch_page: bool = True,
          ready=None) -> int:
    """Run until the page goes away or asks to quit. Returns an exit code."""
    srv = make_server(session, port)
    st = srv.solotrace_state       # type: ignore[attr-defined]
    host, port = srv.server_address[:2]
    url = "http://127.0.0.1:%d/" % port
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    t.start()
    print("%s web UI: %s   (Ctrl+C or File > Quit in the page stops it)" % (APP_NAME, url), flush=True)
    if ready:
        ready(url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            print("Could not open a browser by itself. Open this address yourself: %s" % url, flush=True)
    code = 0
    try:
        started = time.time()
        while not st.quit:
            time.sleep(0.5)
            if not watch_page:
                continue
            if st.seen_page and time.time() - st.last_ping > HEARTBEAT_GRACE:
                print("The page has gone; stopping.", flush=True)
                break
            if not st.seen_page and time.time() - started > 600:
                print("No browser connected for 10 minutes; stopping. Open %s to use SoloTrace." % url, flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
        srv.server_close()
    return code


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = 0
    open_browser = True
    path = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                port = 0
            i += 2
            continue
        if a == "--no-browser":
            open_browser = False
        elif a == "--demo":
            path = "--demo"
        elif not a.startswith("--"):
            path = a
        i += 1
    board = None
    if path == "--demo":
        from .. import demos
        board = demos.DEMOS["555 LED flasher"]()
        path = None
    elif path:
        try:
            board = Board.load(path)
        except Exception as exc:          # noqa: BLE001
            print("Could not open %s: %s" % (path, exc), file=sys.stderr)
            path = None
    session = Session(board, path)
    return serve(session, port=port, open_browser=open_browser)


if __name__ == "__main__":
    sys.exit(main())
