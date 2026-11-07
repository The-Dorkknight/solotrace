# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Design rule checks on exact copper geometry."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .board import Board
from .geom import Cap, Poly, bbox_gap, max_turn, segments_cross, shape_dist, turn_angle


@dataclass
class Issue:
    kind: str           # clearance | width | edge | corner | unrouted | ring | jumper | outside
    message: str
    x: float
    y: float
    severity: str = "error"     # error | warn | info
    where: Optional[tuple] = None   # ((tagA), (tagB)) for the GUI to highlight

    def __str__(self) -> str:
        return "[%s] %s (%.2f, %.2f)" % (self.severity, self.message, self.x, self.y)


def _owner(tag: Optional[tuple]) -> tuple:
    if not tag:
        return ("?",)
    if tag[0] == "pad":
        return ("pad", tag[1], tag[2])
    if tag[0] in ("trace", "jpad", "via", "isl"):
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
    if owner[0] == "via":
        return "via #%d" % (owner[1] + 1)
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


def part_collisions(board: Board, ref: str) -> List[Issue]:
    """Fast check of ONE part against everything else: used live while a part is dragged and right
    after it is moved, turned or mirrored, so a pad dropped on a trace of another net is reported at
    once instead of waiting for Check. Same rule as check_clearance (copper of different nets closer
    than the clearance), plus body_on_traces for a part soldered flat under the board."""
    if ref not in board.parts:
        return []
    cu = board.copper()
    clr = board.settings.clearance
    mine = [s for s in cu if s.tag and s.tag[0] == "pad" and s.tag[1] == ref]
    others = [s for s in cu if not (s.tag and s.tag[0] == "pad" and s.tag[1] == ref)]
    obb = [s.bbox() for s in others]
    issues: List[Issue] = []
    reported = set()
    for a in mine:
        ba = a.bbox()
        for b, bb in zip(others, obb):
            if a.net is not None and a.net == b.net:
                continue
            if bbox_gap(ba, bb) >= clr:
                continue
            d = shape_dist(a, b)
            if d < clr - 1e-4:
                oa, ob = _owner(a.tag), _owner(b.tag)
                if (oa, ob) in reported:
                    continue
                reported.add((oa, ob))
                x = (max(ba[0], bb[0]) + min(ba[2], bb[2])) / 2.0
                y = (max(ba[1], bb[1]) + min(ba[3], bb[3])) / 2.0
                msg = ("%s touches %s" % (_label(oa), _label(ob)) if d <= 1e-9 else
                       "%s is %.2f mm from %s (needs %.2f)" % (_label(oa), d, _label(ob), clr))
                issues.append(Issue("clearance", msg, x, y, "error", (oa, ob)))
    issues.extend(body_on_traces(board, ref))
    return issues


def body_on_traces(board: Board, ref: str) -> List[Issue]:
    """A through-hole part mounted UNDER the board (mirrored) sits on the copper side. Soldered flat
    (deadbug / castellated pads) its underside rests on any trace running under it: a short waiting to
    happen, so that is a warning. On header pins it stands clear, so that is only a note."""
    if ref not in board.parts or board.is_smd(ref) or not board.on_copper_side(ref):
        return []
    pl = board.parts[ref]
    flat = pl.style in ("dead", "mixed") or any(v in ("dead", "mixed") for v in pl.pad_styles.values())
    x0, y0, x1, y1 = board.court_rect(ref)
    body = Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    own = {n.name for n in (board.net_of("%s.%s" % (ref, p.name)) for p in board.get_def(pl.part_id).pads) if n}
    under = []
    for ti, t in enumerate(board.traces):
        if t.net in own and not flat:
            continue
        for si in range(len(t.widths)):
            a, b = t.points[si], t.points[si + 1]
            if shape_dist(body, Cap(a[0], a[1], b[0], b[1], t.widths[si] / 2.0)) <= 0.0:
                under.append((ti, a, b))
                break
    out = []
    for ti, a, b in under:
        mx, my = (max(min(a[0], b[0]), x0) + min(max(a[0], b[0]), x1)) / 2, (max(min(a[1], b[1]), y0) + min(max(a[1], b[1]), y1)) / 2
        if flat:
            out.append(Issue("body", "%s is soldered flat UNDER the board and its body rests on trace #%d (net %s): "
                             "insulate it (Kapton tape) or move the trace" % (ref, ti, board.traces[ti].net), mx, my,
                             "warn", (("pad", ref), ("trace", ti))))
        else:
            out.append(Issue("body", "%s is mounted under the board over trace #%d (net %s): keep it up on its "
                             "header pins or spacers so it cannot touch the copper" % (ref, ti, board.traces[ti].net),
                             mx, my, "info", (("pad", ref), ("trace", ti))))
    return out


def after_part_edit(board: Board, ref: str, what: str = "Moved") -> Tuple[List[Issue], str]:
    """What to tell the person right after a part is moved, turned, mirrored or placed: the problems
    it caused (to mark in red) and one status line. Traces never follow a part, so the two things that
    go wrong are copper of another net now too close (an error) and trace ends left hanging where the
    pads used to be (a warning)."""
    issues = [i for i in run_drc(board, check_unrouted=False)
              if i.kind in ("clearance", "dangling", "body", "edge")]
    near = part_collisions(board, ref)
    seen = {(i.kind, round(i.x, 2), round(i.y, 2)) for i in issues}
    issues += [i for i in near if (i.kind, round(i.x, 2), round(i.y, 2)) not in seen]
    hits = [i for i in issues if i.kind == "clearance"]
    hang = [i for i in issues if i.kind == "dangling"]
    body = [i for i in issues if i.kind == "body" and i.severity != "info"]
    bits = []
    if hits:
        bits.append("%d COLLISION(S) with copper of another net, marked red (%s%s)" % (
            len(hits), hits[0].message, "; ..." if len(hits) > 1 else ""))
    if body:
        bits.append(body[0].message)
    if hang:
        bits.append("%d trace end(s) left hanging where pads used to be" % len(hang))
    if not bits:
        return issues, "%s %s. No collisions." % (what, ref)
    tail = (" Drag it clear, or right-click it > Route this part's nets (re-routes its traces)."
            if hits or hang else "")
    return issues, "%s %s: %s.%s" % (what, ref, "; ".join(bits), tail)


def run_drc(board: Board, check_unrouted: bool = True) -> List[Issue]:
    st = board.settings
    issues: List[Issue] = []
    W, H = board.width, board.height
    # parts mounted the other way round: not a fault, but easy to build wrong, so always said
    for ref in board.parts:
        if board.is_mirrored(ref):
            x0, y0, x1, y1 = board.court_rect(ref)
            where = "UNDER the board (on the copper side)" if board.on_copper_side(ref) else "on the COMPONENT side"
            issues.append(Issue("mirrored", "%s is MIRRORED: mounted %s, so its pins are mirrored. Fit it on that "
                                "side, and check pin 1 before soldering." % (ref, where),
                                (x0 + x1) / 2, (y0 + y1) / 2, "info"))
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
    for ref in board.parts:
        issues.extend(body_on_traces(board, ref))
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
        from .islands import floating_fill, ground_net, plan as _plan
        _plan(board, full=True)        # so the rubber bands below come from the full fill too
        gnd = ground_net(board)
        if gnd is None:
            issues.append(Issue("islands", "the ground fill is on but the board has no nets, so the fill is "
                                "not joined to any ground pin", board.width / 2, board.height / 2, "warn"))
        else:
            for x, y, area in floating_fill(board):
                issues.append(Issue("islands", "a %.0f mm² piece of ground fill is cut off by islands and "
                                    "touches no %s pin (floating copper)" % (area, gnd), x, y, "warn"))
    if st.backplane:
        from .plane import holes as plane_holes, plan as plane_plan, stitch_frequency, fmt_freq
        from .islands import ground_net as _gn
        gnd = _gn(board)
        pp = plane_plan(board)
        if gnd is None:
            issues.append(Issue("plane", "the back-side ground plane is on but no net is ground yet",
                                W / 2, H / 2, "warn"))
        else:
            hs = plane_holes(board)
            # a via's connection to the plane must not be cut by a neighbouring antipad
            rv = st.via_pad / 2.0
            for vi, v in enumerate(board.vias):
                for hx, hy, dr, net, tag in hs:
                    if net == gnd:
                        continue
                    need = dr / 2.0 + st.backplane_clearance + rv + st.clearance
                    if math.hypot(hx - v.x, hy - v.y) < need - 1e-6:
                        issues.append(Issue("plane", "via #%d is so close to the %s hole that the plane's clearance ring "
                                            "round that hole cuts into the via's back-side connection" % (vi + 1, _label(_owner(tag))),
                                            v.x, v.y, "error"))
            # non-ground holes closer than their antipads to each other merge into one bare hole: fine; but a
            # ground lead's relief ring inside another hole's antipad means that lead is cut off the plane
            for x, y, dr, net, tag in hs:
                if net != gnd:
                    continue
                for hx, hy, dr2, net2, tag2 in hs:
                    if net2 == gnd:
                        continue
                    if math.hypot(hx - x, hy - y) < dr2 / 2.0 + st.backplane_clearance + dr / 2.0 + 0.3:
                        issues.append(Issue("plane", "%s (ground) is inside the plane's clearance ring of %s: it cannot "
                                            "reach the plane there; move the parts apart or make it solid-ground"
                                            % (_label(_owner(tag)), _label(_owner(tag2))), x, y, "warn"))
                        break
            if not board.vias and not any(board.pin_drilled(p) for p in board.nets[gnd].pins if board.has_pin(p)):
                issues.append(Issue("plane", "nothing joins the trace side to the back-side plane: add a via (V) or a "
                                    "through-hole ground pin", W / 2, H / 2, "warn"))
            # stitching guide
            n_links = len(board.vias) + sum(1 for p in board.nets[gnd].pins if board.has_pin(p) and board.pin_drilled(p))
            if n_links:
                area = W * H / n_links
                spacing = math.sqrt(area)
                issues.append(Issue("plane", "plane joined at %d point(s), about one per %.0f mm: fine up to about %s "
                                    "(lambda/20 in FR4); add stitching vias for faster circuits" %
                                    (n_links, spacing, fmt_freq(stitch_frequency(spacing))), W / 2, H / 2, "info"))
    if st.island_mode and st.relief:
        from .islands import relief_current, ground_net as _gn2
        gnd2 = _gn2(board)
        if gnd2 and gnd2 in board.nets:
            from .board import current_capacity
            want = current_capacity(board.net_width(gnd2), st.copper_oz, st.temp_rise)
            have = relief_current(st)
            if want > have * 1.05:
                issues.append(Issue("relief", "the ground net's trace width is good for about %.1f A but each thermal "
                                    "relief carries only about %.1f A: widen the spokes or size them for the current "
                                    "(Board > Ground fill settings), or mark heavy parts solid" % (want, have),
                                    W / 2, H / 2, "warn"))
    if check_unrouted:
        if board.settings.island_mode:
            from .islands import plan as _plan2
            _plan2(board, full=True)
        for net, p1, p2, a, b in board.airwires():
            issues.append(Issue("unrouted", "net %s: %s is not connected to %s yet" % (net, a, b),
                                (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, "warn"))
    return issues


def summarize(issues: List[Issue]) -> str:
    if not issues:
        return "No problems found."
    errs = sum(1 for i in issues if i.severity == "error")
    warns = sum(1 for i in issues if i.severity == "warn")
    issues = [i for i in issues if i.severity != "info"]          # notes (stitching guide) are not problems
    if not issues:
        return "No problems found."
    kinds: Dict[str, int] = {}
    for i in issues:
        kinds[i.kind] = kinds.get(i.kind, 0) + 1
    return "%d error(s), %d warning(s): %s" % (errs, warns, ", ".join("%s x%d" % (k, v) for k, v in sorted(kinds.items())))
