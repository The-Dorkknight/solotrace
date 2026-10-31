# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Take the README / project-page screenshots of the real window.

Run from the repo root (needs xvfb and ImageMagick):
    xvfb-run -a -s "-screen 0 1280x840x24" /usr/bin/python3.12 tools/take_screenshots.py
The window holds the demo boards; nothing here is simulated hardware.
"""
import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
home = os.path.join(tempfile.mkdtemp(), "home", "matthew")
os.makedirs(home)
os.environ["HOME"] = home

from solotrace import demos                      # noqa: E402
from solotrace.app import App                    # noqa: E402
from solotrace.board import Board                # noqa: E402

OUT = os.path.join(ROOT, "docs", "images")
tmp = tempfile.mkdtemp()
root = tk.Tk()
root.geometry("1280x800+0+0")
app = App(root)


def pump(n=20, d=0.02):
    for _ in range(n):
        root.update()
        time.sleep(d)


def shot(name, crop=None):
    root.update()
    png = os.path.join(tmp, name + ".png")
    subprocess.run(["import", "-window", "root", png], check=True)
    cmd = ["convert", png]
    if crop:
        cmd += ["-crop", "%dx%d+%d+%d" % crop, "+repage"]
    cmd += ["-define", "webp:lossless=true", os.path.join(OUT, name + ".webp")]
    subprocess.run(cmd, check=True)
    print("wrote", name)


def top_crop(win):
    win.update()
    return (win.winfo_width(), win.winfo_height(), win.winfo_rootx(), win.winfo_rooty())


def load_example(name):
    b = Board.load(os.path.join(ROOT, "examples", name, name + ".solotrace"))
    app.load_board(b)
    pump(10)


def trace_longest(b):
    def length(t):
        return sum(((t.points[k + 1][0] - t.points[k][0]) ** 2 + (t.points[k + 1][1] - t.points[k][1]) ** 2) ** .5
                   for k in range(len(t.points) - 1))
    return max(range(len(b.traces)), key=lambda i: length(b.traces[i]))


pump(20)
# 1. main window, routed 555, a trace selected, the parts tree open on standing resistors
load_example("555-led-flasher")
tv = app.lib_tree
tv.item("g:Resistors, diodes & inductors", open=True)
tv.item("s:Resistors, diodes & inductors:Resistors standing", open=True)
tv.selection_set("p:R_V_0.25W_2.54")
pump(10)
app.set_tool("select")
app.sel = {"trace": trace_longest(app.board), "seg": 0}
app.show_props()
app.fit()
pump(10)
shot("gui-routed")
# 2. the same board looked at from the copper side, nothing selected
app.sel = {}
app.show_props()
app.toggle_mirror()
pump(10)
shot("gui-copper-side")
app.toggle_mirror()
# 3. deadbug 555: the DIP-8 gets deadbug pads BEFORE placing and routing, so the copper fits
from solotrace.placer import auto_place          # noqa: E402
from solotrace.router import AutoRouter, RouteOptions          # noqa: E402
b = demos.flasher_555()
b.parts["U1"].style = "dead"
auto_place(b, time_limit=20, seed=2)
print("deadbug 555:", AutoRouter(b).route_all().summary())
app.load_board(b)
app.sel = {"part": "U1", "pin": "2"}
app.show_props()
app.fit()
pump(10)
shot("gui-deadbug")
# 4. unrouted board with rubber-band lines and a net selected
b = demos.flasher_555()
app.load_board(b)
app.sel = {"net": "THR"}
app.show_props()
app.fit()
pump(10)
shot("gui-ratsnest")
# 4a. pin labels, values, D-shaped TO-92 and a rigid (orange) power trunk
load_example("555-power-oscillator")
app.sel = {"part": "Q1"}
app.show_props()
app.fit()
pump(10)
shot("gui-pin-labels")
# 4c. Manhattan board: hand-placed copper islands on a ground fill, one island selected (corner handles)
load_example("manhattan-rf-amplifier")
app.set_tool("select")
app.sel = {"island": 5}
app.show_props()
app.fit()
pump(10)
shot("gui-islands")
# 4d. ground fill with routed islands, net panel of the ground net
load_example("rf-oscillator-ground-fill")
app.sel = {"net": "GND"}
app.show_props()
app.fit()
pump(10)
shot("gui-ground-fill")
app.island_dialog()
pump(20)
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
dlg.geometry("+300+120")
dlg.lift()
pump(20)
shot("islands-dialog", top_crop(dlg))
dlg.destroy()
pump(5)
# 4b. right-click menu on a trace
load_example("555-led-flasher")
tv.selection_remove(tv.selection())
app.preview_id = "TO220_3"
app.draw_preview()


class _Ev:
    pass


t = app.board.traces[trace_longest(app.board)]
mid = ((t.points[1][0] + t.points[2][0]) / 2, (t.points[1][1] + t.points[2][1]) / 2)
ev = _Ev()
ev.x, ev.y = (int(v) for v in app.w2s(*mid))
ev.x_root, ev.y_root = ev.x + app.canvas.winfo_rootx(), ev.y + app.canvas.winfo_rooty()
root.after(400, lambda: (shot("gui-context-menu"), app._menu.unpost(), root.quit()))
app.context_menu(ev)
root.mainloop()
pump(5)
# 4c. the wide-trace fix: the board from the bug report, 2 mm trace before and after tidying
w = Board(45, 35, "Two transistors")
w.add_part("TO92", 5.08, 27.94, ref="Q1", value="BC547")
w.add_part("TO92", 30.48, 27.94, ref="Q2", value="BC547")
w.add_part("R_0.25W_10.16", 5.08, 7.62, rot=90, ref="R1", value="10k")
w.add_part("R_0.25W_10.16", 30.48, 7.62, rot=90, ref="R2", value="10k")
w.connect("Q1.1", "R1.2", "A")
w.connect("Q2.1", "R2.2", "B")
w.connect("Q1.2", "R2.1", "C")
w.connect("R1.1", "Q2.2", "D")
r = AutoRouter(w, RouteOptions(smooth=False))
r.route_all()
w.set_net_trace_width("C", 2.0)
app.load_board(w)
app.sel = {}
app.show_props()
app.fit()
pump(10)
cx, cy = app.canvas.winfo_rootx(), app.canvas.winfo_rooty()
cw, ch = app.canvas.winfo_width(), app.canvas.winfo_height()
shot("tidy-before", (cw, ch, cx, cy))
from solotrace.tidy import tidy_traces      # noqa: E402
tidy_traces(app.board)
app.request_redraw()
pump(10)
shot("tidy-after", (cw, ch, cx, cy))
for f, label in (("tidy-before", "Before: 2 mm trace leaves Q1 at an angle, ends off-centre on R2"),
                 ("tidy-after", "After: straight exits, ends on the pad centres")):
    subprocess.run(["convert", os.path.join(OUT, f + ".webp"), "-gravity", "center", "-crop", "100%x84%+0+0", "+repage",
                    "-background", "#22313f", "-gravity", "north", "-splice", "0x34",
                    "-fill", "#f1f4f7", "-pointsize", "16", "-annotate", "+0+8", label,
                    os.path.join(tmp, ("a" if f == "tidy-before" else "b") + ".png")], check=True)
subprocess.run(["convert", os.path.join(tmp, "a.png"), "-size", "12x1", "xc:#eef1f4", os.path.join(tmp, "b.png"), "+append",
                "-define", "webp:lossless=true", os.path.join(OUT, "wide-trace-tidy.webp")], check=True)
for f in ("tidy-before", "tidy-after"):
    os.remove(os.path.join(OUT, f + ".webp"))
print("wrote wide-trace-tidy")
# 5. laser dialogs: negative, then isolation with the gap widened by thinning the copper
load_example("555-led-flasher")
app.laser_dialog()
pump(40)
ld = app.laser_dlg
ld.d.geometry("1040x700+120+40")
ld.d.lift()
pump(20)
shot("laser-negative", top_crop(ld.d))
ld.v["mode"].set("isolation")
ld.v["trace_comp"].set("-0.05")
ld.v["gap"].set("0.8")
ld.refresh()
pump(20)
shot("laser-isolation", top_crop(ld.d))
ld.d.destroy()
pump(5)
# 6. footprint wizard
app.footprint_wizard()
pump(30)
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
dlg.geometry("860x560+200+60")
dlg.lift()
pump(20)
shot("footprint-wizard", top_crop(dlg))
dlg.destroy()
app.shutdown()
root.destroy()
