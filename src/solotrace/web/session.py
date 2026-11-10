# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The SoloTrace editor without a window toolkit.

A ``Session`` holds the board, the undo stack, the current tool and selection, and answers
commands (``cmd("press", wx=..., wy=...)``) the way the tkinter window's mouse and menu
handlers do in app.py. Instead of drawing, it hands out the picture as plain data
(``scene()``) and the side panel, the right-click menu and the dialogs as lists of widgets
(``panel()``, ``menu()``, ``dialog()``) that the browser page renders. The editing rules
(snapping, 45 degree traces, cut / trim / tidy, islands, vias, the ground fill) are the same
code the desktop window uses, from board.py, tidy.py, islands.py and plane.py.

WORK IN PROGRESS: many features may be broken.
"""
from __future__ import annotations

import io
import json
import sys
import math
import os
import threading
import time
import zipfile
from typing import Dict, List, Optional, Tuple

from .. import APP_NAME, __build_date__, __version__, title as app_title
from .. import coil, demos, gerber, library, render
from ..library import _natural, short_name


def mirror_message(b, ref: str) -> str:
    """What a mirrored part means for the person building the board (the same words as the window)."""
    if not b.is_mirrored(ref):
        return "%s is mounted normally." % ref
    if b.on_copper_side(ref):
        return ("%s is MIRRORED: mounted UNDER the board, on the copper side, with its pins through the holes from "
                "below (or soldered flat to the copper as deadbug pads). Its pinout is mirrored left to right in this "
                "view and its outline goes on the bottom silkscreen. Check pin 1 before you solder." % ref)
    return ("%s is MIRRORED: an SMD part on the COMPONENT side. Its pads are still on the copper side, so you "
            "can only solder it there if it has leads through holes. Usually you want it unmirrored." % ref)
from ..board import (Board, Island, ISLAND_MIN, MAX_WIDTH, MIN_WIDTH, Placed, Settings, Trace, Via, clamp_island,
                     clamp_width, current_capacity, width_for_current)
from .. import plane as planemod
from ..drc import after_part_edit, part_collisions, run_drc, summarize
from ..geom import Cap, dist, seg_point_dist, shape_dist
from ..islands import (ground_net, guess_ground, make_pads_deadbug, plan as island_plan, ready as island_ready,
                       spoke_width)
from ..laser import LaserOptions, frame_gcode, generate as laser_generate, speed_power_card, trace_ladder_card, validate
from ..parts import FIXED_STYLE_KINDS, PadDef, PartDef
from ..placer import Placer
from ..router import AutoRouter, RouteOptions
from ..tidy import (apply_drag, attached_ends, cut_between, follow_trunk, piece_bounds, project_on_trace,
                    settle_branch_ends, split_trace, tidy_trace, tidy_traces, trim_piece, trim_segment,
                    violation_set)

WIP_TEXT = "WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN"
WIDTH_PRESETS = (0.4, 0.8, 1.5, 2.5, 5.0, 10.0)
ISLAND_SIZES = (2.54, 3.81, 5.08, 6.35, 7.62, 10.16, 12.7, 15.24)
ISLAND_GRID = 0.635
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".solotrace")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
AUTOSAVE_FILE = os.path.join(CONFIG_DIR, "autosave.solotrace")

TOOL_HINTS = {
    "select": "Click things to select them. Drag a part to move it. Right-click for a menu.",
    "place": "Click to place. Shift + click (or R) turns the part. Esc to stop.",
    "wire": "Click a pin, then the pin it connects to. Hold Shift for a rigid wire.",
    "trace": "Click a pin to start a trace, click corners, finish on a pin (Enter or double-click ends early).",
    "trim": "Trim: click a trace section to cut it out. The rest of the trace stays. Esc to stop.",
    "cut": "Cut: click a trace and that piece goes, up to the nearest joints; the rest of the net stays. "
           "Shift + click two points to cut between them.",
    "jumper": "Click the first end, then the second end in a straight line (5 to 15 mm).",
    "via": "Via: click on ground copper (a ground pad, trace, island or the ground fill) to add a via: a hole "
           "with a wire soldered on both sides, joining it to the back-side ground plane. Esc to stop.",
}

HELP_TEXT = """SoloTrace quick guide (web UI)

Single-sided copper board, parts on top, copper underneath. The view shows the board from the
COMPONENT side (press M to flip to the copper side, as you will solder it).

1. Pick a part in the list on the left (the big button swaps the list between through-hole and SMD
   parts), then click on the board to place it. R turns it. Esc stops placing.
2. Wire (W): click a pin, then the pin it connects to. That makes a net (a yellow rubber band).
   Shift makes a rigid wire: the router joins those two pins directly.
3. Auto-place and Auto-route (Board menu), or draw traces by hand with the Trace tool (T).
4. Select (S) and drag parts; drag a trace section sideways to move it. Right-click anything for
   its menu: widths, cut, trim, tidy, re-route one net, pin labels, deadbug pads...
5. Trim (X) removes one section; Cut (C) removes a piece up to the nearest joints; Jumper (J)
   adds a wire link across a trace; Island (I) drops a copper pad; Via (V) adds a via.
6. Board > Ground fill: deadbug / Manhattan style boards with a ground fill. Board > Back-side
   ground plane: a double-clad board whose component side stays solid ground.
7. Check (DRC) lists problems and marks them in red. Then export: Gerber zip, 1:1 PDF / SVG for
   toner transfer, or laser G-code (Elegoo Phecda, GRBL-style, untested on a real machine).

Mouse: wheel = zoom, right or middle drag = pan, right-click = menu, left = tool.
Keys: S select, P place, W wire, T trace, X trim, C cut, J jumper, I island, V via, R / Shift+R
rotate, arrows nudge (Shift = 2.54 mm), Ctrl+D duplicate, Delete, Ctrl+Z / Ctrl+Y, F fit, M flip view,
Shift+M mirror the part (mount it under the board: it gets a pink dashed frame and a MIRRORED tag).
Files: Open reads a .solotrace file from your computer; Save downloads one (your browser's downloads
folder). The board is also autosaved every 2 minutes (File > Recover autosave).
"""


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=1)
    except Exception:
        pass


def shape_json(s) -> dict:
    """A Cap or Poly as a small dict the page can draw."""
    tag = list(s.tag) if s.tag else None
    if s.kind == "cap":
        return {"k": "c", "a": [round(s.x1, 4), round(s.y1, 4)], "b": [round(s.x2, 4), round(s.y2, 4)],
                "r": round(s.r, 4), "net": s.net, "tag": tag}
    return {"k": "p", "pts": [[round(x, 4), round(y, 4)] for x, y in s.pts], "net": s.net, "tag": tag}


def png_from_rows(rows: List[List[Tuple[int, int, int]]]) -> bytes:
    """A small PNG writer (RGB, no dependencies) for the laser preview."""
    import struct
    import zlib
    h = len(rows)
    w = len(rows[0]) if rows else 0
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b in row:
            raw += bytes((r, g, b))

    def chunk(kind: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


class Job:
    """A background task (placer or router) working on a copy of the board."""

    def __init__(self, label: str, func, on_done) -> None:
        self.label = label
        self.func = func
        self.on_done = on_done
        self.msg = "starting"
        self.frac = 0.0
        self.cancel = False
        self.done = False
        self.error: Optional[str] = None
        self.result = None

    def start(self) -> None:
        def run() -> None:
            try:
                self.result = self.func(self)
            except Exception as exc:          # noqa: BLE001 - shown to the user
                self.error = "%s: %s" % (type(exc).__name__, exc)
            self.done = True
        threading.Thread(target=run, daemon=True).start()


class Session:
    """One board being edited, with everything the page needs to show it."""

    def __init__(self, board: Optional[Board] = None, path: Optional[str] = None,
                 sync_mode: Optional[bool] = None) -> None:
        self.lock = threading.RLock()
        # sync_mode: no threads (the in-browser version runs on Pyodide, which cannot start them).
        # Auto-place / auto-route then run inside the command and report progress through
        # progress_hook; the full ground fill is worked out when the page next asks for the state.
        self.sync_mode = (sys.platform == "emscripten") if sync_mode is None else bool(sync_mode)
        self.progress_hook = None
        self.board = board or Board(100, 80, "Untitled")
        self.path = path
        self.dirty = False
        self.undo: List[str] = []
        self.redo: List[str] = []
        self.tool = "select"
        self.armed: Optional[str] = None
        self.arm_rot = 0
        self.arm_mirror = False
        self.sel: Dict[str, object] = {}
        self.scale = 8.0                      # the page tells us its zoom so hit tolerances match
        self.default_style = "tht"
        self.pending_pin: Optional[str] = None
        self.rigid_next = False
        self.trace_pts: List[Tuple[float, float]] = []
        self.trace_net: Optional[str] = None
        self.jump_start: Optional[Tuple[float, float]] = None
        self.cut_start: Optional[Tuple[int, Tuple[float, float]]] = None
        self.marks: List[Tuple[float, float]] = []
        self.drag: Optional[dict] = None
        self.island_new = {"shape": "rect", "w": 5.08, "h": 5.08}
        self.auto_tidy = True
        self.width_scope = "segment"
        self.show_air = True
        self.show_grid = True
        self.lib = library.all_parts()
        self.lib.update({pid: d for pid, d in self.board.defs.items() if pid not in self.lib})
        cfg = load_config()
        mode = cfg.get("parts_mode", "smd" if cfg.get("pro") else "tht")
        self.parts_mode = "smd" if mode == "smd" else "tht"
        self.job: Optional[Job] = None
        self.status_text = "Welcome to %s. %s" % (APP_NAME, WIP_TEXT)
        self.rev = 1
        self.last_autosave = time.time()
        self.drc_issues: List = []
        self.alerts: List[dict] = []          # messages the page shows in a box (what messagebox did)
        self.want_fit = True
        self._fill_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------- basics
    def status(self, msg: str) -> None:
        self.status_text = msg

    def alert(self, msg: str, kind: str = "info") -> None:
        self.alerts.append({"kind": kind, "text": msg})

    def touch(self) -> None:
        self.rev += 1

    def mark_dirty(self) -> None:
        self.dirty = True
        self.touch()

    def snapshot(self) -> str:
        return json.dumps(self.board.to_dict())

    def push_undo(self) -> None:
        self.undo.append(self.snapshot())
        if len(self.undo) > 60:
            self.undo.pop(0)
        self.redo.clear()
        self.mark_dirty()

    def restore(self, snap: str) -> None:
        self.board = Board.from_dict(json.loads(snap))
        self.cut_start = None
        self.sel = {}
        self.marks = []
        self.touch()

    def do_undo(self) -> None:
        if self.undo:
            self.redo.append(self.snapshot())
            self.restore(self.undo.pop())
            self.status("Undo")

    def do_redo(self) -> None:
        if self.redo:
            self.undo.append(self.snapshot())
            self.restore(self.redo.pop())
            self.status("Redo")

    def snap(self, p: Tuple[float, float], g: Optional[float] = None) -> Tuple[float, float]:
        g = g or self.board.settings.place_grid
        return (round(p[0] / g) * g, round(p[1] / g) * g)

    def title(self) -> str:
        name = os.path.basename(self.path) if self.path else self.board.name
        return "%s - %s%s" % (app_title(), name, " *" if self.dirty else "")

    # ------------------------------------------------------------- library
    def library_tree(self, query: str = "") -> List[dict]:
        words = query.strip().lower().split()
        want_smd = self.parts_mode == "smd"
        groups: Dict[str, Dict[str, List[str]]] = {}
        for pid, d in self.lib.items():
            if (d.kind == "smd") != want_smd:
                continue
            grp, sub = library.form_factor(d)
            hay = ("%s %s %s %s %s" % (d.name, pid, d.category, grp, sub)).lower()
            if words and not all(w in hay for w in words):
                continue
            groups.setdefault(grp, {}).setdefault(sub, []).append(pid)
        order = library.FORM_GROUPS + sorted(g for g in groups if g not in library.FORM_GROUPS)
        out = []
        for grp in order:
            if grp not in groups:
                continue
            subs = []
            for sub in sorted(groups[grp], key=lambda x: (x == "", library.SUB_ORDER.index(x)
                                                           if x in library.SUB_ORDER else 99, x)):
                parts = [{"id": pid, "name": short_name(self.lib[pid].name, sub)}
                         for pid in sorted(groups[grp][sub], key=lambda k: _natural(self.lib[k].name))]
                subs.append({"name": sub, "parts": parts})
            out.append({"name": grp, "subs": subs, "open": bool(words) or len(out) == 0 and False})
        return out

    def set_parts_mode(self, mode: str) -> None:
        self.parts_mode = "smd" if mode == "smd" else "tht"
        cfg = load_config()
        cfg["parts_mode"] = self.parts_mode
        cfg.pop("pro", None)
        save_config(cfg)
        if self.parts_mode == "smd":
            self.status("SMD parts: they sit on the COPPER side, so they look mirrored in this view; press M to see "
                        "the board as you will solder it. Needs a steady hand: no solder mask on a home-etched board.")
        else:
            self.status("Through-hole parts (SMD parts already on the board stay).")

    def part_preview(self, pid: str) -> dict:
        if pid not in self.lib:
            return {}
        d = self.lib[pid]
        gb = Board(60, 60, "preview")
        gb.defs = {pid: d}
        gb.parts = {"P": Placed("P", pid, 0, 0, 0, False, "", "tht")}
        gb.touch()
        return {"id": pid, "name": d.name, "note": d.note, "kind": d.kind, "pins": len(d.pads),
                "shapes": [shape_json(s) for s in gb.copper()],
                "drills": [[x, y, dd] for x, y, dd in gb.drills()],
                "segs": [list(sg) for sg in render.part_segments(gb, "P")],
                "favourite": pid in self._favs()}

    def _favs(self) -> List[str]:
        return [p for p in load_config().get("fav_parts", []) if isinstance(p, str)]

    def _recent_parts(self) -> List[str]:
        return [p for p in load_config().get("recent_parts", []) if isinstance(p, str)]

    def set_fav(self, pid: str, on: bool) -> None:
        cfg = load_config()
        favs = [p for p in cfg.get("fav_parts", []) if p != pid]
        if on:
            favs.insert(0, pid)
        cfg["fav_parts"] = favs[:30]
        save_config(cfg)
        self.status(("%s added to favourites." if on else "%s removed from favourites.") % self.lib[pid].name
                    if pid in self.lib else "Favourites updated.")

    def _note_recent(self, pid: str) -> None:
        cfg = load_config()
        rec = [p for p in cfg.get("recent_parts", []) if p != pid]
        cfg["recent_parts"] = [pid] + rec[:11]
        save_config(cfg)

    def quick_list(self) -> List[dict]:
        out = []
        for pid in self._favs():
            if pid in self.lib:
                out.append({"id": pid, "name": "* " + self.lib[pid].name})
        for pid in self._recent_parts():
            if pid in self.lib and pid not in self._favs():
                out.append({"id": pid, "name": self.lib[pid].name})
        return out

    def arm_part(self, pid: str) -> None:
        if pid not in self.lib:
            return
        self.armed = pid
        self.arm_rot = 0
        self.arm_mirror = False
        self.set_tool("place")
        d = self.lib[pid]
        self.status("%s: click on the board to place it. Shift + click or R turns it. Esc to stop." % d.name
                    + ("  SMD: it goes on the COPPER side." if d.kind == "smd" else ""))

    # ------------------------------------------------------------- tools
    def set_tool(self, t: str) -> None:
        if self.tool == "trace" and t != "trace":
            self.trace_pts = []
        self.tool = t
        self.pending_pin = None
        self.jump_start = None
        if t == "place" and not self.armed:
            self.status("Pick a part in the list on the left, then click on the board.")
            return
        if t == "island":
            self.status("Island: click to drop a %s %.4g x %.4g mm copper pad, or drag out a rectangle. Shift + click "
                        "switches round / rectangle. Click an island to select it; drag its corner squares to resize."
                        % (self.island_new["shape"] == "round" and "round" or "rectangular",
                           self.island_new["w"], self.island_new["h"]))
        else:
            self.status(TOOL_HINTS.get(t, ""))

    def escape(self) -> None:
        self.drag = None
        self.trace_pts = []
        self.pending_pin = None
        self.jump_start = None
        self.cut_start = None
        if self.tool in ("place", "wire", "trace", "jumper", "trim", "cut", "island", "via"):
            self.set_tool("select")
        self.sel = {}
        self.touch()

    # ------------------------------------------------------------- hit testing
    def hit_test(self, wx: float, wy: float) -> Dict[str, object]:
        b = self.board
        tol = max(0.25, 4.0 / self.scale)
        probe = Cap(wx, wy, wx, wy, 0.0)
        cu = b.copper()
        best = None
        for s in cu:
            if s.tag and s.tag[0] == "jpad":
                d = shape_dist(probe, s)
                if d <= tol and (best is None or d < best[0]):
                    best = (d, {"jumper": s.tag[1]})
        if best:
            return best[1]
        for s in cu:
            if s.tag and s.tag[0] == "pad" and shape_dist(probe, s) <= 0.0:
                return {"part": s.tag[1], "pin": s.tag[2]}
        bt = None
        for s in cu:
            if s.tag and s.tag[0] == "trace":
                d = shape_dist(probe, s)
                if d <= tol and (bt is None or d < bt[0]):
                    bt = (d, {"trace": s.tag[1], "seg": s.tag[2]})
        if bt:
            return bt[1]
        for s in cu:
            if s.tag and s.tag[0] == "pad" and shape_dist(probe, s) <= tol:
                return {"part": s.tag[1], "pin": s.tag[2]}
        if self.show_air:
            for net, p1, p2, pa, pb in b.airwires():
                if seg_point_dist((wx, wy), p1, p2) <= tol:
                    return {"net": net, "pins": (pa, pb)}
        for ref in reversed(list(b.parts)):
            x0, y0, x1, y1 = b.court_rect(ref)
            if x0 - 0.5 <= wx <= x1 + 0.5 and y0 - 0.5 <= wy <= y1 + 0.5:
                return {"part": ref}
        vi = self.via_at(wx, wy)
        if vi is not None:
            return {"via": vi}
        isl = self.island_at(wx, wy)
        if isl is not None:
            return {"island": isl}
        return {}

    def via_at(self, wx: float, wy: float) -> Optional[int]:
        r = self.board.settings.via_pad / 2.0 + max(0.2, 3.0 / self.scale)
        for i in range(len(self.board.vias) - 1, -1, -1):
            v = self.board.vias[i]
            if math.hypot(v.x - wx, v.y - wy) <= r:
                return i
        return None

    def island_at(self, wx: float, wy: float) -> Optional[int]:
        probe = Cap(wx, wy, wx, wy, 0.0)
        for i in range(len(self.board.islands) - 1, -1, -1):
            if shape_dist(probe, self.board.islands[i].copper()) <= 0.0:
                return i
        return None

    def island_handle(self, wx: float, wy: float) -> Optional[Tuple[int, int, int]]:
        i = self.sel.get("island")
        if i is None or i >= len(self.board.islands):
            return None
        isl = self.board.islands[i]
        tol = 7.0 / self.scale
        for kx in (-1, 1):
            for ky in (-1, 1):
                hx, hy = isl.x + kx * isl.w / 2, isl.y + ky * isl.h / 2
                if abs(hx - wx) <= tol and abs(hy - wy) <= tol:
                    return (i, kx, ky)
        return None

    def lock_radius(self) -> float:
        """How far from a pad's copper a wire click still locks onto it: about 14 screen pixels, so
        it is easy to hit when zoomed out and does not grab the wrong pin when zoomed in."""
        return max(1.4, min(3.0, 14.0 / max(self.scale, 1.0)))

    def pin_near(self, wx: float, wy: float, radius: Optional[float] = None) -> Optional[str]:
        lk = self.board.pin_lock(wx, wy, radius if radius is not None else self.lock_radius())
        return lk[0] if lk else None

    def wire_lock(self, wx: float, wy: float) -> Optional[dict]:
        """What the wire tool would lock onto at this point (drawn as a solid green circle)."""
        lk = self.board.pin_lock(wx, wy, self.lock_radius())
        if lk is None:
            return None
        pin, (sx, sy), r = lk
        n = self.board.net_of(pin)
        return {"pin": pin, "x": round(sx, 4), "y": round(sy, 4), "r": round(r, 3), "ok": pin != self.pending_pin,
                "net": n.name if n else None}

    def hover_net(self, wx: float, wy: float) -> Optional[str]:
        h = self.hit_test(wx, wy)
        if "trace" in h:
            return self.board.traces[h["trace"]].net
        if "pin" in h:
            n = self.board.net_of("%s.%s" % (h["part"], h["pin"]))
            return n.name if n else None
        if "net" in h:
            return h["net"]
        if "jumper" in h:
            return self.board.jumpers[h["jumper"]].net
        return None

    # ------------------------------------------------------------- mouse
    def press(self, wx: float, wy: float, shift: bool = False) -> None:
        """A left click (or the start of a drag) at this board point. ``self.drag`` says what a
        following ``drag_to`` would move."""
        t = self.tool
        self.drag = None
        if t == "via":
            self.via_press(wx, wy)
        elif t == "island" or (t == "select" and self.island_handle(wx, wy)):
            self.island_press(wx, wy, shift)
        elif t == "select":
            hit = self.hit_test(wx, wy)
            if "part" in hit and "pin" not in hit and self.sel == hit:
                isl = self.island_at(wx, wy)
                if isl is not None:
                    hit = {"island": isl}
            self.sel = hit
            ref = hit.get("part")
            if ref and ref in self.board.parts and not self.board.parts[ref].locked:
                pl = self.board.parts[ref]
                self.drag = {"ref": ref, "dx": pl.x - wx, "dy": pl.y - wy}
            elif "island" in hit:
                isl = self.board.islands[hit["island"]]
                self.drag = {"island": hit["island"], "dx": isl.x - wx, "dy": isl.y - wy}
            elif "via" in hit:
                v = self.board.vias[hit["via"]]
                self.drag = {"via": hit["via"], "dx": v.x - wx, "dy": v.y - wy}
            elif "trace" in hit:
                tr = self.board.traces[hit["trace"]]
                self.drag = {"trace": hit["trace"], "seg": hit["seg"], "base": list(tr.points),
                             "basew": list(tr.widths), "start": (wx, wy),
                             "attached": attached_ends(self.board, tr)}
            self.touch()
        elif t == "place":
            if shift:
                self.arm_rot = (self.arm_rot + 90) % 360
                self.status("Turned to %d degrees. Shift + click turns again; click without Shift to place." % self.arm_rot)
            else:
                self.place_here(wx, wy)
        elif t == "wire":
            self.wire_click(wx, wy, shift)
        elif t == "trace":
            self.trace_click(wx, wy)
        elif t == "trim":
            hit = self.hit_test(wx, wy)
            if "trace" in hit:
                self.trim(hit["trace"], hit["seg"])
            else:
                self.status("Trim: click on a trace section to cut it out.")
        elif t == "cut":
            self.cut_click(wx, wy, shift)
        elif t == "jumper":
            self.jumper_click(wx, wy)

    def drag_to(self, wx: float, wy: float, final: bool = True) -> None:
        """Move what ``press`` picked up to this point (the page sends one of these when the mouse
        is let go, after showing a ghost while it moved)."""
        d = self.drag
        if not d:
            return
        b = self.board
        if "draw_island" in d:
            (x0, y0), (x1, y1) = d["draw_island"], self.snap((wx, wy), ISLAND_GRID)
            self.drag = None
            if abs(x1 - x0) >= ISLAND_MIN and abs(y1 - y0) >= ISLAND_MIN:
                self.island_new["w"], self.island_new["h"] = abs(x1 - x0), abs(y1 - y0)
                self.add_island((x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0), abs(y1 - y0))
            else:
                self.add_island(x0, y0)
            return
        moved = False
        if "island" in d:
            i = d["island"]
            if i < len(b.islands):
                isl = b.islands[i]
                if "resize" in d:
                    ax, ay = d["resize"]
                    cx, cy = self.snap((wx, wy), ISLAND_GRID)
                    w = clamp_island(abs(cx - ax))
                    h = clamp_island(abs(cy - ay))
                    new = (ax + (w / 2 if cx >= ax else -w / 2), ay + (h / 2 if cy >= ay else -h / 2), w, h)
                else:
                    nx, ny = self.snap((wx + d["dx"], wy + d["dy"]), ISLAND_GRID)
                    new = (nx, ny, isl.w, isl.h)
                if new != (isl.x, isl.y, isl.w, isl.h):
                    self.push_undo()
                    isl.x, isl.y, isl.w, isl.h = new
                    b.touch()
                    moved = True
                    if "resize" in d:
                        self.island_new = {"shape": isl.shape, "w": isl.w, "h": isl.h}
                    self._island_status(i, "Island #%d %s" % (i + 1, "resized to %.4g x %.4g mm" % (isl.w, isl.h)
                                                               if "resize" in d else "moved"))
        elif "via" in d:
            if d["via"] < len(b.vias):
                v = b.vias[d["via"]]
                nx, ny = self.snap((wx + d["dx"], wy + d["dy"]), ISLAND_GRID)
                if (nx, ny) != (v.x, v.y):
                    self.push_undo()
                    v.x, v.y = nx, ny
                    b.touch()
                    moved = True
                    self.quick_drc("Via moved.")
        elif "ref" in d:
            if d["ref"] in b.parts:
                nx, ny = self.snap((wx + d["dx"], wy + d["dy"]))
                pl = b.parts[d["ref"]]
                if (nx, ny) != (pl.x, pl.y):
                    self.push_undo()
                    b.move_part(d["ref"], nx, ny)
                    moved = True
                    self.part_report(d["ref"], "Moved")
        elif "trace" in d:
            ti = d["trace"]
            if ti < len(b.traces) and dist((wx, wy), d["start"]) * self.scale >= 5:
                off = (wx - d["start"][0], wy - d["start"][1])
                self.push_undo()
                apply_drag(b, ti, d["seg"], d["base"], d["basew"], off)
                follow_trunk(b, b.traces[ti], d["attached"])
                t = b.traces[ti]
                si = min(range(len(t.points) - 1),
                         key=lambda k: seg_point_dist((wx, wy), t.points[k], t.points[k + 1]))
                self.sel = {"trace": ti, "seg": si}
                settle_branch_ends(b)
                moved = True
                n_att = len(d.get("attached", []))
                self.quick_drc("Trace moved%s." % (" (with the %d branch(es) joined to it)" % n_att if n_att else ""))
        if final:
            self.drag = None
        if moved:
            self.touch()

    def double(self, wx: float, wy: float) -> None:
        if self.tool == "trace":
            self.finish_trace()
        elif self.tool == "select":
            h = self.hit_test(wx, wy)
            if "part" in h and h["part"] in self.board.parts:
                self.sel = {"part": h["part"]}
                self.touch()

    # ------------------------------------------------------------- tool actions
    def place_here(self, wx: float, wy: float) -> None:
        if not self.armed or self.armed not in self.lib:
            self.status("Pick a part in the list first.")
            return
        x, y = self.snap((wx, wy))
        self.push_undo()
        b = self.board
        d = self.lib[self.armed]
        if self.armed not in b.defs:
            b.defs[self.armed] = d
        style = self.default_style
        if d.kind in FIXED_STYLE_KINDS:
            style = "tht"
        pl = b.add_part(self.armed, x, y, self.arm_rot, (d.kind == "smd") != self.arm_mirror, style=style)
        self._note_recent(self.armed)
        self.sel = {"part": pl.ref}
        if self.arm_mirror:
            self.status("Placed %s MIRRORED. %s" % (pl.ref, mirror_message(b, pl.ref)))
        elif d.kind == "smd":
            self.status("Placed %s on the COPPER side (SMD): it is mirrored in this view, press M to see it as you "
                        "will solder it. Click again to place another, Esc to stop." % pl.ref)
        else:
            self.status("Placed %s. Click again to place another, Esc to stop." % pl.ref)
        if part_collisions(b, pl.ref):
            self.part_report(pl.ref, "Placed")

    def mirror_selected(self) -> None:
        """Shift+M: mirror the part being placed, or the selected part (mount it on the other side)."""
        if self.tool == "place" and self.armed:
            self.arm_mirror = not self.arm_mirror
            self.status(("The next part goes on MIRRORED: mounted under the board (copper side), pins mirrored. "
                         "Shift+M again to place it normally.") if self.arm_mirror else "The next part goes on normally.")
            self.touch()
            return
        ref = self.sel.get("part")
        if not ref or ref not in self.board.parts:
            self.status("Select a part first (or pick one to place), then Shift+M mirrors it.")
            return
        self.set_mirrored(ref, not self.board.is_mirrored(ref))

    def set_mirrored(self, ref: str, on: bool) -> None:
        b = self.board
        if ref not in b.parts or b.is_mirrored(ref) == bool(on):
            return
        self.push_undo()
        b.mirror_part(ref)
        if not self.part_report(ref, "Mirrored"):
            self.status(mirror_message(b, ref))

    def part_report(self, ref: str, what: str = "Moved") -> list:
        """After a part has moved, turned, been mirrored or placed: mark what it now collides with and
        say so (traces never follow a part, so this is where a pad dropped on a trace is caught)."""
        issues, msg = after_part_edit(self.board, ref, what)
        self.marks = [(i.x, i.y) for i in issues if i.severity != "info"]
        self.status(msg)
        self.touch()
        return [i for i in issues if i.kind == "clearance"]

    def probe_part(self, ref: str, x: float, y: float) -> List[List[float]]:
        """Where the part WOULD collide if dropped with its origin at (x, y): for the red rings the page
        draws on the ghost while dragging. Nothing is changed."""
        b = self.board
        if ref not in b.parts:
            return []
        pl = b.parts[ref]
        nx, ny = self.snap((x, y))
        old = (pl.x, pl.y)
        pl.x, pl.y = nx, ny
        b.touch()
        try:
            return [[round(i.x, 3), round(i.y, 3)] for i in part_collisions(b, ref) if i.severity != "info"]
        finally:
            pl.x, pl.y = old
            b.touch()

    def rotate(self, step: int = 90) -> None:
        if self.tool == "place":
            self.arm_rot = (self.arm_rot + step) % 360
        elif "part" in self.sel and self.sel["part"] in self.board.parts:
            self.push_undo()
            self.board.rotate_part(self.sel["part"], step)
            self.part_report(self.sel["part"], "Turned")
        self.touch()

    def delete_selection(self) -> None:
        s = self.sel
        b = self.board
        if not s:
            return
        self.push_undo()
        if "trace" in s and s["trace"] < len(b.traces):
            del b.traces[s["trace"]]
        elif "jumper" in s and s["jumper"] < len(b.jumpers):
            del b.jumpers[s["jumper"]]
        elif "island" in s and s["island"] < len(b.islands):
            del b.islands[s["island"]]
        elif "via" in s and s["via"] < len(b.vias):
            del b.vias[s["via"]]
        elif "pin" in s:
            b.disconnect("%s.%s" % (s["part"], s["pin"]))
        elif "part" in s:
            b.remove_part(s["part"])
        elif "net" in s:
            b.drop_net(s["net"])
        b.touch()
        self.sel = {}
        self.touch()

    def snap_dir(self, prev: Tuple[float, float], cur: Tuple[float, float]) -> Tuple[float, float]:
        g = self.board.settings.grid
        dx, dy = cur[0] - prev[0], cur[1] - prev[1]
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return prev
        ang = math.atan2(dy, dx)
        k = round(ang / (math.pi / 4))
        ux, uy = math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)
        L = dx * ux + dy * uy
        if k % 2 == 0:
            L = round(L / g) * g
            return (prev[0] + ux * L, prev[1] + uy * L)
        L = round(L / (g * math.sqrt(2))) * g * math.sqrt(2)
        return (prev[0] + ux * L, prev[1] + uy * L)

    def trace_click(self, wx: float, wy: float) -> None:
        b = self.board
        pin = self.pin_near(wx, wy, 1.4)
        isl = self.island_at(wx, wy) if pin is None else None
        isl_net = b.island_net(isl) if isl is not None else None
        if not self.trace_pts:
            if pin is None and isl_net:
                self.trace_net = isl_net
                sp = self.snap((wx, wy), ISLAND_GRID)
                if self.island_at(*sp) != isl:
                    sp = (round(wx, 3), round(wy, 3))
                self.trace_pts = [sp]
                self.status("Net %s (from island #%d). Click corners; finish on a pin or island of the same net."
                            % (isl_net, isl + 1))
                return
            if pin is None:
                self.status("Start a trace on a pin that is already connected (use the Wire tool first), "
                            "or on a copper island that is joined to a net.")
                return
            n = b.net_of(pin)
            if n is None:
                self.status("%s is not on a net yet. Use the Wire tool to connect it first." % pin)
                return
            self.trace_net = n.name
            self.trace_pts = [b.pin_pos(pin)]
            self.status("Net %s. Click corners; finish on a pin of the same net." % n.name)
            return
        if pin is not None:
            n = b.net_of(pin)
            if n is None or n.name != self.trace_net:
                self.status("%s is not on net %s." % (pin, self.trace_net))
                return
            end = b.pin_pos(pin)
            if end != self.trace_pts[-1]:
                self.trace_pts.append(end)
            self.finish_trace(final=True)
            return
        if isl is not None and isl_net == self.trace_net and len(self.trace_pts) >= 1:
            end = (round(wx, 3), round(wy, 3))
            if end != self.trace_pts[-1]:
                self.trace_pts.append(end)
            if len(self.trace_pts) >= 2:
                self.finish_trace(final=True)
                return
        p = self.snap_dir(self.trace_pts[-1], (wx, wy))
        if p != self.trace_pts[-1]:
            self.trace_pts.append(p)

    def finish_trace(self, final: bool = False) -> None:
        if self.tool != "trace" or len(self.trace_pts) < 2 or not self.trace_net:
            self.trace_pts = []
            self.touch()
            return
        pts: List[Tuple[float, float]] = []
        for i, p in enumerate(self.trace_pts):
            if i > 0 and abs(p[0] - pts[-1][0]) > 1e-6 and abs(p[1] - pts[-1][1]) > 1e-6 \
                    and abs(abs(p[0] - pts[-1][0]) - abs(p[1] - pts[-1][1])) > 1e-6:
                q = pts[-1]
                dx, dy = p[0] - q[0], p[1] - q[1]
                m = min(abs(dx), abs(dy))
                pts.append((q[0] + math.copysign(m, dx), q[1] + math.copysign(m, dy)))
            pts.append(p)
        self.push_undo()
        t = self.board.add_trace(self.trace_net, pts, None, manual=True)
        self.status("Trace added to %s (corners are chamfered automatically)." % self.trace_net)
        if t is not None:
            self.sel = {"trace": len(self.board.traces) - 1, "seg": 0}
        self.trace_pts = []
        self.touch()

    def trace_backup(self) -> None:
        if len(self.trace_pts) > 1:
            self.trace_pts.pop()
        else:
            self.trace_pts = []
        self.touch()

    def wire_click(self, wx: float, wy: float, rigid: bool = False) -> None:
        pin = self.pin_near(wx, wy)
        if pin is None:
            self.pending_pin = None
            self.status("Click on a pin.")
        elif self.pending_pin is None:
            self.pending_pin = pin
            self.status("From %s. Now click the other pin (hold Shift for a rigid wire)." % pin)
        elif pin == self.pending_pin:
            self.pending_pin = None
        else:
            self.push_undo()
            rigid = rigid or self.rigid_next
            n = self.board.connect(self.pending_pin, pin, rigid=rigid)
            if rigid:
                self.status("Rigid wire %s - %s on net %s: Auto-route joins these two pins with their own trace "
                            "and branches the rest of the net off it." % (self.pending_pin, pin, n.name))
            else:
                self.status("%s and %s are on net %s" % (self.pending_pin, pin, n.name))
            self.pending_pin = pin
            self.rigid_next = False
        self.touch()

    def cut_click(self, wx: float, wy: float, two_point: bool = False) -> None:
        hit = self.hit_test(wx, wy)
        if "trace" not in hit:
            self.status("Cut: click on a trace to remove that piece (up to the nearest joints). "
                        "Shift + click two points to cut between them.")
            return
        ti = hit["trace"]
        if two_point or self.cut_start is not None:
            _s, q, _d = project_on_trace(self.board.traces[ti], (wx, wy))
            if self.cut_start is None or self.cut_start[0] >= len(self.board.traces):
                self.cut_start = (ti, q)
                self.status("Cut from here: now Shift + click the second point on the same trace (Esc cancels).")
            elif self.cut_start[0] != ti:
                self.status("The second point must be on the same trace. Esc to start over.")
                return
            else:
                self.push_undo()
                net = self.board.traces[ti].net
                kept = cut_between(self.board, ti, self.cut_start[1], q)
                self.cut_start = None
                self.sel = {}
                self.status("Cut between two points on net %s; %d piece(s) of that trace stay. Ctrl+Z undoes it."
                            % (net, kept))
            self.touch()
            return
        self.cut_piece(ti, (wx, wy))

    def cut_piece(self, ti: int, p) -> None:
        b = self.board
        if ti >= len(b.traces):
            return
        net = b.traces[ti].net
        if piece_bounds(b, ti, p) is None:
            self.status("That spot is on a joint (a pad or where another trace meets it). Click the copper between joints.")
            return
        self.push_undo()
        kept = trim_piece(b, ti, p)
        self.sel = {}
        self.status("Removed a piece of net %s between its joints; %d piece(s) of that trace stay, the rest of the "
                    "net is untouched. Ctrl+Z undoes it." % (net, kept or 0))
        self.touch()

    def jumper_click(self, wx: float, wy: float) -> None:
        b = self.board
        st = b.settings
        if self.jump_start is None:
            self.jump_start = self.snap((wx, wy), st.jumper_step)
            self.status("Now click the other end (straight line, %.1f to %.1f mm)." % (st.jumper_min, st.jumper_max))
            return
        a = self.jump_start
        dx, dy = wx - a[0], wy - a[1]
        if abs(dx) >= abs(dy):
            L, p = dx, 0
        else:
            L, p = dy, 1
        steps = max(1, round(abs(L) / st.jumper_step))
        L = math.copysign(min(max(steps * st.jumper_step, st.jumper_min), st.jumper_max), L)
        c = (a[0] + L, a[1]) if p == 0 else (a[0], a[1] + L)
        net = None
        r = st.jumper_pad / 2.0
        for end in (a, c):
            probe = Cap(end[0], end[1], end[0], end[1], r)
            for s in b.copper():
                if s.net and not s.net.startswith("~") and shape_dist(probe, s) <= 0.01:
                    net = s.net
                    break
            if net:
                break
        if not net:
            self.status("Put at least one end of the jumper on a pad or trace that has a net.")
            self.jump_start = None
            return
        self.push_undo()
        b.add_jumper(net, a, c, auto=False)
        self.status("Jumper added on net %s." % net)
        self.jump_start = None
        self.touch()

    # ------------------------------------------------------------- trace edits
    def trim(self, ti: int, si: int) -> None:
        b = self.board
        if ti >= len(b.traces):
            return
        self.push_undo()
        net = b.traces[ti].net
        kept = trim_segment(b, ti, si)
        self.sel = {}
        self.status("Trimmed a section of net %s; %d piece(s) of that trace left. Ctrl+Z undoes it." % (net, kept))
        self.touch()

    def split_here(self, ti: int, si: int, p) -> None:
        if ti >= len(self.board.traces):
            return
        si = min(si, len(self.board.traces[ti].widths) - 1)
        self.push_undo()
        split_trace(self.board, ti, si, p)
        # splitting right at an end leaves a one-point stub: drop it rather than keep an empty trace
        self.board.traces = [t for t in self.board.traces if len(t.points) >= 2 and t.widths]
        self.board.touch()
        if ti >= len(self.board.traces):
            ti = len(self.board.traces) - 1
        self.sel = {"trace": ti, "seg": min(si, len(self.board.traces[ti].widths) - 1)} if ti >= 0 else {}
        self.status("Trace split in two. Each half can now be moved, trimmed or deleted on its own.")
        self.touch()

    def tidy_one(self, ti: int) -> None:
        if ti < len(self.board.traces):
            self.push_undo()
            ch = tidy_trace(self.board, self.board.traces[ti])
            self.status("Trace tidied: ends centred on pads, straight exits for wide traces, chamfers enlarged."
                        if ch else "Nothing to tidy (no room, or it is already tidy).")
            self.touch()

    def tidy_all(self) -> None:
        self.push_undo()
        n = tidy_traces(self.board)
        settle_branch_ends(self.board)
        self.quick_drc("Tidied %d trace(s)." % n)

    def set_width(self, ti: int, si: int, w: float, scope: str) -> None:
        b = self.board
        if ti >= len(b.traces):
            return
        w = clamp_width(float(w))
        self.push_undo()
        t = b.traces[ti]
        si = min(si, len(t.widths) - 1)
        if scope == "segment":
            b.set_segment_width(t, si, w)
        elif scope == "trace":
            b.set_trace_width(t, w)
        else:
            b.set_net_trace_width(t.net, w)
        if self.auto_tidy:
            tidy_traces(b, [x for x in b.traces if x.net == t.net] if scope == "net" else [t])
            settle_branch_ends(b)
        self.sel = {"trace": min(ti, len(b.traces) - 1), "seg": si}
        if t in b.traces:
            self.sel["seg"] = min(si, len(t.widths) - 1)
        self.quick_drc("Width set to %g mm." % w)

    def set_net_width(self, name: str, w: float, apply_existing: bool = True) -> None:
        b = self.board
        if name not in b.nets:
            return
        w = clamp_width(float(w))
        self.push_undo()
        cls = "%g mm" % round(w, 2)
        b.settings.classes[cls] = w
        b.nets[name].cls = cls
        if apply_existing:
            b.set_net_trace_width(name, w)
        b.touch()
        self.touch()

    def quick_drc(self, prefix: str = "Width changed.") -> None:
        iss = [i for i in run_drc(self.board, check_unrouted=False) if i.kind in ("clearance", "edge")]
        self.marks = [(i.x, i.y) for i in iss]
        self.status("%s %s" % (prefix, "%d clearance/edge problem(s) marked in red: make the trace thinner "
                                        "or move things apart." % len(iss) if iss else "Clearances OK."))
        self.touch()

    def fits_up_to(self, t: Trace) -> float:
        b = self.board
        saved = b.traces
        b.traces = [x for x in saved if x is not t]
        b.touch()
        try:
            def ok(w: float) -> bool:
                return not violation_set(b, t.net, t.points, w, stop=1)
            if not ok(MIN_WIDTH):
                return 0.0
            lo, hi = MIN_WIDTH, MAX_WIDTH
            if ok(hi):
                return hi
            for _ in range(9):
                mid = (lo + hi) / 2
                if ok(mid):
                    lo = mid
                else:
                    hi = mid
            return math.floor(lo * 20) / 20
        finally:
            b.traces = saved
            b.touch()

    # ------------------------------------------------------------- nets and parts
    def select_net(self, net: str) -> None:
        self.sel = {"net": net} if net in self.board.nets else {}
        self.touch()

    def net_jumpers(self, net: str, ok: bool) -> None:
        if net in self.board.nets:
            self.push_undo()
            self.board.nets[net].jumpers_ok = bool(ok)
            self.status("Net %s: jumpers %s." % (net, "allowed" if ok else "not allowed"))

    def toggle_rigid(self, a: str, b: str, on: bool) -> None:
        self.push_undo()
        try:
            self.board.set_rigid(a, b, on)
        except ValueError as exc:
            self.status(str(exc))
            return
        self.touch()
        self.status("%s - %s is now %s. Re-route the net to apply it." % (a, b, "rigid" if on else "a normal connection"))

    def rename_net(self, old: str, new: str) -> None:
        new = (new or "").strip()
        if new and new != old and new not in self.board.nets and old in self.board.nets:
            self.push_undo()
            self.board.rename_net(old, new)
            self.sel = {"net": new}
            self.touch()

    def net_class(self, name: str, cls: str) -> None:
        if name in self.board.nets and cls in self.board.settings.classes:
            self.push_undo()
            self.board.set_net_class(name, cls)

    def unroute(self, name: str) -> None:
        self.push_undo()
        b = self.board
        b.traces = [t for t in b.traces if t.net != name]
        b.jumpers = [j for j in b.jumpers if j.net != name]
        b.touch()
        self.touch()

    def start_wire(self, pin: str, rigid: bool = False) -> None:
        if pin not in self.board.all_pins():
            return
        self.set_tool("wire")
        self.pending_pin = pin
        self.rigid_next = rigid
        self.status("From %s. Now click the other pin%s." % (pin, " (rigid wire)" if rigid else ""))

    def start_trace(self, pin: str) -> None:
        if pin not in self.board.all_pins():
            return
        self.set_tool("trace")
        p = self.board.pin_pos(pin)
        self.trace_click(p[0], p[1])

    def start_cut(self, ti: int, p) -> None:
        if ti >= len(self.board.traces):
            return
        self.set_tool("cut")
        _s, q, _d = project_on_trace(self.board.traces[ti], p)
        self.cut_start = (ti, q)
        self.status("Cut from here: now Shift + click the second point on the same trace (Esc cancels).")

    def disconnect(self, pin: str) -> None:
        self.push_undo()
        self.board.disconnect(pin)
        self.board.touch()
        self.touch()

    def set_value(self, ref: str, v: str) -> None:
        if ref in self.board.parts and self.board.parts[ref].value != v:
            self.push_undo()
            self.board.parts[ref].value = v
            self.board.touch()

    def set_pin_labels(self, ref: str, labels: Dict[str, str]) -> None:
        if ref not in self.board.parts:
            return
        self.push_undo()
        pl = self.board.parts[ref]
        pl.pin_labels = dict(labels) if labels else {"_": ""}
        self.board.touch()
        self.touch()

    def set_pin_labels_text(self, ref: str, text: str) -> None:
        if ref in self.board.parts:
            d = self.board.get_def(self.board.parts[ref].part_id)
            self.set_pin_labels(ref, library.parse_pin_labels(d, text or ""))

    def set_pin_labels_preset(self, ref: str, name: str) -> None:
        if ref not in self.board.parts:
            return
        d = self.board.get_def(self.board.parts[ref].part_id)
        if name == "(none)":
            self.set_pin_labels(ref, {})
            return
        for nm, lab in library.pinout_presets(d):
            if nm == name:
                self.set_pin_labels(ref, dict(lab))
                return

    def set_lock(self, ref: str, v: bool) -> None:
        if ref in self.board.parts:
            self.push_undo()
            self.board.parts[ref].locked = bool(v)

    def set_ground_contact(self, ref: str, how: str) -> None:
        if ref in self.board.parts and how in ("", "heavy", "solid"):
            self.push_undo()
            pl = self.board.parts[ref]
            pl.ground_contact = how
            pl.solid_ground = False
            self.board.touch()
            self.status({"": "%s: ground pads get the board's thermal relief.",
                         "heavy": "%s: ground pads get spokes twice as wide (more current, harder to solder).",
                         "solid": "%s: ground pads join the fill / plane solidly (no relief)."}[how] % ref)

    def set_flip(self, ref: str, flip: bool) -> None:
        if ref in self.board.parts:
            self.push_undo()
            self.board.parts[ref].flip = bool(flip)
            self.board.touch()

    def set_style(self, ref: str, style: str) -> None:
        if ref in self.board.parts and style in ("tht", "dead", "mixed"):
            self.push_undo()
            pl = self.board.parts[ref]
            pl.style = style
            pl.pad_styles = {}
            self.board.touch()

    def set_pad_style(self, ref: str, pad: str, style: str) -> None:
        if ref not in self.board.parts:
            return
        self.push_undo()
        pl = self.board.parts[ref]
        if style == "(part)":
            pl.pad_styles.pop(pad, None)
        elif style in ("tht", "dead", "mixed"):
            pl.pad_styles[pad] = style
        self.board.touch()

    def duplicate(self) -> None:
        if "island" in self.sel and self.sel["island"] < len(self.board.islands):
            self.duplicate_island(self.sel["island"])
            return
        ref = self.sel.get("part")
        b = self.board
        if not ref or ref not in b.parts:
            self.status("Select a part to duplicate.")
            return
        pl = b.parts[ref]
        self.push_undo()
        x0, y0, x1, y1 = b.court_rect(ref)
        step = math.ceil((x1 - x0 + 2.54) / 2.54) * 2.54
        nx = pl.x + step if x1 + step < b.width else pl.x - step
        np_ = b.add_part(pl.part_id, nx, pl.y, pl.rot, pl.flip, style=pl.style)
        np_.value = pl.value
        np_.pad_styles = dict(pl.pad_styles)
        b.touch()
        self.sel = {"part": np_.ref}
        if not self.part_report(np_.ref, "Duplicated %s as" % ref):
            self.status("Duplicated %s as %s. Drag it where you want it." % (ref, np_.ref))

    def nudge(self, dx: int, dy: int, big: bool = False) -> None:
        i = self.sel.get("island")
        if i is not None and i < len(self.board.islands):
            g = 2.54 if big else self.board.settings.place_grid
            self.push_undo()
            isl = self.board.islands[i]
            isl.x += dx * g
            isl.y += dy * g
            self.board.touch()
            return
        ref = self.sel.get("part")
        if not ref or ref not in self.board.parts or self.board.parts[ref].locked:
            return
        g = 2.54 if big else self.board.settings.place_grid
        pl = self.board.parts[ref]
        self.push_undo()
        self.board.move_part(ref, pl.x + dx * g, pl.y + dy * g)
        self.part_report(ref, "Nudged")

    # ------------------------------------------------------------- vias
    def via_press(self, wx: float, wy: float) -> None:
        b = self.board
        i = self.via_at(wx, wy)
        if i is not None:
            v = b.vias[i]
            self.sel = {"via": i}
            self.drag = {"via": i, "dx": v.x - wx, "dy": v.y - wy}
            self.touch()
            return
        x, y = self.snap((wx, wy), ISLAND_GRID)
        self.push_undo()
        b.vias.append(Via(x, y))
        b.touch()
        self.sel = {"via": len(b.vias) - 1}
        if not b.settings.backplane:
            self.status("Via added. The back-side ground plane is OFF (Board > Back-side ground plane): until it is on, "
                        "a via is just a ground pad with a hole.")
        elif planemod.via_fits(b, x, y, join_pad=True):
            self.status("Via added: a %.2g mm hole with a wire soldered on both sides. Click to add more, Esc to stop."
                        % b.settings.via_drill)
        else:
            self.status("Via added, but it is not on ground copper, or too close to another net or a part body: "
                        "Check will say what is wrong. Drag it, or add a trace to it.")

    def add_stitch_vias(self) -> None:
        b = self.board
        if not b.settings.backplane:
            self.alert("Turn on Board > Back-side ground plane first.")
            return
        pts = planemod.stitch_points(b)
        if not pts:
            self.status("No room for stitching vias: they need to sit on ground copper or the ground fill, clear of "
                        "parts and other nets.")
            return
        self.push_undo()
        for x, y in pts:
            b.vias.append(Via(x, y))
        b.touch()
        sp = b.settings.stitch_spacing
        self.status("Added %d stitching via(s) on a %g mm grid (good to about %s). Each is a hole with a wire soldered "
                    "on both sides." % (len(pts), sp, planemod.fmt_freq(planemod.stitch_frequency(sp))))

    def add_pin_vias(self) -> None:
        b = self.board
        if not b.settings.backplane:
            self.alert("Turn on Board > Back-side ground plane first.")
            return
        pts = planemod.via_at_ground_pins(b)
        if not pts:
            self.status("Every ground pin is already joined to the plane (or has no room for a via beside it).")
            return
        self.push_undo()
        for x, y in pts:
            b.vias.append(Via(x, y))
        b.touch()
        self.status("Added %d via(s) at the end of deadbug / SMD ground pads; the lead folds over the via, solder both "
                    "sides." % len(pts))

    def countersink_text(self) -> str:
        b = self.board
        rows = planemod.countersink_list(b)
        lines = ["Countersink list for %s: leave the back copper solid, drill every hole, then clear the copper round "
                 "these %d non-ground holes with a 2 to 2.5 mm drill tip or countersink (just enough to break the "
                 "copper ring). Ground leads and vias are NOT in this list: solder them on both sides."
                 % (b.name, len(rows)), "", "X (mm)   Y (mm)   drill   what"]
        for x, y, dr, what in sorted(rows, key=lambda r: (r[1], r[0])):
            lines.append("%7.2f  %7.2f   %.2f    %s" % (x, y, dr, what))
        lines.append("")
        lines.append("Coordinates are the design view (component side), origin at the lower-left corner, Y up.")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------- islands
    def add_island(self, wx: float, wy: float, w: Optional[float] = None, h: Optional[float] = None,
                   shape: Optional[str] = None) -> int:
        n = self.island_new
        x, y = self.snap((wx, wy), ISLAND_GRID)
        self.push_undo()
        isl = Island(x, y, clamp_island(w or n["w"]), clamp_island(h or n["h"]), shape or n["shape"])
        self.board.islands.append(isl)
        self.board.touch()
        i = len(self.board.islands) - 1
        self.sel = {"island": i}
        self._island_status(i, "Island #%d added" % (i + 1))
        return i

    def _island_status(self, i: int, what: str) -> None:
        net = self.board.island_net(i)
        pins = self._island_pins(i)
        if net:
            self.status("%s: joined to net %s%s." % (what, net, " (pins %s)" % ", ".join(pins) if pins else ""))
        else:
            self.status("%s: not joined to anything yet. Put a part's pin on it (deadbug pads are easiest), or draw a "
                        "trace onto it." % what)

    def _island_pins(self, i: int) -> List[str]:
        b = self.board
        shp = None
        for s in b.copper():
            if s.tag and s.tag[0] == "isl" and s.tag[1] == i:
                shp = s
        if shp is None:
            return []
        out = []
        for s in b.copper():
            if s.tag and s.tag[0] == "pad" and shape_dist(s, shp) <= 1e-6:
                pin = "%s.%s" % (s.tag[1], s.tag[2])
                if pin not in out:
                    out.append(pin)
        return out

    def duplicate_island(self, i: int) -> None:
        b = self.board
        if i >= len(b.islands):
            return
        isl = b.islands[i]
        step = math.ceil((isl.w + 1.27) / 1.27) * 1.27
        nx = isl.x + step if isl.x + step + isl.w / 2 < b.width else isl.x - step
        self.push_undo()
        b.islands.append(Island(nx, isl.y, isl.w, isl.h, isl.shape, isl.corner))
        b.touch()
        self.sel = {"island": len(b.islands) - 1}
        self.status("Duplicated island #%d. Drag it where you want it." % (i + 1))

    def set_island(self, i: int, **kw) -> None:
        b = self.board
        if i >= len(b.islands):
            return
        isl = b.islands[i]
        changes = {}
        for k, v in kw.items():
            try:
                if k in ("w", "h"):
                    v = clamp_island(float(v))
                elif k == "corner":
                    v = max(0.0, min(float(v), min(isl.w, isl.h) / 2))
                elif k == "shape":
                    v = "round" if v == "round" else "rect"
                else:
                    continue
            except (TypeError, ValueError):
                self.status("Type a number in mm.")
                return
            changes[k] = v
        self.push_undo()
        for k, v in changes.items():
            setattr(isl, k, v)
        self.island_new = {"shape": isl.shape, "w": isl.w, "h": isl.h}
        b.touch()
        self.sel = {"island": i}
        self._island_status(i, "Island #%d is now %s %.4g x %.4g mm" % (
            i + 1, isl.shape == "round" and "round" or "rectangular", isl.w, isl.h))

    def island_press(self, wx: float, wy: float, shift: bool) -> None:
        b = self.board
        self.drag = None
        h = self.island_handle(wx, wy)
        if h:
            i, kx, ky = h
            isl = b.islands[i]
            self.drag = {"island": i, "resize": (isl.x - kx * isl.w / 2, isl.y - ky * isl.h / 2)}
            return
        if shift:
            n = self.island_new
            n["shape"] = "round" if n["shape"] == "rect" else "rect"
            self.status("New islands will be %s. Shift + click switches back." % (
                "round" if n["shape"] == "round" else "rectangular"))
            self.touch()
            return
        i = self.island_at(wx, wy)
        if i is not None:
            isl = b.islands[i]
            self.sel = {"island": i}
            self.drag = {"island": i, "dx": isl.x - wx, "dy": isl.y - wy}
            self.touch()
            return
        p0 = self.snap((wx, wy), ISLAND_GRID)
        self.drag = {"draw_island": p0}

    def set_islands(self, on: bool, net: str, gap: float, grow: float, dead: bool) -> None:
        b = self.board
        st = b.settings
        self.push_undo()
        was = st.island_mode
        st.island_mode, st.island_net, st.island_gap, st.island_grow = bool(on), net, gap, grow
        msg = []
        if dead:
            n = make_pads_deadbug(b)
            if n:
                msg.append("%d part(s) now have deadbug pads." % n)
        if on:
            g = ground_net(b)
            if g:
                before = len(b.traces)
                b.traces = [t for t in b.traces if t.manual or t.net != g]
                if len(b.traces) != before:
                    msg.append("Removed %d automatic %s trace(s): the fill joins them." % (before - len(b.traces), g))
                msg.insert(0, "Ground fill on: ground fill on %s, %.2g mm gap round everything else." % (g, max(gap, st.clearance)))
            else:
                msg.insert(0, "Ground fill on, but there is no net to use as ground yet; wire some pins first.")
        elif was:
            msg.insert(0, "Ground fill off. Auto-route will route the ground net again.")
        b.touch()
        self.touch()
        self.status(" ".join(msg) or "Ground fill settings saved.")

    def set_backplane(self, on: bool, net: str, vals: dict, relief: bool) -> None:
        b = self.board
        st = b.settings
        self.push_undo()
        was = st.backplane
        st.backplane = bool(on)
        if net or not st.island_mode:
            st.island_net = net
        st.backplane_relief = bool(relief)
        for k, v in vals.items():
            setattr(st, k, v)
        b.touch()
        self.touch()
        g = ground_net(b)
        if on and g:
            self.status("Back-side ground plane on, ground net %s. Ground leads with holes are joined by the plane; "
                        "add vias (V) for deadbug or SMD ground pins and a stitching grid. Check lists what is left." % g)
        elif on:
            self.status("Back-side ground plane on, but there is no net to use as ground yet; wire some pins first.")
        elif was:
            self.status("Back-side ground plane off. Vias stay on the board; delete them if you no longer want them.")
        else:
            self.status("Back plane settings saved.")

    # ------------------------------------------------------------- board settings
    def set_setting(self, key: str, value) -> None:
        """One of the simple on/off or choice settings from the Board menu."""
        st = self.board.settings
        self.push_undo()
        if key == "allow_jumpers":
            st.allow_jumpers = bool(value)
            self.status("Auto-route %s add wire-link jumpers." % ("may" if st.allow_jumpers else "will NOT"))
        elif key == "keep_out_under_parts":
            st.keep_out_under_parts = bool(value)
            self.status("Auto-route will %s. Route again to apply it." % (
                "go round part bodies unless there is no other way" if st.keep_out_under_parts
                else "run under part bodies when that is shorter"))
        elif key == "router" and value in ("auto", "negotiated", "classic"):
            st.router = value
            self.status({"auto": "Auto-route: negotiated congestion first, then the classic tries only if something is "
                                 "left unrouted or needs a jumper.",
                         "negotiated": "Auto-route: negotiated congestion (PathFinder). All nets are routed together; the "
                                       "price of contested copper rises pass after pass until they sort themselves out.",
                         "classic": "Auto-route: classic sequential router, best of up to 6 net orders."}[value])
        elif key == "placer" and value in ("anneal", "routability"):
            st.placer = value
            self.status({"anneal": "Auto-place: annealing on ratsnest length and crossings.",
                         "routability": "Auto-place: annealing that also estimates congestion and penalises boxed-in "
                                        "pads. Slower; often fewer crossings."}[value])
        self.board.touch()

    def apply_settings(self, vals: dict) -> Optional[str]:
        """The Board size and rules dialog. Returns an error message, or None when applied."""
        b = self.board
        st = b.settings
        try:
            def num(k, lo, hi, what):
                v = float(vals.get(k, ""))
                if not (lo <= v <= hi):
                    raise ValueError("%s must be between %g and %g." % (what, lo, hi))
                return v
            w = num("width", 10, 400, "Width")
            h = num("height", 10, 400, "Height")
            new = {"clearance": num("clearance", 0.1, 2, "Gap"),
                   "min_trace": num("min_trace", 0.2, 2, "Thinnest trace"),
                   "edge_clearance": num("edge_clearance", 0, 5, "Edge distance"),
                   "chamfer_factor": num("chamfer_factor", 0.5, 4, "Corner factor"),
                   "chamfer_min": num("chamfer_min", 0.3, 5, "Smallest corner cut"),
                   "jumper_min": num("jumper_min", 2.54, 30, "Shortest jumper"),
                   "jumper_max": num("jumper_max", 5.08, 40, "Longest jumper"),
                   "copper_oz": num("copper_oz", 0.5, 4, "Copper weight"),
                   "temp_rise": num("temp_rise", 1, 60, "Temperature rise")}
            classes: Dict[str, float] = {}
            for line in str(vals.get("classes", "")).splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    classes[k.strip()] = max(0.4, min(10.0, float(v)))
            if not classes:
                raise ValueError("Add at least one net class.")
        except ValueError as exc:
            return str(exc) if str(exc) else "Please type numbers."
        self.push_undo()
        b.name = str(vals.get("name") or b.name)
        b.width, b.height = w, h
        for k, v in new.items():
            setattr(st, k, v)
        st.classes = classes
        for n in b.nets.values():
            if n.cls not in classes:
                n.cls = next(iter(classes))
        b.touch()
        self.want_fit = True
        return None

    # ------------------------------------------------------------- jobs
    def run_job(self, label: str, func, on_done) -> bool:
        if self.job and not self.job.done:
            self.alert("Another job is still running.")
            return False
        j = Job(label, func, on_done)
        if self.sync_mode:
            # no threads: run it here and now; the page shows a "working" box meanwhile
            hook = self.progress_hook

            class _Watch(Job):
                def __setattr__(self, k, v):
                    object.__setattr__(self, k, v)
                    if k in ("msg", "frac") and hook is not None:
                        try:
                            hook(label, str(getattr(self, "msg", "")), float(getattr(self, "frac", 0.0)))
                        except Exception:
                            pass
            j.__class__ = _Watch
            try:
                j.result = func(j)
            except Exception as exc:          # noqa: BLE001 - shown to the user
                j.error = "%s: %s" % (type(exc).__name__, exc)
            j.done = True
            self.job = j
            self.poll_job()
            return True
        self.job = j
        j.start()
        return True

    def poll_job(self) -> Optional[dict]:
        """Called by the server on every request: finishes a job that is done."""
        j = self.job
        if j is None:
            return None
        if not j.done:
            return {"label": j.label, "msg": j.msg, "frac": j.frac, "done": False}
        self.job = None
        if j.error:
            self.alert("%s failed:\n%s" % (j.label, j.error), "error")
            self.status("%s failed." % j.label)
        else:
            j.on_done(j.result)
        self.touch()
        return None

    def cancel_job(self) -> None:
        if self.job:
            self.job.cancel = True
            self.status("Cancelling...")

    def auto_place(self, force: bool = False) -> None:
        if not self.board.parts or not self.board.nets:
            self.alert("Place some parts and connect pins with the Wire tool first.")
            return
        if self.board.islands and not force:
            self.alerts.append({"kind": "ask", "text": "This board has copper islands. Auto-place moves the parts but "
                                "not the islands, so pins will end up off their islands or on the wrong ones (shorts).\n\n"
                                "Auto-place anyway?", "cmd": "auto_place", "args": {"force": True}})
            return
        work = self.board.clone()

        def func(job: Job):
            pl = Placer(work, progress=lambda m, f: (setattr(job, "msg", m), setattr(job, "frac", f)),
                        cancel=lambda: job.cancel, mode=work.settings.placer)
            return pl.run(time_limit=25.0)

        def done(res) -> None:
            self.push_undo()
            for ref, p in work.parts.items():
                if ref in self.board.parts and not self.board.parts[ref].locked:
                    self.board.parts[ref].x, self.board.parts[ref].y, self.board.parts[ref].rot = p.x, p.y, p.rot
            self.board.clear_auto_routes()
            self.board.touch()
            hits = [i for i in run_drc(self.board, check_unrouted=False) if i.kind == "clearance"]
            self.marks = [(i.x, i.y) for i in hits]
            self.status("Placement done: " + res.summary() + ". Automatic routes were removed."
                        + (" %d COLLISION(S) between parts and the hand-drawn traces that stayed, marked red: "
                           "re-route or redraw them." % len(hits) if hits else ""))

        self.run_job("Placing", func, done)

    def auto_route(self, only=None) -> None:
        if not self.board.nets:
            self.alert("Connect some pins with the Wire tool first.")
            return
        work = self.board.clone()

        def func(job: Job):
            r = AutoRouter(work, RouteOptions(time_limit=180.0, algorithm=work.settings.router),
                           progress=lambda m, f: (setattr(job, "msg", m), setattr(job, "frac", f)),
                           cancel=lambda: job.cancel)
            if not only:
                return r.route_all()
            return r.route_nets([only] if isinstance(only, str) else list(only))

        def done(res) -> None:
            self.push_undo()
            self.board.traces = work.traces
            self.board.jumpers = work.jumpers
            self.board.touch()
            issues = run_drc(self.board)
            errs = [i for i in issues if i.severity == "error"]
            self.status("Routing: %s. DRC: %s" % (res.summary(), summarize(issues) if errs else "no errors"))
            if res.failed_nets:
                self.alert("These nets could not be routed:\n%s\n\nTry moving parts apart, Auto-place, a bigger "
                           "board, or draw them by hand with the Trace tool." % ", ".join(res.failed_nets), "warn")

        self.run_job("Routing", func, done)

    def clear_auto(self) -> None:
        self.push_undo()
        self.board.clear_auto_routes()

    def clear_all(self) -> None:
        self.push_undo()
        self.board.clear_all_routes()

    # ------------------------------------------------------------- DRC
    def drc(self) -> dict:
        issues = run_drc(self.board)
        self.drc_issues = issues
        self.marks = [(i.x, i.y) for i in issues]
        self.touch()
        return {"summary": summarize(issues),
                "issues": [{"severity": i.severity, "kind": i.kind, "message": i.message, "x": i.x, "y": i.y}
                           for i in issues]}

    def set_marks(self, pts) -> None:
        self.marks = [(float(x), float(y)) for x, y in pts]
        self.touch()

    # ------------------------------------------------------------- files
    def load_board(self, board: Board, path: Optional[str] = None) -> None:
        self.board = board
        self.path = path
        self.dirty = False
        self.undo.clear()
        self.redo.clear()
        self.sel = {}
        self.marks = []
        self.drag = None
        self.trace_pts = []
        self.pending_pin = None
        self.cut_start = None
        self.jump_start = None
        self.lib.update({pid: d for pid, d in board.defs.items() if pid not in self.lib})
        self.want_fit = True
        self.touch()

    def new_board(self, name: str, w: float, h: float) -> Optional[str]:
        try:
            w, h = float(w), float(h)
            if not (10 <= w <= 400 and 10 <= h <= 400):
                raise ValueError
        except (TypeError, ValueError):
            return "Width and height must be between 10 and 400 mm."
        self.load_board(Board(w, h, name or "Untitled"))
        self.status("New board %s, %g x %g mm." % (self.board.name, w, h))
        return None

    def open_text(self, text: str, name: str) -> Optional[str]:
        try:
            b = Board.from_dict(json.loads(text))
        except Exception as exc:          # noqa: BLE001
            return "Could not open that file: %s" % exc
        self.load_board(b, None)
        self.status("Opened %s." % name)
        return None

    def open_path(self, p: str) -> Optional[str]:
        try:
            b = Board.load(p)
        except Exception as exc:          # noqa: BLE001
            return "Could not open that file: %s" % exc
        self.load_board(b, p)
        self._remember_recent(p)
        self.status("Opened %s." % p)
        return None

    def _remember_recent(self, path: str) -> None:
        cfg = load_config()
        rec = [p for p in cfg.get("recent", []) if p != path]
        cfg["recent"] = [path] + rec[:7]
        save_config(cfg)

    def recent_files(self) -> List[str]:
        return [p for p in load_config().get("recent", []) if isinstance(p, str) and os.path.exists(p)]

    def board_text(self) -> str:
        return json.dumps(self.board.to_dict(), indent=1)

    def file_name(self, suffix: str) -> str:
        base = os.path.basename(self.path) if self.path else self.board.name
        base = base.rsplit(".", 1)[0] if "." in base and self.path else base
        return "%s%s" % (base.replace(" ", "_") or "board", suffix)

    def saved(self) -> None:
        """The page downloaded the board file: nothing is unsaved any more."""
        self.dirty = False
        self.touch()
        self.status("Saved (look in your browser's downloads folder).")

    def save_to_path(self) -> Optional[str]:
        """Save straight to the file it was opened from (only when the server opened a path)."""
        if not self.path:
            return "This board has no file yet: use Save (download)."
        try:
            self.board.save(self.path)
        except Exception as exc:          # noqa: BLE001
            return "Could not save: %s" % exc
        self.dirty = False
        self.touch()
        self.status("Saved %s" % self.path)
        return None

    def autosave_tick(self) -> None:
        if self.dirty and time.time() - self.last_autosave > 120:
            self.last_autosave = time.time()
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                self.board.save(AUTOSAVE_FILE)
            except Exception:
                pass

    def recover_autosave(self) -> Optional[str]:
        if not os.path.exists(AUTOSAVE_FILE):
            return "There is no autosaved board."
        try:
            b = Board.load(AUTOSAVE_FILE)
        except Exception as exc:          # noqa: BLE001
            return "The autosave could not be read: %s" % exc
        self.load_board(b)
        self.dirty = True
        self.status("Recovered the autosaved board. Save it under a name to keep it.")
        return None

    def load_demo(self, name: str) -> None:
        if name in demos.DEMOS:
            self.load_board(demos.DEMOS[name]())
            self.status("Loaded example '%s'. Try Auto-place then Auto-route." % name)

    def import_netlist_text(self, text: str, name: str) -> Optional[str]:
        try:
            nb = Board(self.board.width, self.board.height, name)
            for pid, d in self.lib.items():
                nb.defs[pid] = d
            nb.import_netlist(text)
            nb.defs = {k: v for k, v in nb.defs.items() if any(pl.part_id == k for pl in nb.parts.values())}
        except Exception as exc:          # noqa: BLE001
            return "Could not read the netlist: %s" % exc
        self.load_board(nb)
        return None

    def export_warning(self) -> Optional[str]:
        issues = [i for i in run_drc(self.board, check_unrouted=False) if i.severity == "error"]
        n_air = self.board.unrouted_count()
        if issues or n_air:
            return "The board has %d design-rule error(s) and %d unrouted connection(s)." % (len(issues), n_air)
        return None

    def export(self, kind: str, mirror: bool = True, layer: str = "bottom") -> Tuple[str, bytes, str]:
        """(file name, bytes, mime) for a download."""
        b = self.board
        if kind == "gerber":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for name, text in gerber.make_files(b).items():
                    z.writestr(name, text)
            return self.file_name("_gerber.zip"), buf.getvalue(), "application/zip"
        if kind in ("pdf", "svg"):
            tag = "back-plane" if layer == "top" else ("mirrored" if mirror else "design")
            if kind == "pdf":
                return self.file_name("_%s.pdf" % tag), render.to_pdf(b, mirror=mirror, layer=layer), "application/pdf"
            return (self.file_name("_%s.svg" % tag), render.to_svg(b, mirror=mirror, layer=layer).encode("utf-8"),
                    "image/svg+xml")
        if kind == "netlist":
            return self.file_name("_netlist.txt"), b.export_netlist().encode("utf-8"), "text/plain"
        if kind == "bom":
            return self.file_name("_bom.csv"), render.to_bom_csv(b).encode("utf-8"), "text/csv"
        if kind == "countersink":
            return self.file_name("_countersink.txt"), self.countersink_text().encode("utf-8"), "text/plain"
        if kind == "board":
            return self.file_name(".solotrace"), self.board_text().encode("utf-8"), "application/json"
        raise ValueError("unknown export %r" % kind)

    # ------------------------------------------------------------- laser
    def laser_options(self, vals: Optional[dict] = None) -> LaserOptions:
        o = LaserOptions.from_dict(load_config().get("laser", {}))
        if vals:
            for k, v in vals.items():
                if not hasattr(o, k) or k == "mode" and v not in ("negative", "isolation", "positive"):
                    continue
                cur = getattr(o, k)
                try:
                    if isinstance(cur, bool):
                        v = bool(v)
                    elif isinstance(cur, int):
                        v = int(float(v))
                    elif isinstance(cur, float):
                        v = float(v)
                    else:
                        v = str(v)
                except (TypeError, ValueError):
                    continue
                setattr(o, k, v)
        return o

    def laser_job(self, vals: dict, layer: str = "bottom"):
        o = self.laser_options(vals)
        probs = validate(self.board, o)
        if probs:
            return None, o, probs
        job = laser_generate(self.board, o, self.board.name, layer=layer)
        cfg = load_config()
        cfg["laser"] = o.to_dict()
        save_config(cfg)
        return job, o, []

    def laser_preview_png(self, job, maxw: int = 560, maxh: int = 400) -> bytes:
        import bisect
        b = self.board
        s = min(maxw / b.width, maxh / b.height)
        w, h = max(1, int(b.width * s)), max(1, int(b.height * s))
        paint, burn = (28, 42, 32), (255, 154, 31)
        rows: Dict[float, list] = {}
        for x0, y, x1, _y in job.segments:
            rows.setdefault(round(y, 5), []).append((x0, x1))
        ys = sorted(rows)
        tol = max(1.0 / s, 0.1)
        out = []
        for py in range(h):
            y = b.height - (py + 0.5) / s
            row = [paint] * w
            if ys:
                k = bisect.bisect_left(ys, y)
                cand = [ys[i] for i in (k - 1, k) if 0 <= i < len(ys)]
                near = min(cand, key=lambda v: abs(v - y))
                if abs(near - y) <= tol:
                    for a, c in rows[near]:
                        for px in range(max(0, int(a * s)), min(w, int(c * s) + 1)):
                            row[px] = burn
            out.append(row)
        return png_from_rows(out)

    def laser_extra(self, kind: str, vals: dict) -> Tuple[str, bytes, str]:
        o = self.laser_options(vals)
        if kind == "frame":
            return self.file_name("_frame.gcode"), frame_gcode(self.board, o).encode("utf-8"), "text/plain"
        if kind == "speed":
            return "speed_power_test.gcode", speed_power_card(o).gcode.encode("utf-8"), "text/plain"
        if kind == "ladder":
            return "trace_gap_test.gcode", trace_ladder_card(o).gcode.encode("utf-8"), "text/plain"
        raise ValueError(kind)

    # ------------------------------------------------------------- custom parts
    def save_part(self, vals: dict) -> Optional[str]:
        """The footprint wizard: pads typed as lines 'name x y shape w h drill'."""
        name = str(vals.get("name", "")).strip()
        if not name:
            return "Give the part a name."
        pads: List[PadDef] = []
        for line in str(vals.get("pads", "")).splitlines():
            f = line.split()
            if not f:
                continue
            try:
                shape = f[3] if len(f) > 3 else "round"
                if shape not in ("round", "oval", "rect"):
                    raise ValueError
                w = float(f[4]) if len(f) > 4 else 1.8
                h = float(f[5]) if len(f) > 5 else w
                dr = float(f[6]) if len(f) > 6 else 0.9
                pads.append(PadDef(f[0], float(f[1]), float(f[2]), shape, w, h, dr))
            except (ValueError, IndexError):
                return "Could not read this pad line: %r (name x y shape w h drill)" % line
        if not pads:
            return "Add at least one pad."
        xs = [p.x for p in pads]
        ys = [p.y for p in pads]
        court = (min(xs) - 1.5, min(ys) - 1.5, max(xs) + 1.5, max(ys) + 1.5)
        pid = "USER_" + "".join(c if c.isalnum() else "_" for c in name)[:40]
        part = PartDef(pid, name, str(vals.get("category") or "Custom"), str(vals.get("prefix") or "U"), pads,
                       [("rect", court[0], court[1], court[2], court[3])], court, "part", (0.0, -1.0),
                       str(vals.get("note", "")))
        try:
            fn = library.save_user_part(part)
        except OSError as exc:
            return "Could not save the part: %s" % exc
        self.lib[pid] = part
        self.status("Saved %s to %s. It is under My parts." % (name, fn))
        return None

    def import_kicad_text(self, text: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            part = library.import_kicad_mod(text)
        except Exception as exc:          # noqa: BLE001
            return None, "Could not import that footprint: %s (only through-hole pads are imported)" % exc
        pads = "\n".join("%s %g %g %s %g %g %g" % (p.name, p.x, p.y, p.shape, p.w, p.h, p.drill) for p in part.pads)
        return {"name": part.name, "category": part.category, "prefix": part.prefix, "note": part.note, "pads": pads}, None

    # ------------------------------------------------------------- the picture
    def scene(self) -> dict:
        """Everything the page draws, in paint order, in board mm (Y up)."""
        b = self.board
        sel = self.sel
        pp = planemod.plan(b)
        b._island_fast = True
        ip = island_plan(b)
        fill_ready = island_ready(b) if b.settings.island_mode else True
        out: dict = {
            "rev": self.rev, "w": b.width, "h": b.height, "name": b.name, "title": self.title(),
            "grid": b.settings.place_grid,
            "plane": None, "fill": None, "fill_ready": fill_ready,
            "copper": [shape_json(s) for s in b.copper()],
            "keepouts": [{"ref": r, "pts": [[round(x, 4), round(y, 4)] for x, y in k.pts],
                          "hatch": [[round(v, 3) for v in h] for h in render.keepout_hatch(k.pts)]} for r, k in b.keepouts()],
            "rigid": [[list(p) for p in t.points] for t in b.traces if t.rigid],
            "drills": [[round(x, 4), round(y, 4), d] for x, y, d in b.drills()],
            "vias": [[v.x, v.y] for v in b.vias], "via_pad": b.settings.via_pad,
            "jumpers": [[j.a[0], j.a[1], j.b[0], j.b[1]] for j in b.jumpers],
            "islands": [{"x": i.x, "y": i.y, "w": i.w, "h": i.h, "shape": i.shape} for i in b.islands],
            "marks": [[x, y] for x, y in self.marks],
            "unrouted": b.unrouted_count() if b.nets else -1,
            "sel": {k: (list(v) if isinstance(v, tuple) else v) for k, v in sel.items()},
            "tool": self.tool, "armed": self.armed, "arm_rot": self.arm_rot, "arm_mirror": self.arm_mirror,
            "trace_pts": [list(p) for p in self.trace_pts], "trace_net": self.trace_net,
            "trace_w": b.net_width(self.trace_net) if self.trace_net and self.trace_net in b.nets else 0.8,
            "route_grid": b.settings.grid,
            "pending_pin": self._pending_pin_pos(),
            "rigid_next": self.rigid_next,
            "jump_start": list(self.jump_start) if self.jump_start else None,
            "island_new": dict(self.island_new),
            "backplane": b.settings.backplane, "island_mode": b.settings.island_mode,
            "dirty": self.dirty, "can_undo": bool(self.undo), "can_redo": bool(self.redo),
            "path": self.path, "show_air": self.show_air,
            "status": self.status_text, "parts_mode": self.parts_mode,
            "settings": {"allow_jumpers": b.settings.allow_jumpers, "keep_out": b.settings.keep_out_under_parts,
                         "router": b.settings.router, "placer": b.settings.placer,
                         "island_mode": b.settings.island_mode, "backplane": b.settings.backplane},
            "default_style": self.default_style, "auto_tidy": self.auto_tidy,
            "version": __version__, "build": __build_date__, "wip": WIP_TEXT,
            "want_fit": self.want_fit,
        }
        self.want_fit = False
        if pp is not None:
            out["plane"] = {"rect": list(pp.rect), "cut": [shape_json(s) for s in pp.cut],
                            "fat": [shape_json(s) for s in pp.fat]}
        if ip is not None:
            out["fill"] = {"rect": list(ip.rect), "cut": [shape_json(s) for s in ip.cut],
                           "fat": [shape_json(s) for s in ip.fat]}
        parts = []
        for ref, pl in b.parts.items():
            labs = b.pin_labels_of(ref)
            parts.append({"ref": ref, "label": ref if not pl.value else "%s %s" % (ref, pl.value),
                          "segs": [[round(v, 4) for v in sg] for sg in render.part_segments(b, ref)],
                          "court": [round(v, 4) for v in b.court_rect(ref)], "locked": pl.locked,
                          "mirrored": b.is_mirrored(ref), "under": b.on_copper_side(ref),
                          "x": pl.x, "y": pl.y, "pinlabels": self._pin_label_layout(ref, labs) if labs else []})
        out["parts"] = parts
        air = []
        for net, p1, p2, pa, pb in b.airwires():
            rig = ([pa, pb] in b.nets[net].links or [pb, pa] in b.nets[net].links) if net in b.nets else False
            air.append([net, round(p1[0], 4), round(p1[1], 4), round(p2[0], 4), round(p2[1], 4), rig])
        out["airwires"] = air
        if self.tool == "place" and self.armed and self.armed in self.lib:
            d = self.lib[self.armed]
            gb = Board(400, 400, "ghost")
            gb.defs = {self.armed: d}
            gb.parts = {"G": Placed("G", self.armed, 0, 0, self.arm_rot, (d.kind == "smd") != self.arm_mirror, "", "tht")}
            gb.touch()
            out["ghost"] = {"shapes": [shape_json(s) for s in gb.copper()],
                            "drills": [[x, y, dd] for x, y, dd in gb.drills()],
                            "segs": [list(sg) for sg in render.part_segments(gb, "G")]}
        if self.tool == "cut" and self.cut_start and self.cut_start[0] < len(b.traces):
            out["cut_start"] = {"trace": self.cut_start[0], "p": list(self.cut_start[1])}
        return out

    def _pending_pin_pos(self) -> Optional[List[float]]:
        if not self.pending_pin:
            return None
        try:
            return list(self.board.pin_pos(self.pending_pin))
        except (KeyError, ValueError):
            self.pending_pin = None       # the part went (deleted, undone): nothing to rubber-band from
            return None

    def _pin_label_layout(self, ref: str, labs: Dict[str, str]) -> List[dict]:
        """Where each pin label goes: (x, y, text, direction, offset, room) in mm; the page picks the
        font size and anchor from the zoom. Same rules as the desktop window."""
        b = self.board
        d = b.get_def(b.parts[ref].part_id)
        pads = [(pd, b.pin_pos("%s.%s" % (ref, pd.name))) for pd in d.pads]
        if not pads:
            return []
        x0, y0, x1, y1 = b.court_rect(ref)
        bcx, bcy = (x0 + x1) / 2, (y0 + y1) / 2
        mx = sum(p[0] for _pd, p in pads) / len(pads)
        my = sum(p[1] for _pd, p in pads) / len(pads)
        xs = {round(p[0], 1) for _pd, p in pads}
        ys = {round(p[1], 1) for _pd, p in pads}
        room = -1.0
        if len(xs) == 2 or (len(ys) == 2 and len(xs) != 1):
            gap = (max(xs) - min(xs)) if len(xs) == 2 else (max(ys) - min(ys))
            room = gap / 2 - max(max(pd.w, pd.h) for pd, _p in pads) / 2 - 0.4
        out = []
        for pd, (px, py) in pads:
            t = labs.get(pd.name)
            if not t:
                continue
            if len(ys) == 1 and len(pads) > 1:
                vx, vy = 0.0, (-1.0 if bcy >= py - 1e-6 else 1.0)
            elif len(xs) == 1 and len(pads) > 1:
                vx, vy = (-1.0 if bcx >= px - 1e-6 else 1.0), 0.0
            elif len(xs) == 2:
                vx, vy = (1.0 if mx > px else -1.0), 0.0
            elif len(ys) == 2:
                vx, vy = 0.0, (1.0 if my > py else -1.0)
            else:
                vx, vy = px - mx, py - my
                L = math.hypot(vx, vy) or 1.0
                vx, vy = vx / L, vy / L
            off = max(pd.w, pd.h) / 2 + 0.5
            out.append({"x": round(px, 4), "y": round(py, 4), "t": t, "vx": vx, "vy": vy, "off": off, "room": room})
        return out

    # ------------------------------------------------------------- the side panel
    def panel(self) -> List[dict]:
        """The 'Selection' panel as widgets: label, entry, select, check, radio, button, slider, sep."""
        b = self.board
        s = self.sel
        if "trace" in s and s["trace"] < len(b.traces) and b.traces[s["trace"]].widths:
            return self._panel_trace()
        if "jumper" in s and s["jumper"] < len(b.jumpers):
            j = b.jumpers[s["jumper"]]
            return [{"t": "head", "text": "Wire-link jumper, net %s" % j.net},
                    {"t": "label", "text": "%.1f mm long, %s. Fit a bare wire or a link part on the COMPONENT side; "
                                           "solder both ends on the copper side." % (j.length(), "automatic" if j.auto else "manual")},
                    {"t": "button", "label": "Re-route net %s" % j.net, "cmd": "auto_route", "args": {"only": j.net}},
                    {"t": "button", "label": "Delete jumper", "cmd": "delete", "args": {}, "style": "red"}]
        if "island" in s and s["island"] < len(b.islands):
            return self._panel_island(s["island"])
        if "via" in s and s["via"] < len(b.vias):
            return self._panel_via(s["via"])
        if "part" in s and s["part"] in b.parts:
            return self._panel_part()
        if "net" in s and s["net"] in b.nets:
            return self._panel_net(s["net"])
        n_air = b.unrouted_count()
        return [{"t": "head", "text": "Board %s" % b.name},
                {"t": "label", "text": "%.0f x %.0f mm. %d parts, %d nets, %d traces, %d jumpers, %d connection(s) "
                                       "still to route." % (b.width, b.height, len(b.parts), len(b.nets), len(b.traces),
                                                            len(b.jumpers), n_air)},
                {"t": "label", "muted": True, "text": "Nothing selected. Click a part, a pin, a trace or a yellow "
                                                      "rubber-band line."},
                {"t": "button", "label": "Board size and rules...", "cmd": "dialog", "args": {"name": "settings"}}]

    def _slider(self, start: float, cmd: str, args: dict) -> dict:
        st = self.board.settings
        return {"t": "slider", "value": round(start, 2), "min": MIN_WIDTH, "max": MAX_WIDTH, "step": 0.05,
                "presets": list(WIDTH_PRESETS), "cmd": cmd, "args": args,
                "caption": "%.2f mm  ~ %.1f A (%g oz copper, %g C rise)" % (
                    start, current_capacity(start, st.copper_oz, st.temp_rise), st.copper_oz, st.temp_rise),
                "oz": st.copper_oz, "rise": st.temp_rise}

    def _panel_trace(self) -> List[dict]:
        b = self.board
        ti, si = self.sel["trace"], self.sel.get("seg", 0)
        t = b.traces[ti]
        si = min(si, len(t.widths) - 1)
        a, c = t.points[si], t.points[si + 1]
        fit = self.fits_up_to(t)
        out = [{"t": "head", "text": "Trace on net %s" % t.net},
               {"t": "label", "text": "Section %d of %d, %.1f mm long%s%s" % (
                   si + 1, len(t.widths), dist(a, c), " (drawn by hand)" if t.manual else " (auto-routed)",
                   ", rigid trunk (from a Shift + Wire link)" if t.rigid else "")},
               {"t": "radio", "label": "Width of", "value": self.width_scope, "cmd": "width_scope", "args": {},
                "options": [["segment", "This section only"], ["trace", "Whole trace"], ["net", "Every trace of this net"]]},
               self._slider(t.widths[si], "set_width", {"ti": ti, "si": si}),
               {"t": "label", "muted": True, "text": ("Fits up to about %.2f mm here." % fit) if fit > 0 else
                "Too close to other copper even at the minimum width."},
               {"t": "check", "label": "Auto-tidy when the width changes", "value": self.auto_tidy, "cmd": "auto_tidy", "args": {}},
               {"t": "row", "items": [
                   {"t": "button", "label": "Tidy", "cmd": "tidy", "args": {"ti": ti}},
                   {"t": "button", "label": "Trim", "cmd": "trim", "args": {"ti": ti, "si": si}},
                   {"t": "button", "label": "Delete", "cmd": "delete", "args": {}, "style": "red"}]},
               {"t": "label", "muted": True, "text": "Drag a section sideways to move it. Right-click for more."}]
        if max(t.widths) < b.settings.min_trace:
            out.append({"t": "label", "warn": True, "text": "Below the minimum trace width."})
        return out

    def _panel_part(self) -> List[dict]:
        b = self.board
        ref = self.sel["part"]
        pl = b.parts[ref]
        d = b.get_def(pl.part_id)
        presets = library.pinout_presets(d)
        cur = b.pin_labels_of(ref)
        cur_txt = " ".join(cur.get(pd.name, ".") for pd in d.pads)
        cur_name = next((nm for nm, lab in presets if lab == cur), "(none)" if not cur else "Custom")
        out = [{"t": "head", "text": "%s  -  %s" % (ref, d.name)},
               {"t": "entry", "label": "Value / type", "value": pl.value, "cmd": "set_value", "args": {"ref": ref},
                "focus": True, "hint": "e.g. NE555, BC547, 10k, 100uF 25V. Shown on the board."},
               {"t": "select", "label": "Pin labels", "value": cur_name, "cmd": "pin_labels_preset", "args": {"ref": ref},
                "options": ["(none)"] + [nm for nm, _lab in presets] + ["Custom"]},
               {"t": "entry", "label": "Custom labels", "value": cur_txt if cur else "", "cmd": "pin_labels_text",
                "args": {"ref": ref}, "hint": "In pin order, separated by spaces; '.' skips a pin. Check your datasheet."}]
        gnd = ground_net(b)
        if gnd and any(n.name == gnd for n in [b.net_of("%s.%s" % (ref, pd.name)) for pd in d.pads] if n):
            out.append({"t": "select", "label": "Ground contact", "cmd": "ground_contact", "args": {"ref": ref},
                        "value": "solid" if pl.solid_ground else pl.ground_contact,
                        "options": [["", "Thermal relief (board setting)"], ["heavy", "Heavy: spokes twice as wide"],
                                    ["solid", "Solid: no relief (high current, RF decoupling)"]]})
        out.append({"t": "row", "items": [
            {"t": "button", "label": "Rotate 90", "cmd": "rotate", "args": {"step": 90}},
            {"t": "button", "label": "Duplicate", "cmd": "duplicate", "args": {}},
            {"t": "check", "label": "Lock", "value": pl.locked, "cmd": "set_lock", "args": {"ref": ref}}]})
        out.append({"t": "check", "mirror": True, "value": b.is_mirrored(ref), "cmd": "set_mirrored", "args": {"ref": ref},
                    "label": "Mirrored (SMD on the top side)" if d.kind == "smd"
                    else "Mirrored (mounted UNDER the board)"})
        if b.is_mirrored(ref):
            out.append({"t": "label", "mirror": True, "text": mirror_message(b, ref)})
        if d.kind == "antenna":
            out.append({"t": "label", "muted": True, "text": "Antenna or coil: its copper is part of the part and its hatched "
                        "keep-out box must stay free of copper, fill and plane. Antenna parts are formula starting points: "
                        "measure and trim."})
        elif d.kind == "smd":
            out.append({"t": "label", "muted": True, "text": "SMD part: it sits on the COPPER side, so it is mirrored in "
                        "the component-side view (press M to see it as you will solder it). Its pads are plain copper "
                        "lands with no holes."})
        elif d.kind == "strip":
            out.append({"t": "label", "muted": True, "text": "Hole strip: one bar of copper, one pin, every hole on the same "
                        "net. Through-hole and deadbug at once: push a pin or lead through any hole, or solder a wire or SMD "
                        "part flat on the bar. Rotate it (R) to run it the other way."})
        else:
            out.append({"t": "radio", "label": "Pads of this part", "value": pl.style, "cmd": "set_style", "args": {"ref": ref},
                        "options": [["tht", "Through-hole"], ["dead", "Deadbug (surface solder, no hole)"], ["mixed", "Both"]]})
        if "pin" in self.sel:
            pin = "%s.%s" % (ref, self.sel["pin"])
            n = b.net_of(pin)
            out.append({"t": "sep"})
            out.append({"t": "label", "text": "Pin %s   net: %s" % (self.sel["pin"], n.name if n else "none")})
            out.append({"t": "select", "label": "This pad only", "value": pl.pad_styles.get(self.sel["pin"], "(part)"),
                        "cmd": "set_pad_style", "args": {"ref": ref, "pad": self.sel["pin"]},
                        "options": ["(part)", "tht", "dead", "mixed"]})
            if n:
                out.append({"t": "button", "label": "Disconnect this pin", "cmd": "delete", "args": {}})
        nets = sorted({b.net_of("%s.%s" % (ref, p.name)).name for p in d.pads if b.net_of("%s.%s" % (ref, p.name))})
        if nets:
            out.append({"t": "button", "label": "Route this part's nets", "cmd": "auto_route", "args": {"only": nets}})
        out.append({"t": "button", "label": "Delete part", "cmd": "delete_part", "args": {"ref": ref}, "style": "red"})
        if d.note:
            out.append({"t": "label", "muted": True, "text": d.note})
        return out

    def _panel_net(self, name: str) -> List[dict]:
        b = self.board
        n = b.nets[name]
        out = [{"t": "head", "text": "Net %s" % name},
               {"t": "label", "text": "%d pins: %s" % (len(n.pins), ", ".join(n.pins[:10]) + (" ..." if len(n.pins) > 10 else ""))},
               {"t": "entry", "label": "Name", "value": name, "cmd": "rename_net", "args": {"old": name}},
               {"t": "select", "label": "Class", "value": n.cls, "cmd": "net_class", "args": {"name": name},
                "options": list(b.settings.classes)},
               {"t": "label", "text": "Width used when routing this net", "bold": True},
               {"t": "check", "label": "Also change traces already drawn", "value": True, "cmd": "noop", "args": {},
                "id": "apply_existing"},
               self._slider(b.net_width(name), "set_net_width", {"name": name, "apply_existing_from": "apply_existing"}),
               {"t": "check", "label": "Auto-route may use jumpers on this net", "value": n.jumpers_ok,
                "cmd": "net_jumpers", "args": {"net": name}}]
        if b.settings.island_mode:
            if ground_net(b) == name:
                out.append({"t": "label", "muted": True, "text": "This net is the ground fill: its pins are joined by the "
                            "fill, so Auto-route leaves it alone. A yellow line means a pin sits on a piece of fill that "
                            "is cut off; join it with a trace or a jumper."})
            else:
                out.append({"t": "button", "label": "Use this net as the ground fill", "cmd": "set_islands",
                            "args": {"on": True, "net": name, "gap": b.settings.island_gap, "grow": b.settings.island_grow,
                                     "dead": False}})
        links = b.rigid_links(name)
        if links:
            out.append({"t": "label", "text": "Rigid wires (routed first, direct):", "bold": True})
            for la, lb in links:
                out.append({"t": "row", "items": [{"t": "label", "text": "%s - %s" % (la, lb), "rigid": True},
                                                  {"t": "button", "label": "make normal", "cmd": "toggle_rigid",
                                                   "args": {"a": la, "b": lb, "on": False}, "small": True}]})
        else:
            out.append({"t": "label", "muted": True, "text": "Tip: Shift + Wire between two pins makes a rigid wire: the "
                        "router joins them directly and the rest of the net branches off it (good for power)."})
        out.append({"t": "row", "items": [
            {"t": "button", "label": "Route just this net", "cmd": "auto_route", "args": {"only": name}},
            {"t": "button", "label": "Remove this net's routes", "cmd": "unroute", "args": {"name": name}}]})
        out.append({"t": "button", "label": "Remove net %s" % name, "cmd": "delete", "args": {}, "style": "red"})
        return out

    def _panel_island(self, i: int) -> List[dict]:
        b = self.board
        isl = b.islands[i]
        net = b.island_net(i)
        pins = self._island_pins(i)
        out = [{"t": "head", "text": "Copper island #%d" % (i + 1)},
               {"t": "label", "text": ("Joined to net %s%s" % (net, (". Pins on it: " + ", ".join(pins)) if pins else ""))
                if net else "Not joined to anything yet: put a part's pin on it, or draw a trace onto it."},
               {"t": "radio", "label": "Shape", "value": isl.shape, "cmd": "set_island", "args": {"i": i, "key": "shape"},
                "options": [["rect", "Rectangle"], ["round", "Round"]]},
               {"t": "entry", "label": "Width (mm)", "value": "%.4g" % isl.w, "cmd": "set_island", "args": {"i": i, "key": "w"}, "num": True},
               {"t": "entry", "label": "Height (mm)", "value": "%.4g" % isl.h, "cmd": "set_island", "args": {"i": i, "key": "h"}, "num": True}]
        if isl.shape != "round":
            out.append({"t": "entry", "label": "Corner cut (mm)", "value": "%.4g" % isl.corner, "cmd": "set_island",
                        "args": {"i": i, "key": "corner"}, "num": True})
        out.append({"t": "label", "text": "Square / circle sizes:"})
        out.append({"t": "row", "items": [{"t": "button", "label": "%.4g" % v, "small": True, "cmd": "set_island_size",
                                           "args": {"i": i, "w": v, "h": v}} for v in ISLAND_SIZES]})
        out.append({"t": "row", "items": [
            {"t": "button", "label": "Turn 90", "cmd": "set_island_size", "args": {"i": i, "w": isl.h, "h": isl.w}},
            {"t": "button", "label": "Duplicate", "cmd": "duplicate_island", "args": {"i": i}},
            {"t": "button", "label": "Delete", "cmd": "delete", "args": {}, "style": "red"}]})
        out.append({"t": "label", "muted": True, "text": "Drag the island to move it, drag a white corner square to resize "
                    "it. Pins of two different nets on one island short them (Check marks it)."})
        return out

    def _panel_via(self, i: int) -> List[dict]:
        b = self.board
        v = b.vias[i]
        g = ground_net(b)
        out = [{"t": "head", "text": "Via #%d at %.2f, %.2f mm" % (i + 1, v.x, v.y)},
               {"t": "label", "text": "A %.2g mm hole with a bit of bare wire through it, soldered on both sides: it "
                                      "joins the copper here to the back-side ground plane%s." % (
                                          b.settings.via_drill, " (net %s)" % g if g else "")}]
        if not b.settings.backplane:
            out.append({"t": "label", "muted": True, "text": "The back-side plane is off: Board > Back-side ground plane."})
        elif not planemod.via_fits(b, v.x, v.y, join_pad=True):
            out.append({"t": "label", "warn": True, "text": "This via is not on ground copper, or too close to another "
                        "net, a part body or a non-ground hole. Drag it somewhere better."})
        out.append({"t": "row", "items": [
            {"t": "button", "label": "Delete via", "cmd": "delete", "args": {}, "style": "red"},
            {"t": "button", "label": "Plane settings...", "cmd": "dialog", "args": {"name": "backplane"}}]})
        return out

    # ------------------------------------------------------------- the right-click menu
    def menu(self, wx: float, wy: float) -> List[dict]:
        """Items: {label, cmd, args, head, sep, disabled, checked, sub:[...]}."""
        b = self.board
        st = b.settings
        m: List[dict] = []

        def head(text: str) -> None:
            m.append({"label": text, "head": True})

        def width_menu(cmd: str, args: dict) -> List[dict]:
            return [{"label": "%g mm  (~%.1f A)" % (w, current_capacity(w, st.copper_oz, st.temp_rise)),
                     "cmd": cmd, "args": dict(args, w=w)} for w in sorted(WIDTH_PRESETS + (3.0, 7.5))]

        if self.tool == "trace" and self.trace_pts:
            head("Drawing a trace on net %s" % self.trace_net)
            m += [{"label": "Finish trace here", "cmd": "finish_trace", "args": {}, "key": "Enter"},
                  {"label": "Remove last corner", "cmd": "trace_backup", "args": {}, "key": "Backspace"},
                  {"label": "Cancel trace", "cmd": "escape", "args": {}, "key": "Esc"}]
        elif self.tool == "place" and self.armed and self.armed in self.lib:
            head("Placing %s" % self.lib[self.armed].name)
            m += [{"label": "Turn part 90 degrees", "cmd": "rotate", "args": {"step": 90}, "key": "R"},
                  {"label": "Place it mirrored (under the board)", "checked": self.arm_mirror, "cmd": "mirror", "args": {},
                   "key": "Shift+M"},
                  {"label": "Stop placing", "cmd": "escape", "args": {}, "key": "Esc"}]
        else:
            hit = self.hit_test(wx, wy)
            self.sel = hit
            self.touch()
            if "trace" in hit:
                ti, si = hit["trace"], hit["seg"]
                t = b.traces[ti]
                head("Trace on net %s (%.2f mm)" % (t.net, t.widths[si]))
                m.append({"label": "Width of this section", "sub": width_menu("set_width", {"ti": ti, "si": si, "scope": "segment"})})
                m.append({"label": "Width of whole trace", "sub": width_menu("set_width", {"ti": ti, "si": si, "scope": "trace"})})
                m.append({"label": "Width of whole net", "sub": width_menu("set_width", {"ti": ti, "si": si, "scope": "net"})})
                m.append({"sep": True})
                m.append({"label": "Trim this section", "cmd": "trim", "args": {"ti": ti, "si": si}})
                pb = piece_bounds(b, ti, (wx, wy))
                m.append({"label": "Cut this piece (up to the nearest joints)" if pb else
                          "Cut this piece (not on a joint: right-click the copper between joints)",
                          "cmd": "cut_piece", "args": {"ti": ti, "x": wx, "y": wy}, "disabled": not pb})
                m.append({"label": "Cut between two points (click the second)...", "cmd": "start_cut", "args": {"ti": ti, "x": wx, "y": wy}})
                m.append({"label": "Split trace here", "cmd": "split", "args": {"ti": ti, "si": si, "x": wx, "y": wy}})
                m.append({"label": "Tidy: straight pad exits, bigger chamfers", "cmd": "tidy", "args": {"ti": ti}})
                m.append({"label": "Tip: drag a section sideways to move it", "disabled": True})
                m.append({"sep": True})
                m.append({"label": "Highlight net %s" % t.net, "cmd": "select_net", "args": {"net": t.net}})
                jok = b.nets[t.net].jumpers_ok if t.net in b.nets else True
                m.append({"label": "Allow jumpers on net %s" % t.net, "checked": jok, "cmd": "net_jumpers",
                          "args": {"net": t.net, "ok": not jok}})
                m.append({"label": "Re-route net %s" % t.net, "cmd": "auto_route", "args": {"only": t.net}})
                m.append({"label": "Delete trace", "cmd": "delete", "args": {}, "key": "Del"})
            elif "via" in hit and hit["via"] < len(b.vias):
                head("Via #%d (hole + wire soldered both sides, to the back-side ground plane)" % (hit["via"] + 1))
                m.append({"label": "Delete via", "cmd": "delete", "args": {}, "key": "Del"})
                m.append({"label": "Add stitching vias", "cmd": "add_stitch_vias", "args": {}})
                m.append({"label": "Back-side ground plane settings...", "cmd": "dialog", "args": {"name": "backplane"}})
            elif "island" in hit and hit["island"] < len(b.islands):
                ii = hit["island"]
                isl = b.islands[ii]
                net = b.island_net(ii)
                head("Island #%d, %s %.4g x %.4g mm, %s" % (ii + 1, isl.shape == "round" and "round" or "rectangle",
                                                            isl.w, isl.h, "net %s" % net if net else "not joined yet"))
                m.append({"label": "Make it round" if isl.shape == "rect" else "Make it rectangular", "cmd": "set_island",
                          "args": {"i": ii, "key": "shape", "value": "round" if isl.shape == "rect" else "rect"}})
                sizes = [{"label": "%.4g x %.4g mm" % (v, v), "cmd": "set_island_size", "args": {"i": ii, "w": v, "h": v}}
                         for v in ISLAND_SIZES]
                sizes += [{"label": "%.4g x %.4g mm" % (a_, b_), "cmd": "set_island_size", "args": {"i": ii, "w": a_, "h": b_}}
                          for a_, b_ in ((5.08, 2.54), (7.62, 3.81), (10.16, 5.08), (15.24, 5.08))]
                m.append({"label": "Size", "sub": sizes})
                m.append({"label": "Turn 90 degrees (swap width and height)", "cmd": "set_island_size",
                          "args": {"i": ii, "w": isl.h, "h": isl.w}})
                m.append({"sep": True})
                m.append({"label": "Duplicate island", "cmd": "duplicate_island", "args": {"i": ii}, "key": "Ctrl+D"})
                m.append({"label": "Delete island", "cmd": "delete", "args": {}, "key": "Del"})
            elif "jumper" in hit:
                j = b.jumpers[hit["jumper"]]
                head("Jumper on net %s (%.1f mm)" % (j.net, j.length()))
                m.append({"label": "Re-route net %s" % j.net, "cmd": "auto_route", "args": {"only": j.net}})
                m.append({"label": "Delete jumper", "cmd": "delete", "args": {}, "key": "Del"})
            elif "part" in hit and hit["part"] in b.parts:
                ref = hit["part"]
                pl = b.parts[ref]
                d = b.get_def(pl.part_id)
                if "pin" in hit:
                    pin = "%s.%s" % (ref, hit["pin"])
                    n = b.net_of(pin)
                    head("Pin %s  (net %s)" % (pin, n.name if n else "none"))
                    m.append({"label": "Wire from this pin", "cmd": "start_wire", "args": {"pin": pin}, "key": "W"})
                    m.append({"label": "Rigid (direct A-B) wire from this pin", "cmd": "start_wire", "args": {"pin": pin, "rigid": True}})
                    if n:
                        m.append({"label": "Draw trace from this pin", "cmd": "start_trace", "args": {"pin": pin}, "key": "T"})
                        m.append({"label": "Route net %s" % n.name, "cmd": "auto_route", "args": {"only": n.name}})
                        m.append({"label": "Disconnect this pin", "cmd": "disconnect", "args": {"pin": pin}})
                    m.append({"label": "This pad's style", "sub": [
                        {"label": tx, "cmd": "set_pad_style", "args": {"ref": ref, "pad": hit["pin"], "style": v}}
                        for v, tx in (("(part)", "Same as the part"), ("tht", "Through-hole"), ("dead", "Deadbug"), ("mixed", "Both"))]})
                    m.append({"sep": True})
                else:
                    head("%s  -  %s" % (ref, d.name))
                m.append({"label": "Set value / type...", "cmd": "focus_value", "args": {"ref": ref}, "key": "double-click"})
                labs = [{"label": "%s   (%s)" % (nm, " ".join(lab.get(pd.name, ".") for pd in d.pads)) if len(d.pads) <= 4 else nm,
                         "cmd": "pin_labels_preset", "args": {"ref": ref, "value": nm}} for nm, lab in library.pinout_presets(d)]
                labs += [{"sep": True}, {"label": "Custom (type them in the right panel)...", "cmd": "focus_value", "args": {"ref": ref}},
                         {"label": "No labels", "cmd": "pin_labels_preset", "args": {"ref": ref, "value": "(none)"}}]
                m.append({"label": "Pin labels", "sub": labs})
                m.append({"sep": True})
                m.append({"label": "Rotate 90 degrees", "cmd": "rotate", "args": {"step": 90}, "key": "R"})
                m.append({"label": "Rotate back 90 degrees", "cmd": "rotate", "args": {"step": -90}, "key": "Shift+R"})
                m.append({"label": "Duplicate", "cmd": "duplicate", "args": {}, "key": "Ctrl+D"})
                m.append({"label": "Mirrored (SMD on the component side)" if b.is_smd(ref) else "Mirrored (mount it under the board)",
                          "checked": b.is_mirrored(ref), "cmd": "set_mirrored", "args": {"ref": ref, "value": not b.is_mirrored(ref)},
                          "key": "Shift+M"})
                m.append({"label": "Lock (auto-place leaves it alone)", "checked": pl.locked, "cmd": "set_lock",
                          "args": {"ref": ref, "value": not pl.locked}})
                m.append({"label": "Pads of this part", "sub": [
                    {"label": tx, "cmd": "set_style", "args": {"ref": ref, "value": v}}
                    for v, tx in (("tht", "Through-hole"), ("dead", "Deadbug (no hole)"), ("mixed", "Both"))]})
                nets = sorted({b.net_of("%s.%s" % (ref, p.name)).name for p in d.pads if b.net_of("%s.%s" % (ref, p.name))})
                if nets:
                    m.append({"label": "Route this part's nets", "cmd": "auto_route", "args": {"only": nets}})
                m.append({"sep": True})
                m.append({"label": "Delete part", "cmd": "delete_part", "args": {"ref": ref}, "key": "Del"})
            elif "net" in hit:
                name = hit["net"]
                head("Connection, net %s" % name)
                m.append({"label": "Route this net", "cmd": "auto_route", "args": {"only": name}})
                if hit.get("pins"):
                    pa, pb_ = hit["pins"]
                    is_rigid = any(set(lk) == {pa, pb_} for lk in b.nets[name].links)
                    m.append({"label": ("Make %s - %s a normal connection" if is_rigid else "Make %s - %s rigid (direct trunk)") % (pa, pb_),
                              "cmd": "toggle_rigid", "args": {"a": pa, "b": pb_, "on": not is_rigid}})
                m.append({"label": "Width for this net", "sub": width_menu("set_net_width", {"name": name})})
                jok = b.nets[name].jumpers_ok
                m.append({"label": "Allow jumpers on this net", "checked": jok, "cmd": "net_jumpers", "args": {"net": name, "ok": not jok}})
                m.append({"label": "Draw it by hand (Trace tool)", "cmd": "tool", "args": {"name": "trace"}})
                m.append({"sep": True})
                m.append({"label": "Remove net %s" % name, "cmd": "delete", "args": {}, "key": "Del"})
            else:
                head("Board %s" % b.name)
                if self.armed and self.armed in self.lib:
                    m.append({"label": "Place %s here" % self.lib[self.armed].name, "cmd": "place_at", "args": {"x": wx, "y": wy}})
                m.append({"label": "Add a copper island here", "cmd": "add_island", "args": {"x": wx, "y": wy}})
                if st.backplane:
                    m.append({"label": "Add a via here", "cmd": "via_at", "args": {"x": wx, "y": wy}})
                m.append({"label": "Auto-place", "cmd": "auto_place", "args": {}})
                m.append({"label": "Auto-route", "cmd": "auto_route", "args": {}})
                m.append({"label": "Tidy all traces", "cmd": "tidy_all", "args": {}})
                m.append({"label": "Check (DRC)", "cmd": "show_drc", "args": {}})
                m.append({"sep": True})
                m.append({"label": "Fit board", "cmd": "fit", "args": {}, "key": "F"})
                m.append({"label": "Flip view (copper / component side)", "cmd": "mirror", "args": {}, "key": "M"})
                m.append({"label": "Board size and rules...", "cmd": "dialog", "args": {"name": "settings"}})
        m.append({"sep": True})
        m.append({"label": "Undo", "cmd": "undo", "args": {}, "key": "Ctrl+Z", "disabled": not self.undo})
        m.append({"label": "Redo", "cmd": "redo", "args": {}, "key": "Ctrl+Y", "disabled": not self.redo})
        return m

    # ------------------------------------------------------------- dialogs
    def dialog(self, name: str) -> dict:
        """A dialog as data: {title, fields:[{k,label,type,value,options,hint}], info, submit, buttons}."""
        b = self.board
        st = b.settings
        if name == "settings":
            fields = [{"k": "name", "label": "Board name", "type": "text", "value": b.name},
                      {"k": "width", "label": "Width (mm)", "type": "number", "value": b.width},
                      {"k": "height", "label": "Height (mm)", "type": "number", "value": b.height},
                      {"k": "clearance", "label": "Copper to copper gap (mm)", "type": "number", "value": st.clearance},
                      {"k": "min_trace", "label": "Thinnest trace (mm)", "type": "number", "value": st.min_trace},
                      {"k": "edge_clearance", "label": "Copper to board edge (mm)", "type": "number", "value": st.edge_clearance},
                      {"k": "chamfer_factor", "label": "Corner cut = this x trace width", "type": "number", "value": st.chamfer_factor},
                      {"k": "chamfer_min", "label": "Smallest corner cut (mm)", "type": "number", "value": st.chamfer_min},
                      {"k": "jumper_min", "label": "Shortest jumper (mm)", "type": "number", "value": st.jumper_min},
                      {"k": "jumper_max", "label": "Longest jumper (mm)", "type": "number", "value": st.jumper_max},
                      {"k": "copper_oz", "label": "Copper weight (oz)", "type": "number", "value": st.copper_oz},
                      {"k": "temp_rise", "label": "Allowed temperature rise (C)", "type": "number", "value": st.temp_rise},
                      {"k": "classes", "label": "Net classes (name = width mm)", "type": "textarea",
                       "value": "\n".join("%s = %g" % kv for kv in st.classes.items())}]
            return {"title": "Board size and rules", "fields": fields, "submit": "apply_settings", "ok": "Apply",
                    "info": "Every trace width is limited to 0.4 to 10 mm. A 90 degree trace corner cannot be made."}
        if name == "new":
            return {"title": "New board", "submit": "new_board", "ok": "Create",
                    "fields": [{"k": "name", "label": "Name", "type": "text", "value": "My board"},
                               {"k": "w", "label": "Width mm", "type": "number", "value": 100},
                               {"k": "h", "label": "Height mm", "type": "number", "value": 80}]}
        if name == "islands":
            guess = guess_ground(b)
            nets = sorted(b.nets)
            n_tht = sum(1 for r, pl in b.parts.items() if (pl.style != "dead" or pl.pad_styles) and not b.is_smd(r))
            sw = spoke_width(st)
            fields = [{"k": "on", "label": "Ground fill on (deadbug / Manhattan style)", "type": "check", "value": st.island_mode},
                      {"k": "net", "label": "Ground net", "type": "select", "value": st.island_net if st.island_net in b.nets else "",
                       "options": [["", "Guess (%s)" % (guess or "none yet")]] + [[n, n] for n in nets]},
                      {"k": "gap", "label": "Gap round every other net (mm)", "type": "number", "value": st.island_gap},
                      {"k": "grow", "label": "Fatten islands by (mm)", "type": "number", "value": st.island_grow},
                      {"k": "dead", "label": "Make every pad a deadbug pad (no holes to drill)", "type": "check",
                       "value": (not st.island_mode) and n_tht > 0},
                      {"k": "drop", "label": "Cut away pieces of fill no ground pin sits on", "type": "check", "value": st.island_drop_floating},
                      {"k": "sep1", "label": "Thermal reliefs (ground pads: a ring of bare board bridged by spokes)", "type": "head"},
                      {"k": "relief", "label": "Thermal reliefs on ground pads", "type": "check", "value": st.relief},
                      {"k": "spokes", "label": "Spokes per pad (2, 4 or 8)", "type": "number", "value": st.relief_spokes},
                      {"k": "swidth", "label": "Spoke width (mm)", "type": "number", "value": st.relief_width},
                      {"k": "sgap", "label": "Ring width (mm)", "type": "number", "value": st.relief_gap},
                      {"k": "amps", "label": "Or size the spokes for this current (A; blank = use the width)", "type": "text",
                       "value": "%g" % st.relief_amps if st.relief_amps > 0 else ""},
                      {"k": "rislands", "label": "Also relieve ground islands (scaled spokes)", "type": "check", "value": st.relief_islands},
                      {"k": "rdiag", "label": "Round pads: spokes at 45 degrees (off = 0/90)", "type": "check", "value": st.relief_diag}]
            return {"title": "Ground fill", "fields": fields, "submit": "apply_islands", "ok": "Apply",
                    "info": "With the fill on, every other net becomes an island of copper with a gap round it (at least "
                            "the board's %g mm clearance). Spokes now: %g mm wide; 4 x %g mm carry about %.1f A at a %g C "
                            "rise. Each part's panel can make its ground pads heavy or solid." % (
                                st.clearance, sw, sw, 4 * current_capacity(sw, st.copper_oz, st.temp_rise), st.temp_rise)}
        if name == "backplane":
            guess = guess_ground(b)
            nets = sorted(b.nets)
            fields = [{"k": "on", "label": "Back-side ground plane on (double-clad board, component side solid copper)",
                       "type": "check", "value": st.backplane},
                      {"k": "net", "label": "Ground net", "type": "select", "value": st.island_net if st.island_net in b.nets else "",
                       "options": [["", "Guess (%s)" % (guess or "none yet")]] + [[n, n] for n in nets]},
                      {"k": "backplane_clearance", "label": "Bare ring round each non-ground hole, beyond the hole (mm)",
                       "type": "number", "value": st.backplane_clearance},
                      {"k": "via_drill", "label": "Via hole (mm; 0.7 for 0.6 mm wire)", "type": "number", "value": st.via_drill},
                      {"k": "via_pad", "label": "Via pad on the trace side (mm)", "type": "number", "value": st.via_pad},
                      {"k": "stitch_spacing", "label": "Stitching via grid (mm)", "type": "number", "value": st.stitch_spacing},
                      {"k": "relief", "label": "Thermal reliefs on the plane round ground leads and vias", "type": "check",
                       "value": st.backplane_relief}]
            f = planemod.stitch_frequency(st.stitch_spacing)
            return {"title": "Back-side ground plane", "fields": fields, "submit": "apply_backplane", "ok": "Apply",
                    "buttons": [{"label": "Add stitching vias", "cmd": "add_stitch_vias"},
                                {"label": "Vias at deadbug / SMD ground pins", "cmd": "add_pin_vias"},
                                {"label": "Countersink list...", "cmd": "show_countersink"}],
                    "info": "Ground leads with holes are soldered on both sides and join the plane; every other hole gets a "
                            "bare ring. A %g mm stitching grid keeps the plane quiet to about %s. Export: the plane is a "
                            "second Gerber / PDF / G-code layer (not mirrored)." % (st.stitch_spacing, planemod.fmt_freq(f))}
        if name == "footprint":
            return {"title": "New footprint (My parts)", "submit": "save_part", "ok": "Save part",
                    "fields": [{"k": "name", "label": "Part name", "type": "text", "value": ""},
                               {"k": "category", "label": "Category", "type": "text", "value": "Custom"},
                               {"k": "prefix", "label": "Ref prefix (R, C, U...)", "type": "text", "value": "U"},
                               {"k": "note", "label": "Note", "type": "text", "value": ""},
                               {"k": "pads", "label": "Pads, one per line: name x y shape w h drill (mm from pin 1 at 0 0; "
                                                      "y up; shape round | oval | rect)", "type": "textarea",
                                "value": "1 0 0 round 1.8 1.8 0.9\n2 2.54 0 round 1.8 1.8 0.9"}],
                    "buttons": [{"label": "Fill in a DIP-8", "cmd": "footprint_preset", "args": {"kind": "dip", "n": 8, "row": 7.62}},
                                {"label": "Fill in a 4 x 1 header", "cmd": "footprint_preset", "args": {"kind": "header", "cols": 4, "rows": 1}},
                                {"label": "Import a KiCad .kicad_mod...", "cmd": "pick_file", "args": {"what": "kicad"}}],
                    "info": "The outline is drawn round the pads. Through-hole only. Saved as a small .json file in %s."
                            % library.user_part_dir()}
        if name == "coil":
            return {"title": "PCB coil generator", "submit": "save_coil", "ok": "Save coil and place",
                    "fields": [{"k": "mode", "label": "I know", "type": "select", "value": "uh",
                                "options": [["uh", "The area and the inductance wanted (find the turns)"],
                                            ["turns", "The area and the number of turns (work out the inductance)"]]},
                               {"k": "width", "label": "Outer width (mm)", "type": "number", "value": 30},
                               {"k": "height", "label": "Outer height (mm)", "type": "number", "value": 20},
                               {"k": "uh", "label": "Inductance wanted (uH), used in the first mode", "type": "number", "value": 1.5},
                               {"k": "turns", "label": "Turns wanted, used in the second mode", "type": "number", "value": 8},
                               {"k": "track", "label": "Track width (mm)", "type": "number", "value": 0.5},
                               {"k": "gap", "label": "Smallest gap between turns (mm)", "type": "number", "value": 0.4},
                               {"k": "thick", "label": "Copper thickness (um; 35 = 1 oz)", "type": "number", "value": 35},
                               {"k": "freq", "label": "Frequency (MHz, optional: gives the tuning capacitor)", "type": "number", "value": ""},
                               {"k": "name", "label": "Part name (optional)", "type": "text", "value": ""}],
                    "buttons": [{"label": "Calculate", "cmd": "coil_calc"}],
                    "info": "A flat rectangular spiral on one copper layer, saved under My parts. The inductance is an "
                            "ESTIMATE for a coil in air (measure the real one). On a single-sided board the inner end "
                            "needs an insulated wire over the turns: pins 2 and 3 of the part are that wire. The part "
                            "carries a 2 mm copper-free keep-out round the coil."}
        if name == "laser":
            o = self.laser_options()
            fields = []
            if st.backplane:
                fields.append({"k": "layer", "label": "Which side", "type": "select", "value": "bottom",
                               "options": [["bottom", "Copper side (traces)"],
                                           ["top", "Back-side ground plane (component side; not mirrored)"]]})
            fields.append({"k": "mode", "label": "What to burn", "type": "select", "value": o.mode,
                           "options": [["negative", "Negative: burn everything except the copper (cleanest etch, slowest)"],
                                       ["isolation", "Isolation: burn only a gap around the copper (fast)"],
                                       ["positive", "Positive: burn the copper shapes themselves"]]})
            for k, t in (("trace_comp", "Trace adjust (mm per side, + fatter, - thinner)"), ("gap", "Isolation gap width (mm)"),
                         ("border", "Unburned border at board edge (mm)"), ("line_interval", "Line spacing (mm)"),
                         ("feed", "Speed (mm/min)"), ("power", "Power (% of S max)"), ("smax", "S max ($30 in GRBL)"),
                         ("passes", "Passes"), ("overscan", "Run-in/out in M3 mode (mm)"), ("dot_dia", "Drill dot diameter (mm)")):
                fields.append({"k": k, "label": t, "type": "number", "value": getattr(o, k)})
            for k, t in (("mirror", "Mirror for the copper side (normal: leave ticked)"),
                         ("crosshatch", "Cross-hatch (second pass at 90 degrees)"), ("bidirectional", "Burn in both directions"),
                         ("dynamic", "Use M4 dynamic power (untick for M3)"), ("drill_dots", "Mark drill centres")):
                fields.append({"k": k, "label": t, "type": "check", "value": getattr(o, k)})
            return {"title": "Laser export - Elegoo Phecda (GRBL-style, untested on a real machine)", "fields": fields,
                    "laser": True, "ok": "Save G-code",
                    "warn": "WORK IN PROGRESS. The laser only removes PAINT (paint the copper, burn, then etch). Wear laser "
                            "eye protection and ventilate. Run the test cards before a real board.",
                    "info": "Setup: jog the laser to the lower-left corner of the board as you look at the COPPER side and "
                            "set that as the work zero. Preview: component-side view; orange = paint burned off."}
        raise KeyError(name)

    def apply_islands(self, v: dict) -> Optional[str]:
        st = self.board.settings
        try:
            n = int(float(v.get("spokes", 4)))
            if n not in (2, 4, 8):
                return "Spokes per pad must be 2, 4 or 8."
            w = float(v.get("swidth", st.relief_width))
            g = float(v.get("sgap", st.relief_gap))
            a_txt = str(v.get("amps", "")).strip()
            a = float(a_txt) if a_txt else 0.0
            gap = float(v.get("gap", st.island_gap))
            grow = float(v.get("grow", st.island_grow))
            if not (0.2 <= w <= 4 and 0.2 <= g <= 3 and 0.1 <= gap <= 5 and 0 <= grow <= 10 and 0 <= a <= 200):
                return "A value is out of range (spokes 0.2-4 mm, ring 0.2-3 mm, gap 0.1-5 mm, fatten 0-10 mm)."
        except (TypeError, ValueError):
            return "Please type numbers."
        st.island_drop_floating = bool(v.get("drop", True))
        st.relief, st.relief_spokes, st.relief_width, st.relief_gap, st.relief_amps = bool(v.get("relief", True)), n, w, g, a
        st.relief_islands, st.relief_diag = bool(v.get("rislands", True)), bool(v.get("rdiag", True))
        net = str(v.get("net", ""))
        self.set_islands(bool(v.get("on")), net if net in self.board.nets else "", gap, grow, bool(v.get("dead")))
        return None

    def apply_backplane(self, v: dict) -> Optional[str]:
        try:
            vals = {"backplane_clearance": float(v.get("backplane_clearance")), "via_drill": float(v.get("via_drill")),
                    "via_pad": float(v.get("via_pad")), "stitch_spacing": float(v.get("stitch_spacing"))}
            if not (0.1 <= vals["backplane_clearance"] <= 3 and 0.3 <= vals["via_drill"] <= 3
                    and 1.0 <= vals["via_pad"] <= 5 and 2 <= vals["stitch_spacing"] <= 100):
                return "A value is out of range (ring 0.1-3, via hole 0.3-3, via pad 1-5, grid 2-100 mm)."
        except (TypeError, ValueError):
            return "Please type numbers."
        net = str(v.get("net", ""))
        self.set_backplane(bool(v.get("on")), net if net in self.board.nets else "", vals, bool(v.get("relief", True)))
        return None

    def coil_calc(self, vals: dict) -> dict:
        try:
            res = coil.design_from_values(vals)
        except ValueError as exc:
            return {"ok": False, "report": str(exc)}
        return {"ok": res.ok, "report": res.summary()}

    def save_coil(self, vals: dict) -> Optional[str]:
        """The coil generator: design it, save it under My parts and arm it so one click places it."""
        try:
            res = coil.design_from_values(vals)
        except ValueError as exc:
            return str(exc)
        if not res.ok:
            return res.summary()
        part = coil.coil_part(res, name=str(vals.get("name", "")).strip())
        try:
            fn = library.save_user_part(part)
        except OSError as exc:
            return "Could not save the coil: %s" % exc
        self.lib[part.id] = part
        self.armed = part.id
        self.status("Saved %s to %s. It is under My parts and armed: click the board to place it." % (part.name, fn))
        return None

    def footprint_preset(self, kind: str, **kw) -> str:
        try:
            if kind == "dip":
                p = library.dip(max(4, int(kw.get("n", 8))), float(kw.get("row", 7.62)))
            else:
                p = library.header(max(1, int(kw.get("cols", 4))), max(1, int(kw.get("rows", 1))), float(kw.get("pitch", 2.54)))
        except (TypeError, ValueError):
            return ""
        return "\n".join("%s %g %g %s %g %g %g" % (pd.name, pd.x, pd.y, pd.shape, pd.w, pd.h, pd.drill) for pd in p.pads)

    # ------------------------------------------------------------- the command switch
    def cmd(self, name: str, a: dict) -> dict:
        """Run one command from the page. Returns extra data for some commands."""
        b = self.board
        f = lambda k, d=0.0: float(a.get(k, d))      # noqa: E731

        def idx(k: str, d: int = 0) -> int:
            """An index from the page; a negative one must never reach a list (Python would count back)."""
            try:
                v = int(a.get(k, d))
            except (TypeError, ValueError):
                v = d
            return v if v >= 0 else 10 ** 9
        out: dict = {}
        if name == "press":
            self.scale = max(1.0, f("scale", self.scale))
            self.press(f("x"), f("y"), bool(a.get("shift")))
            # what the page needs to draw the ghost; the rest (Trace objects for a trace drag) stays here
            out["drag"] = None if self.drag is None else {k: v for k, v in self.drag.items()
                                                          if k in ("ref", "dx", "dy", "trace", "seg", "via",
                                                                   "island", "draw_island", "resize")}
        elif name == "drag_to":
            self.drag_to(f("x"), f("y"))
        elif name == "double":
            self.double(f("x"), f("y"))
        elif name == "probe_part":
            out["hits"] = self.probe_part(str(a.get("ref", "")), f("x"), f("y"))
            return out
        elif name == "hover":
            self.scale = max(1.0, f("scale", self.scale))
            out["net"] = self.hover_net(f("x"), f("y"))
            out["hit"] = self.hit_test(f("x"), f("y"))
            if self.tool == "wire":
                out["lock"] = self.wire_lock(f("x"), f("y"))
            return out
        elif name == "tool":
            self.set_tool(str(a.get("name", "select")))
        elif name == "escape":
            self.escape()
        elif name == "arm":
            self.arm_part(str(a.get("pid", "")))
        elif name == "parts_mode":
            self.set_parts_mode(str(a.get("mode", "tht")))
        elif name == "fav":
            self.set_fav(str(a.get("pid", "")), bool(a.get("on")))
        elif name == "rotate":
            self.rotate(int(a.get("step", 90)))
        elif name == "delete":
            self.delete_selection()
        elif name == "delete_part":
            self.sel = {"part": str(a.get("ref"))}
            self.delete_selection()
        elif name == "duplicate":
            self.duplicate()
        elif name == "nudge":
            self.nudge(int(a.get("dx", 0)), int(a.get("dy", 0)), bool(a.get("big")))
        elif name == "undo":
            self.do_undo()
        elif name == "redo":
            self.do_redo()
        elif name == "finish_trace":
            self.finish_trace()
        elif name == "trace_backup":
            self.trace_backup()
        elif name == "set_width":
            self.set_width(idx("ti", -1), idx("si", 0), f("w", a.get("value", 0.8)),
                           str(a.get("scope", self.width_scope)))
        elif name == "width_scope":
            self.width_scope = str(a.get("value", "segment"))
        elif name == "auto_tidy":
            self.auto_tidy = bool(a.get("value", True))
        elif name == "set_net_width":
            self.set_net_width(str(a.get("name")), f("w", a.get("value", 0.8)), bool(a.get("apply_existing", True)))
        elif name == "trim":
            self.trim(idx("ti", -1), idx("si", 0))
        elif name == "cut_piece":
            self.cut_piece(idx("ti", -1), (f("x"), f("y")))
        elif name == "start_cut":
            self.start_cut(idx("ti", -1), (f("x"), f("y")))
        elif name == "split":
            self.split_here(idx("ti", -1), idx("si", 0), (f("x"), f("y")))
        elif name == "tidy":
            self.tidy_one(idx("ti", -1))
        elif name == "tidy_all":
            self.tidy_all()
        elif name == "select_net":
            self.select_net(str(a.get("net")))
        elif name == "net_jumpers":
            self.net_jumpers(str(a.get("net")), bool(a.get("ok", a.get("value", True))))
        elif name == "toggle_rigid":
            self.toggle_rigid(str(a.get("a")), str(a.get("b")), bool(a.get("on")))
        elif name == "rename_net":
            self.rename_net(str(a.get("old")), str(a.get("value", "")))
        elif name == "net_class":
            self.net_class(str(a.get("name")), str(a.get("value")))
        elif name == "unroute":
            self.unroute(str(a.get("name")))
        elif name == "start_wire":
            self.start_wire(str(a.get("pin")), bool(a.get("rigid")))
        elif name == "start_trace":
            self.start_trace(str(a.get("pin")))
        elif name == "disconnect":
            self.disconnect(str(a.get("pin")))
        elif name == "set_value":
            self.set_value(str(a.get("ref")), str(a.get("value", "")))
        elif name == "pin_labels_preset":
            self.set_pin_labels_preset(str(a.get("ref")), str(a.get("value", "(none)")))
        elif name == "pin_labels_text":
            self.set_pin_labels_text(str(a.get("ref")), str(a.get("value", "")))
        elif name == "focus_value":
            self.sel = {"part": str(a.get("ref"))}
            out["focus"] = "value"
            self.touch()
        elif name == "set_lock":
            self.set_lock(str(a.get("ref")), bool(a.get("value")))
        elif name == "ground_contact":
            self.set_ground_contact(str(a.get("ref")), str(a.get("value", "")))
        elif name == "set_flip_inv":
            self.set_flip(str(a.get("ref")), not bool(a.get("value")))
        elif name == "set_mirrored":
            self.set_mirrored(str(a.get("ref")), bool(a.get("value")))
        elif name == "mirror":
            self.mirror_selected()
        elif name == "set_style":
            self.set_style(str(a.get("ref")), str(a.get("value")))
        elif name == "set_pad_style":
            self.set_pad_style(str(a.get("ref")), str(a.get("pad")), str(a.get("style", a.get("value"))))
        elif name == "default_style":
            if a.get("value") in ("tht", "dead", "mixed"):
                self.default_style = a["value"]
                self.status("New parts will use %s pads." % {"tht": "through-hole", "dead": "deadbug",
                                                             "mixed": "through-hole + deadbug"}[self.default_style])
        elif name == "set_island":
            self.set_island(idx("i", -1), **{str(a.get("key")): a.get("value")})
        elif name == "set_island_size":
            self.set_island(idx("i", -1), w=f("w"), h=f("h"))
        elif name == "duplicate_island":
            self.duplicate_island(idx("i", -1))
        elif name == "add_island":
            self.add_island(f("x"), f("y"))
        elif name == "via_at":
            self.via_press(f("x"), f("y"))
        elif name == "place_at":
            self.place_here(f("x"), f("y"))
        elif name == "add_stitch_vias":
            self.add_stitch_vias()
        elif name == "add_pin_vias":
            self.add_pin_vias()
        elif name == "show_countersink":
            if not b.settings.backplane:
                self.alert("The back-side ground plane is off (Board > Back-side ground plane).")
            else:
                out["text"] = self.countersink_text()
                out["text_title"] = "Countersink list"
                out["download"] = "countersink"
        elif name == "setting":
            self.set_setting(str(a.get("key")), a.get("value"))
        elif name == "set_islands":
            self.set_islands(bool(a.get("on")), str(a.get("net", "")), f("gap", 0.6), f("grow", 1.0), bool(a.get("dead")))
        elif name == "toggle_islands":
            st = b.settings
            on = not st.island_mode
            if on and any((pl.style != "dead" or pl.pad_styles) and not b.is_smd(r) for r, pl in b.parts.items()) \
                    and not a.get("answered"):
                self.alerts.append({"kind": "ask", "text": "A ground-fill board is usually built with the parts soldered "
                                    "straight onto the copper.\n\nMake every pad a deadbug pad (no holes to drill)?",
                                    "cmd": "toggle_islands", "args": {"answered": True, "dead": True},
                                    "no_cmd": "toggle_islands", "no_args": {"answered": True, "dead": False}})
            else:
                self.set_islands(on, st.island_net, st.island_gap, st.island_grow, bool(a.get("dead")))
        elif name == "apply_settings":
            out["error"] = self.apply_settings(a.get("values", {}))
        elif name == "apply_islands":
            out["error"] = self.apply_islands(a.get("values", {}))
        elif name == "apply_backplane":
            out["error"] = self.apply_backplane(a.get("values", {}))
        elif name == "save_part":
            out["error"] = self.save_part(a.get("values", {}))
        elif name == "save_coil":
            out["error"] = self.save_coil(a.get("values", {}))
        elif name == "coil_calc":
            out.update(self.coil_calc(a.get("values", {})))
        elif name == "footprint_preset":
            out["pads"] = self.footprint_preset(str(a.get("kind", "dip")), **{k: v for k, v in a.items() if k != "kind"})
        elif name == "new_board":
            v = a.get("values", {})
            out["error"] = self.new_board(str(v.get("name", "")), v.get("w", 0), v.get("h", 0))
        elif name == "open_text":
            out["error"] = self.open_text(str(a.get("text", "")), str(a.get("name", "board")))
        elif name == "open_path":
            out["error"] = self.open_path(str(a.get("path", "")))
        elif name == "import_netlist":
            out["error"] = self.import_netlist_text(str(a.get("text", "")), str(a.get("name", "netlist")))
        elif name == "import_kicad":
            out["preset"], out["error"] = self.import_kicad_text(str(a.get("text", "")))
        elif name == "saved":
            self.saved()
        elif name == "save_path":
            out["error"] = self.save_to_path()
        elif name == "recover_autosave":
            out["error"] = self.recover_autosave()
        elif name == "demo":
            self.load_demo(str(a.get("name", "")))
        elif name == "auto_place":
            self.auto_place(bool(a.get("force")))
        elif name == "auto_route":
            self.auto_route(a.get("only"))
        elif name == "cancel_job":
            self.cancel_job()
        elif name == "clear_auto":
            self.clear_auto()
        elif name == "clear_all":
            self.clear_all()
        elif name == "show_drc":
            out["drc"] = self.drc()
        elif name == "clear_marks":
            self.marks = []
            self.touch()
        elif name == "set_marks":
            self.set_marks(a.get("pts", []))
        elif name == "export_check":
            out["warning"] = self.export_warning()
        elif name == "help":
            out["text"] = HELP_TEXT
            out["text_title"] = "Quick guide"
        elif name == "about":
            out["text"] = ("%s\n\n%s\n\nCopyright Matthew Armstrong (https://github.com/The-Dorkknight)\n"
                           "Licensed under the PolyForm Noncommercial License 1.0.0 (source-available, non-commercial "
                           "use only).\nNo warranty. Not tested on a real Elegoo Phecda yet.\n\nBuilt %s\n\n"
                           "%s" % (app_title(), WIP_TEXT, __build_date__,
                                  "This is the in-browser version: SoloTrace's own Python runs inside your browser with "
                                  "Pyodide (Mozilla Public License 2.0, loaded from cdn.jsdelivr.net). Nothing is installed "
                                  "and nothing you draw is uploaded; settings and the autosave stay in this browser."
                                  if self.sync_mode else
                                  "SoloTrace is running as a small local server (127.0.0.1 only) with the editor in your "
                                  "browser. The old tkinter desktop window: python3 src/main.py desktop"))
            out["text_title"] = "About " + APP_NAME
        elif name == "show_air":
            self.show_air = bool(a.get("value", True))
        elif name == "dialog":
            try:
                out["dialog"] = self.dialog(str(a.get("name", "")))
            except KeyError:
                out["error"] = "There is no dialog called %r." % a.get("name")
        elif name == "noop":
            pass
        elif name == "accept":
            cfg = load_config()
            cfg["accepted"] = __version__.split("-")[0].rsplit(".", 1)[0]
            save_config(cfg)
        else:
            out["error"] = "Unknown command %r" % name
        return out

    def accepted(self) -> bool:
        return load_config().get("accepted") == __version__.split("-")[0].rsplit(".", 1)[0]

    def finish_fill_now(self) -> None:
        """sync_mode: work out the full ground fill now (the page asks a moment after an edit)."""
        b = self.board
        if b.settings.island_mode and not island_ready(b):
            island_plan(b, full=True)
            self.touch()

    def _schedule_full_fill(self) -> None:
        """Work out the full ground fill (floating copper removed) a moment after the last change,
        in the background, like the desktop window's 0.4 s timer. The page polls until fill_ready."""
        b = self.board
        if self.sync_mode or not b.settings.island_mode or island_ready(b):
            return
        if self._fill_thread is not None and self._fill_thread.is_alive():
            return

        def go() -> None:
            time.sleep(0.35)
            with self.lock:
                if self.board is not b or island_ready(b) or not b.settings.island_mode:
                    return
                try:
                    island_plan(b, full=True)
                finally:
                    self.touch()
        self._fill_thread = threading.Thread(target=go, daemon=True)
        self._fill_thread.start()

    def state(self) -> dict:
        """What every command answer carries: the scene, the panel, alerts and the job."""
        self.autosave_tick()
        job = self.poll_job()
        st = {"scene": self.scene(), "panel": self.panel(), "alerts": self.alerts, "job": job}
        self.alerts = []
        self._schedule_full_fill()
        return st
