# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Drives the real window with synthetic mouse events. Skipped when there is no display or no tkinter."""
import time
import unittest

import _path  # noqa: F401

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_TK = True
except Exception:
    HAVE_TK = False


@unittest.skipUnless(HAVE_TK, "tkinter or a display is not available")
class Window(unittest.TestCase):
    def setUp(self):
        from solotrace.app import App
        self.root = tk.Tk()
        self.root.geometry("1200x760")
        self.app = App(self.root)
        self.pump()

    def tearDown(self):
        self.app.shutdown()
        self.root.destroy()

    def pump(self, n=15):
        for _ in range(n):
            self.root.update()
            time.sleep(0.01)

    def click(self, wx, wy):
        sx, sy = self.app.w2s(wx, wy)
        c = self.app.canvas
        c.event_generate("<Motion>", x=int(sx), y=int(sy))
        c.event_generate("<ButtonPress-1>", x=int(sx), y=int(sy))
        c.event_generate("<ButtonRelease-1>", x=int(sx), y=int(sy))
        self.pump(3)

    def wait_job(self, limit=120):
        t = time.time()
        while self.app.job and time.time() - t < limit:
            self.pump(5)

    def test_title_and_stamp(self):
        from solotrace import __version__
        self.assertIn("v" + __version__, self.root.title())
        self.assertIn("Built", self.root.title())
        self.assertIn("WIP", self.app.stamp_var.get())

    def test_place_wire_route_width(self):
        a = self.app
        a.board.settings.classes["Signal"] = 0.8
        for pid, x in (("R_0.25W_10.16", 20.32), ("R_0.25W_10.16", 50.8)):
            a.armed = pid
            a.set_tool("place")
            self.click(x, 40.64)
        self.assertEqual(len(a.board.parts), 2)
        a.set_tool("wire")
        p1 = a.board.pin_pos("R1.2")
        p2 = a.board.pin_pos("R2.1")
        self.click(*p1)
        self.click(*p2)
        self.assertEqual(len(a.board.nets), 1)
        a.set_tool("select")
        a.auto_route()
        self.wait_job()
        self.assertTrue(a.board.is_fully_routed())
        t = a.board.traces[0]
        mid = ((t.points[0][0] + t.points[1][0]) / 2, (t.points[0][1] + t.points[1][1]) / 2)
        self.click(*mid)
        self.assertIn("trace", a.sel)
        scales = []

        def find(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Scale):
                    scales.append(c)
                find(c)
        find(a.prop)
        self.assertEqual(len(scales), 1)
        a.width_scope.set("trace")
        scales[0].set(6.5)
        self.pump()
        self.assertTrue(all(abs(w - 6.5) < 1e-6 for w in a.board.traces[a.sel["trace"]].widths))
        a.do_undo()
        self.pump()

    def test_deadbug_toggle(self):
        a = self.app
        a.armed = "DIP8_N"
        a.set_tool("place")
        self.click(30, 40)
        ref = list(a.board.parts)[0]
        a.sel = {"part": ref}
        a._set_style(ref, "dead")
        self.assertEqual(a.board.parts[ref].style, "dead")
        self.assertEqual(a.board.drills(), [])

    def test_dialogs_open(self):
        from solotrace import demos
        a = self.app
        a.load_board(demos.flasher_555())
        a.laser_dialog()
        self.pump(20)
        a.footprint_wizard()
        a.board_settings()
        self.pump(10)
        a.show_drc()
        self.pump(10)

    def test_parts_tree_and_preview(self):
        a = self.app
        tv = a.lib_tree
        top = [tv.item(i, "text").strip().split("  (")[0] for i in tv.get_children("")]
        self.assertEqual(top[:3], ["Chips (DIP)", "Transistors & regulators", "Resistors, diodes & inductors"])
        tv.selection_set("p:R_V_0.25W_2.54")
        self.pump(5)
        self.assertEqual(a.armed, "R_V_0.25W_2.54")
        self.assertEqual(a.tool, "place")
        self.assertGreater(len(a.preview.find_all()), 5)          # copper, holes, outline, text
        a.search_var.set("to-220")
        self.pump(3)
        found = []

        def walk(i):
            for k in tv.get_children(i):
                if k.startswith("p:"):
                    found.append(k)
                walk(k)
        walk("")
        self.assertTrue(found and all("TO220" in k for k in found), found)

    def test_context_menu_drag_and_trim(self):
        from solotrace import demos
        from solotrace.geom import max_turn
        a = self.app
        b = demos.flasher_555()
        from solotrace.router import AutoRouter
        AutoRouter(b).route_all()
        a.load_board(b)
        self.pump(5)

        class E:
            pass

        def ev(wx, wy):
            e = E()
            e.x, e.y = (int(v) for v in a.w2s(wx, wy))
            e.x_root, e.y_root = e.x + 50, e.y + 50
            return e
        t = max(a.board.traces, key=lambda t: len(t.points))
        ti = a.board.traces.index(t)
        si = max(range(len(t.points) - 1), key=lambda k: ((t.points[k + 1][0] - t.points[k][0]) ** 2 +
                                                           (t.points[k + 1][1] - t.points[k][1]) ** 2))
        mid = ((t.points[si][0] + t.points[si + 1][0]) / 2, (t.points[si][1] + t.points[si + 1][1]) / 2)
        a.context_menu(ev(*mid))
        self.pump(3)
        labels = [a._menu.entrycget(i, "label") for i in range(a._menu.index("end") + 1) if a._menu.type(i) != "separator"]
        a._menu.unpost()
        for want in ("Trim this section", "Split trace here", "Width of whole trace"):
            self.assertIn(want, labels)
        # drag the section sideways with the mouse
        before_pts = list(t.points)
        a.set_tool("select")
        sx, sy = a.w2s(*mid)
        c = a.canvas
        c.event_generate("<ButtonPress-1>", x=int(sx), y=int(sy))
        for k in range(1, 6):
            c.event_generate("<B1-Motion>", x=int(sx) + 5 * k, y=int(sy) + 5 * k)
        c.event_generate("<ButtonRelease-1>", x=int(sx) + 25, y=int(sy) + 25)
        self.pump(5)
        before = before_pts
        moved = a.board.traces[ti]
        self.assertTrue(moved.manual)
        self.assertNotEqual(moved.points, before)
        self.assertLessEqual(max_turn(moved.points), 46.0)
        a.do_undo()
        self.pump(3)
        # trim tool removes a section
        n = a.board.unrouted_count()
        a.set_tool("trim")
        t = a.board.traces[ti]
        mid = ((t.points[si][0] + t.points[si + 1][0]) / 2, (t.points[si][1] + t.points[si + 1][1]) / 2)
        a.on_press(ev(*mid))       # synthetic press (Xvfb sometimes drops a press right after a drag)
        self.pump(3)
        self.assertGreater(a.board.unrouted_count(), n)

    def test_mouse_moves_only_redraw_the_moving_layer(self):
        from solotrace import demos
        from solotrace.router import AutoRouter
        a = self.app
        b = demos.flasher_555()
        AutoRouter(b).route_all()
        a.load_board(b)
        self.pump(5)
        a.set_tool("wire")
        a.pending_pin = "U1.1"
        self.pump(5)                    # let the redraw asked for by set_tool happen first
        static = set(a.canvas.find_all()) - set(a.canvas.find_withtag("dyn"))
        for k in range(10):
            a.canvas.event_generate("<Motion>", x=300 + 7 * k, y=300 + 3 * k)
            self.pump(1)
        self.assertTrue(a.canvas.find_withtag("dyn"))              # the rubber band is there
        self.assertTrue(static <= set(a.canvas.find_all()))       # and the board was not redrawn

    def test_shift_wire_is_rigid_and_labels_show(self):
        a = self.app
        for pid, x in (("TO220_3", 20.32), ("TERM_5.08_2", 50.8)):
            a.armed = pid
            a.set_tool("place")
            self.click(x, 40.64)
        a.set_tool("wire")
        c = a.canvas
        for pin, state in (("Q1.3", 0), ("J1.1", 1)):          # second click with Shift held
            sx, sy = a.w2s(*a.board.pin_pos(pin))
            c.event_generate("<ButtonPress-1>", x=int(sx), y=int(sy), state=state)
            c.event_generate("<ButtonRelease-1>", x=int(sx), y=int(sy), state=state)
            self.pump(2)
        net = a.board.net_of("Q1.3")
        self.assertIsNotNone(net)
        self.assertEqual(net.links, [["Q1.3", "J1.1"]])
        a._set_pin_labels("Q1", {"1": "G", "2": "D", "3": "S"})
        a.redraw()
        texts = {a.canvas.itemcget(i, "text") for i in a.canvas.find_all() if a.canvas.type(i) == "text"}
        self.assertTrue({"G", "D", "S"} <= texts, texts)

    def test_cut_tool_and_jumper_switch(self):
        from solotrace import demos
        from solotrace.geom import dist
        from solotrace.router import AutoRouter
        a = self.app
        b = demos.flasher_555()
        AutoRouter(b).route_all()
        a.load_board(b)
        self.pump(3)
        t = max(a.board.traces, key=lambda t: max(dist(t.points[i], t.points[i + 1]) for i in range(len(t.points) - 1)))
        i = max(range(len(t.points) - 1), key=lambda k: dist(t.points[k], t.points[k + 1]))
        p, q = t.points[i], t.points[i + 1]
        n_before = len(a.board.traces)
        a.set_tool("cut")
        a.cut_click(p[0] + (q[0] - p[0]) * 0.3, p[1] + (q[1] - p[1]) * 0.3, two_point=True)
        self.assertIsNotNone(a.cut_start)
        a.redraw()                                         # the red preview draws without errors
        a.cut_click(p[0] + (q[0] - p[0]) * 0.7, p[1] + (q[1] - p[1]) * 0.7, two_point=True)
        self.assertIsNone(a.cut_start)
        self.assertGreater(a.board.unrouted_count(), 0)
        self.assertGreaterEqual(len(a.board.traces), n_before)
        a.jumpers_var.set(False)
        a._toggle_jumpers()
        self.assertFalse(a.board.settings.allow_jumpers)
        a.do_undo()
        self.assertTrue(a.board.settings.allow_jumpers)
        self.assertTrue(a.jumpers_var.get())

    def test_cut_click_removes_one_piece_and_shift_click_turns_parts(self):
        from solotrace import demos
        from solotrace.geom import dist
        from solotrace.router import AutoRouter
        a = self.app
        b = demos.flasher_555()
        AutoRouter(b).route_all()
        a.load_board(b)
        self.pump(3)
        t = max(a.board.traces, key=lambda t: sum(dist(t.points[i], t.points[i + 1]) for i in range(len(t.points) - 1)))
        i = max(range(len(t.points) - 1), key=lambda k: dist(t.points[k], t.points[k + 1]))
        mid = ((t.points[i][0] + t.points[i + 1][0]) / 2, (t.points[i][1] + t.points[i + 1][1]) / 2)
        a.set_tool("cut")
        sx, sy = a.w2s(*mid)
        a.canvas.event_generate("<Motion>", x=int(sx), y=int(sy))
        self.pump(3)
        self.assertTrue(a.cut_preview)                         # the piece is shown in red first
        before = a.board.unrouted_count()
        a.cut_click(*mid)
        self.assertGreater(a.board.unrouted_count(), before)
        self.assertFalse([x for x in a.board.traces if x is t])
        # Shift + click while placing turns the part instead of placing it
        a.arm_part("TO92")
        n = len(a.board.parts)

        class E:
            pass
        e = E()
        e.x, e.y = (int(v) for v in a.w2s(60.0, 40.0))
        e.state = 1
        a.on_press(e)
        self.assertEqual(a.arm_rot, 90)
        self.assertEqual(len(a.board.parts), n)
        e.state = 0
        a.on_press(e)
        self.assertEqual(len(a.board.parts), n + 1)
        self.assertEqual(a.board.parts[a.sel["part"]].rot, 90)
        # favourites and recent
        a._set_fav("DIP8_N", True)
        a._fill_quick()
        vals = list(a.quick_cb.cget("values"))
        self.assertTrue(any("DIP-8" in v for v in vals))
        self.assertTrue(any("TO-92" in v for v in vals))       # just placed, so it is recent
        a.quick_cb.current([j for j, v in enumerate(vals) if "DIP-8" in v][0])
        a._quick_pick()
        self.assertEqual(a.armed, "DIP8_N")

    def test_right_click_only_opens_a_menu_and_previews_the_cut(self):
        from solotrace import demos
        from solotrace.geom import dist
        from solotrace.router import AutoRouter
        a = self.app
        b = demos.flasher_555()
        AutoRouter(b).route_all()
        a.load_board(b)
        self.pump(3)
        t = max(a.board.traces, key=lambda t: sum(dist(t.points[i], t.points[i + 1]) for i in range(len(t.points) - 1)))
        i = max(range(len(t.points) - 1), key=lambda k: dist(t.points[k], t.points[k + 1]))
        mid = ((t.points[i][0] + t.points[i + 1][0]) / 2, (t.points[i][1] + t.points[i + 1][1]) / 2)
        n = len(a.board.traces)

        class E:
            pass
        e = E()
        e.x, e.y = (int(v) for v in a.w2s(*mid))
        e.x_root, e.y_root = e.x + 50, e.y + 50
        a.context_menu(e)
        self.pump(3)
        self.assertEqual(len(a.board.traces), n)                 # a right-click alone removes nothing
        m = a._menu
        idx = [k for k in range(m.index("end") + 1) if m.type(k) == "command"
               and m.entrycget(k, "label").startswith("Cut this piece")][0]
        m.activate(idx)
        m.event_generate("<<MenuSelect>>")
        self.pump(3)
        self.assertIsNotNone(a.menu_preview)                     # the piece is shown in red
        m.invoke(idx)
        m.unpost()
        self.pump(3)
        self.assertFalse([x for x in a.board.traces if x is t])  # only now is it gone

    def test_island_tool_drop_drag_resize_and_menu(self):
        from solotrace.board import Board
        a = self.app
        b = Board(60, 40, "islands")
        b.add_part("R_V_0.25W_2.54", 20.32, 20.32, ref="R1", style="dead")
        a.load_board(b)
        self.pump(3)
        a.set_tool("island")
        self.click(40.64, 20.32)                                     # a click drops one of the default size
        self.assertEqual(len(a.board.islands), 1)
        isl = a.board.islands[0]
        self.assertEqual((isl.x, isl.y, isl.w, isl.h, isl.shape), (40.64, 20.32, 5.08, 5.08, "rect"))
        self.assertEqual(a.sel, {"island": 0})
        # drag out a rectangle somewhere empty
        c = a.canvas
        s0, s1 = a.w2s(5.08, 5.08), a.w2s(15.24, 10.16)
        c.event_generate("<ButtonPress-1>", x=int(s0[0]), y=int(s0[1]))
        c.event_generate("<B1-Motion>", x=int(s1[0]), y=int(s1[1]))
        c.event_generate("<ButtonRelease-1>", x=int(s1[0]), y=int(s1[1]))
        self.pump(3)
        self.assertEqual(len(a.board.islands), 2)
        r = a.board.islands[1]
        self.assertAlmostEqual(r.w, 10.16, places=2)
        self.assertAlmostEqual(r.h, 5.08, places=2)
        # Shift + click switches new islands to round
        sx, sy = a.w2s(50, 35)
        c.event_generate("<ButtonPress-1>", x=int(sx), y=int(sy), state=1)
        c.event_generate("<ButtonRelease-1>", x=int(sx), y=int(sy), state=1)
        self.pump(3)
        self.assertEqual(a.island_new["shape"], "round")
        # select tool: drag the first island onto R1's pin 1, so it joins that pin
        a.set_tool("select")
        px, py = a.board.pin_pos("R1.1")
        a.sel = {"island": 0}
        f, t = a.w2s(40.64, 20.32), a.w2s(px - 1.27, py)
        c.event_generate("<ButtonPress-1>", x=int(f[0]), y=int(f[1]))
        c.event_generate("<B1-Motion>", x=int((f[0] + t[0]) / 2), y=int(f[1]))
        c.event_generate("<B1-Motion>", x=int(t[0]), y=int(t[1]))
        c.event_generate("<ButtonRelease-1>", x=int(t[0]), y=int(t[1]))
        self.pump(3)
        isl = a.board.islands[0]
        self.assertAlmostEqual(isl.x, px - 1.27, delta=0.64)
        # resize from the top-right corner handle; the opposite corner stays put
        a.sel = {"island": 0}
        a.redraw()
        left, bottom = isl.x - isl.w / 2, isl.y - isl.h / 2
        h = a.w2s(isl.x + isl.w / 2, isl.y + isl.h / 2)
        self.assertIsNotNone(a.island_handle(*h))
        to = a.w2s(left + 3.81, bottom + 7.62)
        c.event_generate("<ButtonPress-1>", x=int(round(h[0])), y=int(round(h[1])))
        c.event_generate("<B1-Motion>", x=int(to[0]), y=int(to[1]))
        c.event_generate("<ButtonRelease-1>", x=int(to[0]), y=int(to[1]))
        self.pump(3)
        isl = a.board.islands[0]
        self.assertAlmostEqual(isl.w, 3.81, delta=0.01)
        self.assertAlmostEqual(isl.h, 7.62, delta=0.01)
        self.assertAlmostEqual(isl.x - isl.w / 2, left, delta=0.01)
        # the panel and the right-click menu
        a.show_props()
        self.pump(2)
        a.set_island(0, shape="round")
        self.assertEqual(a.board.islands[0].shape, "round")
        a.do_undo()
        self.assertEqual(a.board.islands[0].shape, "rect")

        class E:
            pass
        e = E()
        e.x, e.y = (int(v) for v in a.w2s(a.board.islands[1].x, a.board.islands[1].y))
        e.x_root, e.y_root = e.x + 50, e.y + 50
        a.context_menu(e)
        self.pump(2)
        m = a._menu
        labels = [m.entrycget(k, "label") for k in range(m.index("end") + 1) if m.type(k) in ("command", "cascade")]
        self.assertTrue(any(l.startswith("Island #2") for l in labels))
        self.assertIn("Make it round", labels)
        m.unpost()
        a.sel = {"island": 1}
        a.duplicate()
        self.assertEqual(len(a.board.islands), 3)
        a.delete_selection()
        self.assertEqual(len(a.board.islands), 2)

    def test_ground_fill_toggle(self):
        from solotrace import demos
        from unittest import mock
        a = self.app
        a.load_board(demos.flasher_555())
        self.pump(3)
        with mock.patch("solotrace.app.messagebox.askyesno", return_value=True):
            a.island_var.set(True)
            a._toggle_islands()
        self.assertTrue(a.board.settings.island_mode)
        self.assertTrue(all(pl.style == "dead" for pl in a.board.parts.values()))
        self.assertIn("ground fill on GND", a.status_var.get())
        a.island_dialog()
        self.pump(5)
        a.do_undo()
        self.assertFalse(a.board.settings.island_mode)


if __name__ == "__main__":
    unittest.main()
