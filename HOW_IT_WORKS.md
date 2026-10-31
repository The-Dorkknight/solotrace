# How SoloTrace works

**WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN.** This page explains in plain English what the program reads, what it writes, and what it never does. For the reasoning behind the choices see [DESIGN_NOTES.md](DESIGN_NOTES.md).

## What it reads and writes

| It reads | When |
| --- | --- |
| `.solotrace` board files | File > Open, or a path given on the command line |
| Netlist text files | File > Import netlist text |
| KiCad `.kicad_mod` footprints | Parts > Import KiCad .kicad_mod |
| Your own parts in `~/.solotrace/parts/*.json` | At start |
| `~/.solotrace/config.json` | At start (notice accepted, last laser settings, recent files) |
| `~/.solotrace/autosave.solotrace` | Only when you pick *File > Recover autosave* |

| It writes | When |
| --- | --- |
| `.solotrace` board files | File > Save (a board is plain, readable JSON that also embeds its part shapes, copper islands and ground-fill settings, so it opens anywhere) |
| Gerber zip, PDF, SVG, BOM CSV, netlist text, G-code files | Only when you pick an Export menu item and choose a file name |
| `~/.solotrace/parts/*.json` | When you save a footprint in the wizard |
| `~/.solotrace/config.json` | When you accept the first-start notice, export laser code, or open/save a board (recent files list) |
| `~/.solotrace/autosave.solotrace` | Every 2 minutes while the board has unsaved changes; deleted when you quit normally |

It **never** connects to the internet, never talks to your laser or your printer (you open the G-code in your own laser software), never installs anything, and never changes files you did not ask it to save.

## The board

- Units are **millimetres**, Y points **up**. The screen normally shows the **component side, looking through the board**. Copper is on the other side.
- Parts sit at grid points (1.27 mm by default). Pins of DIPs and headers are 2.54 mm apart, and the router grid is 0.635 mm (a quarter of 2.54) so everything lines up.
- A **net** is a list of pins that must be connected, plus any **rigid pairs** (two pins of the net that must be joined directly). The wire tool adds pins to nets, and a yellow rubber-band line shows what is not yet routed.
- A **trace** is a list of points with one width per segment. Every segment is a straight capsule (a line with round ends), and a pad is a circle, oval or square polygon. Copper is simply the union of those shapes.
- **Chamfers:** whenever two segments meet at a corner, the corner is replaced by two shorter bends of 45° each. The chamfer leg is at least 0.9 mm or 1.5 × the trace width, whichever is larger, so a 10 mm trace gets a 15 mm chamfer. The route checker complains about any turn over 46°, so a hand-made 90° corner cannot survive.
- **Pads:** *through-hole* has a drilled hole and a ring. *Deadbug* has no hole; the pad is stretched outwards by about 2.2 mm so you can bend the lead flat and solder it on the copper side. *Both* keeps the hole and the extra copper. The part definitions are checked so that pads stay at least 0.25 mm apart in all three styles.

## Copper islands

An island is a round, oval or rectangular piece of copper with its corners cut at 45 degrees (rectangles only). It is saved in the board file with its centre, width, height, shape and corner cut, and nothing else: it has **no net of its own**. Whenever the copper is worked out, each island takes the net of whatever touches it (a pad, a trace, a jumper pad; islands that touch each other are taken together). If two real nets touch it, it takes one of them and the checker reports the other as a clash, which is the short it is. An island nothing touches is its own little net and is kept clear of everything else. Because islands are ordinary copper once their net is known, the router steers round them, connections through them count as made, and every export contains them.

## Ground fill

With *Board > Ground fill* on, the board is copper except where it must not be. The program never cuts polygons; it describes the copper as a paint order that each output follows:

1. a rectangle covering the board, inset by the edge clearance, in copper;
2. every piece of copper that is not ground, grown by its own growth plus the gap, in bare board;
3. the fattened copper of those nets, then all the ordinary copper, in copper.

The growth of each shape is the wanted growth, cut down so that it keeps the gap from ground copper and the edge, and keeps the gap from any other net's shape even if that one grows by as much (half the free space each). Islands you placed do not grow.

To find floating fill, the fill is sampled along lines 0.05 mm apart; neighbouring intervals that overlap are joined into pieces, and each ground pin is looked up in its piece. Pieces with no ground pin are cut away (one polygon per run of rows), and the same is done once more across the other direction for slivers thinner than a row. Ground pins that sit on different pieces are shown as yellow rubber bands between the pieces. The editor skips the floating-fill check while you drag and does it when you let go.

Outputs: the editor and the PDF/SVG prints draw in the paint order; Gerber writes the fill as a dark region, switches to clear polarity (`%LPC*%`) for step 2 and back (`%LPD*%`) for step 3; the laser engine adds the fill to the copper intervals of each scan line (fill interval minus the cut intervals), so negative mode burns only the gaps.

## Tidying wide traces

A trace that is 1.2 mm or wider gets three fixes, in this order, each checked against the real copper and the clearance rule:

1. If an end lies inside a pad of its own net but not on its centre (the router works on a 0.635 mm grid, so it often stops a little off-centre), the end is moved to the pad centre.
2. From the pad centre the trace first runs straight up, down, left or right for about the pad radius plus the trace width, then joins the rest of the trace at 45°. All four directions and a few ways of rejoining are tried; the shortest that fits wins, and running over the part's own body is avoided.
3. Corners are cut again with chamfers that may not shorten those straight exits, then lengthened where there is room.

A reshaped trace is only kept if everything of its own net that it touched (pads it ran over, branches ending on it, jumper pads) still touches it, with every branch end at least as deep inside it as before; otherwise only the end is moved onto the pad centre, or nothing changes. It must also be no closer to copper of any other net than it already was (thin traces only get step 1). This runs after auto-routing and, if *Auto-tidy* is ticked, a moment after the width slider stops. If a straight exit cannot fit (for example a 3 mm trace between 2.54 mm pitch pads), the trace keeps its old shape and the clash is marked in red.

## T-joints

Where a branch ends on another trace of its net, the branch is stopped on that trace's centre line, or pulled back by half the difference in width when the branch is the wider one, so its round end does not stick out of the far side. The end always stays inside the other trace's copper. This runs after routing, after tidying and after a drag.

## Dragging, trimming, splitting

- **Drag:** branches that end on the trace you drag move with it: each slides along its own last section until it meets the moved trace again (or gets a short 45° link), so it stays joined. The section you hold moves sideways (only at right angles to itself, in grid steps). Each neighbouring section keeps its direction and is lengthened or shortened to meet the moved line, so a 45° section stays 45°. A section that starts on a pad cannot move its pad end; a 45° link is added there. The result is chamfered like any trace.
- **Trim:** the clicked section is removed; what is left either side becomes separate traces.
- **Split:** the trace is cut in two at the clicked point; no copper is removed.

Edited traces count as hand-drawn, so Auto-route leaves them alone.

## Auto-place

Simulated annealing (random moves that are accepted if they help, or sometimes if they don't, less often as time goes on). It moves, rotates and swaps parts that are not locked. The score is the total length of the shortest ratsnest (minimum spanning tree per net) plus a penalty for each crossing of two airwires plus a large penalty for overlaps and parts off the board. It runs on a copy of the board in the background and you can cancel it.

## Auto-route

1. Nets are ordered: wide nets first, then short nets first.
2. **Rigid pairs first.** Pairs marked rigid (Shift + Wire) are routed before anything else in their net, each as one pin-to-pin search, and those traces are flagged so the editor can mark them with a thin orange centre line.
3. Each remaining connection is searched with **A\*** on a 0.635 mm grid. The search state is *position and heading*, and a turn costs extra. Moves are straight or diagonal, and a 90° turn costs as much as two 45° turns, so it prefers long straight runs and gentle bends instead of staircases.
4. Each width class has its own obstacle map, so a 5 mm trace keeps further away from other copper than a 0.8 mm one. A step under a part's body (away from its pins) costs a little extra, and a lot extra with *Keep traces out from under parts*.
5. A found path is **checked with exact geometry** (the real copper shapes, with the real clearance). If it fails, the offending grid cell is forbidden and the net is searched again.
6. If a net cannot be routed, a "soft" search is allowed to pass through other nets. Those nets are torn out (**rip-up**) and routed again after the blocked one. This is limited: at most 3 tear-outs per net, 40 in total per round, 3 rounds.
7. If a net still fails, a **jumper pass** looks for an orthogonal wire link of 5.08 to 15.24 mm (2.54 mm steps) that lands on free pads and doesn't pass over a part's body or another jumper.
8. Finally, corners on wide traces are enlarged to the chamfer rule, and every trace is tidied as described above.

Traces you drew yourself are kept. This is **not** a full PathFinder router: it has no per-cell "history cost" that grows over repeated rounds. The research notes explain the idea and why it was left for later.

## DRC

The checker measures the real copper shapes: clearance between different nets, edge clearance, width, corner angle, ring size, jumper length and crossings, and unrouted pins.

## Exports

- **Gerber:** RS-274X, coordinates in millimetres with 4.6 format. Traces are drawn with round apertures (so the capsule ends are right), pads and polygons as regions. The copper layer is labelled *bottom copper* and uses the same coordinates as the design view, which is how a fab expects a single-sided board whose copper is on the back. Files: copper, board outline, silkscreen (component outlines), and an Excellon drill file. There is no soldermask layer.
- **1:1 PDF/SVG:** the page is exactly the board size. For toner transfer use the mirrored version.
- **BOM:** parts grouped by name and value.

## Laser G-code

The exporter works out, for each scan line, the exact stretches that must be burned, instead of converting an image. That gives sharp edges and lets the **trace adjust** and **gap** settings be exact:

- *Negative:* burn the whole board area **except** copper, shrunk or grown by *trace adjust*, and keep a border. Paint is left only where copper is wanted.
- *Isolation:* burn only a band *gap* mm wide around the copper (copper grown by *trace adjust* first).
- *Positive:* burn the copper itself.

Negative adjust is done by "eroding" the copper shapes through their edges, which is exact for the capsule and polygon shapes used here. Scan lines run along X, every *line interval* mm, optionally alternating direction and optionally repeated at 90° (cross-hatch) or several passes. G-code uses `G21 G90`, a rapid `G0` to the start of each run and `G1 X.. S.. F..` along it. With **M4** (GRBL "dynamic power") the controller scales power with speed; with **M3** the exporter adds a zero-power run-in and run-out (*overscan*). Drill centres get a short dot. The time estimate is distance divided by speed plus rapids, and is not a promise.

**What is assumed, not known:** that the Phecda behaves like a GRBL machine (the manual names LaserGRBL and LightBurn), that `$30` matches the S max you enter, and that laser mode (`$32=1`) is on. No file has been run on a real Phecda. See [docs/research/phecda-laser-notes.md](docs/research/phecda-laser-notes.md).
