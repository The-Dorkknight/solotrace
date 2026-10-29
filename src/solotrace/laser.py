# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""G-code for a gantry diode laser (made for the Elegoo Phecda, GRBL-style) that burns the
resist paint off a painted copper board before etching.

WORKFLOW (paint, burn, etch):
  1. Spray the copper-clad board with matt black (or any dark) paint and let it dry.
  2. The laser burns paint off the places where copper must be REMOVED.
  3. Etch the board; copper under the remaining paint stays.
A diode laser cannot cut copper. It only removes paint. Wear laser safety glasses rated for
the laser wavelength, ventilate, and never leave a running laser unattended. Burning paint
makes fumes. The defaults here are untested starting points: always run the test cards first.

MODES
  negative   burn everything that is not copper, so paint stays only on the traces and pads.
             Slowest, but gives the cleanest etch and the biggest, most even gaps.
  isolation  burn only a band of ``gap`` mm around the copper. Fast; the paint left between
             traces stays as copper "islands" (they must not touch the circuit).
  positive   burn the copper shapes themselves (for a negative-working resist or for marking).

TRACE GAP ADJUSTMENT
  ``trace_comp`` grows (+) or thins (-) every copper shape by that many mm per side before the
  burn region is computed. A negative value widens every gap between traces. Use it to
  cancel out the laser spot size and the etchant undercut. ``gap`` is the width of the burned
  band in isolation mode. ``line_interval`` is the distance between scan lines.

The scan engine is exact: for every scan line it computes the copper intervals from the real
pad and trace geometry, so the burn edges follow the chamfered traces and round pads.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from . import __version__
from .board import Board, Trace
from .geom import (Cap, Poly, cap_interval, merge_intervals, poly_intervals, shape_intervals,
                   subtract_intervals)

MODES = ("negative", "isolation", "positive")
PHECDA_AREA = (400.0, 400.0)
PHECDA_PRESS_MAX_FEED = 9600.0      # 160 mm/s from press reports; Elegoo manual spec table: X 25000, Y 18000 mm/min


@dataclass
class LaserOptions:
    mode: str = "negative"
    mirror: bool = True               # laser sees the copper side: mirror the design view in X
    trace_comp: float = 0.0           # mm per side; + grows copper, - thins it (widens gaps)
    gap: float = 0.6                  # isolation band width, mm
    border: float = 0.0               # keep this much paint at the board edge, mm
    line_interval: float = 0.08       # mm between scan lines (spot is about 0.07 x 0.13 mm)
    feed: float = 1500.0              # mm/min while burning
    power: float = 70.0               # percent of S max
    smax: float = 1000.0              # GRBL $30
    passes: int = 1
    crosshatch: bool = False          # second pass at 90 degrees
    bidirectional: bool = True        # serpentine scan
    dynamic: bool = True              # M4 (GRBL dynamic power) instead of M3
    overscan: float = 1.0             # mm of zero-power run-in/out in M3 mode
    drill_dots: bool = True           # short burn at every hole centre
    dot_dia: float = 0.3
    rapid: float = 6000.0             # mm/min, only used for the time estimate and G0 hints
    frame_power: float = 1.0          # percent for the frame outline; 0 moves silently
    min_segment: float = 0.03         # shorter burn runs are dropped, mm
    join_gap: float = 0.04            # gaps shorter than this are burned through, mm
    max_lines: int = 40000

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "LaserOptions":
        o = LaserOptions()
        for k, v in d.items():
            if hasattr(o, k):
                setattr(o, k, type(getattr(o, k))(v))
        return o


@dataclass
class LaserJob:
    gcode: str = ""
    segments: List[Tuple[float, float, float, float]] = field(default_factory=list)   # design coords, preview
    burn_length: float = 0.0
    lines: int = 0
    seconds: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        m = int(self.seconds // 60)
        return "%d scan lines, %.0f mm burned, about %d min %02d s" % (self.lines, self.burn_length, m, int(self.seconds % 60))


def validate(board: Board, o: LaserOptions) -> List[str]:
    w: List[str] = []
    if o.mode not in MODES:
        w.append("Unknown mode %r." % o.mode)
    if board.width > PHECDA_AREA[0] or board.height > PHECDA_AREA[1]:
        w.append("Board is larger than the 400 x 400 mm Phecda work area.")
    if not (0 < o.power <= 100):
        w.append("Power must be between 0 and 100 percent.")
    if o.feed <= 0:
        w.append("Feed must be above zero.")
    if o.feed > PHECDA_PRESS_MAX_FEED:
        w.append("Feed %.0f mm/min is above the 160 mm/s (9600 mm/min) quoted in press reports; "
                 "Elegoo's manual quotes up to 25000 mm/min (X) and 18000 mm/min (Y). Check what your machine really does." % o.feed)
    if o.line_interval < 0.02:
        w.append("Line interval below 0.02 mm will take a very long time.")
    if o.line_interval > 0.13:
        w.append("Line interval above the 0.13 mm spot height leaves unburned stripes.")
    if o.mode == "isolation" and o.gap < 2 * o.line_interval:
        w.append("Isolation gap is very small compared with the line interval.")
    if o.trace_comp < -0.3:
        w.append("A negative trace compensation this large will eat into thin traces.")
    if board.height / max(o.line_interval, 1e-6) > o.max_lines:
        w.append("Too many scan lines; increase the line interval.")
    return w


# ---------------------------------------------------------------------------------------
# scan engine
# ---------------------------------------------------------------------------------------
def _ivals(sh, y: float, comp: float) -> List[Tuple[float, float]]:
    """Intervals of a copper shape grown (+) or eroded (-) by ``comp`` on the line at y."""
    if comp >= 0:
        return shape_intervals(sh, y, comp)
    if sh.kind == "cap":
        iv = cap_interval(sh, y, comp)
        return [iv] if iv else []
    base = merge_intervals(poly_intervals(sh.pts, y))
    cut: List[Tuple[float, float]] = []
    n = len(sh.pts)
    for i in range(n):
        a, b = sh.pts[i], sh.pts[(i + 1) % n]
        iv = cap_interval(Cap(a[0], a[1], b[0], b[1], 0.0), y, -comp)
        if iv:
            cut.append(iv)
    return subtract_intervals(base, merge_intervals(cut))


def _transpose(shapes):
    out = []
    for s in shapes:
        if s.kind == "cap":
            out.append(Cap(s.y1, s.x1, s.y2, s.x2, s.r, s.net, s.tag))
        else:
            out.append(Poly([(y, x) for x, y in s.pts], s.net, s.tag))
    return out


def _scan(shapes, W: float, H: float, o: LaserOptions, dots) -> List[Tuple[float, List[Tuple[float, float]]]]:
    """Burn intervals per scan line for lines along X; y runs 0..H."""
    comp = o.trace_comp
    grow_out = max(comp, 0.0) + (o.gap if o.mode == "isolation" else 0.0)
    items = []
    for s in shapes:
        bb = s.bbox()
        items.append((bb[1] - grow_out - 0.01, bb[3] + grow_out + 0.01, s))
    items.sort(key=lambda t: t[0])
    b = o.border
    x_lo, x_hi = b, W - b
    y_lo, y_hi = b, H - b
    lines = []
    nl = int((y_hi - y_lo) / o.line_interval)
    if nl <= 0:
        return lines
    pad = (y_hi - y_lo - (nl - 1) * o.line_interval) / 2.0
    active: List[tuple] = []
    nxt = 0
    for k in range(nl):
        y = y_lo + pad + k * o.line_interval
        while nxt < len(items) and items[nxt][0] <= y:
            active.append(items[nxt])
            nxt += 1
        active = [t for t in active if t[1] >= y]
        inner: List[Tuple[float, float]] = []
        outer: List[Tuple[float, float]] = []
        for _lo, _hi, s in active:
            inner.extend(_ivals(s, y, comp))
            if o.mode == "isolation":
                outer.extend(_ivals(s, y, comp + o.gap))
        inner = merge_intervals(inner)
        if o.mode == "negative":
            burn = subtract_intervals([(x_lo, x_hi)], inner)
        elif o.mode == "positive":
            burn = [(max(lo, x_lo), min(hi, x_hi)) for lo, hi in inner if hi > x_lo and lo < x_hi]
        else:
            outer = merge_intervals(outer)
            burn = [(max(lo, x_lo), min(hi, x_hi)) for lo, hi in subtract_intervals(outer, inner)
                    if hi > x_lo and lo < x_hi]
        if dots:
            for cx, cy, r in dots:
                if abs(y - cy) < r:
                    h = math.sqrt(r * r - (y - cy) ** 2)
                    burn = merge_intervals(burn + [(cx - h, cx + h)])
        if o.join_gap > 0 and burn:
            burn = merge_intervals(burn, o.join_gap)
        burn = [(a, c) for a, c in burn if c - a >= o.min_segment]
        if burn:
            lines.append((y, burn))
    return lines


def _fmt(v: float) -> str:
    s = "%.3f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _header(board_name: str, o: LaserOptions, W: float, H: float, title: str) -> List[str]:
    return [
        "; SoloTrace %s - laser job: %s" % (__version__, title),
        "; WORK IN PROGRESS: defaults are untested starting points. Run the test cards first.",
        "; Board: %s  %.1f x %.1f mm  mode=%s  mirror=%s" % (board_name, W, H, o.mode, o.mirror),
        "; comp=%.3f mm  gap=%.3f mm  interval=%.3f mm  feed=%.0f mm/min  power=%.0f%% of S%.0f  passes=%d%s"
        % (o.trace_comp, o.gap, o.line_interval, o.feed, o.power, o.smax, o.passes,
           "  crosshatch" if o.crosshatch else ""),
        "; Machine assumed GRBL-style (verify): $30=%.0f (S max), $32=1 (laser mode)." % o.smax,
        "; Set WORK ZERO at the lower-left corner of the board as you look at the copper side.",
        "; Paint the copper, burn, then etch. A diode laser removes paint only, not copper.",
        "; Wear laser eye protection. Ventilate. Never leave the laser running unattended.",
        "G21 ; millimetres",
        "G90 ; absolute",
    ]


def _emit(lines, W: float, o: LaserOptions, vertical: bool, reverse_first: bool = False) -> Tuple[List[str], float, float]:
    """G-code for one set of scan lines. Returns (code, burn_length, travel_length)."""
    S = int(round(o.power / 100.0 * o.smax))
    out: List[str] = []
    burn = 0.0
    travel = 0.0
    mcode = "M4" if o.dynamic else "M3"
    out.append("%s S0" % mcode)
    first_move = True
    last = (0.0, 0.0)
    span = W      # extent along the scan direction (already swapped for vertical passes)
    if vertical:
        def xy(u: float, v: float) -> str:
            return "Y%s X%s" % (_fmt(u), _fmt(v))
    else:
        def xy(u: float, v: float) -> str:
            return "X%s Y%s" % (_fmt(u), _fmt(v))
    for idx, (y, ivs) in enumerate(lines):
        ivs = sorted(ivs)
        # mirror along the scan axis only for X lines of a mirrored job: handled by caller via W
        rev = o.bidirectional and ((idx & 1) == 1) != reverse_first
        seq = list(reversed(ivs)) if rev else ivs
        for a, c in seq:
            p0, p1 = (c, a) if rev else (a, c)
            d = 1.0 if p1 > p0 else -1.0
            if o.dynamic:
                start = p0
            else:
                start = min(max(p0 - d * o.overscan, 0.0), span)
            pt = (start, y)
            travel += math.hypot(pt[0] - last[0], pt[1] - last[1])
            out.append("G0 " + xy(start, y))
            if o.dynamic:
                if first_move:
                    out.append("G1 %s S%d F%.0f" % (xy(p1, y), S, o.feed))
                else:
                    out.append("G1 %s S%d" % (xy(p1, y), S))
            else:
                if start != p0:
                    out.append("G1 %s S0 F%.0f" % (xy(p0, y), o.feed))
                out.append("G1 %s S%d F%.0f" % (xy(p1, y), S, o.feed))
                end = min(max(p1 + d * o.overscan, 0.0), span)
                if end != p1:
                    out.append("G1 %s S0" % xy(end, y))
                    p1 = end
            first_move = False
            burn += abs(c - a)
            last = (p1, y)
    out.append("M5")
    return out, burn, travel


def _mirror_lines(lines, W: float):
    out = []
    for y, ivs in lines:
        out.append((y, sorted((W - c, W - a) for a, c in ivs)))
    return out


def generate(board: Board, o: Optional[LaserOptions] = None, title: str = "copper") -> LaserJob:
    o = o or LaserOptions()
    job = LaserJob()
    job.warnings = validate(board, o)
    if o.mode not in MODES:
        raise ValueError("unknown mode %s" % o.mode)
    W, H = board.width, board.height
    shapes = board.copper()
    dots = [(x, y, o.dot_dia / 2.0) for x, y, _d in board.drills()] if o.drill_dots else []
    hz = _scan(shapes, W, H, o, dots)
    # preview in design coordinates
    for y, ivs in hz:
        for a, c in ivs:
            job.segments.append((a, y, c, y))
    code = _header(board.name, o, W, H, title)
    burn_total = 0.0
    travel_total = 0.0
    nlines = 0
    passes: List[Tuple[list, bool]] = []
    base_h = _mirror_lines(hz, W) if o.mirror else hz
    for p in range(max(1, o.passes)):
        passes.append((base_h, False))
        if o.crosshatch:
            vt = _scan(_transpose(shapes), H, W, o, [(y, x, r) for x, y, r in dots])
            if o.mirror:
                # vertical lines sit at design x; mirrored x' = W - x, scanning along Y unchanged
                vt = [(W - x, ivs) for x, ivs in vt][::-1]
            passes.append((vt, True))
    for n, (lines, vertical) in enumerate(passes):
        code.append("; --- pass %d%s: %d lines" % (n + 1, " (vertical)" if vertical else "", len(lines)))
        span_w = H if vertical else W
        seg, bl, tr = _emit(lines, span_w, o, vertical)
        code.extend(seg)
        burn_total += bl
        travel_total += tr
        nlines += len(lines)
    code.append("G0 X0 Y0")
    code.append("M5 S0")
    code.append("M2 ; end of job")
    job.gcode = "\n".join(code) + "\n"
    job.burn_length = burn_total
    job.lines = nlines
    accel = nlines * 0.02          # rough 20 ms lost per scan line for turning round
    job.seconds = burn_total / (o.feed / 60.0) + travel_total / (o.rapid / 60.0) + accel
    return job


# ---------------------------------------------------------------------------------------
# frame, drill-dot-only and test cards
# ---------------------------------------------------------------------------------------
def frame_gcode(board: Board, o: Optional[LaserOptions] = None) -> str:
    o = o or LaserOptions()
    S = int(round(o.frame_power / 100.0 * o.smax))
    W, H = board.width, board.height
    pts = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
    out = ["; SoloTrace %s - frame outline (check the position before burning)" % __version__,
           "G21", "G90", "M4 S0", "G0 X0 Y0"]
    for i, (x, y) in enumerate(pts[1:]):
        out.append("G1 X%s Y%s S%d F3000" % (_fmt(x), _fmt(y), S))
    out += ["M5", "G0 X0 Y0", "M2"]
    return "\n".join(out) + "\n"


def speed_power_card(o: Optional[LaserOptions] = None, powers=(30, 45, 60, 75, 90),
                     feeds=(600, 1000, 1500, 2000, 3000), size: float = 6.0, gap: float = 3.0) -> LaserJob:
    """A grid of filled squares: speed increases left to right, power increases bottom to top.

    Burn it on a scrap of painted board and pick the square that removes the paint cleanly
    without scorching the copper (copper that has gone dark or pitted took too much heat).
    """
    o = o or LaserOptions()
    n_p, n_f = len(powers), len(feeds)
    W = n_f * size + (n_f - 1) * gap
    H = n_p * size + (n_p - 1) * gap
    S_of = lambda p: int(round(p / 100.0 * o.smax))
    code = ["; SoloTrace %s - SPEED/POWER TEST CARD" % __version__,
            "; Columns left to right use feeds %s mm/min." % ", ".join("%.0f" % f for f in feeds),
            "; Rows bottom to top use power %s %% of S%.0f." % (", ".join("%.0f" % p for p in powers), o.smax),
            "; Each square is %.0f mm and filled with lines %.3f mm apart." % (size, o.line_interval),
            "; Set work zero at the lower-left corner of a painted scrap piece at least %.0f x %.0f mm." % (W, H),
            "; Wear laser eye protection. Ventilate.",
            "G21", "G90", "M4 S0"]
    burn = 0.0
    secs = 0.0
    segs = []
    for j, p in enumerate(powers):
        for i, f in enumerate(feeds):
            x0 = i * (size + gap)
            y0 = j * (size + gap)
            code.append("; square feed=%.0f power=%.0f%%" % (f, p))
            ny = max(1, int(size / o.line_interval))
            for k in range(ny):
                y = y0 + k * size / max(1, ny - 1) if ny > 1 else y0
                a, c = (x0, x0 + size) if k % 2 == 0 else (x0 + size, x0)
                code.append("G0 X%s Y%s" % (_fmt(a), _fmt(y)))
                code.append("G1 X%s S%d F%.0f" % (_fmt(c), S_of(p), f))
                burn += size
                secs += size / (f / 60.0)
                segs.append((x0, y, x0 + size, y))
    code += ["M5", "G0 X0 Y0", "M2"]
    job = LaserJob("\n".join(code) + "\n", segs, burn, len(powers) * len(feeds), secs)
    return job


def trace_ladder_card(o: Optional[LaserOptions] = None) -> LaserJob:
    """Negative-mode test of fine traces and gaps using the real engine and your current settings.

    A block with copper strips of 0.2 to 1.0 mm width, spaced apart so the burned gaps are
    0.2 to 0.8 mm. Etch it, then look at which strips and gaps survive. Change ``trace_comp``
    until the strips come out at their drawn width.
    """
    o = o or LaserOptions()
    widths = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    gaps = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    h = 14.0
    x = 3.0
    b = Board(3.0 + sum(widths) + sum(gaps) + 3.0 + 6.0, h + 6.0, "ladder")
    for w, g in zip(widths, gaps):
        x += g + w / 2.0
        b.traces.append(Trace("T", [(x, 3.0), (x, 3.0 + h)], [w]))
        x += w / 2.0
    # a big pad to see large area clearing and a ring to see roundness
    b.traces.append(Trace("P", [(x + 4.0, 6.0), (x + 4.0, 6.0)], [4.0]))
    o2 = LaserOptions.from_dict(o.to_dict())
    o2.mode = "negative"
    o2.drill_dots = False
    o2.mirror = False
    job = generate(b, o2, "TRACE / GAP LADDER (strips %s mm wide)" % ", ".join(str(w) for w in widths))
    return job
