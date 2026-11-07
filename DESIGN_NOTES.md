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
- **2026-11-06, request for 0.7.0:** "add common esp 8xx, esp32, rp2040 and arduino components both for through hole and deadbug, especially the postage stamp size esp c and s3; also the spi sd card reader and the 0.9x inch oled displays; add a mirror function for when we place for instance the display under the board. Mirrored must be highlighted to stand out." Built as 23 module footprints from sourced data (below) and Shift+M with a pink frame and tag.
- **2026-11-05, request for 0.6.0:** "please give this app a web ui when tk doesnt install properly it ruins users experience", plus: rename Pro to SMD with an SMD transistor icon, make the button a whole rectangle in the sidebar, and have it swap the whole list (SMD only, the button then reading Through-hole with a plastic transistor icon). Built as a headless session + local server + canvas page (below); the SMD / through-hole button in both UIs.
- **2026-11-05, request for 0.5.0:** "App is amazing but I have tokens to burn": research other autoroute/autoplace options and add anything better as a selectable option; deadbug ground pads with partial cut-outs that are easy to solder yet carry a fair current; vias / through-hole jumpers to use the back of a double-clad board as a ground plane "without making the back a big LC circuit"; and a "pro" button for the common large SMD parts, with the app staying "first and foremost a single layer non-SMD app with SMD options". Mid-way he added that the first reliefs "look a bit skinny" and the contact should be adjustable for high current "as ground usually takes heavy current": hence the 0.8 mm default, the "size for N amps" box, and the heavy / solid per-part choice. Four research notes were written first (docs/research/), with sources; what was built from them is below.
- Problems he found, and what changed: drawing a wire felt slightly slow (0.2.1: only the moving layer is redrawn); auto-route chained the ground net Q1 emitter -> C1 -> J1 instead of a thick trunk from Q1 to J1 with a branch to the capacitor (0.3.0: rigid wires, his idea of Shift + wire); the rubber bands were hard to see (thicker, edged lines); pins could not be labelled and values were hard to find (pin-label layouts, a bold value field); TO-92 outlines looked odd (D shape).

## Findings (with sources)

- The closest existing tool is a paid Windows program (Sprint-Layout); the free ones are multi-layer, SMD-heavy and weak at single-layer jumpers. Sources and the comparison table are in the research plan.
- "Tangled string" comes from routers that commit copper before choosing topology and route nets one after another. The literature offers rip-up and reroute, negotiated congestion (PathFinder), topological/rubber-band routing and planarisation; see the plan for links.
- Elegoo's manual names LaserGRBL and LightBurn, lists X 25 000 / Y 18 000 mm/min and spot sizes of 0.06 x 0.06 mm (10 W) and 0.07 x 0.13 mm (20 W), and says to set an origin; it does not mention homing, limit switches, GRBL or G-code. Details and links: [phecda-laser-notes.md](docs/research/phecda-laser-notes.md).

## Decisions, and what was rejected

| Decision | Chosen | Rejected, and why |
| --- | --- | --- |
| Module data (0.7) | **Only text sources**: makers' and well-checked community KiCad/Eagle/Fritzing files, datasheets and vendor pages, each number with a confidence word in docs/research/mcu-modules.md; pins labelled from the files' own pin names | Pinout pictures (cannot be checked by machine), memory (one wrong row spacing and the module will not plug in). Where only a footprint author's outline exists, it is used and the note says so; mounting holes that the sources disagree on are left out rather than guessed |
| Mirroring (0.7) | **The existing `flip` flag** (mirror about pin 1), with "mirrored" meaning *not on the part's usual side*; drawn in pink, a colour nothing else on the board uses | A separate "bottom" flag (two flags that could contradict each other); highlighting every copper-side part (every SMD part would be pink and the warning would mean nothing) |
| Web UI (0.6) | **A local HTTP server from the standard library plus a plain HTML/JS page**, the editor logic in a headless `Session` shared with nothing but the window removed, panels and menus sent to the page as data | A second GUI toolkit (Qt, wx): another install that can fail, the very problem being solved. Rewriting the editor in JavaScript: two copies of every rule (snapping, 45 degree traces, cut/trim/tidy, the fill) that would drift apart; so the page draws and the server decides. A third-party web framework: nothing may be installed. WebSockets: hand-written framing for a page that needs a few requests per second; plain POSTs and a short poll while a job runs are enough |
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
| Thermal reliefs (0.5) | Ring + spokes generated in the fill/plane paint order; KiCad's geometry (4 spokes, 0.5 mm ring, 45° on round pads, sides on ovals), spokes 0.8 mm by default and sizable for a current by the inverse IPC-2221 formula; per-part heavy / solid | Two-spoke reliefs (higher inductance, less current); per-pad relief settings (more UI than the problem needs); Eagle's "half the drill" rule alone (too thin for a ground that carries the return current) |
| Back-side plane (0.5) | A second paint-order layer: plane, antipads, reliefs; vias as points that are ground pads with a hole; connectivity by "drilled ground pins and vias are on the plane"; exports as top copper, non-mirrored prints and laser, plus a countersink list | Routing on the back (two-layer routing is a different program); plane as explicit polygons (clipping library needed); a via as a part in the library (a via is not a part and must take the ground net automatically) |
| LC / resonance worry (0.5) | A stitching grid with a frequency guide f = c/(20 s sqrt(er)) and the two-sentence explanation in the dialog; a DRC note on how far the existing joins are good for | Ignoring it (he asked), or a split ground (the EMC literature is unanimous: one plane, many connections) |
| SMD library (0.5) | Only packages with maker-sourced, labelled land patterns and 0.3 mm pad gaps; roomier wave-solder / level-A patterns; SMD parts flip to the copper side on placement; bottom silkscreen Gerber | Generating pads from IPC-7351 formulas (the standard itself was not accessible; no numbers invented); fine-pitch parts (SOT-363, TSSOP, TQFP: gaps under 0.3 mm, unmaskable); exposed-pad parts (cannot be soldered from the copper side) |
| Router option (0.5) | Negotiated congestion (PathFinder) on the existing grid and search: overlaps allowed, rising present and history costs, jumpers as a priced resource; "Auto" = negotiated then classic tries | Expansion-room / shove routers (FreeRouting: far too much code), rubber-band topological routing (right idea for one layer, no small open implementation of the geometric stage), keeping classic only |
| Placer option (0.5) | RUDY congestion + boxed-pad terms with VPR's adaptive schedule, kept as an *experimental* option because it measured no better | Force-directed or min-cut placement (built for scale this program does not have; needs a legaliser that would itself be an annealer) |
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

### 0.8: a web app, and collisions after moving a part

- **The browser is the default.** tkinter is the part of Python most often missing or broken, so `main.py` now always opens the web UI; the window is kept behind `main.py desktop`. Rejected: dropping the window (people use it, and it moves parts live).
- **No-install version with Pyodide, in a Web Worker.** The editor stays Python: one code base for the window, the local server and the browser. Rejected: rewriting the editor in JavaScript (two code bases to keep in step), Brython/PyScript on the main thread (the page would freeze during auto-route), shipping Pyodide in the repository (about 12 MB of someone else's build in every clone; the CDN version is pinned instead). `web/api.py` is the request handler shared by `server.py` and the worker, so the browser version answers exactly what the server answers; `Session(sync_mode=True)` runs jobs without threads and reports progress through a hook.
- **Collision finding.** Check itself never missed an overlap: on 64 random part moves over the routed examples it agreed with a brute-force comparison of every pair of copper shapes (`tests/test_collisions.py`). What was missing was any check *at the moment of the move*: dragging, turning, nudging, mirroring or dropping a part over laid copper said nothing until the next Check, and the part body of a mirrored module pressed flat on traces was never checked at all. Now both UIs mark collisions live while dragging and report them on drop, and Check has the body test.

## Measurements

### 0.8: has auto-route got lazier? (12 boards, 12 s budget, development machine)

The four examples that exist in every version (555 flasher, 5 V regulator, 555 power oscillator, logic mix), each as built and with two seeded random placements, saved by 0.3.4 and routed by each version with its default settings.

| Version | Jumpers (all 12) | Unrouted | Copper, mm |
| --- | --- | --- | --- |
| 0.3.4 (oldest in git) | 64 | 3 | 4 515 |
| 0.7.0 (= 0.8.0 before the fixes) | 44 | 0 | 4 509 |
| 0.8.0 (sorted rip-up order + polish) | 42 | 0 | 4 498 |

So no, by these numbers: fewer jumpers, nothing left unrouted, the same copper. Per board the newer router is sometimes longer on the small boards (5 V regulator moved: 323 mm with 3 jumpers in 0.3.4, 366 mm with 2 now) because the best-of score puts fewer jumpers before shorter copper. A weighted score (a jumper worth about 30 mm of copper) was considered and not done: it would pick more jumpers on exactly those boards, and jumpers are what people want fewer of. Versions before 0.3.4 are not in the repository and were not measured.

Found on the way: results changed from run to run. The rip-up step rerouted its victims in the order of a Python `set` of net names, which depends on `PYTHONHASHSEED` (random for every start of Python): the moved regulator board routed as 2 jumpers / 366 mm, 3 / 351 mm and 4 / 269 mm under three seeds. The victims are now sorted; three seeds give identical copper (tested). The polish pass (each net rerouted once against the finished board, kept only if strictly better, at most two passes) runs only on the winning try, so it does not use up the time for more tries; on these boards it removed 2 jumpers and shortened the logic boards by 2 to 4 %.


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

### Router and placer options (0.5.0)

Eleven boards, each placed once and saved, then routed by each algorithm from the same placement, on the development machine with nothing else running (`tools/` has no benchmark script; the boards were the five demos plus six random boards of 12 to 30 parts). Classic = best of 6 net orders within its 12 s budget; negotiated = one run; auto = negotiated, then the classic tries only if needed.

| Algorithm | Unrouted connections | Jumpers | Copper length | Time |
| --- | --- | --- | --- | --- |
| Classic | 3 | 53 | 4993 mm | 78 s |
| Negotiated | 0 | 55 | 4402 mm | 52 s |
| Auto | 0 | 54 | 4471 mm | 99 s |

Per board the negotiated router was better or equal on nine of the eleven (logic demo 5 jumpers instead of 7 and 383 mm instead of 466; power oscillator 237 mm instead of 296); it was worse on the one genuinely non-planar random board (19 jumpers against 14 to 16), and *auto* does not recover that because the negotiated run alone uses up the time budget there. Earlier variants of the jumper pricing (jumpers allowed from the first pass; allowed only once the price reached 2, 3 or 4) gave 71, 54 (3 unrouted), 53 (2 unrouted) and 61 jumpers; the shipped setting (allowed once the price reaches 1, at five times the usual cost) was the only one with nothing unrouted and no jumper penalty. The classic router's numbers move by a jumper or two between runs because its time budget decides how many tries happen; in one run on the non-planar board it also produced a layout with one DRC clearance error that could not be reproduced afterwards.

Placer, same method (place for 15 s, route with classic, 11 boards): annealing 73 ratsnest crossings, 1 unrouted, 69 jumpers, 55 s; routability 119 crossings, 3 unrouted, 57 jumpers, 133 s. Fewer jumpers in total but more crossings and more unrouted, and twice the time: not better, so it stays experimental and off by default. Weight tuning (RUDY 0.5 / boxed 5, RUDY only, boxed only) on three boards did not change the picture.

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

### The web UI (0.6)

- **The page is a thin client.** `scene()` sends every copper shape in paint order (capsules and polygons in mm, Y up, with net and tag), the plane and fill plans, outlines, pin-label anchors, rubber bands, vias, marks and the tool state; the page draws it with canvas 2D and the same colours as theme.py. Hit testing, snapping, trace finishing, cut/trim/tidy, dialogs and menus all run on the server, so a rule changed in board.py or tidy.py changes both UIs. The page keeps only what has to follow the mouse without a round trip: pan and zoom, the ghost of a dragged part / island / via / trace section, the next trace leg (`snap_dir` is the one function ported to JavaScript, 12 lines), the wire rubber band and the placing ghost (the armed part's shapes at the origin, translated).
- **Panels, menus and dialogs as data.** The selection panel is a list of widgets (`head`, `label`, `entry`, `select`, `check`, `radio`, `slider`, `button`, `row`); the right-click menu a list of `{label, cmd, args, sub, checked, disabled}`; a dialog a list of fields plus the command that applies them. The page renders them generically, so the desktop panels and the web panels show the same choices without a second copy of the logic.
- **Drag = ghost + one command.** A press answers with what was picked up (`{"ref": ...}`, `{"trace": ..., "seg": ...}`, `{"island": ..., "resize": ...}`); the page draws a ghost while the mouse moves and sends `drag_to` once when it is let go. The desktop window moves things live, which is nicer for traces (the branches follow); the ghost keeps the server traffic to two requests per drag. The mouse can move on before the press has been answered, so the page counts that movement too (a fast drag used to end as a click).
- **The ground fill's second pass.** The desktop window computes the full fill (floating copper removed) 0.4 s after the last edit; the session does the same in a background thread while the page polls `fill_ready`, so a quick plan is drawn at once and the final one a moment later, as in the window.
- **Jobs.** Auto-place and auto-route run in a thread on a copy of the board, exactly as in the window; the page polls every 0.4 s for the progress text and the result is applied on the next request after the job ends.
- **Hover is a request too** (`hover`, throttled to about 15 per second and never queued more than one deep); it returns the net under the mouse and what the hit test found, so the page can highlight the net and pick the cursor. On a ground-fill board with 500 copper shapes it takes a few milliseconds.
- **Fuzzing the session** (`cmd` with random names and random, often wrong, arguments on all eight example boards, 400 steps each, several seeds) found: negative indexes reaching a list (Python counts from the end), a split at the very end of a trace leaving a one-point trace that then broke tidy, a pending wire pin whose part had been deleted, and a dialog name that was not one. All fixed; the server also catches anything a command raises and shows it to the page rather than dying.
- **Security.** The server binds 127.0.0.1 and refuses any request whose `Host` is not the local address (a web page elsewhere cannot make the browser talk to it by name), serves only files inside `static/`, and reads only the JSON body it is given. There is no authentication beyond that; another program on the same computer could talk to it, as it could to the window.

### Edge-case sweep (0.4.1)

`tools/` has no fuzzer in the repo; the sweep scripts were throwaway. What they did, so it can be repeated: (1) about 400 random boards (3 to 9 random parts, 0 to 8 random islands including off-board and sub-minimum ones, random fill settings and ground net including a non-existent one), each checked before and after auto-route that fattening never closes a gap and that a floating cut never covers a ground pin, then exported to Gerber, SVG, PDF, BOM and G-code in all three laser modes (with crosshatch and trace adjust), and round-tripped through the file format; (2) about 4 000 random editor actions on the four demo boards with the Tk error hook recording any exception. Neither found a crash after the fixes; the bugs listed in the changelog came from the targeted checks and from reading the code. Timing of the fill check, 160 x 100 mm board with 574 copper shapes: 0.95 s full, 0.02 s without the floating check; a 0.1 mm sampling step would have saved only a quarter, so the check was moved off the editing path instead.

## Tried and dropped (0.2)

- **"No worse" by count.** The first tidy version accepted a reshaped trace if it touched no *more* shapes than before. On a board where a 5 mm trace already overlapped a thin one, the thin trace was then re-pathed straight across the wide one: the same count, but a new short. Now a reshaped trace may only touch copper of nets it was already too close to, and thin traces are only allowed to move their end onto the pad centre, never to shortcut.
- **Comparing by shape tag** in that rule also failed in a test, because trace numbers change when other traces are tidied; the test now compares by net.
- **Tool button labels with the shortcut key** ("Select  S") made the tool bar wider than a 1280 px window; the keys moved into the hover hints.

Found while making the power-oscillator demo (0.3): a 2.5 mm power net could not be routed from the middle pin of a TO-220, because at 2.54 mm pitch a trace that wide plus 0.3 mm clearance does not fit between the neighbouring pads (it misses by 0.01 mm at 2.5 mm). The demo uses 2 mm; a "neck-down" that narrows the first millimetres near a pad is on the ideas list.

## Not tested (be honest)

- **The in-browser version (0.8)** was tested in headless Chromium with a local copy of the npm package `pyodide@0.29.5` (the same files the CDN serves), not with the CDN itself: the build machine's network does not reach `cdn.jsdelivr.net`. Firefox, Safari and phones have not been tried. Speed on a slow laptop has not been measured.
- **Module footprints (0.7)** have not been etched and had a real module plugged in. The SuperMini's position along its board (about 1 mm of disagreement between sources), the Waveshare Zero outlines, the DOIT outline, the 0.96 inch SPI OLED header position and the SD modules' pin orders are single-source or disputed; the part notes say so.

- **The web UI (0.6)** has been driven by unit tests, a headless-Chromium test and the screenshot script only; no person has designed a board in it, and no browser other than Chromium has shown it (Firefox and Safari should be fine: canvas 2D, fetch and plain CSS, no libraries, but it has not been looked at). The no-tkinter fall-back was exercised with a Python 3.13 that really has no tkinter and with tkinter blocked in the tests; the launchers' "tkinter missing" branches were not run on Windows or macOS.
- **Real laser, real Phecda, real etching.** All laser defaults (1 500 mm/min, 70 %, 0.08 mm interval, 0.6 mm gap) are starting guesses.
- That the Phecda's controller behaves like GRBL (`$30`, `$32`, M4 dynamic power).
- Windows and macOS launchers and the macOS Tk; GitHub workflows (never run).
- Gerber files in a fab's own CAM or a second viewer.
- 7th-gen Core i3 speed; large boards (above about 40 parts).
- The Trace and Jumper tools have had light manual testing only. Trace dragging, trim and the right-click menus have been tested with scripted mouse events, not by a person.
- The new generic footprints (standing resistors and diodes, inductors, 5.08 mm pot, triangle trimmer) are not measured against real parts.
- Tooltips and the right-click menu on Windows and macOS (Tk draws menus natively there, so colours will differ).
- Part outlines (silkscreen) are approximate; check against the real part.
- Thermal reliefs, the back-side plane, vias and the SMD parts (0.5): tests, examples and screenshots only. Nobody has soldered a relieved pad, drilled a via, countersunk a plane or placed an SMD part from this library. The relief current figures are the IPC-2221 formula, conservative for short spokes, not measurements. The SMD pad sizes are the makers' recommendations; two inductor patterns and the SMD electrolytics were read off drawings whose labels did not survive extraction (the research note says which).
- The negotiated router was measured on eleven boards on the development machine only; the classic router's results vary a little between runs because its 12 s time budget decides how many of the six tries happen.
- Copper islands and the ground fill (0.4): only tests, the examples, screenshots and gerbonara. Nobody has etched, lasered or soldered such a board yet, and the 0.05 mm sampling leaves slivers of fill below about 0.01 mm² (too small to etch).

## Ideas

- Native accelerator for the router and placer (a small C library loaded with `ctypes`, with the pure-Python code kept as the fallback so double-click still works without a compiler). Pre-built libraries for Linux, Windows and macOS would come from the GitHub release workflow. The A* search, the obstacle maps and the annealing loop are the hot spots.
- A topological (rubber-band) router for a hand-drawn look; the negotiated router (0.5) covers the PathFinder half.
- Routability placer: tune the weights against routed jumper counts rather than crossings, or drop the RUDY term and keep only boxed pads; a force-directed first placement to seed the annealer.
- Back plane: a second routing layer is out of scope, but a few *back-side jumper traces* (short straight runs on the plane with their own clearance) would remove most jumpers on a double-clad board.
- SMD: pin-1 markers in the bottom silkscreen export; an "exposed pad" footprint once there is a way to solder it (a through-hole slug via).
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
python3 tools/take_web_screenshots.py                                      # needs Playwright + Chromium; rebuilds docs/images/web-ui*.webp
```

The GUI tests need a display (`xvfb-run` on a headless machine) and a Python with tkinter.
