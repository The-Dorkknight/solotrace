# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Build docs/SoloTrace-guide.pdf: the README, how it works, the changelog and the breakout and antenna notes in one file.

Run:  python3 tools/make_pdf.py
Needs the 'markdown' package and Playwright with Chromium (development tools only; the app itself needs neither).
The release workflow attaches the committed PDF to every release."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import markdown                                       # noqa: E402
from solotrace import __version__, __build_date__     # noqa: E402

PARTS = [("README.md", ""), ("HOW_IT_WORKS.md", "how-it-works"), ("docs/research/breakout-boards.md", "breakouts"), ("docs/research/pcb-antennas.md", "antennas"),
         ("CHANGELOG.md", "changelog"), ("DESIGN_NOTES.md", "design-notes")]
CSS = """
body{font:10.5pt/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#111;max-width:none}
h1{font-size:22pt;border-bottom:2px solid #444;padding-bottom:4px;margin-top:0}
h2{font-size:15pt;border-bottom:1px solid #aaa;padding-bottom:2px;margin-top:22px}
h3{font-size:12pt}
code,pre{font:9pt Menlo,Consolas,monospace;background:#f2f2f2}
pre{padding:6px;white-space:pre-wrap}
table{border-collapse:collapse;margin:8px 0;font-size:9pt}
td,th{border:1px solid #bbb;padding:3px 6px;vertical-align:top}
th{background:#eee}
img{max-width:100%;height:auto;page-break-inside:avoid}
blockquote{border-left:3px solid #c80;margin:8px 0;padding:2px 10px;background:#fff8e8}
.doc{page-break-before:always}
.cover{text-align:center;padding-top:120px}
.cover h1{border:0;font-size:34pt}
"""


def render(path):
    text = open(os.path.join(ROOT, path), encoding="utf-8").read()
    base = os.path.dirname(path)
    # make relative image paths work from the repository root
    def fix(m):
        src = m.group(2)
        if re.match(r"^(https?:|data:|/)", src):
            return m.group(0)
        return "%s%s)" % (m.group(1), "file://" + os.path.normpath(os.path.join(ROOT, base, src)))
    text = re.sub(r"(!\[[^\]]*\]\()([^)\s]+)\)", fix, text)
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def main():
    from playwright.sync_api import sync_playwright
    cover = ('<div class="cover"><h1>SoloTrace</h1><p><b>WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN</b></p>'
             '<p>Version %s (built %s)</p><p>Matthew Armstrong &middot; PolyForm Noncommercial 1.0.0 (source-available)</p>'
             '<p>github.com/The-Dorkknight/solotrace</p></div>' % (__version__, __build_date__))
    body = cover + "".join('<div class="doc">%s</div>' % render(p) for p, _ in PARTS)
    html = "<!doctype html><meta charset=utf-8><title>SoloTrace guide</title><style>%s</style>%s" % (CSS, body)
    tmp = os.path.join(ROOT, "docs", ".guide-tmp.html")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(html)
    out = os.path.join(ROOT, "docs", "SoloTrace-guide.pdf")
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--no-proxy-server", "--allow-file-access-from-files"])
            pg = br.new_page()
            pg.goto("file://" + tmp)
            pg.wait_for_load_state("load")
            pg.pdf(path=out, format="A4", margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
                   print_background=True, display_header_footer=True,
                   header_template="<span></span>",
                   footer_template='<div style="font-size:8px;width:100%;text-align:center">SoloTrace ' + __version__
                                   + ' (work in progress) - page <span class="pageNumber"></span> of <span class="totalPages"></span></div>')
            br.close()
    finally:
        os.remove(tmp)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
