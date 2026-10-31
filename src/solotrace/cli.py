# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Command line: open the editor, or route and export boards without a window."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import APP_NAME, __version__, title


def _load(path: str):
    from .board import Board
    return Board.load(path)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv or "-V" in argv:
        print("%s  [WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN]" % title())
        return 0
    cmds = {"route", "place", "export", "demo", "drc", "islands", "selftest"}
    if not argv or argv[0] not in cmds:
        from .app import main as gui_main
        return gui_main(argv)
    ap = argparse.ArgumentParser(prog="solotrace", description="%s command line (work in progress)" % APP_NAME)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("demo", help="write an example board")
    p.add_argument("name", nargs="?", default="555 LED flasher")
    p.add_argument("out")
    p = sub.add_parser("place", help="auto-place a board")
    p.add_argument("board")
    p.add_argument("out")
    p.add_argument("--seconds", type=float, default=20.0)
    p = sub.add_parser("route", help="auto-route a board")
    p.add_argument("board")
    p.add_argument("out")
    p.add_argument("--no-jumpers", action="store_true")
    p = sub.add_parser("islands", help="turn the ground fill (RF / Manhattan boards) on or off")
    p.add_argument("board")
    p.add_argument("out")
    p.add_argument("--off", action="store_true", help="turn island mode off")
    p.add_argument("--net", default="", help="ground net (default: guess GND, 0V, VSS..., else the biggest net)")
    p.add_argument("--gap", type=float, default=0.6, help="gap round each island, mm")
    p.add_argument("--grow", type=float, default=1.0, help="make islands fatter by up to this, mm")
    p.add_argument("--deadbug", action="store_true", help="also make every pad a deadbug pad (no holes)")
    p.add_argument("--keep-floating", action="store_true", help="keep pieces of fill no ground pin sits on")
    p = sub.add_parser("drc", help="design rule check")
    p.add_argument("board")
    p = sub.add_parser("export", help="write manufacturing files")
    p.add_argument("board")
    p.add_argument("--gerber")
    p.add_argument("--pdf")
    p.add_argument("--svg")
    p.add_argument("--bom")
    p.add_argument("--no-mirror", action="store_true", help="print the design view instead of the copper side")
    p.add_argument("--laser")
    p.add_argument("--mode", choices=["negative", "isolation", "positive"], default="negative")
    p.add_argument("--comp", type=float, default=0.0, help="trace adjust, mm per side")
    p.add_argument("--gap", type=float, default=0.6)
    p.add_argument("--interval", type=float, default=0.08)
    p.add_argument("--feed", type=float, default=1500.0)
    p.add_argument("--power", type=float, default=70.0)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        from .demos import DEMOS
        if a.name not in DEMOS:
            print("Unknown example. Choose one of: " + ", ".join(DEMOS))
            return 2
        DEMOS[a.name]().save(a.out)
        print("wrote", a.out)
    elif a.cmd == "place":
        from .placer import auto_place
        b = _load(a.board)
        r = auto_place(b, time_limit=a.seconds)
        b.clear_auto_routes()
        b.save(a.out)
        print(r.summary())
    elif a.cmd == "route":
        from .router import AutoRouter, RouteOptions
        b = _load(a.board)
        r = AutoRouter(b, RouteOptions(use_jumpers=not a.no_jumpers)).route_all()
        b.save(a.out)
        print(r.summary())
        return 0 if r.complete else 1
    elif a.cmd == "islands":
        from .islands import ground_net, make_pads_deadbug
        b = _load(a.board)
        st = b.settings
        st.island_mode = not a.off
        st.island_net, st.island_gap, st.island_grow = a.net, a.gap, a.grow
        st.island_drop_floating = not a.keep_floating
        if a.net and a.net not in b.nets:
            print("No net called %s. Nets: %s" % (a.net, ", ".join(b.nets)))
            return 2
        if a.deadbug:
            print("deadbug pads on %d part(s)" % make_pads_deadbug(b))
        g = ground_net(b)
        if g:
            b.traces = [t for t in b.traces if t.manual or t.net != g]
        b.touch()
        b.save(a.out)
        print("ground fill %s%s" % ("off" if a.off else "on", "" if a.off else ", on net %s" % g))
    elif a.cmd == "drc":
        from .drc import run_drc, summarize
        iss = run_drc(_load(a.board))
        for i in iss:
            print(i)
        print(summarize(iss))
        return 1 if any(i.severity == "error" for i in iss) else 0
    elif a.cmd == "export":
        b = _load(a.board)
        if a.gerber:
            from .gerber import write_zip
            print("gerber:", ", ".join(write_zip(b, a.gerber)))
        if a.pdf:
            from .render import to_pdf
            open(a.pdf, "wb").write(to_pdf(b, mirror=not a.no_mirror))
        if a.svg:
            from .render import to_svg
            open(a.svg, "w", encoding="utf-8").write(to_svg(b, mirror=not a.no_mirror))
        if a.bom:
            from .render import to_bom_csv
            open(a.bom, "w", encoding="utf-8").write(to_bom_csv(b))
        if a.laser:
            from .laser import LaserOptions, generate
            o = LaserOptions(mode=a.mode, trace_comp=a.comp, gap=a.gap, line_interval=a.interval, feed=a.feed, power=a.power)
            job = generate(b, o, b.name)
            open(a.laser, "w", encoding="utf-8", newline="\n").write(job.gcode)
            print("laser:", job.summary())
            for w in job.warnings:
                print("WARNING:", w)
    elif a.cmd == "selftest":
        import unittest
        import os
        here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests")
        suite = unittest.defaultTestLoader.discover(here)
        res = unittest.TextTestRunner(verbosity=1).run(suite)
        return 0 if res.wasSuccessful() else 1
    return 0
