# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Design rule checks on exact copper geometry."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .board import Board
from .geom import Cap, bbox_gap, max_turn, segments_cross, shape_dist, turn_angle


@dataclass
class Issue:
    kind: str           # clearance | width | edge | corner | unrouted | ring | jumper | outside
    message: str
    x: float
    y: float
    severity: str = "error"     # error | warn
    where: Optional[tuple] = None   # ((tagA), (tagB)) for the GUI to highlight

    def __str__(self) -> str:
        return "[%s] %s (%.2f, %.2f)" % (self.severity, self.message, self.x, self.y)


def _owner(tag: Optional[tuple]) -> tuple:
    if not tag:
        return ("?",)
    if tag[0] == "pad":
        return ("pad", tag[1], tag[2])
    if tag[0] in ("trace", "jpad"):
        return (tag[0], tag[1])
    return tuple(tag)


def _label(owner: tuple) -> str:
    if owner[0] == "pad":
        return "pad %s.%s" % (owner[1], owner[2])
    if owner[0] == "trace":
        return "trace #%d" % owner[1]
    if owner[0] == "jpad":
        return "jumper #%d" % owner[1]
    if owner[0] == "isl":
        return "island #%d" % (owner[1] + 1)
    return "?"


def check_clearance(board: Board) -> List[Issue]:
    shapes = board.copper()
    clr = board.settings.clearance
    cell = 4.0
    grid: Dict[Tuple[int, int], List[int]] = {}
    bbs = [s.bbox() for s in shapes]
    for i, bb in enumerate(bbs):
        for cx in range(int(math.floor((bb[0] - clr) / cell)), int(math.floor((bb[2] + clr) / cell)) + 1):
            for cy in range(int(math.floor((bb[1] - clr) / cell)), int(math.floor((bb[3] + clr) / cell)) + 1):
                grid.setdefault((cx, cy), []).append(i)
    seen = set()
    reported = set()
    issues: List[Issue] = []
    for lst in grid.values():
        for a in range(len(lst)):
            i = lst[a]
            si = shapes[i]
            for b in range(a + 1, len(lst)):
                j = lst[b]
                key = (i, j) if i < j else (j, i)
                if key in seen:
                    continue
                seen.add(key)
                sj = shapes[j]
                if si.net is not None and si.net == sj.net:
                    continue
                if bbox_gap(bbs[i], bbs[j]) >= clr:
                    continue
                d = shape_dist(si, sj)
                if d < clr - 1e-4:
                    oa, ob = _owner(si.tag), _owner(sj.tag)
                    if oa == ob:
                        continue
                    rk = (oa, ob) if oa < ob else (ob, oa)
                    if rk in reported:
                        continue
                    reported.add(rk)
                    ba, bb2 = bbs[i], bbs[j]
                    x = (max(ba[0], bb2[0]) + min(ba[2], bb2[2])) / 2.0
                    y = (max(ba[1], bb2[1]) + min(ba[3], bb2[3])) / 2.0
                    if d <= 1e-9:
                        msg = "%s touches %s" % (_label(oa), _label(ob))
                    else:
                        msg = "%s is %.2f mm from %s (needs %.2f)" % (_label(oa), d, _label(ob), clr)
                    issues.append(Issue("clearance", msg, x, y, "error", (oa, ob)))
    return issues


def run_drc(board: Board, check_unrouted: bool = True) -> List[Issue]:
    st = board.settings
    issues: List[Issue] = []
    W, H = board.width, board.height
    # parts inside the board
    for ref in board.parts:
        x0, y0, x1, y1 = board.court_rect(ref)
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            issues.append(Issue("outside", "%s sticks out of the board" % ref, (x0 + x1) / 2, (y0 + y1) / 2, "warn"))
    # trace checks
    for ti, t in enumerate(board.traces):
        for si, w in enumerate(t.widths):
            if w < st.min_trace - 1e-6:
                a = t.points[si]
                issues.append(Issue("width", "trace #%d is %.2f mm wide (minimum %.2f)" % (ti, w, st.min_trace),
                                    a[0], a[1], "error", (("trace", ti), ("trace", ti))))
        for i in range(1, len(t.points) - 1):
            ang = turn_angle(t.points[i - 1], t.points[i], t.points[i + 1])
            if ang > 46.0:
                p = t.points[i]
                issues.append(Issue("corner", "trace #%d has a %.0f degree corner, it must be chamfered"
                                    % (ti, 180 - ang), p[0], p[1], "error", (("trace", ti), ("trace", ti))))
    # edge clearance
    ec = st.edge_clearance
    for s in board.copper():
        x0, y0, x1, y1 = s.bbox()
        if x0 < ec - 1e-4 or y0 < ec - 1e-4 or x1 > W - ec + 1e-4 or y1 > H - ec + 1e-4:
            o = _owner(s.tag)
            if o[0] == "pad" and board.parts[o[1]].part_id.startswith("HOLE"):
                continue
            issues.append(Issue("edge", "%s is closer than %.2f mm to the board edge" % (_label(o), ec),
                                (x0 + x1) / 2, (y0 + y1) / 2, "warn", (o, o)))
    issues.extend(check_clearance(board))
    # pad rings
    for ref, pl in board.parts.items():
        d = board.get_def(pl.part_id)
        for pad in d.pads:
            style = pl.pad_styles.get(pad.name, pl.style)
            if style == "dead" and d.kind != "hole":
                continue
            if pad.drill <= 0:
                continue
            ring = (min(pad.w, pad.h) - pad.drill) / 2.0
            if ring < 0.2:
                p = board.pin_pos("%s.%s" % (ref, pad.name))
                issues.append(Issue("ring", "%s.%s has a %.2f mm copper ring around the hole (aim for 0.3 or more)"
                                    % (ref, pad.name, ring), p[0], p[1], "warn" if ring >= 0 else "error"))
    # jumpers
    for ji, j in enumerate(board.jumpers):
        L = j.length()
        if L < st.jumper_min - 1e-6 or L > st.jumper_max + 1e-6:
            issues.append(Issue("jumper", "jumper #%d is %.1f mm long (allowed %.1f to %.1f)"
                                % (ji, L, st.jumper_min, st.jumper_max), j.a[0], j.a[1], "warn"))
        for k in range(ji + 1, len(board.jumpers)):
            o = board.jumpers[k]
            if segments_cross(j.a, j.b, o.a, o.b):
                issues.append(Issue("jumper", "jumper #%d crosses jumper #%d on the component side" % (ji, k),
                                    (j.a[0] + j.b[0]) / 2, (j.a[1] + j.b[1]) / 2, "error"))
    # trace ends that are not joined to anything of their own net (a stub left hanging)
    cu = board.copper()
    fill_net = None
    if board.settings.island_mode:
        from .islands import ground_net
        fill_net = ground_net(board)
    for ti, t in enumerate(board.traces):
        if len(t.points) < 2 or t.net == fill_net:      # a ground trace ending in the ground fill is joined
            continue
        for end in (t.points[0], t.points[-1]):
            probe = Cap(end[0], end[1], end[0], end[1], 0.0)
            joined = False
            for s in cu:
                if s.net != t.net or (s.tag and s.tag[0] == "trace" and s.tag[1] == ti):
                    continue
                bb = s.bbox()
                if bb[0] - 0.01 <= end[0] <= bb[2] + 0.01 and bb[1] - 0.01 <= end[1] <= bb[3] + 0.01 \
                        and shape_dist(probe, s) <= 1e-6:
                    joined = True
                    break
            if not joined:
                issues.append(Issue("dangling", "trace #%d on net %s has an end that is not joined to anything"
                                    % (ti, t.net), end[0], end[1], "warn"))
    if board.settings.island_mode:
        from .islands import floating_fill, ground_net
        gnd = ground_net(board)
        if gnd is None:
            issues.append(Issue("islands", "the ground fill is on but the board has no nets, so the fill is "
                                "not joined to any ground pin", board.width / 2, board.height / 2, "warn"))
        else:
            for x, y, area in floating_fill(board):
                issues.append(Issue("islands", "a %.0f mm² piece of ground fill is cut off by islands and "
                                    "touches no %s pin (floating copper)" % (area, gnd), x, y, "warn"))
    if check_unrouted:
        for net, p1, p2, a, b in board.airwires():
            issues.append(Issue("unrouted", "net %s: %s is not connected to %s yet" % (net, a, b),
                                (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, "warn"))
    return issues


def summarize(issues: List[Issue]) -> str:
    if not issues:
        return "No problems found."
    errs = sum(1 for i in issues if i.severity == "error")
    warns = len(issues) - errs
    kinds: Dict[str, int] = {}
    for i in issues:
        kinds[i.kind] = kinds.get(i.kind, 0) + 1
    return "%d error(s), %d warning(s): %s" % (errs, warns, ", ".join("%s x%d" % (k, v) for k, v in sorted(kinds.items())))
