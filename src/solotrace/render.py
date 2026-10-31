# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""1:1 vector output (SVG and PDF) for printing and toner transfer, plus the BOM.

Orientation: the design view is the component side looking through the board. Copper is on
the other side, so a print for toner transfer or photo-resist normally needs ``mirror=True``
(the copper side as you will see it). The laser exporter does its own mirroring.
"""
from __future__ import annotations

import csv
import io
import math
import zlib
from typing import Iterable, List, Tuple

from .board import Board
from .geom import Cap, Poly, place_point


def part_segments(board: Board, ref: str) -> List[Tuple[float, float, float, float]]:
    """One part's outline as board-coordinate line segments."""
    segs: List[Tuple[float, float, float, float]] = []
    pl = board.parts[ref]
    d = board.get_def(pl.part_id)

    def P(x: float, y: float):
        return place_point((x, y), pl.x, pl.y, pl.rot, pl.flip)

    for o in d.outline:
        if o[0] == "line":
            a, b = P(o[1], o[2]), P(o[3], o[4])
            segs.append((a[0], a[1], b[0], b[1]))
        elif o[0] == "rect":
            c = [P(o[1], o[2]), P(o[3], o[2]), P(o[3], o[4]), P(o[1], o[4])]
            for i in range(4):
                segs.append((c[i][0], c[i][1], c[(i + 1) % 4][0], c[(i + 1) % 4][1]))
        elif o[0] == "arc":                     # ("arc", cx, cy, r, start_deg, end_deg), counter-clockwise
            cx, cy, r, a0, a1 = o[1], o[2], o[3], o[4], o[5]
            n = max(6, int(abs(a1 - a0) / 10))
            prev = P(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
            for i in range(1, n + 1):
                ang = math.radians(a0 + (a1 - a0) * i / n)
                cur = P(cx + r * math.cos(ang), cy + r * math.sin(ang))
                segs.append((prev[0], prev[1], cur[0], cur[1]))
                prev = cur
        elif o[0] == "circle":
            cx, cy, r = o[1], o[2], o[3]
            n = 36
            prev = P(cx + r, cy)
            for i in range(1, n + 1):
                ang = 2 * math.pi * i / n
                cur = P(cx + r * math.cos(ang), cy + r * math.sin(ang))
                segs.append((prev[0], prev[1], cur[0], cur[1]))
                prev = cur
    return segs


def silk_segments(board: Board) -> List[Tuple[float, float, float, float]]:
    """Component outlines as board-coordinate line segments."""
    segs: List[Tuple[float, float, float, float]] = []
    for ref in board.parts:
        segs.extend(part_segments(board, ref))
    return segs


def paint_order(board: Board):
    """(shape, is_copper) in drawing order; with deadbug islands the ground fill and its cuts come first."""
    from .islands import plan
    p = plan(board)
    cu = board.copper()
    if p is None:
        return [(s, True) for s in cu]
    return p.paint(cu)


def _mx(board: Board, mirror: bool):
    W = board.width
    return (lambda x: W - x) if mirror else (lambda x: x)


def to_svg(board: Board, mirror: bool = False, negative: bool = False, drill_dots: bool = True,
           silk: bool = False, outline: bool = True, dot_dia: float = 0.4) -> str:
    """SVG at exactly 1 mm = 1 user unit and the physical size set in mm."""
    W, H = board.width, board.height
    X = _mx(board, mirror)
    fg, bg = ("#ffffff", "#000000") if negative else ("#000000", "#ffffff")
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">'
         % (W, H, W, H),
         '<title>%s - SoloTrace %s</title>' % (_esc(board.name), "mirrored" if mirror else "design view"),
         '<rect x="0" y="0" width="%g" height="%g" fill="%s"/>' % (W, H, bg)]
    for s, is_cu in paint_order(board):
        col = fg if is_cu else bg
        if s.kind == "cap":
            w = max(2.0 * s.r, 0.01)
            o.append('<line x1="%.4f" y1="%.4f" x2="%.4f" y2="%.4f" stroke="%s" stroke-width="%.4f" '
                     'stroke-linecap="round"/>' % (X(s.x1), H - s.y1, X(s.x2), H - s.y2, col, w))
        else:
            o.append('<polygon points="%s" fill="%s"/>' % (
                " ".join("%.4f,%.4f" % (X(x), H - y) for x, y in s.pts), col))
    if drill_dots:
        for x, y, d in board.drills():
            o.append('<circle cx="%.4f" cy="%.4f" r="%.4f" fill="%s"/>' % (X(x), H - y, dot_dia / 2.0, bg))
    if silk:
        for x1, y1, x2, y2 in silk_segments(board):
            o.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#808080" stroke-width="0.15"/>'
                     % (X(x1), H - y1, X(x2), H - y2))
    if outline:
        o.append('<rect x="0.05" y="0.05" width="%g" height="%g" fill="none" stroke="#808080" '
                 'stroke-width="0.1"/>' % (W - 0.1, H - 0.1))
    o.append("</svg>")
    return "\n".join(o)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_pdf(board: Board, mirror: bool = False, negative: bool = False, drill_dots: bool = True,
           silk: bool = False, outline: bool = True, dot_dia: float = 0.4) -> bytes:
    """A one-page PDF whose page is exactly the board size, drawn 1:1 (1 mm = 2.83465 pt)."""
    k = 72.0 / 25.4
    W, H = board.width, board.height
    X = _mx(board, mirror)
    c: List[str] = []
    fg, bg = ("1 g", "0 g") if negative else ("0 g", "1 g")
    fgs, bgs = ("1 G", "0 G") if negative else ("0 G", "1 G")
    c.append("%s 0 0 %.3f %.3f re f" % (bg, W * k, H * k))
    c.append("1 J 1 j")
    for s, is_cu in paint_order(board):
        if s.kind == "cap":
            w = max(2.0 * s.r, 0.01)
            c.append("%s %.4f w %.3f %.3f m %.3f %.3f l S" % (fgs if is_cu else bgs, w * k, X(s.x1) * k, s.y1 * k,
                                                             X(s.x2) * k, s.y2 * k))
        else:
            pts = [(X(x) * k, y * k) for x, y in s.pts]
            c.append("%s %.3f %.3f m %s f" % (fg if is_cu else bg, pts[0][0], pts[0][1],
                                              " ".join("%.3f %.3f l" % p for p in pts[1:])))
    if drill_dots:
        for x, y, d in board.drills():
            c.append("%s %.4f w %.3f %.3f m %.3f %.3f l S" % (bgs, dot_dia * k, X(x) * k, y * k, X(x) * k, y * k))
    if silk:
        c.append("0.5 G %.3f w" % (0.15 * k))
        for x1, y1, x2, y2 in silk_segments(board):
            c.append("%.3f %.3f m %.3f %.3f l S" % (X(x1) * k, y1 * k, X(x2) * k, y2 * k))
    if outline:
        c.append("0.5 G %.3f w %.3f %.3f %.3f %.3f re S" % (0.1 * k, 0.05 * k, 0.05 * k, (W - 0.1) * k, (H - 0.1) * k))
    stream = zlib.compress("\n".join(x for x in c if x).encode("ascii"))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.3f %.3f] /Contents 4 0 R /Resources << >> >>"
             % (W * k, H * k)).encode("ascii"),
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
            ("<< /Title (%s) /Producer (SoloTrace) >>" % board.name.replace("(", "").replace(")", "")
             .replace("\\", "")).encode("latin-1", "replace")]
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, ob in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + ob + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offs:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 5 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def bom_rows(board: Board) -> List[List[str]]:
    groups: dict = {}
    for ref, pl in board.parts.items():
        d = board.get_def(pl.part_id)
        if d.kind in ("hole", "pad"):
            continue
        key = (d.name, pl.value, pl.part_id)
        groups.setdefault(key, []).append(ref)
    rows = []
    for (name, value, pid), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
        refs.sort(key=lambda r: (r.rstrip("0123456789"), int(r[len(r.rstrip("0123456789")):] or 0)))
        rows.append([", ".join(refs), str(len(refs)), value, name, pid])
    return rows


def to_bom_csv(board: Board) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["References", "Qty", "Value", "Part", "Part id"])
    for r in bom_rows(board):
        w.writerow(r)
    return buf.getvalue()
