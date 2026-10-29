# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Colours, ttk styles, tooltips and rounded corners for the SoloTrace window."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

UI = {
    "panel": "#eef1f4",        # side panels
    "panel2": "#e2e7ec",       # panel headers / cards
    "ink": "#1f2a33",
    "muted": "#5b6b78",
    "bar": "#22313f",          # top tool bar
    "bar2": "#2f4456",         # tool bar hover
    "bar_ink": "#f1f4f7",
    "copper": "#d9822b",       # main accent
    "copper_dark": "#b8691c",
    "teal": "#2a9d8f",
    "teal_dark": "#21867a",
    "blue": "#3a7bd5",
    "blue_dark": "#2f66b3",
    "red": "#c2453d",
    "red_dark": "#a3372f",
    "status": "#1b2630",
    "ok": "#3fbf6f",
    "warn": "#e8a33a",
    "wip": "#b7791f",
    "sel_row": "#f6d2ad",
}

FONT = ("TkDefaultFont", 10)
FONT_B = ("TkDefaultFont", 10, "bold")
FONT_H = ("TkDefaultFont", 11, "bold")
FONT_S = ("TkDefaultFont", 9)


def apply(root: tk.Misc) -> ttk.Style:
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    P = UI["panel"]
    st.configure(".", background=P, foreground=UI["ink"], font=FONT)
    st.configure("TFrame", background=P)
    st.configure("TLabel", background=P, foreground=UI["ink"])
    st.configure("Muted.TLabel", foreground=UI["muted"], font=FONT_S)
    st.configure("Head.TLabel", font=FONT_H, foreground=UI["ink"])
    st.configure("Card.TFrame", background=UI["panel2"])
    st.configure("Card.TLabel", background=UI["panel2"])
    st.configure("TCheckbutton", background=P)
    st.configure("TRadiobutton", background=P)
    st.map("TCheckbutton", background=[("active", P)])
    st.map("TRadiobutton", background=[("active", P)])
    st.configure("TButton", padding=(8, 3), relief="flat", background="#d5dce3", borderwidth=0)
    st.configure("Small.TButton", padding=(2, 2), font=FONT_S)
    st.map("TButton", background=[("pressed", "#bcc6cf"), ("active", "#c9d2da")])
    st.configure("TEntry", fieldbackground="#ffffff", padding=3)
    st.configure("TCombobox", fieldbackground="#ffffff", padding=2)
    for name, base, dark in (("Copper", "copper", "copper_dark"), ("Teal", "teal", "teal_dark"),
                             ("Blue", "blue", "blue_dark"), ("Red", "red", "red_dark")):
        st.configure("%s.TButton" % name, background=UI[base], foreground="white", font=FONT_B,
                     padding=(8, 3), borderwidth=0)
        st.map("%s.TButton" % name, background=[("pressed", UI[dark]), ("active", UI[dark])],
               foreground=[("disabled", "#e0e0e0")])
    # top bar
    B = UI["bar"]
    st.configure("Bar.TFrame", background=B)
    st.configure("Bar.TLabel", background=B, foreground=UI["bar_ink"])
    st.configure("Bar.TSeparator", background="#3d5366")
    st.configure("Tool.TRadiobutton", background=B, foreground=UI["bar_ink"], padding=(7, 4),
                 font=FONT_B, borderwidth=0, relief="flat", indicatorsize=0)
    st.layout("Tool.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [
        ("Radiobutton.label", {"sticky": "nswe"})]})])
    st.map("Tool.TRadiobutton", background=[("selected", UI["copper"]), ("active", UI["bar2"])],
           foreground=[("selected", "white")])
    st.configure("Bar.TRadiobutton", background=B, foreground=UI["bar_ink"], indicatorcolor="#ffffff")
    st.configure("Bar.TCheckbutton", background=B, foreground=UI["bar_ink"], indicatorcolor="#ffffff")
    st.map("Bar.TCheckbutton", background=[("active", B)], indicatorcolor=[("selected", UI["copper"])])
    st.map("Bar.TRadiobutton", background=[("active", B)], indicatorcolor=[("selected", UI["copper"])])
    # parts tree
    st.configure("Parts.Treeview", background="#ffffff", fieldbackground="#ffffff", rowheight=22, borderwidth=0)
    st.map("Parts.Treeview", background=[("selected", UI["sel_row"])], foreground=[("selected", UI["ink"])])
    # status bar
    st.configure("Status.TFrame", background=UI["status"])
    st.configure("Status.TLabel", background=UI["status"], foreground="#cfd8df", font=FONT_S)
    st.configure("Ok.TLabel", background=UI["ok"], foreground="white", font=("TkDefaultFont", 9, "bold"), padding=(8, 1))
    st.configure("Todo.TLabel", background=UI["warn"], foreground="white", font=("TkDefaultFont", 9, "bold"), padding=(8, 1))
    st.configure("Horizontal.TProgressbar", background=UI["copper"], troughcolor="#3d5366", borderwidth=0)
    root.option_add("*Menu.activeBackground", UI["copper"])
    root.option_add("*Menu.activeForeground", "white")
    root.option_add("*Menu.relief", "flat")
    return st


class Tooltip:
    """A small hint that appears when the mouse rests on a widget."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 550) -> None:
        self.w = widget
        self.text = text
        self.delay = delay
        self.tip: Optional[tk.Toplevel] = None
        self.after_id = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _e=None) -> None:
        self._cancel()
        self.after_id = self.w.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self.after_id:
            try:
                self.w.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        try:
            x = self.w.winfo_rootx() + 8
            y = self.w.winfo_rooty() + self.w.winfo_height() + 4
            self.tip = tk.Toplevel(self.w)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_geometry("+%d+%d" % (x, y))
            tk.Label(self.tip, text=self.text, bg="#fffbe6", fg=UI["ink"], relief="solid", borderwidth=1,
                     font=FONT_S, padx=6, pady=3, justify="left", wraplength=320).pack()
        except tk.TclError:
            self.tip = None

    def _leave(self, _e=None) -> None:
        self._cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


def round_corners(canvas: tk.Canvas, radius: int, outside: str, tag: str = "corner_mask") -> None:
    """Paint the four corners of a canvas in the surrounding colour so it looks rounded."""
    canvas.delete(tag)
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 4 * radius or h < 4 * radius:
        return
    r = radius
    n = 8
    import math
    for cx, cy, sx, sy in ((r, r, -1, -1), (w - r, r, 1, -1), (r, h - r, -1, 1), (w - r, h - r, 1, 1)):
        pts = [cx + sx * r, cy + sy * r, cx + sx * r, cy]
        for k in range(n + 1):
            a = (math.pi / 2) * k / n
            pts += [cx + sx * r * math.cos(a), cy + sy * r * math.sin(a)]
        pts += [cx, cy + sy * r]
        canvas.create_polygon(pts, fill=outside, outline=outside, tags=tag)


def _img(root: tk.Misc, size: int = 18) -> tk.PhotoImage:
    return tk.PhotoImage(master=root, width=size, height=size)


def _disc(im: tk.PhotoImage, cx: float, cy: float, r: float, col: str, r_in: float = -1.0) -> None:
    for y in range(int(cy - r - 1), int(cy + r + 2)):
        for x in range(int(cx - r - 1), int(cx + r + 2)):
            d = ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
            if d <= r and d > r_in and 0 <= x < im.width() and 0 <= y < im.height():
                im.put(col, (x, y))


def group_icons(root: tk.Misc) -> dict:
    """Small drawn icons for the parts-panel groups (no image files needed)."""
    ic = {}
    cu, ink = UI["copper"], "#2b2b2b"
    im = _img(root)                                   # chip
    for k in range(4):
        im.put(cu, to=(3, 3 + k * 4, 6, 5 + k * 4))
        im.put(cu, to=(12, 3 + k * 4, 15, 5 + k * 4))
    im.put(ink, to=(5, 2, 13, 17))
    im.put("#ffffff", to=(7, 3, 9, 5))
    ic["Chips (DIP)"] = im
    im = _img(root)                                   # transistor
    _disc(im, 9, 8, 6.5, ink)
    im.put("#ffffff", to=(2, 9, 16, 17))
    im.put(ink, to=(2, 8, 16, 10))
    for x in (4, 8, 12):
        im.put("#9aa3aa", to=(x, 10, x + 2, 17))
    ic["Transistors & regulators"] = im
    im = _img(root)                                   # resistor
    im.put("#9aa3aa", to=(0, 8, 18, 10))
    im.put("#d8b77e", to=(4, 5, 14, 13))
    for x, c in ((6, "#8b4513"), (9, "#111111"), (12, "#d62828")):
        im.put(c, to=(x, 5, x + 1, 13))
    ic["Resistors, diodes & inductors"] = im
    im = _img(root)                                   # capacitor
    im.put("#2f6db3", to=(4, 1, 14, 14))
    im.put("#d6e4f5", to=(11, 1, 13, 14))
    im.put("#9aa3aa", to=(6, 14, 7, 18))
    im.put("#9aa3aa", to=(11, 14, 12, 18))
    ic["Capacitors"] = im
    im = _img(root)                                   # LED
    _disc(im, 9, 7, 6, "#e63946")
    _disc(im, 7, 5, 2, "#ffb3b8")
    im.put("#9aa3aa", to=(6, 12, 7, 18))
    im.put("#9aa3aa", to=(11, 12, 12, 18))
    ic["LEDs"] = im
    im = _img(root)                                   # pot
    _disc(im, 9, 9, 7, "#3a7bd5")
    _disc(im, 9, 9, 3, "#ffffff")
    im.put("#ffffff", to=(8, 2, 10, 8))
    ic["Pots, switches & crystals"] = im
    im = _img(root)                                   # connector
    im.put("#2a9d8f", to=(1, 4, 17, 14))
    for x in (3, 8, 13):
        _disc(im, x + 1, 9, 2.2, "#e9f5f3")
    ic["Connectors"] = im
    im = _img(root)                                   # board bits (pad with hole)
    _disc(im, 9, 9, 7.5, cu, 2.5)
    ic["Board bits"] = im
    im = _img(root)                                   # my parts (star-ish pencil)
    for k in range(12):
        im.put(UI["copper_dark"], to=(3 + k, 14 - k, 5 + k, 16 - k))
    im.put(ink, to=(2, 15, 4, 17))
    ic["My parts"] = im
    return ic
