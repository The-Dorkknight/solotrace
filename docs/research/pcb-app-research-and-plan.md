> **Note (2026-10-29):** this is the *original plan* written before the app was built. The app deviates from it in several places (pure Python instead of a C++ core, no floating slider pop-up, a simpler router than full PathFinder, 76 parts instead of about 60 with a different mix, `.solotrace` instead of `.solo`, laser output added). The honest list of what changed is in [DESIGN_NOTES.md](../../DESIGN_NOTES.md). The "Sources" at the bottom were checked when the plan was written.

# Single-Sided PCB App — Research & Plan

Oct 29, 2026 · @Matthew

## Summary

Build a single-sided, through-hole-first PCB editor where the board is drawn directly (no forced schematic), every bend is chamfered by construction, and the autorouter plans **topology and jumpers first** so results look hand-drawn instead of tangled. Working name: **SoloTrace** (alternatives: OneSider, Copperhead).

Three things set it apart from KiCad, EasyEDA and Fritzing:

1. **A small, honest library** of about 60 full-size parts (DIP, TO-220, TO-92, radial caps, axial resistors, terminal blocks) plus a 2-minute footprint wizard, instead of thousands of obscure SMD codes.
2. **Geometry rules baked into the data model**: traces 0.4 to 10 mm, set by clicking a segment and dragging a slider; 90° corners cannot exist, they are chamfered automatically; pads switch between drilled THT and a big no-drill "deadbug" surface-solder pad.
3. **A single-layer router that thinks like a person**: it counts crossings, suggests rotations to remove them, places the unavoidable crossings as straight wire jumpers at standard pitches, then lays rubber-band (topological) routes and only then turns them into 45° copper.

## Existing tools and the gap

The closest thing to this app already exists but is paid, Windows-only and has no smart single-layer router: Abacom's [Sprint-Layout](https://www.electronicsforu.com/technology-trends/sprint-layout-fast-focused-pcb-design-tool). Users rate it as far easier than KiCad, Eagle or DipTrace ([volt-nuts list](https://www.febo.com/pipermail/volt-nuts/2016-December/005090.html)), and it costs roughly 50 euro as a one-off licence.

| Tool | Good at | Why it fails this brief |
| --- | --- | --- |
| KiCad, EasyEDA, DipTrace | Professional multi-layer work | Huge SMD-heavy libraries, schematic-first, 1-layer + jumpers is a manual workaround |
| Eagle | Single-layer autoroute via "n.a." layer setting ([Parallax forum](https://forums.parallax.com/discussion/comment/548928)) | No jumper insertion, grid maze router, tangled output |
| DipTrace / Ultiboard | Can autoroute one layer | Users must place jumpers by hand or fake them as 0-ohm parts ([DipTrace forum](https://diptrace.com/forum/viewtopic.php?p=17512), [NI forum](https://ni.lithium.com/t5/Multisim-and-Ultiboard/net-bridge/m-p/485053)) |
| Freerouting | Strong free router, 45° and free-angle modes | Multi-layer thinking; KiCad users resort to a fake 3rd layer for jumpers ([KiCad forum](https://forum.kicad.info/t/autorouting-and-jumpers/11285)) |
| tscircuit | Has a real single-layer jumper autorouter ([docs](https://docs.tscircuit.com/guides/tscircuit-essentials/single-layer-jumper-autorouting)) | Code-first (you write the board in JSX), SMD-oriented |
| Sprint-Layout | Drawing-first, simple, isolation milling, photo view | Paid, Windows, no jumper-aware autorouter, allows 90° corners |

The gap is clear: nobody combines Sprint-Layout's draw-first simplicity with a jumper-aware, good-looking single-layer router, free and cross-platform.

## Autorouting: research and chosen approach

The tangled-string look comes from two root causes: routers start drawing copper before deciding the **topology** (which side of each pad a trace passes), and they route nets one at a time, so early nets block later ones. On one layer this is worse, because a crossing has nowhere to go except a jumper the router does not know about.

### Methods compared

| Method | How it works | Verdict for this app |
| --- | --- | --- |
| Lee / grid maze (A\*) | Flood a grid from pad to pad, net by net | Cheap and robust, but staircase paths and strong net-order dependence. Use only as a fallback inside a smarter loop |
| Rip-up and reroute | Route greedily, tear out blocked nets, retry | Helps, but results still depend on which nets you tear out and in what order ([PathFinder paper](https://www.esa.informatik.tu-darmstadt.de/archive/twiki/pub/Lectures/AlgorithmenImChipEntwurfDe/router-pathfinder.pdf)) |
| Negotiated congestion (PathFinder) | Let routes overlap at first, raise the price of shared space each pass, reroute every net every pass until nobody overlaps | Removes most net-order luck. Proven in FPGA tools and adapted to PCBs ([UCR escape routing](https://microfluidics.cs.ucr.edu/dmfb_static_simulator/escape_routing_algorithms)). **Adopt** |
| Topological / rubber-band | Decide each route as a path around obstacles, contract it like an elastic band, only then add widths and angles | Gives the shortest, hand-drawn look and converts cleanly to octilinear (45°) copper ([eevblog](<https://www.eevblog.com/forum/chat/which-eda-(schematicpcb)-package-do-you-use-(poll-discuss)/msg488621/>), [JITX](https://docs.jitx.com/essentials/autorouter.html), [Altium Situs](https://www.altium.com/documentation/altium-circuitmaker/automated-board-layout-situs-topological-autorouter)). Used by TopoR and the open [Topola](https://docs.rs/crate/topola/0.1.0) project. **Adopt for v2** |
| Planarisation first | Treat the netlist as a graph, embed as much of it as possible without crossings, insert the rest with fewest crossings | A 1970s Edinburgh method built exactly for single-sided discrete boards: build a "pseudo planar graph" so crossings are minimised before layout starts ([Edinburgh thesis](https://era.ed.ac.uk/handle/1842/6660)). Modern crossing heuristics exist too ([QuickCross](https://arxiv.org/pdf/1804.09900v2)). **Adopt: this is the jumper planner** |
| Virtual jumper layer | Give the router a fake second layer with a high cost; anything routed there becomes a wire link | The trick KiCad users suggest for Freerouting ([KiCad forum](https://forum.kicad.info/t/autorouting-and-jumpers/11285)); tscircuit's auto\_jumper does it natively. **Adopt in v1** |

### Chosen pipeline

1. **Untangle placement first.** A live counter shows ratsnest crossings (each one is a likely jumper). An "Untangle" button runs simulated annealing over rotations, flips and swaps of unlocked parts, scoring crossings x 10 + ratsnest length. Placement is the biggest lever on a single-sided board.
2. **Plan crossings (planarise).** Insert nets in priority order (power and wide nets first). Each unavoidable crossing becomes a jumper candidate. Free crossings are used first: a trace passing under an axial resistor body, or between DIP pins when the user allows it.
3. **Route.** v1: octilinear grid A\* in C++ with only 0° and 45° turns allowed, a jumper layer at high cost, all inside a PathFinder negotiation loop. v2: topological routing over a constrained Delaunay triangulation of pads and keep-outs, with the same negotiation on triangle edges.
4. **Realise copper.** Convert paths to 45° polylines, enforce clearance, chamfer every corner, widen to each net's target width, add teardrops, snap jumpers to standard pitches (multiples of 2.54 mm, minimum 7.62 mm).
5. **Report and hand back control.** Show jumpers, total length, tightest clearance. Manual traces stay locked; any net can be re-routed alone. One slider sets the trade-off "fewer jumpers / shorter traces".

Optional bridge: export Specctra DSN so people can compare against Freerouting. Freerouting and its Python port [freeroute](https://pypi.org/project/freeroute/) are GPL-3.0, so they run as separate programs and none of their code is copied into this one.

## Component library and custom parts

Ship about 60 parts named by what people call them ("Electrolytic cap, 5 mm pitch"), never by manufacturer codes. Every part is generated from a few parameters, so the library is small, consistent and easy to extend.

| Family | Parts (count) |
| --- | --- |
| Resistors and diodes (axial) | 1/4 W at 7.62 / 10.16 / 12.7 mm, 1/2 W, 1 W, 2 W, 5 W ceramic; 1N4148, 1N400x, 1N540x (11) |
| Capacitors | Ceramic disc 2.54 / 5.08 mm, film box 5 / 7.5 / 10 / 15 mm, radial electrolytic 2 / 2.5 / 3.5 / 5 / 7.5 mm, axial electrolytic, snap-in 10 mm (13) |
| Small semis | TO-92 (inline and triangle), TO-126, LED 3 mm and 5 mm, bridge rectifier round and inline (KBP / GBU) (7) |
| Power semis | TO-220 vertical and flat (2 and 3 pin), TO-220 with heatsink outline, TO-247, TO-3P, TO-3 (8) |
| DIP ICs and sockets | DIP-4, 6, 8, 14, 16, 18, 20, 24 narrow, 28 narrow and wide, 40 (11) |
| Connectors | Pin header 1xN and 2xN, screw terminal 5.0 / 5.08 / 7.5 mm, JST-XH, barrel jack, USB-B, DC power pads (8) |
| Electromechanical | Tactile switch 6 mm, slide switch, relay (small signal and 10 A), trimpot, rotary pot, crystal HC-49, buzzer, fuse holder 5x20 (9) |
| Board parts | Wire link (jumper), test point, mounting hole M3, solder pad, copper text, board outline (6) |

### Custom parts: decision

Not a free-form vector editor. Most "new" parts are a known shape with different numbers, so the cheap path is a **footprint wizard** plus a **grid pad editor**:

1. **Wizard** (covers about 90%): pick a template (axial, radial, inline, dual-row, TO-style, grid), type pin count, pitch, row spacing, lead diameter. Drill and pad size are worked out from the lead diameter, and a live preview updates as you type.
2. **Pad editor** (the rest): click on a 0.635 / 1.27 / 2.54 mm grid to drop pads, drag to move, draw a silkscreen outline with line and arc tools. That is a tiny, purpose-built vector editor, not Inkscape.
3. **Import** (power users): read a KiCad .kicad\_mod footprint (a simple text format) or an SVG with pads as circles in a named layer. Check the licence of any footprint before bundling it.

Parts are saved as one small JSON file each, in a user folder that the app watches; packs can be shared as zips through your drop-in plug-in system.

## Traces, chamfers and pads

### Trace width

Widths run from 0.4 mm (a safe minimum for toner transfer and home etching) to 10 mm, set by clicking.

- **Click a segment** (on the drawing or the 3D-ish copper view) and a slider pops up beside the cursor. The mouse wheel nudges it; it snaps to 0.4, 0.6, 0.8, 1, 1.5, 2, 3, 5, 7.5 and 10 mm, and holding Shift slides freely.
- **Double-click** selects the whole pad-to-pad run; **Ctrl+click** the whole net.
- While dragging, any clearance clash glows red and the slider stops at the widest legal value unless you override it.
- **Net classes** set defaults: Signal 0.8 mm, Power 2 mm, High current 5 mm. The router uses them, so power nets are routed first and fat.
- A small readout shows the approximate current the width carries, from the IPC-2221 external-layer formula (I in amps, ΔT in °C, A = cross-section in square mils):

```latex
I = 0.048 \, \Delta T^{0.44} \, A^{0.725}
```

| Width (mm) | Approx. current, 1 oz copper, 10 °C rise |
| --- | --- |
| 0.5 | 1.4 A |
| 1 | 2.4 A |
| 2 | 3.9 A |
| 5 | 7.7 A |
| 10 | 12.6 A |

These are my calculations from the formula, a guide only; the app will state the copper weight and temperature rise it assumes.

### Chamfered corners, always

The geometry kernel only stores directions in 45° steps, so a square corner cannot exist in the file. Wherever two segments meet at 90°, the corner is cut by a 45° chamfer at least twice the trace width long (minimum 1 mm, adjustable). Angles sharper than 90° (acid traps) are refused and repaired. T-junctions get 45° fill-ins, and traces meet pads with teardrops. A per-board option swaps chamfers for rounded arcs; a 90° option simply does not exist.

### Pads: drilled or deadbug

| Pad style | Shape | Use |
| --- | --- | --- |
| Through-hole (default) | Round; oval on DIPs; square for pin 1. Drill = lead + 0.2 to 0.3 mm, copper ring at least 0.6 mm | Normal drilled build |
| Surface-solder ("deadbug") | No drill, long oval pad roughly 2 to 3 times the area, sized per family (e.g. about 4 x 8 mm for TO-220 legs) | Legs bent flat and soldered on the copper side: no drilling at all |
| Mixed | Drilled pad with extra copper tab | Heavy parts that need both |

Style can be set per pad, per part or for the whole board. The app tracks which side the part sits on and whether it is upside down, and mirrors the pin order for you, because a mirrored pinout is the classic mistake when parts are mounted on the copper side.

## Workflow, file format and outputs

The board is the design: no schematic is required, so a simple circuit goes from idea to etch file in minutes.

1. **Set the board**: size, corner radius, mounting holes, copper weight.
2. **Place parts** from a searchable side panel with big thumbnails; R rotates, F flips to the copper side.
3. **Connect**: drag pin to pin to draw airwires (the netlist). Name a net by clicking it; give it a class (Signal / Power / High current). Optionally import a KiCad netlist later.
4. **Untangle**, then **Route all**, one net, or by hand. Manual routing always produces 45° chamfered copper.
5. **Check (DRC)**: clearance, minimum width, ring size, unrouted nets, jumpers listed with lengths.
6. **Export**.

### Views

Design view (colour per net) and a **copper view** that shows the board as it will look etched, mirrored or not, so trace clicks work on "the actual trace" as asked.

### File format

One human-readable JSON file per board (.solo), with parts, nets, traces as 45° polylines with per-segment width, jumpers, and settings. Parts are referenced by library ID and also embedded, so a board opens anywhere.

### Outputs

| Output | For |
| --- | --- |
| Gerber (RS-274X) + Excellon drill | Sending to a fab such as JLCPCB, single layer |
| PDF / SVG at 1:1, mirrored or not, with print scale check bar | Toner transfer, UV photo-resist film |
| Isolation-milling and drill G-code | Desktop CNC routers (later milestone) |
| Drill template STL | 3D-printed drilling jig for the holes (nice tie-in to your printers) |
| Placement sheet PDF + BOM CSV | Assembly and buying parts |

## Architecture and project standards

A tkinter front end over a C++ core, following your standards: double-click launchers for Linux, Windows and Mac, PolyForm Noncommercial ("source-available"), version and build time in the title bar, and the ErrCode hook.

- **Python / tkinter GUI**: canvas editor, library panel, footprint wizard, slider pop-ups, export dialogs. tkinter's canvas copes with a few thousand items, which is plenty for a 100-part single-sided board.
- **C++17 core** (via pybind11): the 45° geometry kernel (chamfers, clearance by polygon offsetting, e.g. with the Clipper2 library), the router (untangle, planariser, A\* with PathFinder, later topological), DRC and Gerber/G-code writers. Prebuilt for Linux x86-64, Windows x64 and Mac arm64.
- **Low-end target**: route a 160 x 100 mm, 60-part board in under 30 s on a 7th-gen Core i3, under 1 GB RAM. No GPU path: the problem is too small to need one. These are targets to test against, not measurements yet.
- **Libraries**: check licences of Clipper2 and any triangulation library before bundling; nothing GPL is linked in.

### Divergence check

No PCB project exists in your portfolio, so this is new. Related work to reuse rather than duplicate:

- **ImageToSketch** (FreeCAD tracer): its image tracing could later turn a photo of an odd part into a footprint outline.
- **SimpleCAD / SimpleMesh**: same "big obvious buttons" UI philosophy; share the theme.
- **Drop-in plug-ins**: part packs and extra exporters as plug-ins.
- **Your hardware projects** (caliper logger, SquawkBox, gamepad adapter, Angry Putty dongle) make good first test boards; consider adding footprints for the dev-board modules you use as 2-row headers.

## Milestones, risks and open questions

(The original roadmap chart is not included in this copy: 6 steps with 2 gates.)

The app is useful for hand routing after step 3; the autorouter is built on top, and v2 only starts once v1 matches a careful hand layout on five test boards.

| Risk | Mitigation |
| --- | --- |
| Topological routing is research-grade hard | Ship the grid router (v1) first; v2 is an upgrade, not a blocker |
| Printed transfers come out at the wrong scale | 1:1 calibration bar on every print; check it with calipers before ironing |
| Mirrored pinouts on copper-side or deadbug parts | Side and orientation shown on every part; copper view previews the real result |
| tkinter slows on large copper fills | Core renders copper to a cached image when zoomed out |
| Scope creep into schematics and SMD | Kept out of v1 by design |

### Open questions

- [ ] Name: SoloTrace, OneSider or Copperhead?
- [ ] How do you make boards (toner transfer, UV film, CNC, or a fab)? That sets export priority.
- [ ] Jumpers as bare wire links only, or allow 0-ohm resistors too?
- [ ] Allow a trace between DIP pins by default? It is tight at 2.54 mm pitch.
- [ ] Free like Shift-LoK, or a paid tier for some features?

## Sources

- [tscircuit: single-layer jumper autorouting](https://docs.tscircuit.com/guides/tscircuit-essentials/single-layer-jumper-autorouting)
- [KiCad forum: autorouting and jumpers](https://forum.kicad.info/t/autorouting-and-jumpers/11285)
- [DipTrace forum: single-layer routing with jumpers](https://diptrace.com/forum/viewtopic.php?p=17512)
- [NI forum: Ultiboard net bridges](https://ni.lithium.com/t5/Multisim-and-Ultiboard/net-bridge/m-p/485053)
- [Parallax forum: single-layer autoroute in Eagle](https://forums.parallax.com/discussion/comment/548928)
- [JITX: topological autorouter](https://docs.jitx.com/essentials/autorouter.html)
- [Altium CircuitMaker: Situs topological autorouter](https://www.altium.com/documentation/altium-circuitmaker/automated-board-layout-situs-topological-autorouter)
- [Topola: open topological router in Rust](https://docs.rs/crate/topola/0.1.0)
- [EEVblog: topology to any-angle, octilinear or rectilinear](<https://www.eevblog.com/forum/chat/which-eda-(schematicpcb)-package-do-you-use-(poll-discuss)/msg488621/>)
- [UCSC CRL-93-04: rubber-band router (Surf)](https://tr.soe.ucsc.edu/sites/default/files/technical-reports/UCSC-CRL-93-04.pdf)
- [McMurchie and Ebeling: PathFinder](https://www.esa.informatik.tu-darmstadt.de/archive/twiki/pub/Lectures/AlgorithmenImChipEntwurfDe/router-pathfinder.pdf)
- [UCR: negotiated congestion for PCB escape routing](https://microfluidics.cs.ucr.edu/dmfb_static_simulator/escape_routing_algorithms)
- [Edinburgh: computer-aided layout of single-sided boards](https://era.ed.ac.uk/handle/1842/6660)
- [Clancy et al.: QuickCross crossing minimisation](https://arxiv.org/pdf/1804.09900v2)
- [Freerouting on GitHub](https://github.com/freerouting/freerouting/)
- [freeroute: Python port of Freerouting](https://pypi.org/project/freeroute/)
- [Electronics For You: Sprint-Layout](https://www.electronicsforu.com/technology-trends/sprint-layout-fast-focused-pcb-design-tool)
- [volt-nuts list: Sprint-Layout user report](https://www.febo.com/pipermail/volt-nuts/2016-December/005090.html)
