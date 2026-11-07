# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Build the in-browser SoloTrace (no install at all) into docs/app/ for GitHub Pages.

    python3 tools/build_web_app.py          (re)writes docs/app/
    python3 tools/build_web_app.py --check  exit 1 if docs/app/ is out of date with src/

The page is the web UI from src/solotrace/web/static/; the editor's Python (src/solotrace, minus
the tkinter window) goes into solotrace-py.zip, which the page runs with Pyodide in a Web Worker.
Pyodide itself is loaded from the jsDelivr CDN (exact version below). The zip is written with fixed
timestamps so the same source always gives the same bytes, and tests/test_web_app.py checks that
docs/app/ matches the source.
"""
import io
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "solotrace")
STATIC = os.path.join(SRC, "web", "static")
OUT = os.path.join(ROOT, "docs", "app")
PYODIDE = "https://cdn.jsdelivr.net/npm/pyodide@0.29.5/"
SKIP = {"app.py", "dialogs.py", "theme.py"}          # the tkinter window: not used in the browser

BOOT = """<script>
// The in-browser version: Pyodide runs the editor's Python in worker.js. For testing only, a
// same-site path may replace the CDN: ?pyodide=/path/to/pyodide/
(function () {
  var p = new URLSearchParams(location.search).get("pyodide");
  var ok = p && p.charAt(0) === "/" && p.charAt(1) !== "/";
  window.SOLOTRACE_BROWSER = {pyodide: ok ? p : "%s", code: "solotrace-py.zip", worker: "worker.js"};
})();
</script>
""" % PYODIDE


def code_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(SRC):
            dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", "static"))
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(base, f), os.path.dirname(SRC)).replace(os.sep, "/")
                if not f.endswith(".py") or (os.path.dirname(rel) == "solotrace" and f in SKIP):
                    continue
                info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(os.path.join(base, f), "rb") as fh:
                    z.writestr(info, fh.read())
    return buf.getvalue()


def page() -> bytes:
    with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace('href="/static/', 'href="').replace('src="/static/', 'src="')
    html = html.replace('<script src="app.js"></script>', BOOT + '<script src="app.js"></script>')
    html = html.replace("<title>SoloTrace</title>", "<title>SoloTrace in your browser</title>")
    assert "SOLOTRACE_BROWSER" in html
    return html.encode("utf-8")


def files() -> dict:
    out = {"index.html": page(), "solotrace-py.zip": code_zip()}
    for f in ("app.js", "style.css", "worker.js", "icon.png"):
        with open(os.path.join(STATIC, f), "rb") as fh:
            out[f] = fh.read()
    return out


def main(argv) -> int:
    want = files()
    if "--check" in argv:
        stale = [n for n, data in want.items()
                 if not os.path.exists(os.path.join(OUT, n)) or open(os.path.join(OUT, n), "rb").read() != data]
        if stale:
            print("docs/app is out of date: %s. Run python3 tools/build_web_app.py" % ", ".join(stale))
            return 1
        print("docs/app is up to date")
        return 0
    os.makedirs(OUT, exist_ok=True)
    for n, data in want.items():
        with open(os.path.join(OUT, n), "wb") as fh:
            fh.write(data)
    print("wrote docs/app/ (%s), Pyodide from %s" % (", ".join("%s %d kB" % (n, len(d) // 1024) for n, d in want.items()), PYODIDE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
