# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""SoloTrace main window (tkinter).

WORK IN PROGRESS: many features may be broken.
"""
from __future__ import annotations

import json
import math
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from . import APP_NAME, __build_date__, __version__, title as app_title
from . import demos, gerber, library, render
from .board import (Board, Island, ISLAND_MAX, ISLAND_MIN, MAX_WIDTH, MIN_WIDTH, Placed, Trace, clamp_island,
                    clamp_width, current_capacity)
from .drc import run_drc, summarize
from .geom import Cap, dist, seg_point_dist, shape_dist
from .placer import Placer
from .router import AutoRouter, RouteOptions
from . import theme
from .islands import plan as island_plan, guess_ground, make_pads_deadbug
from .theme import FONT, FONT_B, FONT_S, UI, Tooltip
from .tidy import (apply_drag, attached_ends, cut_between, follow_trunk, piece_bounds, project_on_trace,
                   settle_branch_ends, split_trace, tidy_trace, tidy_traces, trim_piece, trim_segment,
                   violation_set, _sub_polyline)

COL = {
    "bg": "#16301c", "board": "#1b3d24", "grid": "#27502f", "copper": "#d79a4e", "copper_dim": "#8a6a3c",
    "hole": "#16301c", "outline": "#e8f0e8", "outline_dim": "#6f8f77", "sel": "#35d0ff", "air": "#f2e24a",
    "rigid": "#ff6b3d", "rigid_dim": "#b0563a", "air_shadow": "#0b1a0f", "pinlabel": "#ffe08a",
    "jump": "#6fb7ff", "drc": "#ff4040", "ghost": "#9fe0ff", "text": "#ffffff", "hover": "#6f8f5a",
    "fill": "#a8783a", "fill_dim": "#5c4a2d",
}
WIDTH_PRESETS = (0.4, 0.8, 1.5, 2.5, 5.0, 10.0)
ISLAND_SIZES = (2.54, 3.81, 5.08, 6.35, 7.62, 10.16, 12.7, 15.24)
ISLAND_GRID = 0.635            # islands snap to a quarter of 2.54 mm so they can sit under pins
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".solotrace")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
AUTOSAVE_FILE = os.path.join(CONFIG_DIR, "autosave.solotrace")
AUTOSAVE_MS = 120000


_SHORT = (("Resistor ", ""), (" standing", ""), ("Diode ", ""), ("Inductor ", ""), ("Electrolytic cap, ", ""),
          ("Film / box cap, ", ""), ("Ceramic disc cap, ", ""), ("Pin header ", ""), ("Screw terminal ", ""),
          ("JST-XH header ", ""), ("Wire link ", ""))


def short_name(name: str, sub: str) -> str:
    """Shorter tree label: the sub-group already says what kind of part it is."""
    if not sub:
        return name
    out = name
    for a, b in _SHORT:
        out = out.replace(a, b)
    if out.startswith("DIP-") and "(" in out:
        out = out.split(" ")[0]
    return out[:1].upper() + out[1:] if out else name


def _natural(s: str):
    """Sort key so DIP-8 comes before DIP-14 and 2.54 mm before 10.16 mm."""
    import re
    return [float(t) if t.replace(".", "", 1).isdigit() else t.lower() for t in re.findall(r"\d+\.?\d*|\D+", s)]

WIP_TEXT = "WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN"

HELP_TEXT = """SoloTrace quick guide

1. Open a group in the parts panel on the left (the arrows show the sub-types), pick a part,
   look at the preview under the list, then click on the board to place it. Shift + click or R
   turns it, Esc stops. Star parts you use a lot; "Favourites & recent" at the top lists them.
2. Wire tool (W): click one pin, then another (or drag pin to pin). A yellow rubber-band line shows
   the connection. Hold Shift for a RIGID wire: Auto-route joins those two pins with their own
   trace (the path can still bend) and branches the rest of the net off it (orange). Good for power.
   Untick "Jumpers" in the tool bar (or per net) if you do not want wire links.
   Select a part to type its value/type and pick its pin labels (B C E, G D S, IN GND OUT...).
3. Click Auto-place to untangle the layout, then Auto-route. Routes use only 0/45/90 degree
   moves and every corner is chamfered. Wide traces leave their pads straight before turning.
   Where a trace cannot get through, a wire-link jumper (blue dashed) is added.
4. Trace width: click any trace section (or a yellow rubber-band line to set a whole net) and
   drag the slider on the right, 0.4 to 10 mm. The panel says how wide it can go and still fit.
5. Move a trace: with Select, drag a trace section sideways. Its neighbours stretch to follow.
6. Cut tool (C): click a trace and that piece goes, up to the nearest joints (pad, branch, jumper);
   the rest of the net stays. It shows in red first. Shift + click two points cuts between them.
   Trim tool (X) removes a whole straight section.  Right-click anything for its menu
   (trim, split, tidy, width, rotate, duplicate, wire from a pin, route one net...).
7. Pads: choose Through-hole, Deadbug (no hole, long copper for surface soldering) or Both.
8. Island tool (I): click to drop a rectangular copper pad, drag to draw one any size, Shift + click
   to switch round / rectangle. Drag an island to move it, drag its white corner squares to resize.
   A part's pins sitting on an island join it (Manhattan / deadbug building, no traces needed).
   Board > Ground fill turns the rest of the board into ground copper, with a gap round every
   other net: quick and dirty RF. The ground net is then joined by the fill, not routed.
9. Check with DRC, then export: Gerber, 1:1 PDF/SVG for toner transfer, or Laser G-code.

Mouse: wheel = zoom, right or middle drag = pan, right-click = menu, left = tool.
Keys: S select, P place, W wire, T trace, X trim, C cut, J jumper, I island, R / Shift+R rotate, arrows nudge
(Shift = 2.54 mm), Ctrl+D duplicate, Delete, Ctrl+Z / Ctrl+Y, F fit, M flip view.
Your board is autosaved every 2 minutes while it has unsaved changes (File > Recover autosave).
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


class Job:
    """A background task (placer or router) working on a copy of the board."""

    def __init__(self, label: str, func, on_done) -> None:
        self.label = label
        self.func = func
        self.on_done = on_done
        self.cancel = False
        self.msg = "Starting..."
        self.frac = 0.0
        self.result = None
        self.error: Optional[str] = None
        self.done = False

    def start(self) -> None:
        def run() -> None:
            try:
                self.result = self.func(self)
            except Exception as exc:       # shown to the user, not swallowed
                self.error = "%s: %s" % (type(exc).__name__, exc)
            self.done = True

        threading.Thread(target=run, daemon=True).start()


class App:
    def __init__(self, root: tk.Tk, board: Optional[Board] = None, path: Optional[str] = None) -> None:
        self.root = root
        self.board = board or Board(100, 80, "Untitled")
        self.path = path
        self.dirty = False
        self.undo: List[str] = []
        self.redo: List[str] = []
        self.tool = "select"
        self.armed: Optional[str] = None
        self.arm_rot = 0
        self.sel: Dict[str, object] = {}
        self.scale = 6.0
        self.ox = 40.0
        self.oy = 40.0
        self.mirror = False
        self.show_air = tk.BooleanVar(value=True)
        self.show_grid = tk.BooleanVar(value=True)
        self.default_style = tk.StringVar(value="tht")
        self.pending_pin: Optional[str] = None
        self.trace_pts: List[Tuple[float, float]] = []
        self.trace_net: Optional[str] = None
        self.jump_start: Optional[Tuple[float, float]] = None
        self.cursor = (0.0, 0.0)
        self.marks: List[Tuple[float, float]] = []
        self.drag: Optional[dict] = None
        self.pan_from: Optional[Tuple[int, int, float, float, int]] = None
        self.job: Optional[Job] = None
        self._redraw_pending = False
        self._closing = False
        self._redraw_id = None
        self.ghost_board = Board(10, 10, "ghost")
        self.lib = library.all_parts()
        self._building_panel = False
        self.width_scope = tk.StringVar(value="segment")
        self.auto_tidy = tk.BooleanVar(value=True)
        self.jumpers_var = tk.BooleanVar(value=self.board.settings.allow_jumpers)
        self.keepout_var = tk.BooleanVar(value=self.board.settings.keep_out_under_parts)
        self.island_var = tk.BooleanVar(value=self.board.settings.island_mode)
        self.hover_net: Optional[str] = None
        self.menu_preview = None
        self.cut_start: Optional[Tuple[int, Tuple[float, float]]] = None
        self.rigid_next = False
        self.island_new = {"shape": "rect", "w": 5.08, "h": 5.08}    # size and shape of the next island
        self._wire_press = None
        self._shift = False
        self._autosave_id = None
        self._menu = None
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self._build_ui()
        self._bind_keys()
        root.after(60, self.fit)
        self._autosave_id = root.after(AUTOSAVE_MS, self._autosave_tick)
        self.set_title()
        self.status("Welcome to %s. %s" % (APP_NAME, WIP_TEXT))

    # ------------------------------------------------------------------ UI build
    def _build_ui(self) -> None:
        r = self.root
        theme.apply(r)
        r.configure(bg=UI["panel"])
        self._build_menu()
        wip = tk.Label(r, text=WIP_TEXT + "   -   " + app_title(), bg=UI["wip"], fg="white",
                       font=("TkDefaultFont", 9, "bold"))
        wip.pack(side="top", fill="x")
        bar = ttk.Frame(r, padding=(6, 5), style="Bar.TFrame")
        bar.pack(side="top", fill="x")
        self.tool_btns: Dict[str, ttk.Radiobutton] = {}
        self.tool_var = tk.StringVar(value="select")
        tips = {"select": "Select and move parts. Drag a trace section sideways to move it.",
                "place": "Place the part chosen in the parts panel. R turns it.",
                "wire": "Connect pins: click one pin, then the other (yellow rubber band).",
                "trace": "Draw copper by hand: click a pin, click corners, finish on a pin.",
                "trim": "Click a trace section to remove that whole section; the rest stays.",
                "cut": "Click a trace: that piece goes, up to the nearest joints (pads, branches). The rest of the net stays. "
                       "Shift + click two points to cut between them.",
                "jumper": "Add a wire-link jumper by hand.",
                "island": "Copper islands (Manhattan / deadbug pads): click to drop one, or drag out a rectangle. "
                          "Shift + click switches round / rectangle. Put a part's pins on an island to join them."}
        for key, label in (("select", "Select"), ("place", "Place"), ("wire", "Wire"),
                           ("trace", "Trace"), ("trim", "Trim"), ("cut", "Cut"), ("jumper", "Jumper"),
                           ("island", "Island")):
            b = ttk.Radiobutton(bar, text=label, value=key, variable=self.tool_var, style="Tool.TRadiobutton",
                                command=lambda k=key: self.set_tool(k))
            b.pack(side="left", padx=1)
            self.tool_btns[key] = b
            Tooltip(b, tips[key] + "  Key: %s" % {"select": "S", "place": "P", "wire": "W", "trace": "T",
                                                    "trim": "X", "cut": "C", "jumper": "J", "island": "I"}[key])
        ttk.Separator(bar, orient="vertical", style="Bar.TSeparator").pack(side="left", fill="y", padx=6)
        ttk.Label(bar, text="Pads:", style="Bar.TLabel").pack(side="left")
        for v, t in (("tht", "Through-hole"), ("dead", "Deadbug"), ("mixed", "Both")):
            ttk.Radiobutton(bar, text=t, value=v, variable=self.default_style, style="Bar.TRadiobutton",
                            command=self.on_default_style).pack(side="left", padx=2)
        ttk.Separator(bar, orient="vertical", style="Bar.TSeparator").pack(side="left", fill="y", padx=6)
        for text, cmd, sty, tip in (("Auto-place", self.auto_place, "Teal.TButton",
                                     "Untangle the layout: moves, turns and swaps unlocked parts."),
                                    ("Auto-route", self.auto_route, "Copper.TButton",
                                     "Route every net with chamfered 45 degree copper; adds jumpers if it must."),
                                    ("Check", self.show_drc, "Blue.TButton", "Design rule check (clearances, corners, widths)."),
                                    ("Laser...", self.laser_dialog, "Red.TButton", "G-code for the Elegoo Phecda laser.")):
            btn = ttk.Button(bar, text=text, command=cmd, style=sty, width=0)   # as wide as the text, so
            btn.pack(side="left", padx=2)                                          # the bar fits 1280 px
            Tooltip(btn, tip)
        jc = ttk.Checkbutton(bar, text="Jumpers", variable=self.jumpers_var, style="Bar.TCheckbutton",
                             command=self._toggle_jumpers)
        jc.pack(side="left", padx=(6, 2))
        Tooltip(jc, "Untick to stop Auto-route adding wire-link jumpers. Connections it cannot route stay as "
                    "rubber bands for you to finish by hand. Each net can also refuse jumpers (net panel).")
        self.cancel_btn = ttk.Button(bar, text="Cancel job", command=self.cancel_job)
        self.progress = ttk.Progressbar(bar, mode="determinate", length=120, maximum=100)
        # status bar first, so it is never squeezed out when the window is small
        sb = ttk.Frame(r, style="Status.TFrame", padding=(4, 2))
        sb.pack(side="bottom", fill="x")
        main = ttk.Frame(r)
        main.pack(side="top", fill="both", expand=True)
        self.status_var = tk.StringVar()
        self.cursor_var = tk.StringVar()
        self.stamp_var = tk.StringVar(value="SoloTrace v%s (Built %s) WIP" % (__version__, __build_date__))
        self.route_var = tk.StringVar(value="")
        ttk.Label(sb, textvariable=self.status_var, anchor="w", style="Status.TLabel", width=1).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Label(sb, textvariable=self.cursor_var, width=24, style="Status.TLabel").pack(side="left")
        self.route_badge = ttk.Label(sb, textvariable=self.route_var, style="Ok.TLabel")
        self.route_badge.pack(side="left", padx=6)
        ttk.Label(sb, textvariable=self.stamp_var, style="Status.TLabel").pack(side="right", padx=6)
        # left: parts panel (tree by form factor + preview)
        left = ttk.Frame(main, width=285, padding=(8, 6, 4, 6))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        ttk.Label(left, text="Parts", style="Head.TLabel").pack(anchor="w")
        self.quick_var = tk.StringVar(value="Favourites & recent...")
        self.quick_cb = ttk.Combobox(left, textvariable=self.quick_var, state="readonly")
        self.quick_cb.pack(fill="x", pady=(3, 0))
        self.quick_cb.bind("<<ComboboxSelected>>", self._quick_pick)
        self.quick_cb.bind("<ButtonPress-1>", lambda e: self._fill_quick(), add="+")
        Tooltip(self.quick_cb, "Your favourite parts (star them under the preview, or right-click one in the list) "
                               "and the parts you placed most recently.")
        self._quick_ids: List[Optional[str]] = []
        self.search_var = tk.StringVar()
        se = ttk.Entry(left, textvariable=self.search_var)
        se.pack(fill="x", pady=(3, 4))
        Tooltip(se, "Type to search, e.g. dip 8, to-220, 5 mm, standing")
        self.search_var.trace_add("write", lambda *a: self.fill_library())
        lf = ttk.Frame(left)
        lf.pack(fill="both", expand=True)
        self.lib_tree = ttk.Treeview(lf, show="tree", selectmode="browse", style="Parts.Treeview")
        self.lib_tree.column("#0", width=250)
        sc = ttk.Scrollbar(lf, orient="vertical", command=self.lib_tree.yview)
        self.lib_tree.configure(yscrollcommand=sc.set)
        self.lib_tree.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")
        self.lib_tree.bind("<<TreeviewSelect>>", self.on_lib_select)
        self.lib_tree.bind("<Button-3>", self._tree_menu)
        self.lib_tree.tag_configure("group", font=FONT_B, foreground=UI["ink"])
        self.group_icons = theme.group_icons(self.root)
        self.lib_tree.tag_configure("sub", foreground=UI["copper_dark"])
        self.preview = tk.Canvas(left, height=170, bg=COL["bg"], highlightthickness=0)
        self.preview.pack(fill="x", pady=(6, 2))
        self.preview.bind("<Configure>", lambda e: self.draw_preview())
        self.lib_info = ttk.Label(left, text="Pick a part to see it here.", wraplength=250, justify="left",
                                  style="Muted.TLabel")
        self.lib_info.pack(fill="x", pady=(2, 4))
        self.fav_btn = ttk.Button(left, text="Add to favourites", command=self._toggle_fav_preview)
        self.fav_btn.pack(fill="x", pady=(0, 3))
        ttk.Button(left, text="New footprint...", command=self.footprint_wizard).pack(fill="x")
        self.preview_id: Optional[str] = None
        self.fill_library()
        self._fill_quick()
        self._update_fav_btn()
        # right: properties
        right = ttk.Frame(main, width=300, padding=(6, 6, 8, 6))
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self.prop = ttk.Frame(right)
        self.prop.pack(fill="both", expand=True)
        # centre: canvas with rounded corners
        holder = ttk.Frame(main, padding=(2, 6, 2, 6))
        holder.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=COL["bg"], highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        c = self.canvas
        c.bind("<Configure>", lambda e: self.request_redraw())
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Double-Button-1>", self.on_double)
        c.bind("<Motion>", self.on_motion)
        c.bind("<Leave>", lambda e: self._set_hover(None))
        for btn in (2, 3):
            c.bind("<ButtonPress-%d>" % btn, self.on_pan_start)
            c.bind("<B%d-Motion>" % btn, self.on_pan)
            c.bind("<ButtonRelease-%d>" % btn, lambda e, k=btn: self.on_pan_end(e, k))
        c.bind("<MouseWheel>", self.on_wheel)
        c.bind("<Button-4>", lambda e: self.zoom_at(e.x, e.y, 1.15))
        c.bind("<Button-5>", lambda e: self.zoom_at(e.x, e.y, 1 / 1.15))
        self.show_props()

    def _build_menu(self) -> None:
        r = self.root
        m = tk.Menu(r)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="New board...", command=self.new_board, accelerator="Ctrl+N")
        f.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        f.add_command(label="Save", command=self.save, accelerator="Ctrl+S")
        f.add_command(label="Save as...", command=self.save_as)
        ex = tk.Menu(f, tearoff=0)
        for name in demos.DEMOS:
            ex.add_command(label=name, command=lambda n=name: self.load_demo(n))
        f.add_cascade(label="Open example", menu=ex)
        self.recent_menu = tk.Menu(f, tearoff=0)
        f.add_cascade(label="Open recent", menu=self.recent_menu)
        f.add_command(label="Recover autosave...", command=self.recover_autosave)
        f.add_separator()
        f.add_command(label="Import netlist text...", command=self.import_netlist)
        f.add_command(label="Export netlist text...", command=self.export_netlist)
        f.add_separator()
        f.add_command(label="Quit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        e = tk.Menu(m, tearoff=0)
        e.add_command(label="Undo", command=self.do_undo, accelerator="Ctrl+Z")
        e.add_command(label="Redo", command=self.do_redo, accelerator="Ctrl+Y")
        e.add_separator()
        e.add_command(label="Rotate", command=self.rotate, accelerator="R")
        e.add_command(label="Rotate back", command=lambda: self.rotate(-90), accelerator="Shift+R")
        e.add_command(label="Duplicate part", command=self.duplicate, accelerator="Ctrl+D")
        e.add_command(label="Delete", command=self.delete_selection, accelerator="Del")
        e.add_separator()
        e.add_command(label="Trim tool", command=lambda: self.set_tool("trim"), accelerator="X")
        e.add_command(label="Tidy all traces", command=self.tidy_all)
        e.add_checkbutton(label="Tidy traces automatically when their width changes", variable=self.auto_tidy)
        m.add_cascade(label="Edit", menu=e)
        b = tk.Menu(m, tearoff=0)
        b.add_command(label="Board size and rules...", command=self.board_settings)
        b.add_command(label="Auto-place", command=self.auto_place)
        b.add_command(label="Auto-route", command=self.auto_route)
        b.add_checkbutton(label="Auto-route may add jumpers", variable=self.jumpers_var, command=self._toggle_jumpers)
        b.add_checkbutton(label="Keep traces out from under parts", variable=self.keepout_var,
                          command=self._toggle_keepout)
        b.add_separator()
        b.add_checkbutton(label="Ground fill (RF / Manhattan)", variable=self.island_var,
                          command=self._toggle_islands)
        b.add_command(label="Ground fill settings...", command=self.island_dialog)
        b.add_separator()
        b.add_command(label="Remove automatic routes", command=self.clear_auto)
        b.add_command(label="Remove ALL routes", command=self.clear_all)
        b.add_command(label="Check (DRC)", command=self.show_drc)
        m.add_cascade(label="Board", menu=b)
        x = tk.Menu(m, tearoff=0)
        x.add_command(label="Gerber + drill (zip)...", command=self.export_gerber)
        x.add_command(label="1:1 PDF (mirrored for toner transfer)...", command=lambda: self.export_print("pdf", True))
        x.add_command(label="1:1 PDF (design view)...", command=lambda: self.export_print("pdf", False))
        x.add_command(label="1:1 SVG...", command=lambda: self.export_print("svg", True))
        x.add_command(label="Bill of materials (CSV)...", command=self.export_bom)
        x.add_separator()
        x.add_command(label="Laser G-code (Elegoo Phecda)...", command=self.laser_dialog)
        m.add_cascade(label="Export", menu=x)
        p = tk.Menu(m, tearoff=0)
        p.add_command(label="New footprint...", command=self.footprint_wizard)
        p.add_command(label="Import KiCad .kicad_mod...", command=self.import_kicad)
        p.add_command(label="Open my parts folder", command=self.show_parts_folder)
        m.add_cascade(label="Parts", menu=p)
        v = tk.Menu(m, tearoff=0)
        v.add_command(label="Fit board", command=self.fit, accelerator="F")
        v.add_command(label="Zoom in", command=lambda: self.zoom_at(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2, 1.3))
        v.add_command(label="Zoom out", command=lambda: self.zoom_at(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2, 1 / 1.3))
        v.add_command(label="Flip view (copper side / component side)", command=self.toggle_mirror, accelerator="M")
        v.add_checkbutton(label="Show grid", variable=self.show_grid, command=self.request_redraw)
        v.add_checkbutton(label="Show rubber-band lines", variable=self.show_air, command=self.request_redraw)
        m.add_cascade(label="View", menu=v)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label="Quick guide", command=self.show_help)
        h.add_command(label="About", command=self.show_about)
        m.add_cascade(label="Help", menu=h)
        r.config(menu=m)
        self._fill_recent()

    def _bind_keys(self) -> None:
        r = self.root
        r.bind("<Control-z>", lambda e: self.do_undo())
        r.bind("<Control-y>", lambda e: self.do_redo())
        r.bind("<Control-s>", lambda e: self.save())
        r.bind("<Control-o>", lambda e: self.open_file())
        r.bind("<Control-n>", lambda e: self.new_board())
        r.bind("<Escape>", lambda e: self.escape())
        r.bind("<Delete>", lambda e: self._key(self.delete_selection))
        r.bind("<BackSpace>", lambda e: self._key(self._trace_backup if (self.tool == "trace" and self.trace_pts)
                                                   else self.delete_selection))
        r.bind("<Return>", lambda e: self._key(self.finish_trace))
        for k, t in (("s", "select"), ("p", "place"), ("w", "wire"), ("t", "trace"), ("j", "jumper"), ("x", "trim"),
                     ("c", "cut"), ("i", "island")):
            r.bind(k, lambda e, t=t: self._key(lambda: self.set_tool(t)))
        r.bind("r", lambda e: self._key(self.rotate))
        r.bind("R", lambda e: self._key(lambda: self.rotate(-90)))
        r.bind("<Control-d>", lambda e: self._key(self.duplicate))
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, 1), ("Down", 0, -1)):
            r.bind("<%s>" % key, lambda e, dx=dx, dy=dy: self._key(lambda: self.nudge(dx if not self.mirror else -dx, dy)))
            r.bind("<Shift-%s>" % key, lambda e, dx=dx, dy=dy: self._key(lambda: self.nudge(dx if not self.mirror else -dx, dy, True)))
        r.bind("f", lambda e: self._key(self.fit))
        r.bind("m", lambda e: self._key(self.toggle_mirror))

    def _key(self, fn) -> None:
        try:
            w = self.root.focus_get()
        except (KeyError, tk.TclError):
            w = None
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, tk.Spinbox, ttk.Spinbox)):
            return
        fn()

    # ------------------------------------------------------------------- helpers
    def status(self, msg: str) -> None:
        self.status_var.set(msg)

    def set_title(self) -> None:
        name = os.path.basename(self.path) if self.path else self.board.name
        self.root.title("%s - %s%s" % (app_title(), name, " *" if self.dirty else ""))

    def mark_dirty(self) -> None:
        self.dirty = True
        self.set_title()

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
        self.jumpers_var.set(self.board.settings.allow_jumpers)
        self.keepout_var.set(self.board.settings.keep_out_under_parts)
        self.island_var.set(self.board.settings.island_mode)
        self.cut_start = None
        self.sel = {}
        self.marks = []
        self.show_props()
        self.request_redraw()

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

    def w2s(self, x: float, y: float) -> Tuple[float, float]:
        if self.mirror:
            x = self.board.width - x
        return (self.ox + x * self.scale, self.oy + (self.board.height - y) * self.scale)

    def s2w(self, sx: float, sy: float) -> Tuple[float, float]:
        x = (sx - self.ox) / self.scale
        y = self.board.height - (sy - self.oy) / self.scale
        if self.mirror:
            x = self.board.width - x
        return (x, y)

    def snap(self, p: Tuple[float, float], g: Optional[float] = None) -> Tuple[float, float]:
        g = g or self.board.settings.place_grid
        return (round(p[0] / g) * g, round(p[1] / g) * g)

    def fit(self) -> None:
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        b = self.board
        self.scale = min((cw - 60) / b.width, (ch - 60) / b.height)
        self.ox = (cw - b.width * self.scale) / 2
        self.oy = (ch - b.height * self.scale) / 2
        self.request_redraw()

    def zoom_at(self, sx: float, sy: float, f: float) -> None:
        wx, wy = self.s2w(sx, sy)
        self.scale = min(120.0, max(1.0, self.scale * f))
        mx = self.board.width - wx if self.mirror else wx
        self.ox = sx - mx * self.scale
        self.oy = sy - (self.board.height - wy) * self.scale
        self.request_redraw()

    def toggle_mirror(self) -> None:
        self.mirror = not self.mirror
        self.status("Viewing the %s side" % ("COPPER (solder)" if self.mirror else "COMPONENT"))
        self.request_redraw()

    def on_default_style(self) -> None:
        self.status("New parts will use %s pads. Select a part to change an existing one." %
                    {"tht": "through-hole", "dead": "deadbug", "mixed": "through-hole + deadbug"}[self.default_style.get()])

    # --------------------------------------------------------------- library list
    def fill_library(self) -> None:
        """Parts grouped by form factor; the arrows open the sub-types."""
        tv = self.lib_tree
        q = self.search_var.get().strip().lower()
        words = q.split()
        open_state = {iid: tv.item(iid, "open") for iid in tv.get_children("")}
        tv.delete(*tv.get_children(""))
        groups: Dict[str, Dict[str, List[str]]] = {}
        for pid, d in self.lib.items():
            grp, sub = library.form_factor(d)
            hay = ("%s %s %s %s %s" % (d.name, pid, d.category, grp, sub)).lower()
            if words and not all(w in hay for w in words):
                continue
            groups.setdefault(grp, {}).setdefault(sub, []).append(pid)
        order = library.FORM_GROUPS + sorted(g for g in groups if g not in library.FORM_GROUPS)
        for grp in order:
            if grp not in groups:
                continue
            gid = "g:" + grp
            tv.insert("", "end", iid=gid, text=" " + grp, tags=("group",),
                      open=bool(words) or open_state.get(gid, False),
                      image=self.group_icons.get(grp, self.group_icons["My parts"]))
            for sub in sorted(groups[grp], key=lambda x: (x == "", library.SUB_ORDER.index(x)
                                                           if x in library.SUB_ORDER else 99, x)):
                parent = gid
                if sub:
                    parent = "s:%s:%s" % (grp, sub)
                    tv.insert(gid, "end", iid=parent, text=sub, tags=("sub",),
                              open=bool(words) or open_state.get(parent, False) or len(groups[grp]) == 1)
                for pid in sorted(groups[grp][sub], key=lambda k: _natural(self.lib[k].name)):
                    tv.insert(parent, "end", iid="p:" + pid, text=short_name(self.lib[pid].name, sub))

    # ---------------------------------------------------- favourites / recent
    def _favs(self) -> List[str]:
        return [p for p in load_config().get("fav_parts", []) if isinstance(p, str)]

    def _recent_parts(self) -> List[str]:
        return [p for p in load_config().get("recent_parts", []) if isinstance(p, str)]

    def _set_fav(self, pid: str, on: bool) -> None:
        cfg = load_config()
        favs = [p for p in cfg.get("fav_parts", []) if p != pid]
        if on:
            favs.insert(0, pid)
        cfg["fav_parts"] = favs[:30]
        save_config(cfg)
        self._fill_quick()
        self._update_fav_btn()
        self.status(("%s added to favourites." if on else "%s removed from favourites.") % self.lib[pid].name
                    if pid in self.lib else "Favourites updated.")

    def _note_recent(self, pid: str) -> None:
        cfg = load_config()
        rec = [p for p in cfg.get("recent_parts", []) if p != pid]
        cfg["recent_parts"] = [pid] + rec[:9]
        save_config(cfg)

    def _fill_quick(self) -> None:
        favs = [p for p in self._favs() if p in self.lib]
        rec = [p for p in self._recent_parts() if p in self.lib and p not in favs]
        vals: List[str] = []
        ids: List[Optional[str]] = []
        if favs:
            vals.append("-- Favourites --")
            ids.append(None)
            for p in favs:
                vals.append("\u2605 " + self.lib[p].name)
                ids.append(p)
        if rec:
            vals.append("-- Recently placed --")
            ids.append(None)
            for p in rec:
                vals.append("    " + self.lib[p].name)
                ids.append(p)
        if not vals:
            vals, ids = ["(no favourites or recent parts yet)"], [None]
        self._quick_ids = ids
        self.quick_cb.configure(values=vals)

    def _quick_pick(self, _e=None) -> None:
        i = self.quick_cb.current()
        pid = self._quick_ids[i] if 0 <= i < len(self._quick_ids) else None
        self.quick_var.set("Favourites & recent...")
        if pid:
            self.arm_part(pid)

    def arm_part(self, pid: str) -> None:
        """Choose a part to place (from the tree, favourites or recent) and show it in the preview."""
        self.armed = pid
        self.arm_rot = 0
        self.preview_id = pid
        self.draw_preview()
        self._update_fav_btn()
        self.tool_var.set("place")
        self.set_tool("place")

    def _update_fav_btn(self) -> None:
        pid = self.preview_id
        if not pid:
            self.fav_btn.configure(text="Add to favourites", state="disabled")
        else:
            self.fav_btn.configure(state="normal",
                                   text="\u2605 Favourite (click to remove)" if pid in self._favs() else "\u2606 Add to favourites")

    def _toggle_fav_preview(self) -> None:
        if self.preview_id:
            self._set_fav(self.preview_id, self.preview_id not in self._favs())

    def _tree_menu(self, e) -> None:
        iid = self.lib_tree.identify_row(e.y)
        if not iid or not iid.startswith("p:"):
            return
        pid = iid[2:]
        self.lib_tree.selection_set(iid)
        m = tk.Menu(self.root, tearoff=0)
        fav = pid in self._favs()
        m.add_command(label="Place this part", command=lambda: self.arm_part(pid))
        m.add_command(label=("Remove from favourites" if fav else "Add to favourites"),
                      command=lambda: self._set_fav(pid, not fav))
        self._menu = m
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def reload_library(self) -> None:
        self.lib = library.all_parts()
        self.lib.update({pid: d for pid, d in self.board.defs.items() if pid not in self.lib})
        self.fill_library()

    def on_lib_select(self, _e=None) -> None:
        sel = self.lib_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("p:"):
            self.lib_tree.item(iid, open=not self.lib_tree.item(iid, "open"))
            return
        pid = iid[2:]
        if pid not in self.lib:
            return
        self.arm_part(pid)

    def draw_preview(self) -> None:
        """Draw the chosen part in the sidebar (copper, holes, body outline, pin numbers)."""
        c = self.preview
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        pid = self.preview_id
        if not pid or pid not in self.lib or W < 20:
            c.create_text(W / 2, H / 2, text="Part preview", fill="#7fa58a", font=FONT)
            theme.round_corners(c, 10, UI["panel"])
            return
        d = self.lib[pid]
        gb = Board(10, 10, "preview")
        gb.defs = {pid: d}
        style = self.default_style.get() if d.kind != "hole" else "tht"
        gb.parts = {"P": Placed("P", pid, 0.0, 0.0, 0, False, "", style)}
        gb.touch()
        shapes = gb.copper()
        segs = render.part_segments(gb, "P")
        xs, ys = [], []
        for s in shapes:
            bb = s.bbox()
            xs += [bb[0], bb[2]]
            ys += [bb[1], bb[3]]
        for x1, y1, x2, y2 in segs:
            xs += [x1, x2]
            ys += [y1, y2]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        k = min((W - 24) / max(x1 - x0, 1.0), (H - 40) / max(y1 - y0, 1.0), 40.0)
        ox = (W - (x1 - x0) * k) / 2 - x0 * k
        oy = (H - 14 - (y1 - y0) * k) / 2 + y1 * k

        def P(x, y):
            return ox + x * k, oy - y * k
        for s in shapes:
            if s.kind == "cap":
                a, b = P(s.x1, s.y1), P(s.x2, s.y2)
                w = max(1.0, 2 * s.r * k)
                if abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 0.01:
                    c.create_oval(a[0] - w / 2, a[1] - w / 2, a[0] + w / 2, a[1] + w / 2, fill=COL["copper"], outline="")
                else:
                    c.create_line(a[0], a[1], b[0], b[1], width=w, fill=COL["copper"], capstyle="round")
            else:
                pts = []
                for x, y in s.pts:
                    pts += list(P(x, y))
                c.create_polygon(pts, fill=COL["copper"], outline="")
        for x, y, dd in gb.drills():
            q = P(x, y)
            r = max(1.0, dd / 2 * k)
            c.create_oval(q[0] - r, q[1] - r, q[0] + r, q[1] + r, fill=COL["bg"], outline="")
        for x1_, y1_, x2_, y2_ in segs:
            a, b = P(x1_, y1_), P(x2_, y2_)
            c.create_line(a[0], a[1], b[0], b[1], fill=COL["outline"], width=1)
        if len(d.pads) <= 20:
            for pad in d.pads:
                q = P(pad.x, pad.y)
                c.create_text(q[0], q[1], text=pad.name, fill="#1b1b1b", font=("TkDefaultFont", 7, "bold"))
        pitch = ""
        if len(d.pads) >= 2:
            pitch = ", pitch %.2f mm" % dist((d.pads[0].x, d.pads[0].y), (d.pads[1].x, d.pads[1].y))
        drills = sorted({p.drill for p in d.pads if p.drill > 0})
        c.create_text(8, H - 9, anchor="w", fill="#cfe3d4", font=FONT_S,
                      text="%d pad%s%s%s" % (len(d.pads), "" if len(d.pads) == 1 else "s", pitch,
                                            (", drill %s mm" % "/".join("%g" % x for x in drills)) if drills else ", no holes"))
        theme.round_corners(c, 10, UI["panel"])
        self.lib_info.config(text="%s\n%s" % (d.name, d.note or "Click on the board to place it. R turns it."))

    def set_tool(self, t: str) -> None:
        if self.tool == "trace" and t != "trace":
            self.trace_pts = []
        self.tool = t
        self.tool_var.set(t)
        self.pending_pin = None
        self.jump_start = None
        if t == "place" and not self.armed:
            self.status("Pick a part in the list on the left, then click on the board.")
        hints = {"select": "Click things to select them. Drag a part to move it.",
                 "place": "Click to place. Shift + click (or R) turns the part. Esc to stop.",
                 "wire": "Click a pin, then the pin it connects to (or drag pin to pin). Hold Shift for a rigid wire.",
                 "trace": "Click a pin to start a trace, click corners, finish on a pin (Enter or double-click ends early).",
                 "trim": "Trim: click a trace section to cut it out. The rest of the trace stays. Esc to stop.",
                 "cut": "Cut: click a trace and that piece goes, up to the nearest joints; the rest of the net stays. "
                        "Shift + click two points to cut between them.",
                 "jumper": "Click the first end, then the second end in a straight line (5 to 15 mm).",
                 "island": "Island: click to drop a %s %.4g x %.4g mm copper pad, or drag out a rectangle. Shift + click "
                           "switches round / rectangle. Click an island to select it; drag its corner squares to "
                           "resize." % (self.island_new["shape"] == "round" and "round" or "rectangular",
                                        self.island_new["w"], self.island_new["h"])}
        self.status(hints.get(t, ""))
        self.request_redraw()

    def escape(self) -> None:
        self.trace_pts = []
        self.pending_pin = None
        self.jump_start = None
        self.cut_start = None
        if self.tool in ("place", "wire", "trace", "jumper", "trim", "cut", "island"):
            self.set_tool("select")
        self.sel = {}
        self.show_props()
        self.request_redraw()

    # ---------------------------------------------------------------- hit testing
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
        if self.show_air.get():
            for net, p1, p2, pa, pb in b.airwires():
                if seg_point_dist((wx, wy), p1, p2) <= tol:
                    return {"net": net, "pins": (pa, pb)}
        for ref in reversed(list(b.parts)):
            x0, y0, x1, y1 = b.court_rect(ref)
            if x0 - 0.5 <= wx <= x1 + 0.5 and y0 - 0.5 <= wy <= y1 + 0.5:
                return {"part": ref}
        isl = self.island_at(wx, wy)
        if isl is not None:
            return {"island": isl}
        return {}

    def island_at(self, wx: float, wy: float) -> Optional[int]:
        """The top-most copper island under this point (None if there is none)."""
        probe = Cap(wx, wy, wx, wy, 0.0)
        for i in range(len(self.board.islands) - 1, -1, -1):
            if shape_dist(probe, self.board.islands[i].copper()) <= 0.0:
                return i
        return None

    def island_handle(self, sx: float, sy: float) -> Optional[Tuple[int, int, int]]:
        """(island, sx_sign, sy_sign) when the screen point is on a corner handle of the selected island."""
        i = self.sel.get("island")
        if i is None or i >= len(self.board.islands):
            return None
        isl = self.board.islands[i]
        for kx in (-1, 1):
            for ky in (-1, 1):
                hx, hy = self.w2s(isl.x + kx * isl.w / 2, isl.y + ky * isl.h / 2)
                if abs(hx - sx) <= 7 and abs(hy - sy) <= 7:
                    return (i, kx, ky)
        return None

    def pin_near(self, wx: float, wy: float, radius: float = 1.6) -> Optional[str]:
        b = self.board
        best = None
        for pin in b.all_pins():
            d = dist(b.pin_pos(pin), (wx, wy))
            if d <= radius and (best is None or d < best[0]):
                best = (d, pin)
        return best[1] if best else None

    # ------------------------------------------------------------- mouse handlers
    def on_motion(self, e) -> None:
        self._shift = bool(getattr(e, "state", 0) & 1)
        wx, wy = self.s2w(e.x, e.y)
        self.cursor = (wx, wy)
        self.cursor_var.set("X %.2f  Y %.2f mm" % (wx, wy))
        if self.tool in ("place", "wire", "trace", "jumper", "cut", "island"):
            self.request_overlay()
        if self.tool in ("select", "island") and not self.drag and self.sel.get("island") is not None:
            if self.island_handle(e.x, e.y):
                self.canvas.configure(cursor="sizing")
                return
        if self.tool in ("select", "wire", "trace", "trim", "cut") and not self.drag:
            last = getattr(self, "_hover_xy", None)
            if last is None or abs(last[0] - e.x) + abs(last[1] - e.y) > 3:
                self._hover_xy = (e.x, e.y)
                h = self.hit_test(wx, wy)
                net = None
                if "trace" in h:
                    net = self.board.traces[h["trace"]].net
                elif "pin" in h:
                    n = self.board.net_of("%s.%s" % (h["part"], h["pin"]))
                    net = n.name if n else None
                elif "net" in h:
                    net = h["net"]
                elif "jumper" in h:
                    net = self.board.jumpers[h["jumper"]].net
                self._set_hover(net, h)
                if self.tool == "cut" and self.cut_start is None:
                    prev = None
                    if "trace" in h:
                        pb = piece_bounds(self.board, h["trace"], (wx, wy))
                        if pb:
                            t = self.board.traces[h["trace"]]
                            prev = (_sub_polyline(t.points, pb[0], pb[1]), max(t.widths))
                    if prev != getattr(self, "cut_preview", None):
                        self.cut_preview = prev
                        self.request_overlay()

    def _set_hover(self, net: Optional[str], hit: Optional[dict] = None) -> None:
        if net != self.hover_net:
            self.hover_net = net
            self.request_overlay()
        if hit is not None and self.tool in ("trim", "cut"):
            self.canvas.configure(cursor="X_cursor" if "trace" in hit else "crosshair")
        elif hit is not None and self.tool == "select":
            self.canvas.configure(cursor="fleur" if ("trace" in hit or ("part" in hit and "pin" not in hit)) else "arrow")

    def on_press(self, e) -> None:
        self.canvas.focus_set()
        wx, wy = self.s2w(e.x, e.y)
        t = self.tool
        if t == "island" or (t == "select" and self.island_handle(e.x, e.y)):
            self.island_press(e, wx, wy)
        elif t == "select":
            hit = self.hit_test(wx, wy)
            self.sel = hit
            self.drag = None
            ref = hit.get("part")
            if ref and ref in self.board.parts and not self.board.parts[ref].locked:
                pl = self.board.parts[ref]
                self.drag = {"ref": ref, "dx": pl.x - wx, "dy": pl.y - wy, "moved": False}
            elif "island" in hit:
                isl = self.board.islands[hit["island"]]
                self.drag = {"island": hit["island"], "dx": isl.x - wx, "dy": isl.y - wy, "moved": False}
            elif "trace" in hit:
                tr = self.board.traces[hit["trace"]]
                self.drag = {"trace": hit["trace"], "seg": hit["seg"], "base": list(tr.points),
                             "basew": list(tr.widths), "start": (wx, wy), "moved": False, "sx": e.x, "sy": e.y,
                             "attached": attached_ends(self.board, tr)}
            self.show_props()
            self.request_redraw()
        elif t == "place":
            if getattr(e, "state", 0) & 1:          # Shift + click turns the part instead of placing it
                self.arm_rot = (self.arm_rot + 90) % 360
                self.status("Turned to %d degrees. Shift + click turns again; click without Shift to place." % self.arm_rot)
                self.request_overlay()
            else:
                self.place_here(wx, wy)
        elif t == "wire":
            self._wire_press = (e.x, e.y, self.pending_pin)
            self.wire_click(wx, wy, bool(getattr(e, "state", 0) & 1))
        elif t == "trace":
            self.trace_click(wx, wy)
        elif t == "trim":
            hit = self.hit_test(wx, wy)
            if "trace" in hit:
                self.trim(hit["trace"], hit["seg"])
            else:
                self.status("Trim: click on a trace section to cut it out.")
        elif t == "cut":
            self.cut_click(wx, wy, bool(getattr(e, "state", 0) & 1))
        elif t == "jumper":
            self.jumper_click(wx, wy)

    def cut_click(self, wx: float, wy: float, two_point: bool = False) -> None:
        """Cut tool. A click removes the piece of trace under the mouse, from the joint before it to
        the joint after it (a pad, a branch, a jumper), and leaves the rest of the net alone.
        Shift + click twice cuts between two points you choose instead."""
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
                self.show_props()
                self.status("Cut between two points on net %s; %d piece(s) of that trace stay. Ctrl+Z undoes it."
                            % (net, kept))
            self.request_redraw()
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
        self.cut_preview = None
        self.menu_preview = None
        self.show_props()
        self.status("Removed a piece of net %s between its joints; %d piece(s) of that trace stay, the rest of the "
                    "net is untouched. Ctrl+Z undoes it." % (net, kept or 0))
        self.request_redraw()

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
                            "(its path still bends round things) and branches the rest of the net off it."
                            % (self.pending_pin, pin, n.name))
            else:
                self.status("%s and %s are on net %s" % (self.pending_pin, pin, n.name))
            self.pending_pin = pin
            self.rigid_next = False
        self.request_redraw()

    def on_drag(self, e) -> None:
        if self.tool == "wire":
            self.on_motion(e)
            return
        if self.tool not in ("select", "island") or not self.drag:
            return
        wx, wy = self.s2w(e.x, e.y)
        d = self.drag
        if self.board.settings.island_mode:
            self.board._island_fast = True           # skip the floating-fill check until the mouse is let go
        if "island" in d or "draw_island" in d:
            self.island_drag(d, wx, wy)
            return
        if "ref" in d:
            nx, ny = self.snap((wx + d["dx"], wy + d["dy"]))
            pl = self.board.parts[d["ref"]]
            if (nx, ny) != (pl.x, pl.y):
                if not d["moved"]:
                    self.push_undo()
                    d["moved"] = True
                self.board.move_part(d["ref"], nx, ny)
                self.request_redraw()
        elif "trace" in d:
            if not d["moved"] and abs(e.x - d["sx"]) + abs(e.y - d["sy"]) < 5:
                return
            if d["trace"] >= len(self.board.traces):
                return
            off = (wx - d["start"][0], wy - d["start"][1])
            if not d["moved"]:
                self.push_undo()
                d["moved"] = True
            apply_drag(self.board, d["trace"], d["seg"], d["base"], d["basew"], off)
            # branches joined to this trace move with it, so they stay joined
            follow_trunk(self.board, self.board.traces[d["trace"]], d["attached"])
            self.request_redraw()

    def on_release(self, e) -> None:
        if getattr(self.board, "_island_fast", False):
            self.board._island_fast = False          # full ground-fill check again now the drag is over
            self.request_redraw()
        wp = getattr(self, "_wire_press", None)
        self._wire_press = None
        if self.tool == "wire" and wp and self.pending_pin and abs(e.x - wp[0]) + abs(e.y - wp[1]) > 8:
            # press on one pin, drag, let go on another: that is a wire too (Shift = rigid)
            wx, wy = self.s2w(e.x, e.y)
            pin = self.pin_near(wx, wy)
            if pin and pin != self.pending_pin:
                self.wire_click(wx, wy, bool(getattr(e, "state", 0) & 1))
            return
        d = self.drag
        if d and ("island" in d or "draw_island" in d):
            self.island_release(d, *self.s2w(e.x, e.y))
            self.drag = None
            return
        if d and d.get("moved"):
            if "ref" in d:
                self.status("Moved. Existing traces stay where they were; re-route if needed.")
            else:
                ti = d["trace"]
                if ti < len(self.board.traces):
                    wx, wy = self.s2w(e.x, e.y)
                    t = self.board.traces[ti]
                    si = min(range(len(t.points) - 1),
                             key=lambda k: seg_point_dist((wx, wy), t.points[k], t.points[k + 1]))
                    self.sel = {"trace": ti, "seg": si}
                    self.show_props()
                    settle_branch_ends(self.board)
                n_att = len(d.get("attached", []))
                self.quick_drc("Trace moved%s." % (" (with the %d branch(es) joined to it)" % n_att if n_att else ""))
        self.drag = None

    def on_double(self, e) -> None:
        if self.tool == "trace":
            self.finish_trace()
        elif self.tool == "select":
            h = self.hit_test(*self.s2w(e.x, e.y))
            if "part" in h and h["part"] in self.board.parts:
                self.focus_value(h["part"])

    def on_pan_start(self, e) -> None:
        self.pan_from = (e.x, e.y, self.ox, self.oy, 0)

    def on_pan(self, e) -> None:
        if not self.pan_from:
            return
        x0, y0, ox, oy, _m = self.pan_from
        if abs(e.x - x0) + abs(e.y - y0) > 4 or self.pan_from[4]:
            self.pan_from = (x0, y0, ox, oy, 1)
            self.canvas.configure(cursor="fleur")
            self.ox = ox + e.x - x0
            self.oy = oy + e.y - y0
            self.request_redraw()

    def on_pan_end(self, e, button: int = 3) -> None:
        moved = bool(self.pan_from and self.pan_from[4])
        self.pan_from = None
        self.canvas.configure(cursor="crosshair")
        if not moved and button == 3:
            self.context_menu(e)

    def on_wheel(self, e) -> None:
        self.zoom_at(e.x, e.y, 1.15 if e.delta > 0 else 1 / 1.15)

    # --------------------------------------------------------------- tool actions
    def place_here(self, wx: float, wy: float) -> None:
        if not self.armed:
            self.status("Pick a part in the list first.")
            return
        x, y = self.snap((wx, wy))
        self.push_undo()
        b = self.board
        d = self.lib[self.armed]
        if self.armed not in b.defs:
            b.defs[self.armed] = d
        style = self.default_style.get()
        if d.kind in ("hole",):
            style = "tht"
        pl = b.add_part(self.armed, x, y, self.arm_rot, False, style=style)
        self._note_recent(self.armed)
        self.sel = {"part": pl.ref}
        self.status("Placed %s. Click again to place another, Esc to stop." % pl.ref)
        self.show_props()
        self.request_redraw()

    def rotate(self, step: int = 90) -> None:
        if self.tool == "place":
            self.arm_rot = (self.arm_rot + step) % 360
        elif "part" in self.sel and self.sel["part"] in self.board.parts:
            self.push_undo()
            self.board.rotate_part(self.sel["part"], step)
        self.request_redraw()

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
        elif "pin" in s:
            b.disconnect("%s.%s" % (s["part"], s["pin"]))
        elif "part" in s:
            b.remove_part(s["part"])
        elif "net" in s:
            b.drop_net(s["net"])
        b.touch()
        self.sel = {}
        self.show_props()
        self.request_redraw()

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
        if not self.trace_pts:
            if pin is None:
                self.status("Start a trace on a pin that is already connected (use the Wire tool first).")
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
                self.trace_pts.append(self._join_octi(self.trace_pts[-1], end))
            self.finish_trace(final=True)
            return
        p = self.snap_dir(self.trace_pts[-1], (wx, wy))
        if p != self.trace_pts[-1]:
            self.trace_pts.append(p)

    def _join_octi(self, a, c):
        return c

    def finish_trace(self, final: bool = False) -> None:
        if self.tool != "trace" or len(self.trace_pts) < 2 or not self.trace_net:
            self.trace_pts = []
            self.request_redraw()
            return
        pts = []
        for i, p in enumerate(self.trace_pts):
            if i > 0 and abs(p[0] - pts[-1][0]) > 1e-6 and abs(p[1] - pts[-1][1]) > 1e-6 \
                    and abs(abs(p[0] - pts[-1][0]) - abs(p[1] - pts[-1][1])) > 1e-6:
                q = pts[-1]
                # a free-angle end (landing on a pin): go 45 degrees first, then straight
                dx, dy = p[0] - q[0], p[1] - q[1]
                m = min(abs(dx), abs(dy))
                pts.append((q[0] + math.copysign(m, dx), q[1] + math.copysign(m, dy)))
            pts.append(p)
        self.push_undo()
        t = self.board.add_trace(self.trace_net, pts, None, manual=True)
        self.status("Trace added to %s (corners are chamfered automatically)." % self.trace_net)
        if t is not None:
            self.sel = {"trace": len(self.board.traces) - 1, "seg": 0}
            self.show_props()
        self.trace_pts = []
        self.request_redraw()

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
            probe = Cap(end[0], end[1], end[1] * 0 + end[0], end[1], r)
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
        self.request_redraw()

    # ------------------------------------------------------------ context menu
    def context_menu(self, e) -> None:
        """Right-click menu with the actions that make sense for what is under the mouse."""
        wx, wy = self.s2w(e.x, e.y)
        m = tk.Menu(self.root, tearoff=0)
        b = self.board
        menu_preview = None
        self.menu_preview = None

        def head(text: str) -> None:
            m.add_command(label=text, state="disabled")
            m.add_separator()

        def width_menu(apply) -> tk.Menu:
            wm = tk.Menu(m, tearoff=0)
            for w in sorted(WIDTH_PRESETS + (3.0, 7.5)):
                wm.add_command(label="%g mm  (~%.1f A)" % (w, current_capacity(w, b.settings.copper_oz, b.settings.temp_rise)),
                               command=lambda w=w: apply(w))
            return wm

        if self.tool == "trace" and self.trace_pts:
            head("Drawing a trace on net %s" % self.trace_net)
            m.add_command(label="Finish trace here", command=self.finish_trace, accelerator="Enter")
            m.add_command(label="Remove last corner", command=self._trace_backup, accelerator="Backspace")
            m.add_command(label="Cancel trace", command=self.escape, accelerator="Esc")
        elif self.tool == "place" and self.armed:
            head("Placing %s" % self.lib[self.armed].name)
            m.add_command(label="Turn part 90 degrees", command=self.rotate, accelerator="R")
            m.add_command(label="Stop placing", command=self.escape, accelerator="Esc")
        else:
            hit = self.hit_test(wx, wy)
            self.sel = hit
            self.show_props()
            self.request_redraw()
            if "trace" in hit:
                ti, si = hit["trace"], hit["seg"]
                t = b.traces[ti]
                head("Trace on net %s (%.2f mm)" % (t.net, t.widths[si]))
                m.add_cascade(label="Width of this section", menu=width_menu(lambda w: self._ctx_width(ti, si, w, "segment")))
                m.add_cascade(label="Width of whole trace", menu=width_menu(lambda w: self._ctx_width(ti, si, w, "trace")))
                m.add_cascade(label="Width of whole net", menu=width_menu(lambda w: self._ctx_width(ti, si, w, "net")))
                m.add_separator()
                m.add_command(label="Trim this section", command=lambda: self.trim(ti, si), accelerator="X tool")
                m.add_command(label="Cut this piece (up to the nearest joints)", accelerator="C",
                              command=lambda: self.cut_piece(ti, (wx, wy)))
                pb = piece_bounds(b, ti, (wx, wy))
                if pb:
                    menu_preview = (_sub_polyline(t.points, pb[0], pb[1]), max(t.widths))
                else:
                    m.entryconfigure("end", state="disabled",
                                     label="Cut this piece (not on a joint: right-click the copper between joints)")
                m.add_command(label="Cut between two points (click the second)...",
                              command=lambda: self._start_cut(ti, (wx, wy)))
                m.add_command(label="Split trace here", command=lambda: self.split_here(ti, si, (wx, wy)))
                m.add_command(label="Tidy: straight pad exits, bigger chamfers", command=lambda: self._tidy(ti))
                m.add_command(label="Tip: drag a section sideways to move it", state="disabled")
                m.add_separator()
                m.add_command(label="Highlight net %s" % t.net, command=lambda: self._select_net(t.net))
                jv = tk.BooleanVar(value=b.nets[t.net].jumpers_ok if t.net in b.nets else True)
                m.add_checkbutton(label="Allow jumpers on net %s" % t.net, variable=jv,
                                  command=lambda: self._net_jumpers(t.net, jv.get()))
                m.add_command(label="Re-route net %s" % t.net, command=lambda: self.auto_route(only=t.net))
                m.add_command(label="Delete trace", command=self.delete_selection, accelerator="Del")
            elif "island" in hit and hit["island"] < len(b.islands):
                ii = hit["island"]
                isl = b.islands[ii]
                net = b.island_net(ii)
                head("Island #%d, %s %.4g x %.4g mm, %s" % (ii + 1, isl.shape == "round" and "round" or "rectangle",
                                                            isl.w, isl.h, "net %s" % net if net else "not joined yet"))
                m.add_command(label="Make it round" if isl.shape == "rect" else "Make it rectangular",
                              command=lambda: self.set_island(ii, shape="round" if isl.shape == "rect" else "rect"))
                sm = tk.Menu(m, tearoff=0)
                for v in ISLAND_SIZES:
                    sm.add_command(label="%.4g x %.4g mm" % (v, v), command=lambda v=v: self.set_island(ii, w=v, h=v))
                for a_, b_ in ((5.08, 2.54), (7.62, 3.81), (10.16, 5.08), (15.24, 5.08)):
                    sm.add_command(label="%.4g x %.4g mm" % (a_, b_), command=lambda a_=a_, b_=b_: self.set_island(ii, w=a_, h=b_))
                m.add_cascade(label="Size", menu=sm)
                m.add_command(label="Turn 90 degrees (swap width and height)",
                              command=lambda: self.set_island(ii, w=isl.h, h=isl.w))
                m.add_separator()
                m.add_command(label="Duplicate island", command=lambda: self.duplicate_island(ii), accelerator="Ctrl+D")
                m.add_command(label="Delete island", command=self.delete_selection, accelerator="Del")
            elif "jumper" in hit:
                j = b.jumpers[hit["jumper"]]
                head("Jumper on net %s (%.1f mm)" % (j.net, j.length()))
                m.add_command(label="Re-route net %s" % j.net, command=lambda: self.auto_route(only=j.net))
                m.add_command(label="Delete jumper", command=self.delete_selection, accelerator="Del")
            elif "part" in hit and hit["part"] in b.parts:
                ref = hit["part"]
                pl = b.parts[ref]
                d = b.get_def(pl.part_id)
                if "pin" in hit:
                    pin = "%s.%s" % (ref, hit["pin"])
                    n = b.net_of(pin)
                    head("Pin %s  (net %s)" % (pin, n.name if n else "none"))
                    m.add_command(label="Wire from this pin", command=lambda: self._start_wire(pin), accelerator="W")
                    m.add_command(label="Rigid (direct A-B) wire from this pin",
                                  command=lambda: self._start_wire(pin, True), accelerator="Shift")
                    if n:
                        m.add_command(label="Draw trace from this pin", command=lambda: self._start_trace(pin), accelerator="T")
                        m.add_command(label="Route net %s" % n.name, command=lambda: self.auto_route(only=n.name))
                        m.add_command(label="Disconnect this pin", command=lambda: self._disconnect(pin))
                    pm = tk.Menu(m, tearoff=0)
                    for v, tx in (("(part)", "Same as the part"), ("tht", "Through-hole"), ("dead", "Deadbug"), ("mixed", "Both")):
                        pm.add_command(label=tx, command=lambda v=v: self._set_pad_style(ref, hit["pin"], v))
                    m.add_cascade(label="This pad's style", menu=pm)
                    m.add_separator()
                else:
                    head("%s  -  %s" % (ref, d.name))
                m.add_command(label="Set value / type...", command=lambda: self.focus_value(ref),
                              accelerator="double-click")
                lm = tk.Menu(m, tearoff=0)
                for nm, lab in library.pinout_presets(d):
                    lm.add_command(label="%s   (%s)" % (nm, " ".join(lab.get(pd.name, ".") for pd in d.pads))
                                   if len(d.pads) <= 4 else nm, command=lambda lab=lab: self._set_pin_labels(ref, lab))
                lm.add_separator()
                lm.add_command(label="Custom (type them in the right panel)...", command=lambda: self.focus_value(ref))
                lm.add_command(label="No labels", command=lambda: self._set_pin_labels(ref, {}))
                m.add_cascade(label="Pin labels", menu=lm)
                m.add_separator()
                m.add_command(label="Rotate 90 degrees", command=self.rotate, accelerator="R")
                m.add_command(label="Rotate back 90 degrees", command=lambda: self.rotate(-90), accelerator="Shift+R")
                m.add_command(label="Duplicate", command=self.duplicate, accelerator="Ctrl+D")
                lk = tk.BooleanVar(value=pl.locked)
                m.add_checkbutton(label="Lock (auto-place leaves it alone)", variable=lk,
                                  command=lambda: self._set_lock(ref, lk.get()))
                sm = tk.Menu(m, tearoff=0)
                for v, tx in (("tht", "Through-hole"), ("dead", "Deadbug (no hole)"), ("mixed", "Both")):
                    sm.add_command(label=tx, command=lambda v=v: self._set_style(ref, v))
                m.add_cascade(label="Pads of this part", menu=sm)
                nets = sorted({b.net_of("%s.%s" % (ref, p.name)).name for p in d.pads
                               if b.net_of("%s.%s" % (ref, p.name))})
                if nets:
                    m.add_command(label="Route this part's nets", command=lambda: self.auto_route(only=nets))
                m.add_separator()
                m.add_command(label="Delete part", command=lambda: self._delete_part(ref), accelerator="Del")
            elif "net" in hit:
                name = hit["net"]
                head("Connection, net %s" % name)
                m.add_command(label="Route this net", command=lambda: self.auto_route(only=name))
                if hit.get("pins"):
                    pa, pb = hit["pins"]
                    is_rigid = any(set(lk) == {pa, pb} for lk in b.nets[name].links)
                    m.add_command(label=("Make %s - %s a normal connection" if is_rigid else
                                         "Make %s - %s rigid (direct trunk)") % (pa, pb),
                                  command=lambda: self._toggle_rigid(pa, pb, not is_rigid))
                m.add_cascade(label="Width for this net", menu=width_menu(lambda w: self._ctx_net_width(name, w)))
                jv2 = tk.BooleanVar(value=b.nets[name].jumpers_ok)
                m.add_checkbutton(label="Allow jumpers on this net", variable=jv2,
                                  command=lambda: self._net_jumpers(name, jv2.get()))
                m.add_command(label="Draw it by hand (Trace tool)", command=lambda: self.set_tool("trace"))
                m.add_separator()
                m.add_command(label="Remove net %s" % name, command=self.delete_selection, accelerator="Del")
            else:
                head("Board %s" % b.name)
                if self.armed:
                    m.add_command(label="Place %s here" % self.lib[self.armed].name if self.armed in self.lib else "Place part here",
                                  command=lambda: self.place_here(wx, wy))
                m.add_command(label="Add a copper island here", command=lambda: self.add_island(wx, wy))
                m.add_command(label="Auto-place", command=self.auto_place)
                m.add_command(label="Auto-route", command=self.auto_route)
                m.add_command(label="Tidy all traces", command=self.tidy_all)
                m.add_command(label="Check (DRC)", command=self.show_drc)
                m.add_separator()
                m.add_command(label="Fit board", command=self.fit, accelerator="F")
                m.add_command(label="Flip view (copper / component side)", command=self.toggle_mirror, accelerator="M")
                m.add_command(label="Board size and rules...", command=self.board_settings)
        m.add_separator()
        m.add_command(label="Undo", command=self.do_undo, accelerator="Ctrl+Z",
                      state="normal" if self.undo else "disabled")
        m.add_command(label="Redo", command=self.do_redo, accelerator="Ctrl+Y",
                      state="normal" if self.redo else "disabled")
        self._menu = m
        if menu_preview:
            # while the mouse is on "Cut this piece", show the piece that would go in red
            def on_select(_ev=None) -> None:
                try:
                    lab = m.entrycget("active", "label")
                except tk.TclError:
                    lab = ""
                show = menu_preview if lab.startswith("Cut this piece") else None
                if show != self.menu_preview:
                    self.menu_preview = show
                    self.draw_dynamic()
            m.bind("<<MenuSelect>>", on_select)
            m.bind("<Unmap>", lambda _ev: (setattr(self, "menu_preview", None), self.request_overlay()))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _ctx_width(self, ti: int, si: int, w: float, scope: str) -> None:
        b = self.board
        if ti >= len(b.traces):
            return
        self.push_undo()
        t = b.traces[ti]
        if scope == "segment":
            b.set_segment_width(t, si, w)
        elif scope == "trace":
            b.set_trace_width(t, w)
        else:
            b.set_net_trace_width(t.net, w)
        if self.auto_tidy.get():
            tidy_traces(b, [x for x in b.traces if x.net == t.net] if scope == "net" else [t])
        self.sel = {"trace": min(ti, len(b.traces) - 1), "seg": si}
        self.show_props()
        self.quick_drc("Width set to %g mm." % w)

    def _ctx_net_width(self, name: str, w: float) -> None:
        b = self.board
        if name not in b.nets:
            return
        self.push_undo()
        cls = "%g mm" % round(w, 2)
        b.settings.classes[cls] = w
        b.nets[name].cls = cls
        b.set_net_trace_width(name, w)
        b.touch()
        self.show_props()
        self.request_redraw()

    def _select_net(self, net: str) -> None:
        self.sel = {"net": net}
        self.show_props()
        self.request_redraw()

    def _start_wire(self, pin: str, rigid: bool = False) -> None:
        self.set_tool("wire")
        self.pending_pin = pin
        self.rigid_next = rigid
        self.status("From %s. Now click the other pin%s." % (pin, " (rigid wire)" if rigid else ""))

    def _start_cut(self, ti: int, p) -> None:
        self.set_tool("cut")
        _s, q, _d = project_on_trace(self.board.traces[ti], p)
        self.cut_start = (ti, q)
        self.status("Cut from here: now Shift + click the second point on the same trace (Esc cancels).")
        self.request_overlay()

    def _toggle_jumpers(self) -> None:
        self.push_undo()
        self.board.settings.allow_jumpers = bool(self.jumpers_var.get())
        self.status("Auto-route %s add wire-link jumpers." % ("may" if self.board.settings.allow_jumpers else "will NOT"))

    def _toggle_keepout(self) -> None:
        self.push_undo()
        self.board.settings.keep_out_under_parts = bool(self.keepout_var.get())
        self.status("Auto-route will %s. Route again to apply it." % (
            "go round part bodies (between DIP rows, under transistors) unless there is no other way"
            if self.board.settings.keep_out_under_parts else "run under part bodies when that is shorter"))

    def _toggle_islands(self) -> None:
        st = self.board.settings
        on = bool(self.island_var.get())
        dead = False
        if on and any(pl.style != "dead" or pl.pad_styles for pl in self.board.parts.values()):
            dead = messagebox.askyesno(
                APP_NAME, "A ground-fill board is usually built with the parts soldered straight onto the copper.\n\n"
                "Make every pad a deadbug pad (no holes to drill)?", parent=self.root)
        self.set_islands(on, st.island_net, st.island_gap, st.island_grow, dead)

    def island_dialog(self) -> None:
        from .dialogs import IslandDialog
        IslandDialog(self)

    def set_islands(self, on: bool, net: str, gap: float, grow: float, dead: bool) -> None:
        """Turn the ground fill on or off with these settings (one undo step)."""
        b = self.board
        st = b.settings
        self.push_undo()
        was = st.island_mode
        st.island_mode, st.island_net, st.island_gap, st.island_grow = on, net, gap, grow
        msg = []
        if dead:
            n = make_pads_deadbug(b)
            if n:
                msg.append("%d part(s) now have deadbug pads." % n)
        if on:
            from .islands import ground_net
            g = ground_net(b)
            if g:
                # the fill joins the ground net; its automatic traces are no longer needed
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
        self.island_var.set(on)
        self.mark_dirty()
        self.redraw()
        self.show_props()
        self.status(" ".join(msg) or "Ground fill settings saved.")

    def _net_jumpers(self, net: str, ok: bool) -> None:
        if net in self.board.nets:
            self.push_undo()
            self.board.nets[net].jumpers_ok = bool(ok)
            self.show_props()
            self.status("Net %s: jumpers %s." % (net, "allowed" if ok else "not allowed"))

    def _toggle_rigid(self, a: str, b: str, on: bool) -> None:
        self.push_undo()
        try:
            self.board.set_rigid(a, b, on)
        except ValueError as exc:
            self.status(str(exc))
            return
        self.show_props()
        self.request_redraw()
        self.status("%s - %s is now %s. Re-route the net to apply it." % (a, b, "rigid" if on else "a normal connection"))

    def _start_trace(self, pin: str) -> None:
        self.set_tool("trace")
        p = self.board.pin_pos(pin)
        self.trace_click(p[0], p[1])

    def _disconnect(self, pin: str) -> None:
        self.push_undo()
        self.board.disconnect(pin)
        self.board.touch()
        self.show_props()
        self.request_redraw()

    def _delete_part(self, ref: str) -> None:
        self.sel = {"part": ref}
        self.delete_selection()

    def _trace_backup(self) -> None:
        if len(self.trace_pts) > 1:
            self.trace_pts.pop()
        else:
            self.trace_pts = []
        self.request_redraw()

    # ---------------------------------------------------------- trace editing
    def trim(self, ti: int, si: int) -> None:
        b = self.board
        if ti >= len(b.traces):
            return
        self.push_undo()
        net = b.traces[ti].net
        kept = trim_segment(b, ti, si)
        self.sel = {}
        self.show_props()
        self.status("Trimmed a section of net %s; %d piece(s) of that trace left. Ctrl+Z undoes it." % (net, kept))
        self.request_redraw()

    def split_here(self, ti: int, si: int, p) -> None:
        self.push_undo()
        split_trace(self.board, ti, si, p)
        self.sel = {"trace": ti, "seg": min(si, len(self.board.traces[ti].widths) - 1)}
        self.show_props()
        self.status("Trace split in two. Each half can now be moved, trimmed or deleted on its own.")
        self.request_redraw()

    def tidy_all(self) -> None:
        self.push_undo()
        n = tidy_traces(self.board)
        settle_branch_ends(self.board)
        self.status("Tidied %d trace(s): centred ends, straight exits on wide traces, larger chamfers." % n)
        self.quick_drc("Tidied %d trace(s)." % n)

    # -------------------------------------------------------------- part edits
    # ----------------------------------------------------------------- islands
    def add_island(self, wx: float, wy: float, w: Optional[float] = None, h: Optional[float] = None,
                   shape: Optional[str] = None) -> int:
        """Drop a copper island centred here (snapped); returns its index."""
        n = self.island_new
        x, y = self.snap((wx, wy), ISLAND_GRID)
        self.push_undo()
        isl = Island(x, y, clamp_island(w or n["w"]), clamp_island(h or n["h"]), shape or n["shape"])
        self.board.islands.append(isl)
        self.board.touch()
        i = len(self.board.islands) - 1
        self.sel = {"island": i}
        self.show_props()
        self._island_status(i, "Island #%d added" % (i + 1))
        self.request_redraw()
        return i

    def _island_status(self, i: int, what: str) -> None:
        net = self.board.island_net(i)
        pins = [p for p in self._island_pins(i)]
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
        self.show_props()
        self.status("Duplicated island #%d. Drag it where you want it." % (i + 1))
        self.request_redraw()

    def set_island(self, i: int, **kw) -> None:
        """Change an island's shape or size (one undo step); the new values become the default for new islands."""
        b = self.board
        if i >= len(b.islands):
            return
        isl = b.islands[i]
        self.push_undo()
        for k, v in kw.items():
            if k in ("w", "h"):
                v = clamp_island(v)
            setattr(isl, k, v)
        self.island_new = {"shape": isl.shape, "w": isl.w, "h": isl.h}
        b.touch()
        self.sel = {"island": i}
        self.show_props()
        self._island_status(i, "Island #%d is now %s %.4g x %.4g mm" % (
            i + 1, isl.shape == "round" and "round" or "rectangular", isl.w, isl.h))
        self.request_redraw()

    def island_press(self, e, wx: float, wy: float) -> None:
        b = self.board
        self.drag = None
        h = self.island_handle(e.x, e.y)
        if h:
            i, kx, ky = h
            isl = b.islands[i]
            self.drag = {"island": i, "resize": (isl.x - kx * isl.w / 2, isl.y - ky * isl.h / 2), "moved": False}
            return
        shift = bool(getattr(e, "state", 0) & 1)
        if shift:
            n = self.island_new
            n["shape"] = "round" if n["shape"] == "rect" else "rect"
            self.status("New islands will be %s. Shift + click switches back." % (
                "round" if n["shape"] == "round" else "rectangular"))
            self.request_overlay()
            return
        i = self.island_at(wx, wy)
        if i is not None:
            isl = b.islands[i]
            self.sel = {"island": i}
            self.drag = {"island": i, "dx": isl.x - wx, "dy": isl.y - wy, "moved": False}
            self.show_props()
            self.request_redraw()
            return
        p0 = self.snap((wx, wy), ISLAND_GRID)
        self.drag = {"draw_island": p0, "cur": p0, "sx": e.x, "sy": e.y}
        self.request_overlay()

    def island_drag(self, d: dict, wx: float, wy: float) -> None:
        b = self.board
        if "draw_island" in d:
            d["cur"] = self.snap((wx, wy), ISLAND_GRID)
            self.request_overlay()
            return
        i = d["island"]
        if i >= len(b.islands):
            return
        isl = b.islands[i]
        if "resize" in d:
            ax, ay = d["resize"]
            cx, cy = self.snap((wx, wy), ISLAND_GRID)
            w = clamp_island(abs(cx - ax))
            h = clamp_island(abs(cy - ay))
            nx = ax + (w / 2 if cx >= ax else -w / 2)
            ny = ay + (h / 2 if cy >= ay else -h / 2)
            new = (nx, ny, w, h)
        else:
            nx, ny = self.snap((wx + d["dx"], wy + d["dy"]), ISLAND_GRID)
            new = (nx, ny, isl.w, isl.h)
        if new != (isl.x, isl.y, isl.w, isl.h):
            if not d["moved"]:
                self.push_undo()
                d["moved"] = True
            isl.x, isl.y, isl.w, isl.h = new
            b.touch()
            self.request_redraw()

    def island_release(self, d: dict, wx: float, wy: float) -> None:
        b = self.board
        if "draw_island" in d:
            (x0, y0), (x1, y1) = d["draw_island"], d["cur"]
            if abs(x1 - x0) >= ISLAND_MIN and abs(y1 - y0) >= ISLAND_MIN:
                self.island_new["w"], self.island_new["h"] = abs(x1 - x0), abs(y1 - y0)
                self.add_island((x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0), abs(y1 - y0))
            else:
                self.add_island(x0, y0)
            return
        i = d["island"]
        if d.get("moved") and i < len(b.islands):
            isl = b.islands[i]
            if "resize" in d:
                self.island_new = {"shape": isl.shape, "w": isl.w, "h": isl.h}
            self.show_props()
            self._island_status(i, "Island #%d %s" % (i + 1, "resized to %.4g x %.4g mm" % (isl.w, isl.h)
                                                       if "resize" in d else "moved"))

    def _props_island(self, p, i: int) -> None:
        b = self.board
        isl = b.islands[i]
        net = b.island_net(i)
        pins = self._island_pins(i)
        ttk.Label(p, text="Copper island #%d" % (i + 1), font=FONT_B).pack(anchor="w", pady=(4, 0))
        if net:
            txt = "Joined to net %s%s" % (net, ("\nPins on it: " + ", ".join(pins)) if pins else "")
        else:
            txt = "Not joined to anything yet: put a part's pin on it, or draw a trace onto it."
        ttk.Label(p, text=txt, wraplength=250, justify="left").pack(anchor="w", pady=(2, 6))
        sv = tk.StringVar(value=isl.shape)
        row = ttk.Frame(p)
        row.pack(anchor="w")
        for val, lab in (("rect", "Rectangle"), ("round", "Round")):
            ttk.Radiobutton(row, text=lab, value=val, variable=sv,
                            command=lambda: self.set_island(i, shape=sv.get())).pack(side="left", padx=(0, 8))
        grid = ttk.Frame(p)
        grid.pack(anchor="w", pady=4)
        ents = {}
        for r, (k, lab) in enumerate((("w", "Width (mm)"), ("h", "Height (mm)"), ("corner", "Corner cut (mm)"))):
            if k == "corner" and isl.shape == "round":
                continue
            ttk.Label(grid, text=lab).grid(row=r, column=0, sticky="w")
            v = tk.StringVar(value="%.4g" % getattr(isl, k))
            en = ttk.Entry(grid, textvariable=v, width=8)
            en.grid(row=r, column=1, padx=4, pady=1)
            ents[k] = v

            def commit(_e=None, k=k, v=v) -> None:
                try:
                    val = float(v.get())
                except ValueError:
                    self.status("Type a number in mm.")
                    return
                if k == "corner":
                    val = max(0.0, min(val, min(isl.w, isl.h) / 2))
                if abs(val - getattr(isl, k)) > 1e-9:
                    self.set_island(i, **{k: val})
            en.bind("<Return>", commit)
            en.bind("<FocusOut>", commit)
        ttk.Label(p, text="Square / circle sizes:").pack(anchor="w")
        pr = ttk.Frame(p)
        pr.pack(anchor="w")
        for n_, v in enumerate(ISLAND_SIZES):
            ttk.Button(pr, text="%.4g" % v, style="Small.TButton", width=5,
                       command=lambda v=v: self.set_island(i, w=v, h=v)).grid(row=n_ // 4, column=n_ % 4, padx=1, pady=1)
        bar = ttk.Frame(p)
        bar.pack(anchor="w", pady=6)
        ttk.Button(bar, text="Turn 90", width=0, command=lambda: self.set_island(i, w=isl.h, h=isl.w)).pack(side="left")
        ttk.Button(bar, text="Duplicate", width=0, command=lambda: self.duplicate_island(i)).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete", width=0, command=self.delete_selection).pack(side="left")
        ttk.Label(p, text="Drag the island to move it, drag a white corner square to resize it. Pins of two "
                          "different nets on one island short them (Check marks it).",
                  wraplength=250, justify="left").pack(anchor="w", pady=(4, 0))

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
        self.show_props()
        self.status("Duplicated %s as %s. Drag it where you want it." % (ref, np_.ref))
        self.request_redraw()

    def nudge(self, dx: int, dy: int, big: bool = False) -> None:
        i = self.sel.get("island")
        if i is not None and i < len(self.board.islands):
            g = 2.54 if big else self.board.settings.place_grid
            self.push_undo()
            isl = self.board.islands[i]
            isl.x += dx * g
            isl.y += dy * g
            self.board.touch()
            self.request_redraw()
            return
        ref = self.sel.get("part")
        if not ref or ref not in self.board.parts or self.board.parts[ref].locked:
            return
        g = 2.54 if big else self.board.settings.place_grid
        pl = self.board.parts[ref]
        self.push_undo()
        self.board.move_part(ref, pl.x + dx * g, pl.y + dy * g)
        self.request_redraw()

    # ------------------------------------------------------- recent / autosave
    def _remember_recent(self, path: str) -> None:
        cfg = load_config()
        rec = [p for p in cfg.get("recent", []) if p != path]
        cfg["recent"] = [path] + rec[:7]
        save_config(cfg)
        self._fill_recent()

    def _fill_recent(self) -> None:
        m = getattr(self, "recent_menu", None)
        if m is None:
            return
        m.delete(0, "end")
        rec = [p for p in load_config().get("recent", []) if isinstance(p, str)]
        if not rec:
            m.add_command(label="(nothing yet)", state="disabled")
        for p in rec:
            m.add_command(label=p, command=lambda p=p: self.open_path(p))

    def open_path(self, p: str) -> None:
        if not self.confirm_discard():
            return
        try:
            self.load_board(Board.load(p), p)
            self._remember_recent(p)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not open that file:\n%s" % exc)

    def _autosave_tick(self) -> None:
        if self._closing:
            return
        if self.dirty:
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                self.board.save(AUTOSAVE_FILE)
                self.status_var.set(self.status_var.get().split("   [")[0] + "   [autosaved]")
            except Exception:
                pass
        self._autosave_id = self.root.after(AUTOSAVE_MS, self._autosave_tick)

    def recover_autosave(self) -> None:
        if not os.path.exists(AUTOSAVE_FILE):
            messagebox.showinfo(APP_NAME, "There is no autosaved board.")
            return
        if not self.confirm_discard():
            return
        try:
            b = Board.load(AUTOSAVE_FILE)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "The autosave could not be read:\n%s" % exc)
            return
        self.load_board(b)
        self.dirty = True
        self.set_title()
        self.status("Recovered the autosaved board. Save it under a name to keep it.")

    # ------------------------------------------------------------------ properties
    def clear_props(self) -> None:
        for w in self.prop.winfo_children():
            w.destroy()

    def show_props(self) -> None:
        self.clear_props()
        p = self.prop
        s = self.sel
        b = self.board
        ttk.Label(p, text="Selection", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        if "trace" in s and s["trace"] < len(b.traces):
            self._props_trace(p)
        elif "jumper" in s and s["jumper"] < len(b.jumpers):
            j = b.jumpers[s["jumper"]]
            ttk.Label(p, text="Wire-link jumper, net %s\n%.1f mm long, %s" % (
                j.net, j.length(), "automatic" if j.auto else "manual"), justify="left").pack(anchor="w", pady=4)
            ttk.Label(p, text="Fit a bare wire or a link part on the COMPONENT side.\nSolder both ends on the copper side.",
                      wraplength=260, justify="left").pack(anchor="w")
            ttk.Button(p, text="Delete jumper", command=self.delete_selection).pack(anchor="w", pady=6)
        elif "island" in s and s["island"] < len(b.islands):
            self._props_island(p, s["island"])
        elif "part" in s and s["part"] in b.parts:
            self._props_part(p)
        elif "net" in s and s["net"] in b.nets:
            self._props_net(p, s["net"])
        else:
            self._props_board(p)

    def _props_board(self, p) -> None:
        b = self.board
        n_air = b.unrouted_count()
        txt = "Board %s\n%.0f x %.0f mm\n%d parts, %d nets\n%d traces, %d jumpers\n%d connection(s) still to route" % (
            b.name, b.width, b.height, len(b.parts), len(b.nets), len(b.traces), len(b.jumpers), n_air)
        ttk.Label(p, text=txt, justify="left").pack(anchor="w", pady=4)
        ttk.Label(p, text="Nothing selected. Click a part, a pin, a trace or a yellow rubber-band line.",
                  wraplength=260, justify="left").pack(anchor="w", pady=4)
        ttk.Button(p, text="Board size and rules...", command=self.board_settings).pack(anchor="w", pady=2)

    def _props_part(self, p) -> None:
        b = self.board
        ref = self.sel["part"]
        pl = b.parts[ref]
        d = b.get_def(pl.part_id)
        ttk.Label(p, text="%s  -  %s" % (ref, d.name), wraplength=270, justify="left").pack(anchor="w", pady=2)
        row = ttk.Frame(p)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Value / type", font=FONT_B).pack(side="left")
        val = tk.StringVar(value=pl.value)
        ent = ttk.Entry(row, textvariable=val, width=15)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self._set_value(ref, val.get()))
        ent.bind("<FocusOut>", lambda e: self._set_value(ref, val.get()))
        self.value_entry = ent
        ttk.Label(p, text="e.g. NE555, BC547, IRF540, 7805, 10k, 100uF 25V, 1N4007. Shown on the board.",
                  style="Muted.TLabel", wraplength=270).pack(anchor="w")
        # pin-function labels
        presets = library.pinout_presets(d)
        cur = b.pin_labels_of(ref)
        cur_txt = " ".join(cur.get(pd.name, ".") for pd in d.pads)
        names = ["(none)"] + [nm for nm, _lab in presets]
        cur_name = next((nm for nm, lab in presets if lab == cur), "(none)" if not cur else "Custom")
        lf = ttk.Frame(p)
        lf.pack(fill="x", pady=(6, 0))
        ttk.Label(lf, text="Pin labels", font=FONT_B).pack(side="left")
        pv = tk.StringVar(value=cur_name)
        cb = ttk.Combobox(lf, textvariable=pv, values=names + ["Custom"], state="readonly", width=24)
        cb.pack(side="left", padx=4)
        cv = tk.StringVar(value=cur_txt if cur else "")
        crow = ttk.Frame(p)
        crow.pack(fill="x", pady=2)
        ce = ttk.Entry(crow, textvariable=cv, width=22)
        ce.pack(side="left")

        def from_preset(_e=None) -> None:
            nm = pv.get()
            if nm == "Custom":
                ce.focus_set()
                return
            labels = dict(next((lab for n2, lab in presets if n2 == nm), {}))
            self._set_pin_labels(ref, labels)

        def from_text(_e=None) -> None:
            self._set_pin_labels(ref, library.parse_pin_labels(d, cv.get()))
        cb.bind("<<ComboboxSelected>>", from_preset)
        ce.bind("<Return>", from_text)
        ttk.Button(crow, text="Set", width=4, command=from_text).pack(side="left", padx=4)
        ttk.Label(p, text="Labels in pin order, separated by spaces; '.' skips a pin. Common layouts only: "
                          "check your part's datasheet.", style="Muted.TLabel", wraplength=270).pack(anchor="w")
        row2 = ttk.Frame(p)
        row2.pack(fill="x", pady=2)
        ttk.Button(row2, text="Rotate 90", command=self.rotate).pack(side="left")
        lock = tk.BooleanVar(value=pl.locked)
        ttk.Checkbutton(row2, text="Lock", variable=lock, command=lambda: self._set_lock(ref, lock.get())).pack(side="left", padx=8)
        ttk.Label(p, text="Pads of this part").pack(anchor="w", pady=(6, 0))
        st = tk.StringVar(value=pl.style)
        for v, t in (("tht", "Through-hole"), ("dead", "Deadbug (surface solder, no hole)"), ("mixed", "Both")):
            ttk.Radiobutton(p, text=t, value=v, variable=st, command=lambda: self._set_style(ref, st.get())).pack(anchor="w")
        if "pin" in self.sel:
            pin = "%s.%s" % (ref, self.sel["pin"])
            n = b.net_of(pin)
            ttk.Separator(p).pack(fill="x", pady=6)
            ttk.Label(p, text="Pin %s   net: %s" % (self.sel["pin"], n.name if n else "none")).pack(anchor="w")
            cur = pl.pad_styles.get(self.sel["pin"], "(part)")
            ps = tk.StringVar(value=cur)
            f = ttk.Frame(p)
            f.pack(anchor="w", pady=2)
            ttk.Label(f, text="This pad only:").pack(side="left")
            cb = ttk.Combobox(f, textvariable=ps, values=["(part)", "tht", "dead", "mixed"], state="readonly", width=8)
            cb.pack(side="left", padx=4)
            cb.bind("<<ComboboxSelected>>", lambda e: self._set_pad_style(ref, self.sel["pin"], ps.get()))
            if n:
                ttk.Button(p, text="Disconnect this pin", command=self.delete_selection).pack(anchor="w", pady=2)
        ttk.Button(p, text="Delete part", command=self.delete_selection).pack(anchor="w", pady=8)
        if d.note:
            ttk.Label(p, text=d.note, wraplength=260, justify="left", foreground="#555").pack(anchor="w")

    def _set_value(self, ref: str, v: str) -> None:
        if ref in self.board.parts and self.board.parts[ref].value != v:
            self.push_undo()
            self.board.parts[ref].value = v
            self.board.touch()

    def _set_pin_labels(self, ref: str, labels: Dict[str, str]) -> None:
        if ref not in self.board.parts:
            return
        self.push_undo()
        pl = self.board.parts[ref]
        pl.pin_labels = dict(labels) if labels else {}
        if not labels:
            pl.pin_labels = {"_": ""}         # explicit "none": hide the default labels too
        self.board.touch()
        self.show_props()
        self.request_redraw()

    def focus_value(self, ref: str) -> None:
        self.sel = {"part": ref}
        self.show_props()
        e = getattr(self, "value_entry", None)
        if e is not None:
            e.focus_set()
            e.select_range(0, "end")

    def _set_lock(self, ref: str, v: bool) -> None:
        self.push_undo()
        self.board.parts[ref].locked = v

    def _set_style(self, ref: str, style: str) -> None:
        self.push_undo()
        pl = self.board.parts[ref]
        pl.style = style
        pl.pad_styles = {}
        self.board.touch()
        self.request_redraw()

    def _set_pad_style(self, ref: str, pad: str, style: str) -> None:
        self.push_undo()
        pl = self.board.parts[ref]
        if style == "(part)":
            pl.pad_styles.pop(pad, None)
        else:
            pl.pad_styles[pad] = style
        self.board.touch()
        self.request_redraw()

    def _width_slider(self, p, start: float, on_change, on_press=None):
        """Slider 0.4 to 10 mm with an entry box and preset buttons. Returns the variable."""
        var = tk.DoubleVar(value=round(start, 2))
        cap = tk.StringVar()

        def upd(v=None) -> None:
            w = clamp_width(float(var.get()))
            cap.set("%.2f mm  ~ %.1f A (1 oz copper, 10 C rise)" % (
                w, current_capacity(w, self.board.settings.copper_oz, self.board.settings.temp_rise)))

        def changed(v=None) -> None:
            if self._building_panel:
                return
            upd()
            on_change(clamp_width(float(var.get())))

        sc = tk.Scale(p, from_=MIN_WIDTH, to=MAX_WIDTH, resolution=0.05, orient="horizontal", length=270,
                      variable=var, command=changed, showvalue=False, troughcolor="#d7c2a8",
                      bg=UI["copper"], activebackground=UI["copper_dark"], highlightthickness=0,
                      sliderrelief="flat", bd=0, width=14, sliderlength=22)
        if on_press:
            sc.bind("<ButtonPress-1>", lambda e: on_press())
        sc.pack(anchor="w", pady=2)
        ttk.Label(p, textvariable=cap).pack(anchor="w")
        f = ttk.Frame(p)
        f.pack(anchor="w", pady=2)
        for w in WIDTH_PRESETS:
            def setw(w=w) -> None:
                if on_press:
                    on_press()
                var.set(w)
                changed()
            ttk.Button(f, text="%g" % w, width=3, style="Small.TButton", command=setw).pack(side="left", padx=1)
        row = ttk.Frame(p)
        row.pack(anchor="w", pady=2)
        ttk.Label(row, text="Exact mm:").pack(side="left")
        ev = tk.StringVar(value="%.2f" % start)
        e = ttk.Entry(row, textvariable=ev, width=7)
        e.pack(side="left", padx=4)

        def from_entry(_e=None) -> None:
            try:
                v = clamp_width(float(ev.get()))
            except ValueError:
                return
            if on_press:
                on_press()
            var.set(v)
            changed()
        e.bind("<Return>", from_entry)
        var.trace_add("write", lambda *a: ev.set("%.2f" % float(var.get())) if not self._building_panel else None)
        upd()
        return var

    def _props_trace(self, p) -> None:
        b = self.board
        ti, si = self.sel["trace"], self.sel.get("seg", 0)
        t = b.traces[ti]
        si = min(si, len(t.widths) - 1)
        a, c = t.points[si], t.points[si + 1]
        ttk.Label(p, text="Trace on net %s\nsection %d of %d, %.1f mm long%s%s" % (
            t.net, si + 1, len(t.widths), dist(a, c), "  (drawn by hand)" if t.manual else "  (auto-routed)",
            "\nrigid trunk (from a Shift + Wire link)" if t.rigid else ""),
            justify="left").pack(anchor="w", pady=4)
        ttk.Label(p, text="Width", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        scope = self.width_scope
        for v, tx in (("segment", "This section only"), ("trace", "Whole trace"), ("net", "Every trace of this net")):
            ttk.Radiobutton(p, text=tx, value=v, variable=scope).pack(anchor="w")

        def change(w: float) -> None:
            if ti >= len(b.traces):
                return
            tr = b.traces[ti]
            sc = scope.get()
            if sc == "segment":
                b.set_segment_width(tr, min(si, len(tr.widths) - 1), w)
            elif sc == "trace":
                b.set_trace_width(tr, w)
            else:
                b.set_net_trace_width(tr.net, w)
            self.mark_dirty()
            self.request_redraw()
            self.quick_drc(tidy=[x for x in b.traces if x.net == tr.net] if sc == "net" else [tr])

        self._building_panel = True
        self._width_slider(p, t.widths[si], change, self.push_undo)
        self._building_panel = False
        fit = self.fits_up_to(t)
        ttk.Label(p, text=("Fits up to about %.2f mm here." % fit) if fit > 0 else
                  "Too close to other copper even at the minimum width.",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Checkbutton(p, text="Auto-tidy when the width changes", variable=self.auto_tidy).pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(p)
        row.pack(anchor="w", pady=4, fill="x")
        ttk.Button(row, text="Tidy", width=7, command=lambda: self._tidy(ti)).pack(side="left")
        ttk.Button(row, text="Trim", width=7, command=lambda: self.trim(ti, si)).pack(side="left", padx=4)
        ttk.Button(row, text="Delete", width=7, style="Red.TButton", command=self.delete_selection).pack(side="left")
        ttk.Label(p, text="Drag a section sideways to move it. Right-click for more.", style="Muted.TLabel",
                  wraplength=270).pack(anchor="w", pady=(4, 0))
        w = max(t.widths)
        if w < b.settings.min_trace:
            ttk.Label(p, text="Below the minimum trace width.", foreground="#b00").pack(anchor="w")

    def quick_drc(self, prefix: str = "Width changed.", tidy: Optional[List[Trace]] = None) -> None:
        """After an edit, say whether the board still meets the clearance rule (debounced).

        ``tidy``: traces to straighten (pad exits, chamfers) once the slider has stopped moving.
        """
        if getattr(self, "_qd", None):
            self.root.after_cancel(self._qd)
        if tidy:
            self._qd_tidy = tidy

        def run() -> None:
            self._qd = None
            todo = getattr(self, "_qd_tidy", None)
            self._qd_tidy = None
            if todo and self.auto_tidy.get():
                keep = self.sel.get("trace")
                tr = self.board.traces[keep] if keep is not None and keep < len(self.board.traces) else None
                tidy_traces(self.board, [t for t in todo if t in self.board.traces])
                settle_branch_ends(self.board)
                if tr is not None and tr in self.board.traces and "seg" in self.sel:
                    self.sel["seg"] = min(self.sel["seg"], len(tr.widths) - 1)
            iss = [i for i in run_drc(self.board, check_unrouted=False) if i.kind in ("clearance", "edge")]
            self.marks = [(i.x, i.y) for i in iss]
            self.status("%s %s" % (prefix, "%d clearance/edge problem(s) marked in red: make the trace thinner "
                                            "or move things apart." % len(iss) if iss else "Clearances OK."))
            self.request_redraw()

        self._qd = self.root.after(400, run)

    def _tidy(self, ti: int) -> None:
        if ti < len(self.board.traces):
            self.push_undo()
            ch = tidy_trace(self.board, self.board.traces[ti])
            self.status("Trace tidied: ends centred on pads, straight exits for wide traces, chamfers enlarged."
                        if ch else "Nothing to tidy (no room, or it is already tidy).")
            self.show_props()
            self.request_redraw()

    def fits_up_to(self, t: Trace) -> float:
        """Widest width (to 0.05 mm) this trace can have where it is without breaking clearance."""
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

    def _props_net(self, p, name: str) -> None:
        b = self.board
        n = b.nets[name]
        ttk.Label(p, text="Net %s\n%d pins: %s" % (name, len(n.pins), ", ".join(n.pins[:10]) + (" ..." if len(n.pins) > 10 else "")),
                  wraplength=260, justify="left").pack(anchor="w", pady=4)
        row = ttk.Frame(p)
        row.pack(anchor="w", pady=2)
        ttk.Label(row, text="Name").pack(side="left")
        nv = tk.StringVar(value=name)
        e = ttk.Entry(row, textvariable=nv, width=14)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self._rename_net(name, nv.get()))
        ttk.Label(p, text="Class").pack(anchor="w")
        cv = tk.StringVar(value=n.cls)
        cb = ttk.Combobox(p, textvariable=cv, values=list(b.settings.classes), state="readonly")
        cb.pack(anchor="w")
        cb.bind("<<ComboboxSelected>>", lambda ev: self._net_class(name, cv.get()))
        ttk.Label(p, text="Width used when routing this net", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(8, 0))
        apply_existing = tk.BooleanVar(value=True)
        ttk.Checkbutton(p, text="Also change traces already drawn", variable=apply_existing).pack(anchor="w")

        def change(w: float) -> None:
            if name not in b.nets:
                return
            cls = "%g mm" % round(w, 2)
            b.settings.classes[cls] = w
            b.nets[name].cls = cls
            if apply_existing.get():
                b.set_net_trace_width(name, w)
            b.touch()
            self.mark_dirty()
            self.request_redraw()

        self._building_panel = True
        self._width_slider(p, b.net_width(name), change, self.push_undo)
        self._building_panel = False
        jok = tk.BooleanVar(value=n.jumpers_ok)
        ttk.Checkbutton(p, text="Auto-route may use jumpers on this net", variable=jok,
                        command=lambda: self._net_jumpers(name, jok.get())).pack(anchor="w", pady=(6, 0))
        if b.settings.island_mode:
            from .islands import ground_net
            if ground_net(b) == name:
                ttk.Label(p, text="This net is the ground fill: its pins are joined by the fill, "
                                  "so Auto-route leaves it alone. A yellow line means a pin sits on a piece of "
                                  "fill that is cut off; join it with a trace or a jumper.",
                          wraplength=230, justify="left").pack(anchor="w", pady=(6, 0))
            else:
                ttk.Button(p, text="Use this net as the ground fill", style="Small.TButton",
                           command=lambda: self.set_islands(True, name, b.settings.island_gap,
                                                            b.settings.island_grow, False)).pack(anchor="w", pady=(6, 0))
        links = b.rigid_links(name)
        if links:
            ttk.Label(p, text="Rigid wires (routed first, direct):", font=FONT_B).pack(anchor="w", pady=(8, 0))
            for la, lb in links:
                row = ttk.Frame(p)
                row.pack(anchor="w", fill="x")
                tk.Label(row, text="  %s - %s" % (la, lb), fg=COL["rigid"], bg=UI["panel"], font=FONT_B).pack(side="left")
                ttk.Button(row, text="make normal", style="Small.TButton",
                           command=lambda la=la, lb=lb: self._toggle_rigid(la, lb, False)).pack(side="left", padx=6)
        else:
            ttk.Label(p, text="Tip: Shift + Wire between two pins makes a rigid wire: the router joins them "
                              "directly and the rest of the net branches off it (good for power).",
                      style="Muted.TLabel", wraplength=270, justify="left").pack(anchor="w", pady=(8, 0))
        ttk.Button(p, text="Route just this net", command=lambda: self.auto_route(only=name)).pack(anchor="w", pady=6)
        ttk.Button(p, text="Remove this net's routes", command=lambda: self._unroute(name)).pack(anchor="w")

    def _rename_net(self, old: str, new: str) -> None:
        new = new.strip()
        if new and new != old and new not in self.board.nets:
            self.push_undo()
            self.board.rename_net(old, new)
            self.sel = {"net": new}
            self.show_props()
            self.request_redraw()

    def _net_class(self, name: str, cls: str) -> None:
        self.push_undo()
        self.board.set_net_class(name, cls)
        self.show_props()

    def _unroute(self, name: str) -> None:
        self.push_undo()
        b = self.board
        b.traces = [t for t in b.traces if t.net != name]
        b.jumpers = [j for j in b.jumpers if j.net != name]
        b.touch()
        self.request_redraw()

    # ------------------------------------------------------------------- drawing
    def request_redraw(self) -> None:
        if not self._redraw_pending and not self._closing:
            self._redraw_pending = True
            self._redraw_id = self.root.after_idle(self.redraw)

    def shutdown(self) -> None:
        """Cancel pending callbacks so the window can be destroyed cleanly."""
        self._closing = True
        for name in ("_redraw_id", "_qd", "_autosave_id", "_overlay_id"):
            i = getattr(self, name, None)
            if i:
                try:
                    self.root.after_cancel(i)
                except Exception:
                    pass
        if self.job:
            self.job.cancel = True
            self.job = None

    def _poly_pts(self, pts) -> List[float]:
        out: List[float] = []
        for x, y in pts:
            sx, sy = self.w2s(x, y)
            out += [sx, sy]
        return out

    def draw_shape(self, s, fill: str, extra: float = 0.0) -> None:
        c = self.canvas
        if s.kind == "cap":
            a = self.w2s(s.x1, s.y1)
            bb = self.w2s(s.x2, s.y2)
            w = max(1.0, (2 * s.r + extra) * self.scale)
            if abs(a[0] - bb[0]) < 0.01 and abs(a[1] - bb[1]) < 0.01:
                r = w / 2
                c.create_oval(a[0] - r, a[1] - r, a[0] + r, a[1] + r, fill=fill, outline=fill)
            else:
                c.create_line(a[0], a[1], bb[0], bb[1], width=w, fill=fill, capstyle="round")
        else:
            c.create_polygon(self._poly_pts(s.pts), fill=fill, outline=fill)

    def redraw(self) -> None:
        rid = getattr(self, "_redraw_id", None)
        if rid:
            # a direct redraw makes any scheduled one pointless; cancel it so none is left behind
            try:
                self.root.after_cancel(rid)
            except Exception:
                pass
            self._redraw_id = None
        self._redraw_pending = False
        c = self.canvas
        c.delete("all")
        b = self.board
        sc = self.scale
        x0, y0 = self.w2s(0, b.height)
        x1, y1 = self.w2s(b.width, 0)
        xa, xb = min(x0, x1), max(x0, x1)
        c.create_rectangle(xa + 5, y0 + 5, xb + 5, y1 + 5, fill="#0f2114", outline="")      # soft shadow
        c.create_rectangle(xa, y0, xb, y1, fill=COL["board"], outline="#9bd0a6", width=2)
        if self.show_grid.get() and sc >= 3.0:
            # one small square per grid point, and only the points that are on screen
            step = 2.54 if sc < 20 else 1.27
            cw, ch = c.winfo_width(), c.winfo_height()
            col = COL["grid"]
            nx = int(b.width / step + 1e-6)
            ny = int(b.height / step + 1e-6)
            ys = [self.oy + (b.height - j * step) * sc for j in range(ny + 1)]
            ys = [y for y in ys if -2 <= y <= ch + 2]
            for i in range(nx + 1):
                gx = i * step
                sx = self.ox + ((b.width - gx) if self.mirror else gx) * sc
                if sx < -2 or sx > cw + 2:
                    continue
                for sy in ys:
                    c.create_rectangle(sx - 1, sy - 1, sx + 1, sy + 1, fill=col, outline="")
        cu = b.copper()
        ip = island_plan(b)
        if ip is not None:
            # ground fill: the fill, the gaps cut round every other net, then the fattened copper
            dimf = not self.mirror
            fcol = COL["fill_dim"] if dimf else COL["fill"]
            self.draw_shape(ip.rect_poly(), fcol)
            for s in ip.cut:
                self.draw_shape(s, COL["board"])
            for s in ip.fat:
                self.draw_shape(s, COL["copper_dim"] if dimf else COL["copper"])
        sel = self.sel
        # selection halo under the copper
        selnet = sel.get("net")
        for s in cu:
            tag = s.tag or ()
            hi = False
            if tag and tag[0] == "trace" and sel.get("trace") == tag[1]:
                hi = True
            if tag and tag[0] == "jpad" and sel.get("jumper") == tag[1]:
                hi = True
            if tag and tag[0] == "isl" and sel.get("island") == tag[1]:
                hi = True
            if tag and tag[0] == "pad" and sel.get("part") == tag[1] and (sel.get("pin") in (None, tag[2])):
                hi = True
            if selnet and s.net == selnet:
                hi = True
            if hi:
                self.draw_shape(s, COL["sel"], 0.5)
        dim = not self.mirror      # in the component view the copper is the "far" layer
        # pin labels go UNDER the copper, so they can never hide a trace (between DIP rows, say)
        if sc >= 5:
            for ref in b.parts:
                labs = b.pin_labels_of(ref)
                if labs:
                    self._draw_pin_labels(ref, labs)
        first = c.create_line(0, 0, 0, 0, tags=("cu",))      # marks where the copper starts in the stack
        for s in cu:
            # every piece of copper in one colour, so joints look like the single piece of copper
            # they are once etched; rigid traces get a thin orange line down the middle instead
            self.draw_shape(s, COL["copper_dim"] if dim else COL["copper"])
        for t in b.traces:
            if t.rigid:
                for i in range(len(t.points) - 1):
                    A, B = self.w2s(*t.points[i]), self.w2s(*t.points[i + 1])
                    c.create_line(A[0], A[1], B[0], B[1], fill=COL["rigid"], width=2, dash=(6, 3))
        self._cu_first = first
        si_ = sel.get("island")
        if si_ is not None and si_ < len(b.islands):
            isl = b.islands[si_]
            a = self.w2s(isl.x - isl.w / 2, isl.y - isl.h / 2)
            e_ = self.w2s(isl.x + isl.w / 2, isl.y + isl.h / 2)
            c.create_rectangle(a[0], a[1], e_[0], e_[1], outline=COL["sel"], dash=(4, 3))
            for hx, hy in ((a[0], a[1]), (a[0], e_[1]), (e_[0], a[1]), (e_[0], e_[1])):
                c.create_rectangle(hx - 5, hy - 5, hx + 5, hy + 5, fill="#ffffff", outline=COL["sel"], width=2)
        if "trace" in sel and sel["trace"] < len(b.traces):
            t = b.traces[sel["trace"]]
            si = min(sel.get("seg", 0), len(t.widths) - 1)
            p1, p2 = self.w2s(*t.points[si]), self.w2s(*t.points[si + 1])
            c.create_line(p1[0], p1[1], p2[0], p2[1], width=max(2, t.widths[si] * sc * 0.45), fill="#fff3b0", capstyle="round")
            for pt in t.points:
                q = self.w2s(*pt)
                c.create_rectangle(q[0] - 2.5, q[1] - 2.5, q[0] + 2.5, q[1] + 2.5, outline=COL["sel"], fill="")
        for x, y, d in b.drills():
            sx, sy = self.w2s(x, y)
            r = max(1.0, d / 2 * sc)
            c.create_oval(sx - r, sy - r, sx + r, sy + r, fill=COL["hole"], outline=COL["hole"])
        # jumpers
        for j in b.jumpers:
            a, e = self.w2s(*j.a), self.w2s(*j.b)
            c.create_line(a[0], a[1], e[0], e[1], fill=COL["jump"], width=max(1.5, 0.5 * sc), dash=(6, 4))
        # part outlines
        ocol = COL["outline_dim"] if self.mirror else COL["outline"]
        for ref in b.parts:
            for x1_, y1_, x2_, y2_ in render.part_segments(b, ref):
                a, e = self.w2s(x1_, y1_), self.w2s(x2_, y2_)
                c.create_line(a[0], a[1], e[0], e[1], fill=COL["sel"] if sel.get("part") == ref else ocol, width=1.5 if sel.get("part") == ref else 1)
            if sc >= 4:
                cx0, cy0, cx1, cy1 = b.court_rect(ref)
                pl = b.parts[ref]
                label = ref if not pl.value else "%s %s" % (ref, pl.value)
                fnt = ("TkDefaultFont", max(7, min(13, int(sc * 1.2))))
                if b.pin_labels_of(ref) or min(cx1 - cx0, cy1 - cy0) < 4.0:
                    # pin labels need the space round the pads, and a small body has no room for
                    # its name: name the part just above its body
                    tx, ty = self.w2s((cx0 + cx1) / 2, cy1)
                    c.create_text(tx, ty - 2, text=label, fill=COL["text"], font=fnt, anchor="s")
                else:
                    tx, ty = self.w2s((cx0 + cx1) / 2, (cy0 + cy1) / 2)
                    c.create_text(tx, ty, text=label, fill=COL["text"], font=fnt)
            if b.parts[ref].locked:
                a = self.w2s(b.parts[ref].x, b.parts[ref].y)
                c.create_text(a[0], a[1] - 10, text="L", fill="#ff9", font=("TkDefaultFont", 8, "bold"))
        # pin 1 marker is part of the outlines; rubber bands
        if self.show_air.get():
            for net, p1, p2, pa, pb in b.airwires():
                a, e = self.w2s(*p1), self.w2s(*p2)
                rig = [pa, pb] in b.nets[net].links or [pb, pa] in b.nets[net].links if net in b.nets else False
                w = 3 if selnet == net else 2
                if rig:
                    w += 1
                c.create_line(a[0], a[1], e[0], e[1], fill=COL["air_shadow"], width=w + 3, capstyle="round")
                c.create_line(a[0], a[1], e[0], e[1], fill=COL["rigid"] if rig else COL["air"], width=w,
                              capstyle="round")
        for mx, my in self.marks:
            sx, sy = self.w2s(mx, my)
            c.create_oval(sx - 10, sy - 10, sx + 10, sy + 10, outline=COL["drc"], width=2)
        theme.round_corners(c, 12, UI["panel"])
        self.draw_dynamic()
        self.unrouted_label()

    def request_overlay(self) -> None:
        """Redraw only the things that follow the mouse (cheap), unless a full redraw is due anyway."""
        if self._redraw_pending or self._closing or getattr(self, "_overlay_pending", False):
            return
        self._overlay_pending = True
        self._overlay_id = self.root.after_idle(self.draw_dynamic)

    def draw_dynamic(self) -> None:
        """The moving layer: rubber band, ghost part, trace preview and the hovered net.

        Only these canvas items are deleted and redrawn while the mouse moves, so drawing a
        wire costs a few items instead of redrawing the whole board.
        """
        self._overlay_pending = False
        c = self.canvas
        c.delete("dyn")
        last = c.create_line(0, 0, 0, 0)
        if self.hover_net and not self.drag:
            for s in self.board.copper():
                if s.net == self.hover_net:
                    self.draw_shape(s, COL["hover"], 0.35)
        hov_end = c.create_line(0, 0, 0, 0)
        self._draw_overlay()
        if self.hover_net and not self.drag:
            c.create_text(12, 12, anchor="nw", text="net %s" % self.hover_net, fill="#e9f7ec",
                          font=("TkDefaultFont", 9, "bold"))
        end = c.create_line(0, 0, 0, 0)
        for i in range(last, end + 1):
            c.addtag_withtag("dyn", i)
        if hov_end > last + 1 and c.find_withtag("cu"):
            for i in range(last + 1, hov_end):
                c.addtag_withtag("dynhov", i)
            c.tag_lower("dynhov", "cu")
            c.dtag("dynhov", "dynhov")
        c.tag_raise("corner_mask")

    def _draw_pin_labels(self, ref: str, labs: Dict[str, str]) -> None:
        """Pin functions (B C E, K A, IN GND OUT...) beside each pad.

        A single row of pins (TO-92, TO-220, terminals) gets its labels on the side away from
        the body; two columns of pins (DIP) get them on the inside, between the columns.
        """
        b = self.board
        c = self.canvas
        d = b.get_def(b.parts[ref].part_id)
        pads = [(pd, b.pin_pos("%s.%s" % (ref, pd.name))) for pd in d.pads]
        if not pads:
            return
        x0, y0, x1, y1 = b.court_rect(ref)
        bcx, bcy = (x0 + x1) / 2, (y0 + y1) / 2
        mx = sum(p[0] for _pd, p in pads) / len(pads)
        my = sum(p[1] for _pd, p in pads) / len(pads)
        xs = {round(p[0], 1) for _pd, p in pads}
        ys = {round(p[1], 1) for _pd, p in pads}
        size = max(7, min(12, int(self.scale * 0.9)))
        if len(xs) == 2 or (len(ys) == 2 and len(xs) != 1):
            # labels sit between two rows of pads: shrink them until the longest one fits half the gap
            gap = (max(xs) - min(xs)) if len(xs) == 2 else (max(ys) - min(ys))
            room_px = (gap / 2 - max(max(pd.w, pd.h) for pd, _p in pads) / 2 - 0.4) * self.scale
            longest = max((len(v) for v in labs.values()), default=1)
            size = max(6, min(size, int(room_px / (0.9 * max(longest, 1)))))
            if room_px < 3 * 0.9 * 6:
                return                                     # too zoomed out to read: zoom in to see them
        for pd, (px, py) in pads:
            t = labs.get(pd.name)
            if not t:
                continue
            if len(ys) == 1 and len(pads) > 1:             # horizontal row: away from the body
                vx, vy = 0.0, (-1.0 if bcy >= py - 1e-6 else 1.0)
            elif len(xs) == 1 and len(pads) > 1:           # vertical row
                vx, vy = (-1.0 if bcx >= px - 1e-6 else 1.0), 0.0
            elif len(xs) == 2:                             # two columns: towards the middle
                vx, vy = (1.0 if mx > px else -1.0), 0.0
            elif len(ys) == 2:                             # two rows
                vx, vy = 0.0, (1.0 if my > py else -1.0)
            else:                                          # anything else: away from the middle
                vx, vy = px - mx, py - my
                L = math.hypot(vx, vy) or 1.0
                vx, vy = vx / L, vy / L
            off = max(pd.w, pd.h) / 2 + 0.5
            sp = self.w2s(px, py)
            sl = self.w2s(px + vx * off, py + vy * off)
            dx, dy = sl[0] - sp[0], sl[1] - sp[1]
            if abs(dx) >= abs(dy):
                anchor = "w" if dx > 0 else "e"
            else:
                anchor = "n" if dy > 0 else "s"
            c.create_text(sl[0] + 1, sl[1] + 1, text=t, fill="#10230f", font=("TkDefaultFont", size, "bold"), anchor=anchor)
            c.create_text(sl[0], sl[1], text=t, fill=COL["pinlabel"], font=("TkDefaultFont", size, "bold"), anchor=anchor)

    def unrouted_label(self) -> None:
        n = self.board.unrouted_count() if self.board.nets else 0
        self.stamp_var.set("SoloTrace v%s (Built %s) WIP" % (__version__, __build_date__))
        if not self.board.nets:
            self.route_var.set("no nets yet")
            self.route_badge.configure(style="Todo.TLabel")
        elif n:
            self.route_var.set("%d to route" % n)
            self.route_badge.configure(style="Todo.TLabel")
        else:
            self.route_var.set("all routed")
            self.route_badge.configure(style="Ok.TLabel")

    def _draw_overlay(self) -> None:
        c = self.canvas
        b = self.board
        wx, wy = self.cursor
        if self.tool == "island":
            d = self.drag or {}
            if "draw_island" in d:
                (x0, y0), (x1, y1) = d["draw_island"], d["cur"]
                a, e = self.w2s(x0, y0), self.w2s(x1, y1)
                c.create_rectangle(a[0], a[1], e[0], e[1], outline=COL["ghost"], width=2, dash=(6, 3))
                c.create_text(e[0] + 10, e[1] + 10, anchor="nw", fill=COL["ghost"], font=("TkDefaultFont", 9, "bold"),
                              text="%.4g x %.4g mm" % (max(ISLAND_MIN, abs(x1 - x0)), max(ISLAND_MIN, abs(y1 - y0))))
            elif not d and self.island_at(wx, wy) is None:
                x, y = self.snap((wx, wy), ISLAND_GRID)
                n = self.island_new
                self.draw_shape(Island(x, y, n["w"], n["h"], n["shape"]).copper(), COL["ghost"])
        elif self.tool == "place" and self.armed:
            d = self.lib[self.armed]
            gb = self.ghost_board
            gb.width, gb.height = b.width, b.height
            gb.defs = {self.armed: d}
            x, y = self.snap((wx, wy))
            gb.parts = {"G": Placed("G", self.armed, x, y, self.arm_rot, False, "", "tht")}
            gb.touch()
            for s in gb.copper():
                self.draw_shape(s, COL["ghost"])
            for ox_, oy_, dd in gb.drills():
                sx, sy = self.w2s(ox_, oy_)
                r = max(1.0, dd / 2 * self.scale)
                c.create_oval(sx - r, sy - r, sx + r, sy + r, fill=COL["hole"], outline=COL["hole"])
            for x1_, y1_, x2_, y2_ in render.part_segments(gb, "G"):
                a, e = self.w2s(x1_, y1_), self.w2s(x2_, y2_)
                c.create_line(a[0], a[1], e[0], e[1], fill=COL["ghost"])
        elif self.tool == "wire" and self.pending_pin:
            a = self.w2s(*b.pin_pos(self.pending_pin))
            e = self.w2s(wx, wy)
            rig = getattr(self, "_shift", False) or self.rigid_next
            c.create_line(a[0], a[1], e[0], e[1], fill=COL["air_shadow"], width=6, capstyle="round")
            c.create_line(a[0], a[1], e[0], e[1], fill=COL["rigid"] if rig else COL["air"], width=3,
                          dash=(8, 4), capstyle="round")
            c.create_text(e[0] + 12, e[1] - 12, anchor="w", fill=COL["rigid"] if rig else COL["air"],
                          font=("TkDefaultFont", 9, "bold"), text="rigid" if rig else "Shift = rigid")
        elif self.tool == "trace" and self.trace_pts:
            pts = list(self.trace_pts)
            nxt = self.snap_dir(pts[-1], (wx, wy))
            w = b.net_width(self.trace_net) if self.trace_net else 0.8
            seq = pts + [nxt]
            for i in range(len(seq) - 1):
                a, e = self.w2s(*seq[i]), self.w2s(*seq[i + 1])
                c.create_line(a[0], a[1], e[0], e[1], fill="#fff3b0", width=max(2, w * self.scale), capstyle="round")
        elif getattr(self, "menu_preview", None) or (self.tool == "cut" and self.cut_start is None
                                                     and getattr(self, "cut_preview", None)):
            pts, w = self.menu_preview or self.cut_preview
            for i in range(len(pts) - 1):
                A, B = self.w2s(*pts[i]), self.w2s(*pts[i + 1])
                c.create_line(A[0], A[1], B[0], B[1], fill=COL["drc"], width=max(3, w * self.scale),
                              capstyle="round")
                c.create_line(A[0], A[1], B[0], B[1], fill="#ffd0d0", width=1, dash=(4, 3))
        elif self.tool == "cut" and self.cut_start and self.cut_start[0] < len(b.traces):
            ti, q0 = self.cut_start
            t = b.traces[ti]
            _s1, q1, d1 = project_on_trace(t, q0)
            _s2, q2, d2 = project_on_trace(t, (wx, wy))
            if d2 < d1:
                d1, d2 = d2, d1
            # the stretch that will go, in red
            pts = []
            run = 0.0
            for i in range(len(t.points) - 1):
                a_, b_ = t.points[i], t.points[i + 1]
                L = dist(a_, b_)
                lo, hi = max(d1, run), min(d2, run + L)
                if hi > lo and L > 1e-9:
                    pa = (a_[0] + (b_[0] - a_[0]) * (lo - run) / L, a_[1] + (b_[1] - a_[1]) * (lo - run) / L)
                    pb = (a_[0] + (b_[0] - a_[0]) * (hi - run) / L, a_[1] + (b_[1] - a_[1]) * (hi - run) / L)
                    pts.append((pa, pb, t.widths[i]))
                run += L
            for pa, pb, w in pts:
                A, B = self.w2s(*pa), self.w2s(*pb)
                c.create_line(A[0], A[1], B[0], B[1], fill=COL["drc"], width=max(3, w * self.scale), capstyle="round")
            sx, sy = self.w2s(*q0)
            c.create_line(sx - 6, sy - 6, sx + 6, sy + 6, fill=COL["drc"], width=3)
            c.create_line(sx - 6, sy + 6, sx + 6, sy - 6, fill=COL["drc"], width=3)
        elif self.tool == "jumper" and self.jump_start:
            a = self.w2s(*self.jump_start)
            e = self.w2s(wx, wy)
            c.create_line(a[0], a[1], e[0], e[1], fill=COL["jump"], dash=(6, 4))

    # -------------------------------------------------------------- background jobs
    def run_job(self, label: str, func, on_done) -> None:
        if self.job and not self.job.done:
            messagebox.showinfo(APP_NAME, "Another job is still running.")
            return
        j = Job(label, func, on_done)
        self.job = j
        self.progress.pack(side="left", padx=6)
        self.cancel_btn.pack(side="left")
        j.start()
        self.root.after(120, self.poll_job)

    def poll_job(self) -> None:
        j = self.job
        if j is None:
            return
        self.status("%s: %s" % (j.label, j.msg))
        self.progress["value"] = j.frac * 100
        if not j.done:
            self.root.after(120, self.poll_job)
            return
        self.progress.pack_forget()
        self.cancel_btn.pack_forget()
        self.job = None
        if j.error:
            messagebox.showerror(APP_NAME, "%s failed:\n%s" % (j.label, j.error))
            self.status("%s failed." % j.label)
        else:
            j.on_done(j.result)

    def cancel_job(self) -> None:
        if self.job:
            self.job.cancel = True
            self.status("Cancelling...")

    def auto_place(self) -> None:
        if not self.board.parts or not self.board.nets:
            messagebox.showinfo(APP_NAME, "Place some parts and connect pins with the Wire tool first.")
            return
        work = self.board.clone()

        def func(job: Job):
            pl = Placer(work, progress=lambda m, f: (setattr(job, "msg", m), setattr(job, "frac", f)),
                        cancel=lambda: job.cancel)
            return pl.run(time_limit=25.0)

        def done(res) -> None:
            self.push_undo()
            for ref, p in work.parts.items():
                if ref in self.board.parts and not self.board.parts[ref].locked:
                    self.board.parts[ref].x, self.board.parts[ref].y, self.board.parts[ref].rot = p.x, p.y, p.rot
            self.board.clear_auto_routes()
            self.board.touch()
            self.status("Placement done: " + res.summary() + ". Automatic routes were removed.")
            self.request_redraw()

        self.run_job("Placing", func, done)

    def auto_route(self, only=None) -> None:
        if not self.board.nets:
            messagebox.showinfo(APP_NAME, "Connect some pins with the Wire tool first.")
            return
        work = self.board.clone()

        def func(job: Job):
            r = AutoRouter(work, RouteOptions(time_limit=180.0),
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
            self.show_props()
            self.request_redraw()
            if res.failed_nets:
                messagebox.showwarning(APP_NAME, "These nets could not be routed:\n%s\n\nTry moving parts apart, "
                                       "Auto-place, a bigger board, or draw them by hand with the Trace tool." %
                                       ", ".join(res.failed_nets))

        self.run_job("Routing", func, done)

    def clear_auto(self) -> None:
        self.push_undo()
        self.board.clear_auto_routes()
        self.request_redraw()

    def clear_all(self) -> None:
        if messagebox.askyesno(APP_NAME, "Remove every trace and jumper, including ones you drew by hand?"):
            self.push_undo()
            self.board.clear_all_routes()
            self.request_redraw()

    # --------------------------------------------------------------------- DRC
    def show_drc(self) -> None:
        issues = run_drc(self.board)
        top = tk.Toplevel(self.root)
        top.title("Design rule check")
        top.geometry("620x360")
        ttk.Label(top, text=summarize(issues)).pack(anchor="w", padx=6, pady=4)
        tv = ttk.Treeview(top, columns=("sev", "kind", "msg"), show="headings", height=12)
        for k, w, t in (("sev", 60, "Level"), ("kind", 80, "Kind"), ("msg", 440, "Problem")):
            tv.heading(k, text=t)
            tv.column(k, width=w)
        for i, it in enumerate(issues):
            tv.insert("", "end", iid=str(i), values=(it.severity, it.kind, it.message))
        tv.pack(fill="both", expand=True, padx=6, pady=4)
        self.marks = [(i.x, i.y) for i in issues]
        self.request_redraw()

        def goto(_e=None) -> None:
            s = tv.selection()
            if not s:
                return
            it = issues[int(s[0])]
            self.marks = [(it.x, it.y)]
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            self.scale = max(self.scale, 14.0)
            mx = self.board.width - it.x if self.mirror else it.x
            self.ox = cw / 2 - mx * self.scale
            self.oy = ch / 2 - (self.board.height - it.y) * self.scale
            self.request_redraw()

        tv.bind("<<TreeviewSelect>>", goto)
        top.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "marks", []), self.request_redraw(), top.destroy()))

    # ------------------------------------------------------------------ file ops
    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        a = messagebox.askyesnocancel(APP_NAME, "Save changes to this board first?")
        if a is None:
            return False
        if a:
            return self.save()
        return True

    def load_board(self, board: Board, path: Optional[str] = None) -> None:
        self.board = board
        self.path = path
        self.dirty = False
        self.undo.clear()
        self.redo.clear()
        self.sel = {}
        self.marks = []
        self.lib.update({pid: d for pid, d in board.defs.items() if pid not in self.lib})
        self.fill_library()
        self.hover_net = None
        self.cut_start = None
        self.jumpers_var.set(board.settings.allow_jumpers)
        self.keepout_var.set(board.settings.keep_out_under_parts)
        self.island_var.set(board.settings.island_mode)
        self.set_title()
        self.show_props()
        self.fit()

    def new_board(self) -> None:
        if not self.confirm_discard():
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("New board")
        dlg.transient(self.root)
        wv, hv, nv = tk.StringVar(value="100"), tk.StringVar(value="80"), tk.StringVar(value="My board")
        for i, (t, v) in enumerate((("Name", nv), ("Width mm", wv), ("Height mm", hv))):
            ttk.Label(dlg, text=t).grid(row=i, column=0, padx=6, pady=3, sticky="w")
            ttk.Entry(dlg, textvariable=v, width=18).grid(row=i, column=1, padx=6, pady=3)

        def ok() -> None:
            try:
                w, h = float(wv.get()), float(hv.get())
                if not (10 <= w <= 400 and 10 <= h <= 400):
                    raise ValueError
            except ValueError:
                messagebox.showerror(APP_NAME, "Width and height must be between 10 and 400 mm.", parent=dlg)
                return
            self.load_board(Board(w, h, nv.get() or "Untitled"))
            dlg.destroy()

        ttk.Button(dlg, text="Create", command=ok).grid(row=3, column=0, columnspan=2, pady=8)

    def open_file(self) -> None:
        if not self.confirm_discard():
            return
        p = filedialog.askopenfilename(filetypes=[("SoloTrace board", "*.solotrace *.json"), ("All files", "*")])
        if not p:
            return
        try:
            self.load_board(Board.load(p), p)
            self._remember_recent(p)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not open that file:\n%s" % exc)

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        try:
            self.board.save(self.path)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not save:\n%s" % exc)
            return False
        self.dirty = False
        self.set_title()
        self.status("Saved %s" % self.path)
        self._remember_recent(self.path)
        return True

    def save_as(self) -> bool:
        p = filedialog.asksaveasfilename(defaultextension=".solotrace", initialfile=self.board.name.replace(" ", "_"),
                                         filetypes=[("SoloTrace board", "*.solotrace")])
        if not p:
            return False
        self.path = p
        return self.save()

    def load_demo(self, name: str) -> None:
        if not self.confirm_discard():
            return
        self.load_board(demos.DEMOS[name]())
        self.status("Loaded example '%s'. Try Auto-place then Auto-route." % name)

    def import_netlist(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("Text", "*.txt *.net"), ("All files", "*")])
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as fh:
                text = fh.read()
            nb = Board(self.board.width, self.board.height, os.path.basename(p))
            for pid, d in self.lib.items():
                nb.defs[pid] = d
            nb.import_netlist(text)
            nb.defs = {k: v for k, v in nb.defs.items() if any(pl.part_id == k for pl in nb.parts.values())}
            if self.confirm_discard():
                self.load_board(nb)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not read the netlist:\n%s" % exc)

    def export_netlist(self) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=self.board.name.replace(" ", "_") + "_netlist.txt")
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(self.board.export_netlist())
            self.status("Netlist saved to %s" % p)

    def _export_warn(self) -> bool:
        issues = [i for i in run_drc(self.board, check_unrouted=False) if i.severity == "error"]
        n_air = self.board.unrouted_count()
        if issues or n_air:
            return messagebox.askyesno(APP_NAME, "The board has %d design-rule error(s) and %d unrouted connection(s).\n\n"
                                       "Export anyway?" % (len(issues), n_air))
        return True

    def export_gerber(self) -> None:
        if not self._export_warn():
            return
        p = filedialog.asksaveasfilename(defaultextension=".zip", initialfile=self.board.name.replace(" ", "_") + "_gerber.zip")
        if p:
            names = gerber.write_zip(self.board, p)
            self.status("Wrote %s (%s)" % (p, ", ".join(names)))

    def export_print(self, kind: str, mirror: bool) -> None:
        ext = "." + kind
        p = filedialog.asksaveasfilename(defaultextension=ext, initialfile="%s_%s%s" % (
            self.board.name.replace(" ", "_"), "mirrored" if mirror else "design", ext))
        if not p:
            return
        if kind == "pdf":
            with open(p, "wb") as fh:
                fh.write(render.to_pdf(self.board, mirror=mirror))
        else:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(render.to_svg(self.board, mirror=mirror))
        self.status("Wrote %s. Print at 100%% scale (no 'fit to page')." % p)

    def export_bom(self) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=self.board.name.replace(" ", "_") + "_bom.csv")
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(render.to_bom_csv(self.board))
            self.status("Wrote %s" % p)

    # ----------------------------------------------------------------- dialogs
    def board_settings(self) -> None:
        from .dialogs import SettingsDialog
        SettingsDialog(self)

    def footprint_wizard(self, preset=None) -> None:
        from .dialogs import FootprintWizard
        FootprintWizard(self, preset)

    def laser_dialog(self) -> None:
        from .dialogs import LaserDialog
        self.laser_dlg = LaserDialog(self)

    def import_kicad(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("KiCad footprint", "*.kicad_mod"), ("All files", "*")])
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as fh:
                part = library.import_kicad_mod(fh.read())
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not import that footprint:\n%s\n\nOnly through-hole pads are imported." % exc)
            return
        self.footprint_wizard(part)

    def show_parts_folder(self) -> None:
        d = library.user_part_dir()
        os.makedirs(d, exist_ok=True)
        messagebox.showinfo(APP_NAME, "Your own parts are saved as small .json files in:\n\n%s\n\nCopy them to share." % d)

    def show_help(self) -> None:
        top = tk.Toplevel(self.root)
        top.title("Quick guide")
        t = tk.Text(top, width=80, height=26, wrap="word")
        t.insert("1.0", HELP_TEXT)
        t.config(state="disabled")
        t.pack(fill="both", expand=True)

    def show_about(self) -> None:
        messagebox.showinfo("About " + APP_NAME, "%s\n\n%s\n\nCopyright Matthew Armstrong (https://github.com/The-Dorkknight)\n"
                            "Licensed under the PolyForm Noncommercial License 1.0.0 (source-available, non-commercial use only).\n"
                            "No warranty. Not tested on a real Elegoo Phecda yet.\n\nBuilt %s" % (app_title(), WIP_TEXT, __build_date__))

    def quit(self) -> None:
        if self.confirm_discard():
            self.shutdown()
            try:
                if os.path.exists(AUTOSAVE_FILE):
                    os.remove(AUTOSAVE_FILE)       # nothing unsaved is left, so the backup is not needed
            except OSError:
                pass
            self.root.destroy()


def disclaimer(root: tk.Tk) -> bool:
    """First-start safety and work-in-progress notice. Returns False if the user declines."""
    cfg = load_config()
    if cfg.get("accepted") == __version__.split("-")[0].rsplit(".", 1)[0]:
        return True
    dlg = tk.Toplevel(root)
    dlg.title("Please read first")
    dlg.transient(root)
    dlg.grab_set()
    ok = {"v": False}
    txt = ("%s\n\n%s\n\n"
           "This is early, untested software. Check every 1:1 print against your real parts before etching.\n\n"
           "LASER SAFETY: a diode laser can blind you and start fires. Wear laser safety glasses rated for "
           "your laser, ventilate (burning paint makes fumes), never leave a running laser unattended, and "
           "keep a fire extinguisher or water nearby. The laser only removes paint; the board is then "
           "etched in chemicals that need their own care.\n\n"
           "Licence: PolyForm Noncommercial 1.0.0 (source-available). No warranty, no liability."
           % (app_title(), WIP_TEXT))
    tk.Label(dlg, text=txt, justify="left", wraplength=480, padx=14, pady=10).pack()
    chk = tk.BooleanVar(value=False)
    agree = ttk.Button(dlg, text="I agree", state="disabled")
    ttk.Checkbutton(dlg, text="I have read this and accept the risks", variable=chk,
                    command=lambda: agree.config(state="normal" if chk.get() else "disabled")).pack()

    def accept() -> None:
        ok["v"] = True
        cfg["accepted"] = __version__.split("-")[0].rsplit(".", 1)[0]
        save_config(cfg)
        dlg.destroy()

    agree.config(command=accept)
    agree.pack(side="left", padx=40, pady=10)
    ttk.Button(dlg, text="Quit", command=dlg.destroy).pack(side="right", padx=40, pady=10)
    root.wait_window(dlg)
    return ok["v"]


def main(argv: Optional[List[str]] = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    root = tk.Tk()
    root.geometry("1280x800")
    root.withdraw()
    if "--skip-disclaimer" not in argv:
        root.deiconify()
        if not disclaimer(root):
            root.destroy()
            return 0
    root.deiconify()
    board = None
    path = None
    args = [a for a in argv if not a.startswith("--")]
    if args:
        try:
            path = args[0]
            board = Board.load(path)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not open %s:\n%s" % (path, exc))
            board, path = None, None
    app = App(root, board, path)
    if board is None and "--demo" in argv:
        app.load_demo("555 LED flasher")
    root.mainloop()
    return 0
