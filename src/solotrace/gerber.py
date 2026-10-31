# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Gerber RS-274X (with X2 attributes) and Excellon drill output for a one-sided board.

All layers use the design-view coordinates (X to the right, Y up). The copper layer is
labelled as the bottom copper layer, which is what a board house expects for a single-sided
board with the parts on top. Gerber viewers mirror a bottom layer themselves.
"""
from __future__ import annotations

import io
import zipfile
from typing import Dict, List, Tuple

from . import __version__
from .board import Board
from .geom import Cap, Poly
from .islands import plan as island_plan
from .render import silk_segments

SCALE = 1000000   # 4.6 format, millimetres


def _c(v: float) -> int:
    return int(round(v * SCALE))


class _Gerber:
    def __init__(self, function: str, polarity: str = "Positive") -> None:
        self.ap: Dict[Tuple, int] = {}
        self.body: List[str] = []
        self.function = function
        self.polarity = polarity
        self.cur = None
        self.pos = None

    def aperture(self, dia: float) -> int:
        key = ("C", round(dia, 4))
        if key not in self.ap:
            self.ap[key] = 10 + len(self.ap)
        return self.ap[key]

    def select(self, dia: float) -> None:
        n = self.aperture(dia)
        if self.cur != n:
            self.body.append("D%d*" % n)
            self.cur = n

    def flash(self, x: float, y: float, dia: float) -> None:
        self.select(dia)
        self.body.append("X%dY%dD03*" % (_c(x), _c(y)))
        self.pos = (x, y)

    def stroke(self, x1: float, y1: float, x2: float, y2: float, dia: float) -> None:
        self.select(dia)
        self.body.append("X%dY%dD02*" % (_c(x1), _c(y1)))
        self.body.append("X%dY%dD01*" % (_c(x2), _c(y2)))

    def region(self, pts) -> None:
        self.body.append("G36*")
        self.body.append("X%dY%dD02*" % (_c(pts[0][0]), _c(pts[0][1])))
        for x, y in list(pts[1:]) + [pts[0]]:
            self.body.append("X%dY%dD01*" % (_c(x), _c(y)))
        self.body.append("G37*")

    def text(self) -> str:
        o = io.StringIO()
        o.write("%%TF.GenerationSoftware,SoloTrace,SoloTrace,%s*%%\n" % __version__)
        o.write("%%TF.FileFunction,%s*%%\n" % self.function)
        o.write("%%TF.FilePolarity,%s*%%\n" % self.polarity)
        o.write("%TF.SameCoordinates,Original*%\n")
        o.write("%FSLAX46Y46*%\n%MOMM*%\n")
        o.write("G01*\n%LPD*%\n")
        for (kind, dia), n in sorted(self.ap.items(), key=lambda kv: kv[1]):
            o.write("%%ADD%dC,%.4f*%%\n" % (n, dia))
        o.write("\n".join(self.body))
        o.write("\nM02*\n")
        return o.getvalue()


def _draw(g: _Gerber, s) -> None:
    if isinstance(s, Poly):
        g.region(s.pts)
    else:
        dia = max(2.0 * s.r, 0.01)
        if abs(s.x1 - s.x2) < 1e-9 and abs(s.y1 - s.y2) < 1e-9:
            g.flash(s.x1, s.y1, dia)
        else:
            g.stroke(s.x1, s.y1, s.x2, s.y2, dia)


def copper_layer(board: Board) -> str:
    g = _Gerber("Copper,L1,Bot")
    p = island_plan(board)
    if p is None:
        for s in board.copper():
            _draw(g, s)
        return g.text()
    # deadbug islands: ground fill (dark), islands + gap cut out of it (clear), then the copper (dark)
    g.region(p.rect_poly().pts)
    g.body.append("%LPC*%")
    for s in p.cut:
        _draw(g, s)
    g.body.append("%LPD*%")
    for s in p.fat:
        _draw(g, s)
    for s in board.copper():
        _draw(g, s)
    return g.text()


def outline_layer(board: Board) -> str:
    g = _Gerber("Profile,NP")
    W, H = board.width, board.height
    pts = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        g.stroke(a[0], a[1], b[0], b[1], 0.1)
    return g.text()


def silk_layer(board: Board) -> str:
    g = _Gerber("Legend,Top")
    for x1, y1, x2, y2 in silk_segments(board):
        g.stroke(x1, y1, x2, y2, 0.15)
    return g.text()


def drill_file(board: Board) -> str:
    holes = board.drills()
    tools: Dict[float, int] = {}
    for _x, _y, d in holes:
        tools.setdefault(round(d, 3), len(tools) + 1)
    o = io.StringIO()
    o.write("M48\n; DRILL file {SoloTrace %s}\n; FORMAT={-:-/ absolute / metric / decimal}\n" % __version__)
    o.write("; #@! TF.FileFunction,Plated,1,2,PTH\n")
    o.write("FMAT,2\nMETRIC,TZ\nG90\n")
    for d, n in sorted(tools.items(), key=lambda kv: kv[1]):
        o.write("T%dC%.3f\n" % (n, d))
    o.write("%\nG05\n")
    for d, n in sorted(tools.items(), key=lambda kv: kv[1]):
        o.write("T%d\n" % n)
        for x, y, dd in holes:
            if round(dd, 3) == d:
                o.write("X%.4fY%.4f\n" % (x, y))
    o.write("T0\nM30\n")
    return o.getvalue()


def make_files(board: Board) -> Dict[str, str]:
    base = board.name.replace(" ", "_") or "board"
    return {
        "%s-Copper_Bottom.gbl" % base: copper_layer(board),
        "%s-Edge_Cuts.gm1" % base: outline_layer(board),
        "%s-Silkscreen_Top.gto" % base: silk_layer(board),
        "%s-PTH.drl" % base: drill_file(board),
    }


def write_zip(board: Board, path: str) -> List[str]:
    files = make_files(board)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
    return sorted(files)
