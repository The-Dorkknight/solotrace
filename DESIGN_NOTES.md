# Design notes

**WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN.** These notes are for anyone who wants to know *why* SoloTrace is built this way, what was measured, and what has not been tested. Plain-English behaviour is in [HOW_IT_WORKS.md](HOW_IT_WORKS.md). The original research and plan (written before the code) is in [docs/research/pcb-app-research-and-plan.md](docs/research/pcb-app-research-and-plan.md) and the laser-machine facts are in [docs/research/phecda-laser-notes.md](docs/research/phecda-laser-notes.md).

## Goals

1. A small, readable library of **real full-size parts** (30 to 100) instead of thousands of SMD codes.
2. **Easy custom parts** without learning a vector editor.
3. **Trace width 0.4 to 10 mm** by clicking a trace and moving a slider.
4. **Deadbug pads** (no drill, extra copper for surface soldering).
5. An **autorouter whose output does not look like tangled string**.
6. **Never a pure 90° trace corner.**
7. **Laser output for a gantry diode laser (Elegoo Phecda)** with a negative option and adjustable gap.
8. Runs on a **7th-generation Core i3** with nothing to install beyond Python.

## Real use

- **2026-10-29, the author:** designed his childhood LM555 astable power oscillator (it drives a high-voltage transformer) in about **5 minutes**; he estimates the same board would have taken about **2 hours** in other PCB programs. Tested on an i5 laptop with 8 GB of RAM.
- **Same day, 0.3.0 on his oscillator board:** "routing got far worse", with tracks that disappear and overlap and forced jumpers. Rebuilt from his photo in `tests/test_edit.py` (`test_branches_join_existing_copper_instead_of_running_over_it`). Cause: a net that was partly routed and then re-routed after a rip-up did not count its existing copper, so new traces ran over it (an old bug that rigid wires triggered more often). Fixed in 0.3.1, together with retries, optional jumpers, a small cost for routing under part bodies, and the Cut tool he asked for. He also explained that "rigid" was meant as "always join A to B directly", not "a stiff straight line"; the docs now say so.
- **Evening, 0.3.1:** "much better", but next to the rigid trunks branches looked repelled and malformed: stubs stopping short of a trunk, one overshooting it, a loose blob on a capacitor pad, and a trunk running through the middle of the 555. Cause: the tidy pass (and corner smoothing) reshaped a wide trunk after its branches had been joined to it. Fixed in 0.3.2 with a "keep joints" rule, a DRC "dangling" warning and the keep-out option; regression tests in `tests/test_edit.py` (`KeepJoints`, `Dangling`).
- **Night, 0.3.4:** a board saved in 0.3.3 reopened fine and routed "much better, completely workable"; the remaining wish was for rigid trunks to merge with their branches ("not a true bool union"). Copper was already merged in the exports; the editor drew rigid copper in its own colour on top, and wide branches poked out of narrow trunks. 0.3.5: one colour plus a thin marker line, branch ends settled inside the trunk, branches follow a dragged trunk (`TrunkAffinity` tests).
- **2026-10-31, request for 0.4.0:** "a deadbug island mode for quick and dirty RF designs". A first take built a ground fill with every net cut out as an island; he then said he was "thinking more just round / rectangular / circular pads which are resizable and draggable", and asked to keep both. So 0.4.0 has copper islands (the pads he meant) and the ground fill (renamed from "deadbug islands" so the two are not confused).
- Problems he found, and what changed: drawing a wire felt slightly slow (0.2.1: only the moving layer is redrawn); auto-route chained the ground net Q1 emitter -> C1 -> J1 instead of a thick trunk from Q1 to J1 with a branch to the capacitor (0.3.0: rigid wires, his idea of Shift + wire); the rubber bands were hard to see (thicker, edged lines); pins could not be labelled and values were hard to find (pin-label layouts, a bold value field); TO-92 outlines looked odd (D shape).

## Findings (with sources)

- The closest existing tool is a paid Windows program (Sprint-Layout); the free ones are multi-layer, SMD-heavy and weak at single-layer jumpers. Sources and the comparison table are in the research plan.
- "Tangled string" comes from routers that commit copper before choosing topology and route nets one after another. The literature offers rip-up and reroute, negotiated congestion (PathFinder), topological/rubber-band routing and planarisation; see the plan for links.
- Elegoo's manual names LaserGRBL and LightBurn, lists X 25 000 / Y 18 000 mm/min and spot sizes of 0.06 x 0.06 mm (10 W) and 0.07 x 0.13 mm (20 W), and says to set an origin; it does not mention homing, limit switches, GRBL or G-code. Details and links: [phecda-laser-notes.md](docs/research/phecda-laser-notes.md).

## Decisions, and what was rejected

| Decision | Chosen | Rejected, and why |
| --- | --- | --- |
| Language | **Pure Python 3 + tkinter**, standard library only | C++ core with pybind11 (the original plan): needs compilers on three systems, which breaks "double-click and run". The router is the part that suffers (see measurements). A C++ accelerator can come later behind the same interface |
| Custom parts | Footprint wizard (pad table, click-to-add, presets) + KiCad `.kicad_mod` import | Full vector editor: much more code, more ways to make a footprint that does not fit |
| Copper model | Capsules and polygons, unioned only when exporting | Raster or polygon-clipping library: heavy, and capsules make exact clearance and exact laser scanlines easy |
| Corners | `Board.add_trace` always chamfers; DRC flags turns over 46° | Allow 90° and warn: the brief said MUST |
| Router | Heading-aware A* on a 0.635 mm grid, 0/45/90 moves, rip-up and reroute, jumper pass | Plain Lee/maze (staircases), full PathFinder, topological router (see below) |
| Jumpers | Wire links on the component side in 2.54 mm steps | 0 Ω resistors as jumpers: same effect, but harder to see and count |
| Width UI | A slider in the right panel plus presets, scope = section / trace / net; preset widths also on the right-click menu | A floating pop-up beside the cursor (the plan): more fiddly in tkinter, deferred |
| Wide-trace shape (0.2) | A tidy pass after routing and after width changes: centred ends, straight axis-aligned pad exits of about pad radius + width, chamfers that may not eat those exits | Routing wide nets with a "leave pads straight" cost inside A*: the grid route is found at the routing width, but the bug report was about traces widened *afterwards*, so a geometric pass that also runs after slider changes covers both |
| Trace dragging (0.2) | Move one section parallel to itself; neighbours keep their direction and stretch (line intersection); pad ends get a 45° link; then chamfer | Free vertex dragging: easy to make non-45° segments. Push-and-shove of other traces: much more code, left for later |
| Trim (0.2) | Remove one section; the pieces either side stay as separate hand-drawn traces | Trim to the nearest junction or pad: harder to predict what disappears |
| Parts panel (0.2) | `ttk.Treeview` grouped by form factor with sub-groups and drawn icons, plus a canvas preview in the sidebar | Thumbnail grid: needs much more room; pop-up preview: the request was "no pop-ups" |
| Keeping joints (0.3.2) | Reshape a trace only if its touch set (pads, traces, jumper pads of its net) is kept and branch ends stay as deep; fall back to centring the end | Re-running the router after tidying, or moving the branches along with the trunk: more code, and moving copper the user did not touch is what caused the complaint |
| Better results (0.3.1) | Best of up to six tries with shuffled net orders and two under-part costs, scored by unrouted count, then jumpers, then length | A real negotiated-congestion router (PathFinder): still the long-term plan, but retries fixed the boards we have now at the cost of time |
| Power trunks (0.3) | Explicit rigid pairs routed first, then the rest of the net branches off them (pins connect to the nearest node of the trunk, which the router already allows) | A Steiner-tree router for wide nets, or always picking the two farthest pins as the trunk: guesses what the designer means; the explicit pair is predictable |
| Pin labels (0.3) | Per-form-factor lists of common layouts plus free text, stored per placed part; defaults only where every part of that shape agrees (diode K A, electrolytic + -) | A database of real part numbers and their pinouts: big, licence questions, and wrong for the many parts that share a package but not a pinout |
| Look (0.2) | ttk "clam" theme with a dark tool bar, copper / teal / blue / red action buttons, a status badge, and a canvas whose corners are painted over in the panel colour (fake 12 px fillet) | A custom-drawn widget set: lots of code for the same effect |
| Copper islands (0.4) | A new board object (round, oval or chamfered rectangle) that takes the net of whatever copper touches it, so it needs no net assignment UI and DRC finds shorts for free | Islands as parts in the library (fixed sizes, a "pin" to wire); or asking the user for each island's net: more clicks, and a wrong choice silently disagrees with the copper |
| Ground fill (0.4) | A paint order instead of polygon clipping: fill rectangle, then every non-ground shape grown by its growth + gap in bare board, then the fattened copper and all copper. Gerber does the same with clear polarity (`%LPC*%`), the laser engine with interval arithmetic per scan line, the canvas, SVG and PDF by drawing order | A polygon-clipping library (pyclipper or shapely): not in the standard library, which breaks double-click and run; writing a robust clipper: a lot of code for the same pictures |
| Fattening (0.4) | Per shape: grow g = min(wanted, edge room, distance to ground copper - gap, (distance to other nets - gap) / 2), so two growing shapes can never close the gap | One growth for the whole board limited by the tightest spot: a single cramped pin pair would stop every other net from growing |
| Floating fill (0.4) | Sample the fill on lines 0.05 mm apart, join overlapping intervals into pieces (union-find), cut away pieces no ground pin sits on with one polygon per chain of rows, then repeat across the other axis for slivers thinner than a row | Leave floating copper (it couples noise into RF circuits); one rectangle per row (hundreds of shapes and hairline seams in prints) |
| Laser | Exact scanline intervals computed from the shapes | Rendering a bitmap and tracing it: blurry edges, no exact "trace adjust" |
| Gerber | Round-aperture strokes + region fills, RS-274X, X2 attributes | Aperture macros for capsules: more to go wrong in viewers |
| Netlist | Wire pin to pin, no schematic | A schematic editor: far outside "easy" |
| Library | 90 parts, generated from a few parameters | Importing a big library: licences and obscure part codes |

### What the plan said and what was built

| Plan | Built |
| --- | --- |
| About 60 parts, C++ core | 90 parts, pure Python |
| PathFinder negotiated congestion | Rip-up and reroute with per-net limits; **no history costs** |
| Planarisation step | Folded into the placer (crossings in the cost) and the jumper fallback |
| Topological routing (v2) | Not started |
| Floating slider pop-up, mouse-wheel nudge, Shift for free value | Right-panel slider + presets + right-click presets |
| `.solo` file | `.solotrace` JSON |
| Drill template STL, Specctra DSN export | Not built |
| Part packs through drop-in plug-ins | Not built (user parts folder instead) |
| (not in the plan) | Laser G-code, test cards, frame file, auto-placer, netlist text, KiCad footprint import; in 0.2: trace drag, trim, split, tidy, right-click menus, autosave, recent files |

## Measurements

All on the cloud sandbox CPU, **not** on a 7th-gen Core i3; expect it to be slower there, by an amount nobody has measured.

| Board | Auto-place | Auto-route | Result |
| --- | --- | --- | --- |
| 555 flasher, 70 x 50 mm, 8 parts | 4.1 s | 0.1 s | all 7 nets, 0 jumpers, DRC clean |
| 5 V regulator, 70 x 45 mm, 6 parts | 2.1 s | < 0.1 s | all 4 nets, 2 jumpers, DRC clean |
| Logic mix, 80 x 60 mm, 8 parts + header | about 7 s | 3.5 s | depends on the placement seed: seed 3 (the shipped example) routes everything with 10 jumpers, DRC clean; seed 2 leaves net G unrouted, seeds 4 and 5 leave net D unrouted |
| Random board, 12 parts / 74 pins | 6.4 s | 2.9 s | all 18 nets, 5 jumpers, DRC clean |
| Random board, 25 parts / 118 pins | 7.3 s | 6.4 s | all 29 nets, 6 jumpers, DRC clean |
| Random stress board, 40 parts / 178 pins | 12.7 s | 33.1 s | 2 nets left unrouted, 25 jumpers |

With the 0.3.1 retries (best of up to six tries, sandbox CPU): 555 flasher 0.1 s (first try was perfect), 5 V regulator 6.9 s (2 jumpers), power oscillator 0.2 s, logic mix 16 s (7 jumpers instead of 10), the rebuild of the bug-report board about 8 s (1 jumper, nothing unrouted; with jumpers switched off, 1 connection is left for hand routing). On seven test boards the unrouted connections went from 2 to 0.

Laser (default settings, `examples/`): 555 board 625 scan lines, negative about 27 min and isolation about 4.5 min by the program's own estimate; 5 V board 24 min / 3 min; logic board 36 min / 8 min. Estimates are distance over feed plus rapids and are not measured on a machine.

Tests: 48 pass (`python3 src/main.py selftest`), including a test that re-reads the exported Gerber and drill files with the independent `gerbonara` library (skipped if it is not installed), chamfer and 45° rules, DRC detection, DRC cleanliness of the routed 555 and regulator demos, pad clearance of all 90 parts in all three pad styles, laser mode geometry (negative burns more than isolation, trace adjust widens gaps, crosshatch doubles the work), G-code sanity, test cards, scripted GUI sessions (place, wire, route, click a trace, move the slider, deadbug toggle, open the dialogs, the parts tree and preview, the right-click menu, dragging a trace with the mouse, trimming), and the 0.2 trace edits: the board from the bug report gets straight pad exits and centred ends at 2 mm, tidying never adds clearance problems with nets it was not already touching (1.5, 3 and 5 mm), dragging keeps every segment at 0/45/90°, trim and split keep the right pieces, and tidy is idempotent.

### Drawing speed (0.2.1)

A slowdown while drawing a wire on an i5 laptop with 8 GB was reported. Profiling a 40-part board showed the cause was not the speed of Python but the drawing strategy: every mouse move deleted and recreated about 6 600 canvas items (most of them grid points drawn as two little lines each), about 97 ms per move. The fix keeps the board as a static layer and redraws only a small "dynamic" layer (rubber band, ghost part, trace preview, hovered net) on mouse moves; grid points became one item each and only the visible ones are drawn; rubber-band lines are cached until the board changes.

| Measured in the sandbox, 40-part random board | Before | After |
| --- | --- | --- |
| Mouse move while drawing a wire | about 97 ms | about 6 ms |
| Mouse move with the Select tool (hover highlight) | not measured (it did a full redraw whenever the hovered net changed) | about 5 ms |
| Full redraw (after an edit, zoom or pan) | about 97 ms | about 29 ms |

Moving the drawing to C would not have helped: the time was spent inside Tk creating canvas items, which is already C. C would help the router and the placer; see Ideas.

## Design details worth knowing

- **Heading in the router state.** The A* state is position *and* direction, with a turn cost, so a 90° bend becomes two 45° turns and long straight runs win over staircases.
- **Exact check after the grid search.** A grid path is only accepted after it has been checked against the real copper shapes and clearances; if it fails, the cell or edge responsible is forbidden and the net is searched again. This is slower than trusting the grid but stops wide traces clipping neighbours.
- **Deadbug pads grow outward.** The extra copper (about 2.2 mm) extends away from the part and is clamped by neighbouring pads; rows of three or more fold perpendicular to the row. The library test checks every part in all three styles keeps at least 0.25 mm between pads.
- **Width of an unrouted net.** Clicking the yellow rubber-band line creates a net class named after the width (for example "2.5 mm"), so the router uses it.

- **Ground fill with clear polarity.** The Gerber copper layer of a filled board is: a dark region (the fill), `%LPC*%`, the cut shapes, `%LPD*%`, then the copper. The independent gerbonara library read this back with 63 clear and 120 dark objects for the RF example and drew it as expected; no fab CAM has seen it yet.

## Tried and dropped (0.2)

- **"No worse" by count.** The first tidy version accepted a reshaped trace if it touched no *more* shapes than before. On a board where a 5 mm trace already overlapped a thin one, the thin trace was then re-pathed straight across the wide one: the same count, but a new short. Now a reshaped trace may only touch copper of nets it was already too close to, and thin traces are only allowed to move their end onto the pad centre, never to shortcut.
- **Comparing by shape tag** in that rule also failed in a test, because trace numbers change when other traces are tidied; the test now compares by net.
- **Tool button labels with the shortcut key** ("Select  S") made the tool bar wider than a 1280 px window; the keys moved into the hover hints.

Found while making the power-oscillator demo (0.3): a 2.5 mm power net could not be routed from the middle pin of a TO-220, because at 2.54 mm pitch a trace that wide plus 0.3 mm clearance does not fit between the neighbouring pads (it misses by 0.01 mm at 2.5 mm). The demo uses 2 mm; a "neck-down" that narrows the first millimetres near a pad is on the ideas list.

## Not tested (be honest)

- **Real laser, real Phecda, real etching.** All laser defaults (1 500 mm/min, 70 %, 0.08 mm interval, 0.6 mm gap) are starting guesses.
- That the Phecda's controller behaves like GRBL (`$30`, `$32`, M4 dynamic power).
- Windows and macOS launchers and the macOS Tk; GitHub workflows (never run).
- Gerber files in a fab's own CAM or a second viewer.
- 7th-gen Core i3 speed; large boards (above about 40 parts).
- The Trace and Jumper tools have had light manual testing only. Trace dragging, trim and the right-click menus have been tested with scripted mouse events, not by a person.
- The new generic footprints (standing resistors and diodes, inductors, 5.08 mm pot, triangle trimmer) are not measured against real parts.
- Tooltips and the right-click menu on Windows and macOS (Tk draws menus natively there, so colours will differ).
- Part outlines (silkscreen) are approximate; check against the real part.
- Copper islands and the ground fill (0.4): only tests, the examples, screenshots and gerbonara. Nobody has etched, lasered or soldered such a board yet, and the 0.05 mm sampling leaves slivers of fill below about 0.01 mm² (too small to etch).

## Ideas

- Native accelerator for the router and placer (a small C library loaded with `ctypes`, with the pure-Python code kept as the fallback so double-click still works without a compiler). Pre-built libraries for Linux, Windows and macOS would come from the GitHub release workflow. The A* search, the obstacle maps and the annealing loop are the hot spots.
- History costs (PathFinder), then a topological router for a hand-drawn look.
- Floating slider pop-up; copper pours; soldermask layer; drill-guide STL for 3D printers.
- Push-and-shove when dragging; dragging a single corner; teardrops where wide traces meet small pads.
- Neck-down: let a wide trace narrow automatically where it leaves a fine-pitch pad.
- Pin labels and values in the silkscreen exports (needs a small stroke font for Gerber).
- Let auto-route choose straight pad exits itself for wide nets (a cost in the search) so the tidy pass has less to do.
- Part packs as plug-ins; flip parts to the copper side for deadbug builds.
- Islands: more shapes (L-shapes by joining rectangles already work), "make an island under every pin of this net", and a stitched fill (several pieces joined by jumpers automatically).
- Laser: exposure-test presets per paint type once real data exists; air-assist and focus notes.

## How to test a change

```
python3 src/main.py selftest                       # or: xvfb-run -a python3 -W ignore -m unittest discover -s tests
python3 tools/make_examples.py                     # rebuilds examples/ from the demos; look at the DRC lines
xvfb-run -a -s "-screen 0 1280x840x24" python3 tools/take_screenshots.py   # needs ImageMagick; rebuilds docs/images/gui-*.webp
```

The GUI tests need a display (`xvfb-run` on a headless machine) and a Python with tkinter.
