# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Dialogs: board settings, footprint wizard (custom parts), laser export."""
from __future__ import annotations

import bisect
import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from . import library
from .board import Board
from .laser import (LaserOptions, MODES, PHECDA_AREA, frame_gcode, generate, speed_power_card, trace_ladder_card)
from .parts import PadDef, PartDef


def _num(var: tk.StringVar, lo: float, hi: float, name: str) -> float:
    try:
        v = float(var.get())
    except ValueError:
        raise ValueError("%s must be a number." % name)
    if not (lo <= v <= hi):
        raise ValueError("%s must be between %g and %g." % (name, lo, hi))
    return v


class SettingsDialog:
    def __init__(self, app) -> None:
        self.app = app
        b = app.board
        st = b.settings
        d = self.d = tk.Toplevel(app.root)
        d.title("Board size and rules")
        d.transient(app.root)
        self.vars: Dict[str, tk.StringVar] = {}
        rows = [("name", "Board name", b.name), ("width", "Width (mm)", b.width), ("height", "Height (mm)", b.height),
                ("clearance", "Copper to copper gap (mm)", st.clearance), ("min_trace", "Thinnest trace (mm)", st.min_trace),
                ("edge_clearance", "Copper to board edge (mm)", st.edge_clearance),
                ("chamfer_factor", "Corner cut = this x trace width", st.chamfer_factor),
                ("chamfer_min", "Smallest corner cut (mm)", st.chamfer_min),
                ("jumper_min", "Shortest jumper (mm)", st.jumper_min), ("jumper_max", "Longest jumper (mm)", st.jumper_max),
                ("copper_oz", "Copper weight (oz)", st.copper_oz), ("temp_rise", "Allowed temperature rise (C)", st.temp_rise)]
        for i, (k, label, val) in enumerate(rows):
            ttk.Label(d, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            v = tk.StringVar(value=str(val))
            ttk.Entry(d, textvariable=v, width=14).grid(row=i, column=1, padx=8, pady=2)
            self.vars[k] = v
        r = len(rows)
        ttk.Label(d, text="Net classes (name = width mm)").grid(row=r, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 0))
        self.cls = tk.Text(d, width=34, height=5)
        self.cls.grid(row=r + 1, column=0, columnspan=2, padx=8)
        self.cls.insert("1.0", "\n".join("%s = %g" % kv for kv in st.classes.items()))
        ttk.Label(d, text="Every trace width is limited to 0.4 to 10 mm. A 90 degree trace corner cannot be made.",
                  wraplength=330, justify="left").grid(row=r + 2, column=0, columnspan=2, padx=8, pady=4)
        ttk.Button(d, text="Apply", command=self.apply).grid(row=r + 3, column=0, columnspan=2, pady=8)

    def apply(self) -> None:
        b = self.app.board
        st = b.settings
        try:
            w = _num(self.vars["width"], 10, 400, "Width")
            h = _num(self.vars["height"], 10, 400, "Height")
            vals = {"clearance": _num(self.vars["clearance"], 0.1, 2, "Gap"),
                    "min_trace": _num(self.vars["min_trace"], 0.2, 2, "Thinnest trace"),
                    "edge_clearance": _num(self.vars["edge_clearance"], 0, 5, "Edge distance"),
                    "chamfer_factor": _num(self.vars["chamfer_factor"], 0.5, 4, "Corner factor"),
                    "chamfer_min": _num(self.vars["chamfer_min"], 0.3, 5, "Smallest corner cut"),
                    "jumper_min": _num(self.vars["jumper_min"], 2.54, 30, "Shortest jumper"),
                    "jumper_max": _num(self.vars["jumper_max"], 5.08, 40, "Longest jumper"),
                    "copper_oz": _num(self.vars["copper_oz"], 0.5, 4, "Copper weight"),
                    "temp_rise": _num(self.vars["temp_rise"], 1, 60, "Temperature rise")}
            classes: Dict[str, float] = {}
            for line in self.cls.get("1.0", "end").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    classes[k.strip()] = max(0.4, min(10.0, float(v)))
            if not classes:
                raise ValueError("Add at least one net class.")
        except ValueError as exc:
            messagebox.showerror("SoloTrace", str(exc), parent=self.d)
            return
        self.app.push_undo()
        b.name = self.vars["name"].get() or b.name
        b.width, b.height = w, h
        for k, v in vals.items():
            setattr(st, k, v)
        st.classes = classes
        for n in b.nets.values():
            if n.cls not in classes:
                n.cls = next(iter(classes))
        b.touch()
        self.app.set_title()
        self.app.fit()
        self.d.destroy()


# ---------------------------------------------------------------------------------------
class FootprintWizard:
    """Build your own part: type or click pads, or start from a preset or a KiCad file."""

    def __init__(self, app, preset: Optional[PartDef] = None) -> None:
        self.app = app
        d = self.d = tk.Toplevel(app.root)
        d.title("New footprint")
        d.geometry("860x560")
        d.transient(app.root)
        self.pads: List[PadDef] = []
        left = ttk.Frame(d, padding=6)
        left.pack(side="left", fill="y")
        self.v = {k: tk.StringVar() for k in ("name", "category", "prefix", "note", "pad", "drill", "grid")}
        self.v["category"].set("Custom")
        self.v["prefix"].set("U")
        self.v["pad"].set("1.8")
        self.v["drill"].set("0.9")
        self.v["grid"].set("1.27")
        for i, (k, t) in enumerate((("name", "Part name"), ("category", "Category"), ("prefix", "Ref prefix (R, C, U...)"),
                                    ("note", "Note"), ("pad", "New pad size (mm)"), ("drill", "New pad hole (mm)"),
                                    ("grid", "Click grid (mm)"))):
            ttk.Label(left, text=t).grid(row=i, column=0, sticky="w", pady=1)
            if k == "category":
                ttk.Combobox(left, textvariable=self.v[k], values=library.CATEGORIES, width=16).grid(row=i, column=1, pady=1)
            else:
                ttk.Entry(left, textvariable=self.v[k], width=18).grid(row=i, column=1, pady=1)
        pf = ttk.LabelFrame(left, text="Start from a preset", padding=4)
        pf.grid(row=8, column=0, columnspan=2, sticky="we", pady=6)
        self.pre = {k: tk.StringVar(value=val) for k, val in (("n", "8"), ("row", "7.62"), ("cols", "4"), ("rows", "1"), ("pitch", "2.54"))}
        r1 = ttk.Frame(pf)
        r1.pack(anchor="w")
        ttk.Label(r1, text="DIP pins").pack(side="left")
        ttk.Entry(r1, textvariable=self.pre["n"], width=4).pack(side="left")
        ttk.Label(r1, text="row mm").pack(side="left")
        ttk.Entry(r1, textvariable=self.pre["row"], width=6).pack(side="left")
        ttk.Button(r1, text="Make", command=self.preset_dip).pack(side="left", padx=3)
        r2 = ttk.Frame(pf)
        r2.pack(anchor="w", pady=2)
        ttk.Label(r2, text="Header").pack(side="left")
        ttk.Entry(r2, textvariable=self.pre["cols"], width=3).pack(side="left")
        ttk.Label(r2, text="x").pack(side="left")
        ttk.Entry(r2, textvariable=self.pre["rows"], width=3).pack(side="left")
        ttk.Label(r2, text="pitch").pack(side="left")
        ttk.Entry(r2, textvariable=self.pre["pitch"], width=5).pack(side="left")
        ttk.Button(r2, text="Make", command=self.preset_header).pack(side="left", padx=3)
        ttk.Label(left, text="Pads: name x y shape(round|oval|rect) w h drill\n(x, y in mm from pin 1 at 0 0; y up)",
                  justify="left").grid(row=9, column=0, columnspan=2, sticky="w")
        self.txt = tk.Text(left, width=40, height=12, font=("TkFixedFont", 9))
        self.txt.grid(row=10, column=0, columnspan=2)
        bf = ttk.Frame(left)
        bf.grid(row=11, column=0, columnspan=2, pady=6)
        ttk.Button(bf, text="Update preview", command=self.parse).pack(side="left", padx=2)
        ttk.Button(bf, text="Save part", command=self.save).pack(side="left", padx=2)
        right = ttk.Frame(d, padding=6)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Click to add a pad. Right-click a pad to remove it. Pin 1 is at the cross.",
                  wraplength=420).pack(anchor="w")
        self.cv = tk.Canvas(right, bg="#16301c", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Button-1>", self.add_click)
        self.cv.bind("<Button-3>", self.del_click)
        self.cv.bind("<Button-2>", self.del_click)
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.s = 12.0
        self.ox = 60.0
        self.oy = 60.0
        if preset:
            self.v["name"].set(preset.name)
            self.v["category"].set(preset.category)
            self.v["prefix"].set(preset.prefix)
            self.v["note"].set(preset.note)
            self.pads = list(preset.pads)
        else:
            self.pads = [PadDef("1", 0.0, 0.0, "round", 1.8, 1.8, 0.9), PadDef("2", 2.54, 0.0, "round", 1.8, 1.8, 0.9)]
        self.sync_text()
        self.draw()

    def sync_text(self) -> None:
        self.txt.delete("1.0", "end")
        for p in self.pads:
            self.txt.insert("end", "%s %g %g %s %g %g %g\n" % (p.name, p.x, p.y, p.shape, p.w, p.h, p.drill))

    def parse(self) -> bool:
        pads: List[PadDef] = []
        for n, line in enumerate(self.txt.get("1.0", "end").splitlines(), 1):
            if not line.strip():
                continue
            t = line.split()
            try:
                if len(t) < 3:
                    raise ValueError("needs at least: name x y")
                shape = t[3] if len(t) > 3 else "round"
                if shape not in ("round", "oval", "rect"):
                    raise ValueError("shape must be round, oval or rect")
                w = float(t[4]) if len(t) > 4 else 1.8
                h = float(t[5]) if len(t) > 5 else w
                dr = float(t[6]) if len(t) > 6 else 0.9
                if w <= 0 or h <= 0 or dr < 0 or dr >= min(w, h):
                    raise ValueError("pad size must be bigger than the hole")
                pads.append(PadDef(t[0], float(t[1]), float(t[2]), shape, w, h, dr))
            except ValueError as exc:
                messagebox.showerror("SoloTrace", "Line %d: %s" % (n, exc), parent=self.d)
                return False
        names = [p.name for p in pads]
        if len(set(names)) != len(names):
            messagebox.showerror("SoloTrace", "Pad names must be different.", parent=self.d)
            return False
        self.pads = pads
        self.draw()
        return True

    def preset_dip(self) -> None:
        try:
            n = int(self.pre["n"].get())
            row = float(self.pre["row"].get())
            if n < 4 or n % 2 or n > 64:
                raise ValueError
        except ValueError:
            messagebox.showerror("SoloTrace", "DIP pins must be an even number from 4 to 64.", parent=self.d)
            return
        self.pads = list(library.dip(n, row).pads)
        self.v["prefix"].set("U")
        self.v["name"].set("DIP-%d (%.2f mm rows)" % (n, row))
        self.sync_text()
        self.draw()

    def preset_header(self) -> None:
        try:
            c, r, pitch = int(self.pre["cols"].get()), int(self.pre["rows"].get()), float(self.pre["pitch"].get())
            if not (1 <= c <= 40 and 1 <= r <= 4):
                raise ValueError
        except ValueError:
            messagebox.showerror("SoloTrace", "Use 1 to 40 columns and 1 to 4 rows.", parent=self.d)
            return
        self.pads = list(library.header(c, r, pitch).pads)
        self.v["prefix"].set("J")
        self.v["name"].set("Header %dx%d, %.2f mm" % (c, r, pitch))
        self.sync_text()
        self.draw()

    def _fit(self) -> None:
        w = max(100, self.cv.winfo_width())
        h = max(100, self.cv.winfo_height())
        if not self.pads:
            self.s, self.ox, self.oy = 12.0, 60.0, h - 60.0
            return
        xs = [p.x for p in self.pads]
        ys = [p.y for p in self.pads]
        x0, x1 = min(xs) - 3, max(xs) + 3
        y0, y1 = min(ys) - 3, max(ys) + 3
        self.s = max(3.0, min((w - 20) / (x1 - x0), (h - 20) / (y1 - y0), 40.0))
        self.ox = 10 - x0 * self.s
        self.oy = h - 10 + y0 * self.s

    def draw(self) -> None:
        c = self.cv
        c.delete("all")
        self._fit()
        s = self.s
        for p in self.pads:
            x, y = self.ox + p.x * s, self.oy - p.y * s
            if p.shape == "rect":
                c.create_rectangle(x - p.w * s / 2, y - p.h * s / 2, x + p.w * s / 2, y + p.h * s / 2, fill="#d79a4e", outline="")
            elif p.shape == "oval":
                c.create_oval(x - p.w * s / 2, y - p.h * s / 2, x + p.w * s / 2, y + p.h * s / 2, fill="#d79a4e", outline="")
            else:
                r = p.w * s / 2
                c.create_oval(x - r, y - r, x + r, y + r, fill="#d79a4e", outline="")
            r = p.drill * s / 2
            c.create_oval(x - r, y - r, x + r, y + r, fill="#16301c", outline="")
            c.create_text(x, y - p.h * s / 2 - 7, text=p.name, fill="white", font=("TkDefaultFont", 8))
        x, y = self.ox, self.oy
        c.create_line(x - 8, y, x + 8, y, fill="#fff")
        c.create_line(x, y - 8, x, y + 8, fill="#fff")

    def _pt(self, e):
        try:
            g = max(0.1, float(self.v["grid"].get()))
        except ValueError:
            g = 1.27
        x = (e.x - self.ox) / self.s
        y = (self.oy - e.y) / self.s
        return (round(x / g) * g, round(y / g) * g)

    def add_click(self, e) -> None:
        x, y = self._pt(e)
        try:
            w = float(self.v["pad"].get())
            dr = float(self.v["drill"].get())
        except ValueError:
            return
        names = {p.name for p in self.pads}
        n = 1
        while str(n) in names:
            n += 1
        self.pads.append(PadDef(str(n), x, y, "round", w, w, dr))
        self.sync_text()
        self.draw()

    def del_click(self, e) -> None:
        x = (e.x - self.ox) / self.s
        y = (self.oy - e.y) / self.s
        if not self.pads:
            return
        best = min(self.pads, key=lambda p: (p.x - x) ** 2 + (p.y - y) ** 2)
        if (best.x - x) ** 2 + (best.y - y) ** 2 < 4.0:
            self.pads.remove(best)
            self.sync_text()
            self.draw()

    def save(self) -> None:
        if not self.parse():
            return
        name = self.v["name"].get().strip()
        if not name or not self.pads:
            messagebox.showerror("SoloTrace", "Give the part a name and at least one pad.", parent=self.d)
            return
        # pads must be at least a clearance apart
        for i, a in enumerate(self.pads):
            for b in self.pads[i + 1:]:
                gap = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 - (max(a.w, a.h) + max(b.w, b.h)) / 2
                if gap < 0.25:
                    if not messagebox.askyesno("SoloTrace", "Pads %s and %s are closer than 0.25 mm. Save anyway?" % (a.name, b.name), parent=self.d):
                        return
                    break
        xs = [p.x for p in self.pads]
        ys = [p.y for p in self.pads]
        m = max(max(p.w, p.h) for p in self.pads) / 2 + 0.6
        x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
        pid = "USR_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        part = PartDef(pid, name, self.v["category"].get() or "Custom", (self.v["prefix"].get() or "U")[:3],
                       self.pads, [("rect", x0, y0, x1, y1)], (x0, y0, x1, y1), "part", (0.0, -1.0), self.v["note"].get())
        try:
            path = library.save_user_part(part)
        except Exception as exc:
            messagebox.showerror("SoloTrace", "Could not save:\n%s" % exc, parent=self.d)
            return
        self.app.reload_library()
        self.app.status("Saved your part '%s' to %s" % (name, path))
        self.d.destroy()


# ---------------------------------------------------------------------------------------
def make_preview(board: Board, job, maxw: int = 560, maxh: int = 400) -> tk.PhotoImage:
    """Raster picture of what the laser will burn (orange) and what stays painted (dark)."""
    s = min(maxw / board.width, maxh / board.height)
    w, h = max(1, int(board.width * s)), max(1, int(board.height * s))
    img = tk.PhotoImage(width=w, height=h)
    paint, burn = "#1c2a20", "#ff9a1f"
    rows: Dict[float, list] = {}
    for x0, y, x1, _y in job.segments:
        rows.setdefault(round(y, 5), []).append((x0, x1))
    ys = sorted(rows)
    blank = "{" + " ".join([paint] * w) + "}"
    tol = max(1.0 / s, 0.1)
    for py in range(h):
        y = board.height - (py + 0.5) / s
        if not ys:
            img.put(blank, to=(0, py))
            continue
        k = bisect.bisect_left(ys, y)
        cand = [ys[i] for i in (k - 1, k) if 0 <= i < len(ys)]
        near = min(cand, key=lambda v: abs(v - y))
        if abs(near - y) > tol:
            img.put(blank, to=(0, py))
            continue
        row = [paint] * w
        for a, c in rows[near]:
            for px in range(max(0, int(a * s)), min(w, int(c * s) + 1)):
                row[px] = burn
        img.put("{" + " ".join(row) + "}", to=(0, py))
    return img


class LaserDialog:
    def __init__(self, app) -> None:
        self.app = app
        self.board = app.board
        d = self.d = tk.Toplevel(app.root)
        d.title("Laser export - Elegoo Phecda (GRBL-style, untested on a real machine)")
        d.geometry("1040x700")
        d.transient(app.root)
        cfg = {}
        try:
            from .app import load_config
            cfg = load_config().get("laser", {})
        except Exception:
            pass
        self.o = LaserOptions.from_dict(cfg)
        self.v: Dict[str, tk.Variable] = {}
        self.job = None
        left = ttk.Frame(d, padding=6)
        left.pack(side="left", fill="y")
        warn = tk.Label(left, text="WORK IN PROGRESS. The laser only removes PAINT (paint the copper, burn, then etch).\n"
                        "Wear laser eye protection and ventilate. Run the test cards before a real board.",
                        bg="#b8860b", fg="white", justify="left", wraplength=330, padx=4, pady=3)
        warn.pack(fill="x")
        mf = ttk.LabelFrame(left, text="What to burn", padding=4)
        mf.pack(fill="x", pady=4)
        self.v["mode"] = tk.StringVar(value=self.o.mode)
        for val, text in (("negative", "Negative: burn everything except the copper (cleanest etch, slowest)"),
                          ("isolation", "Isolation: burn only a gap around the copper (fast)"),
                          ("positive", "Positive: burn the copper shapes themselves")):
            ttk.Radiobutton(mf, text=text, value=val, variable=self.v["mode"], command=self.refresh).pack(anchor="w")
        grid = ttk.Frame(left)
        grid.pack(fill="x")
        fields = [("trace_comp", "Trace adjust (mm per side, + fatter, - thinner / wider gaps)"),
                  ("gap", "Isolation gap width (mm)"), ("border", "Unburned border at board edge (mm)"),
                  ("line_interval", "Line spacing (mm; spot is about 0.07 x 0.13)"), ("feed", "Speed (mm/min)"),
                  ("power", "Power (% of S max)"), ("smax", "S max ($30 in GRBL)"), ("passes", "Passes"),
                  ("overscan", "Run-in/out in M3 mode (mm)"), ("dot_dia", "Drill dot diameter (mm)")]
        for i, (k, t) in enumerate(fields):
            ttk.Label(grid, text=t, wraplength=240, justify="left").grid(row=i, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=("%g" % getattr(self.o, k)))
            self.v[k] = var
            ttk.Entry(grid, textvariable=var, width=8).grid(row=i, column=1, padx=4)
        checks = [("mirror", "Mirror for the copper side (normal: leave ticked)"),
                  ("crosshatch", "Cross-hatch (second pass at 90 degrees)"),
                  ("bidirectional", "Burn in both directions"),
                  ("dynamic", "Use M4 dynamic power (untick for M3)"),
                  ("drill_dots", "Mark drill centres")]
        for k, t in checks:
            var = tk.BooleanVar(value=getattr(self.o, k))
            self.v[k] = var
            ttk.Checkbutton(left, text=t, variable=var).pack(anchor="w")
        bf = ttk.Frame(left)
        bf.pack(fill="x", pady=6)
        ttk.Button(bf, text="Update preview", command=self.refresh).pack(side="left")
        ttk.Button(bf, text="Save G-code...", command=self.save_gcode).pack(side="left", padx=4)
        bf2 = ttk.Frame(left)
        bf2.pack(fill="x")
        ttk.Button(bf2, text="Frame file...", command=self.save_frame).pack(side="left")
        ttk.Button(bf2, text="Speed/power test...", command=lambda: self.save_card("speed")).pack(side="left", padx=4)
        ttk.Button(bf2, text="Trace/gap test...", command=lambda: self.save_card("ladder")).pack(side="left")
        right = ttk.Frame(d, padding=6)
        right.pack(side="left", fill="both", expand=True)
        self.summary = tk.StringVar()
        ttk.Label(right, textvariable=self.summary, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.warn_lbl = tk.Label(right, text="", fg="#b00000", justify="left", wraplength=560)
        self.warn_lbl.pack(anchor="w")
        self.img_lbl = ttk.Label(right)
        self.img_lbl.pack(anchor="nw", pady=4)
        ttk.Label(right, text="Preview: component-side view. Orange = paint burned off, dark = paint stays.",
                  foreground="#555").pack(anchor="w")
        info = ("Setup: jog the laser to the lower-left corner of the board as you look at the COPPER side and set "
                "work zero there (the manual only mentions setting an origin, not homing, so no homing command is sent). Board limit 400 x 400 mm. "
                "G-code assumes GRBL: $32=1 and $30 = S max. Open it in LaserGRBL or LightBurn. "
                "Spot size, speed and power are starting points only: burn the two test cards on scrap first.")
        ttk.Label(right, text=info, wraplength=520, justify="left").pack(anchor="w", pady=6)
        self.img = None
        d.after(80, self.refresh)

    def read(self) -> Optional[LaserOptions]:
        o = LaserOptions()
        try:
            o.mode = self.v["mode"].get()
            for k in ("trace_comp", "gap", "border", "line_interval", "feed", "power", "smax", "overscan", "dot_dia"):
                setattr(o, k, float(self.v[k].get()))
            o.passes = max(1, int(float(self.v["passes"].get())))
            for k in ("mirror", "crosshatch", "bidirectional", "dynamic", "drill_dots"):
                setattr(o, k, bool(self.v[k].get()))
        except ValueError:
            messagebox.showerror("SoloTrace", "One of the numbers is not a number.", parent=self.d)
            return None
        return o

    def refresh(self) -> None:
        o = self.read()
        if o is None:
            return
        try:
            if o.line_interval < 0.01:
                raise ValueError("Line spacing must be at least 0.01 mm.")
            self.job = generate(self.board, o, self.board.name)
        except Exception as exc:
            messagebox.showerror("SoloTrace", str(exc), parent=self.d)
            return
        self.o = o
        self.summary.set(self.job.summary())
        self.warn_lbl.config(text="\n".join(self.job.warnings))
        self.img = make_preview(self.board, self.job)
        self.img_lbl.config(image=self.img)
        try:
            from .app import load_config, save_config
            c = load_config()
            c["laser"] = o.to_dict()
            save_config(c)
        except Exception:
            pass

    def _name(self, suffix: str) -> str:
        return "%s_%s" % (self.board.name.replace(" ", "_"), suffix)

    def save_gcode(self) -> None:
        o = self.read()
        if o is None:
            return
        self.refresh()
        if self.job is None:
            return
        if any("larger than" in w for w in self.job.warnings):
            messagebox.showerror("SoloTrace", "The board does not fit the Phecda work area.", parent=self.d)
            return
        p = filedialog.asksaveasfilename(parent=self.d, defaultextension=".gcode", initialfile=self._name("laser.gcode"),
                                         filetypes=[("G-code", "*.gcode *.nc"), ("All files", "*")])
        if p:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(self.job.gcode)
            self.app.status("Wrote %s (%s)" % (p, self.job.summary()))

    def save_frame(self) -> None:
        o = self.read()
        if o is None:
            return
        p = filedialog.asksaveasfilename(parent=self.d, defaultextension=".gcode", initialfile=self._name("frame.gcode"))
        if p:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(frame_gcode(self.board, o))
            self.app.status("Wrote frame outline %s" % p)

    def save_card(self, kind: str) -> None:
        o = self.read()
        if o is None:
            return
        job = speed_power_card(o) if kind == "speed" else trace_ladder_card(o)
        p = filedialog.asksaveasfilename(parent=self.d, defaultextension=".gcode",
                                         initialfile="solotrace_%s_test.gcode" % kind)
        if p:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(job.gcode)
            self.app.status("Wrote test card %s (%s)" % (p, job.summary()))
