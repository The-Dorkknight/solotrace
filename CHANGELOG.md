# Changelog

**WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN**

## 0.4.0-wip (2026-10-31)

For quick and dirty RF and fast analogue boards, built deadbug / Manhattan style:

- **Copper islands (Island tool, `I`).** Free-standing round or rectangular copper pads. Click to drop one, drag on the board to draw one any size, Shift + click to switch between round and rectangular. With *Select*, drag an island to move it and drag its white corner squares to resize it (the opposite corner stays put); the right panel has exact width, height and corner cut, square/circle size buttons, *Turn 90*, *Duplicate* and *Delete*, and the right-click menu has the same. An island has no net of its own: it joins the net of any pin, trace or jumper pad that touches it, and islands that touch each other share one net. Pins of two different nets on one island are a short, and *Check* says so. A board built from islands needs no traces at all.
- **Ground fill (Board > Ground fill).** The whole board becomes ground copper, with a gap (default 0.6 mm, never less than the copper clearance) cut round every other net. The ground net is guessed (GND, 0V, VSS..., else the net with the most pins) or chosen; it is joined by the fill, so Auto-route leaves it alone and removes its old automatic traces. Other nets' copper can be fattened (default 1 mm, only where it keeps the gap; islands you placed keep their size). Pieces of fill that no ground pin sits on (floating copper) are cut away; a ground pin on a piece of fill that is cut off from the rest gets a yellow rubber band. Turning it on offers to make every pad a deadbug pad (no holes to drill).
- The fill is in every output: the editor, Gerber (with clear polarity, read back by the independent gerbonara library in testing), PDF and SVG prints, and the laser G-code (negative mode then burns only the gaps; isolation mode burns the same as negative on such a board).
- New examples: *Manhattan RF amplifier (copper islands)*, built from islands with no traces, and *RF oscillator (ground fill, routed)*.
- Command line: `solotrace islands board.solotrace out.solotrace [--net GND] [--gap 0.6] [--grow 1] [--deadbug] [--keep-floating] [--off]` turns the ground fill on or off.
- The coloured tool-bar buttons are only as wide as their text, so the bar fits a 1280 px window with the new tool.
- A redraw could be left scheduled when a window closed ("invalid command name ...redraw" in the test output); fixed.

## 0.3.5-wip (2026-10-29)

Rigid-wire refinements, after the author found rigid trunks "still separate, not a true union":

- **One colour.** Routed rigid traces are drawn in the normal copper colour, like the branches joined to them, with a thin dashed orange line down the middle to mark them. (They were always ordinary copper in the exports; only the editor drew them in a different colour on top.)
- **Clean T-joints.** A branch that ends on another trace stops on its centre line, and is pulled back a little when it is the wider one, so its round end no longer pokes out of the far side of a narrow trunk. It always stays inside the trunk's copper. Done after routing, tidying and dragging.
- **Branches follow a dragged trunk.** Dragging a trace sideways now moves the ends of the branches joined to it, so they stay joined (each slides along its own direction, or gets a short 45 degree link).

## 0.3.4-wip (2026-10-29)

- **Right-click never deletes anything by itself.** Right-clicking a trace only opens its menu. While the mouse rests on *Cut this piece*, the piece that would go is shown in red; it is removed only when you choose that item. On a joint the item is greyed out and says why.

## 0.3.3-wip (2026-10-29)

- **Cut (C) is one click now:** click a trace and the piece under the mouse is removed, from the joint before it to the joint after it (a pad, a place where another trace meets it, a jumper pad). The rest of the trace and the net stay. The piece turns red while you hover, before you click. Clicking right on a joint does nothing. The old two-point cut is still there as Shift + click (twice), or right-click > *Cut between two points*.
- **Right-click a trace > Cut this piece** does the same as one click with the Cut tool.
- **Shift + click while placing turns the part** 90 degrees instead of placing it; click without Shift to place.
- **Favourites & recent:** a drop-down at the top of the parts panel lists your starred parts and the last ten you placed. Star a part with the button under the preview, or right-click it in the list.
- The preview of a trace being drawn (Trace tool) and of a cut were drawn with a stipple pattern that some X11 setups do not show; they are solid now.
- The status bar text no longer pushes the version stamp off the window.

## 0.3.2-wip (2026-10-29)

From the next real board: "the second a rigid line appears the other traces form weird, as if they are repelled":

- **Branches no longer come loose from a trunk.** After routing, and whenever a width changes, wide traces are tidied (straight pad exits, centred ends, bigger chamfers). That tidy could move a rigid trunk away from the branches joined to it, leaving stubs that stop short, overshoot, or a pad cut off (in one rebuild a capacitor pad lost its connection). Now a trace is only reshaped if everything it touched still touches it and every branch end sits at least as deep in it as before; otherwise only its end is moved onto the pad centre, or nothing changes. The corner smoothing obeys the same rule.
- **DRC warns about hanging trace ends** ("dangling"): a trace end that is not joined to a pad, trace or jumper of its net.
- **Board > Keep traces out from under parts** (off by default): Auto-route then goes round part bodies (between DIP rows, under transistors) unless there is no other way. The areas round each pin stay free. On a cramped board this can cost jumpers. Without it, the retries now also count copper under part bodies against a result, so a short route through a chip only wins when going round is much longer.

## 0.3.1-wip (2026-10-29)

Fixes after routing a real board with 0.3.0 gave overlapping tracks and forced jumpers:

- **Overlapping / disappearing tracks fixed.** When a net was only partly routed and then routed again (after a rip-up), the copper it already had was not counted as part of it, so new traces ran straight over the old ones or crossed them. Now every trace already on the board joins its net's group, and new connections end where they meet that copper. This bug was older than 0.3.0; rigid wires made it show up much more often.
- **Retries:** Auto-route now tries up to six net orders (within about 12 seconds) and keeps the best result: fewest unrouted connections, then fewest jumpers, then the shortest copper. The progress bar says "Try n of 6". On seven test boards (the demos, two random boards and a rebuild of the board from the bug report) this took the unrouted connections from 2 to 0 with jumpers allowed.
- **Jumpers are optional:** untick **Jumpers** in the tool bar (or *Board > Auto-route may add jumpers*) and Auto-route never adds wire links; what it cannot route stays as rubber bands. Each net can also refuse jumpers (net panel, or right-click > *Allow jumpers on this net*). Saved with the board.
- **Rigid wires are not stiff:** a rigid (Shift + Wire) pair still gets its own pin-to-pin trace, but the path bends round things like any other trace, and traces now cost a little more under part bodies, so a trunk is less likely to cut through the middle of a chip.
- **Cut tool** (`C`, or right-click a trace > *Cut from here*): click two points on a trace and only the copper between them is removed; the rest of the trace and the net stay. (*Trim*, `X`, still removes a whole section.)

## 0.3.0-wip (2026-10-29)

From the first real design made with SoloTrace (a 555 power oscillator):

- **Rigid wires.** Hold **Shift** while wiring (click or drag from pin to pin) and the pair becomes a rigid link: the router joins those two pins with their own direct trace first, and the net's other pins branch off it. Use it for a power trunk, e.g. a transistor emitter straight to the supply terminal, instead of being chained through a capacitor. Rigid links show as thicker orange rubber bands, the routed trunk is drawn in orange copper, and both can be set or cleared from the right-click menu and the net panel.
- **More visible rubber bands:** thicker yellow lines with a dark edge; the wire being drawn is a dashed line that turns orange while Shift is held.
- **Pin labels.** Common pin layouts per form factor, chosen from a list (right panel or right-click > *Pin labels*): TO-92 E B C / C B E / B C E / D G S / G D S / S G D / small regulators; TO-220 power transistor B C E, MOSFET G D S, IGBT G C E, regulator IN GND OUT, adjustable regulator ADJ OUT IN, negative regulator GND IN OUT, triac, dual diode; TO-247; optocouplers (DIP-4, DIP-6); 555-style timer, single and dual op-amp, dual optocoupler (DIP-8); logic GND/VCC and quad op-amp (DIP-14/16/20); pots; 2- and 3-pin connectors. Or type your own. Diodes and LEDs show K A and electrolytics + - by themselves. Labels are drawn beside the pads.
- **Value / type** is now easier to find: bold field at the top of the part panel with examples, *Set value / type...* on the right-click menu, and double-clicking a part jumps to it. Part names and values sit just above small bodies so they no longer cover the pads.
- **TO-92 parts are D-shaped** (flat face and round back) instead of a circle with a line.
- New example and demo: *555 power oscillator* (pin labels, standing resistors, a rigid power trunk).

## 0.2.1-wip (2026-10-29)

- **Smoother drawing.** Moving the mouse while drawing a wire, a trace, a jumper or placing a part used to redraw the whole board on every move. Now only the moving layer (rubber band, ghost part, hover highlight) is redrawn. On a 40-part test board that is about 6 ms per mouse move instead of about 97 ms; a full redraw went from about 97 ms to about 29 ms (grid points are one item each and only the visible ones are drawn; rubber-band lines are cached until the board changes). Measured in the development sandbox, not on your laptop.

## 0.2.0-wip (2026-10-29)

Changes after trying 0.1.0-wip on a real screen. 0.1.0-wip was packaged but never published, so this is the first version on GitHub.

- **Wide traces fixed:** a trace of 1.2 mm or more now leaves each pad with a straight vertical or horizontal run before it turns and ends exactly on the pad centre (before, a widened trace left a TO-92 pad at an angle and ended beside the resistor pad as a blob). Runs after auto-routing and, by default, whenever a width changes; *Tidy* and *Tidy all traces* do it on demand. Chamfers can no longer eat those straight exits.
- **Parts panel by form factor:** chips, transistors & regulators, resistors / diodes / inductors, capacitors, LEDs, pots / switches / crystals, connectors, board bits and your own parts, each with expand arrows for sub-types and a small drawn icon, plus a live drawing of the chosen part in the sidebar (no pop-up). Search matches all words.
- **New parts (90 in total):** standing (vertical) resistors 1/4 W at 2.54 and 5.08 mm, 1/2 W and 1 W at 5.08 mm; standing DO-35 and DO-41 diodes; axial and radial inductors; a 5.08 mm inline pot and a triangle trimmer.
- **Right-click menus** for traces, pins, parts, rubber-band lines, jumpers and the empty board (trim, split, tidy, widths, rotate either way, duplicate, lock, pad styles, wire or trace from a pin, route one net, delete, undo/redo). Right-drag still pans.
- **Trim tool** (`X`) and *Split trace here*.
- **Drag a trace section** sideways with the Select tool; the neighbouring sections follow at their own angle.
- **Look:** coloured tool bar and action buttons, rounded editor corners, a board shadow, status badge (all routed / N to route), net highlight on hover.
- **Ease of use:** "fits up to N mm" hint for the selected trace, arrow-key nudge, `Ctrl+D` duplicate, `Shift+R` rotate back, toolbar hints, *File > Open recent*, autosave every 2 minutes with *File > Recover autosave*, *Route this part's nets*.
- The examples were rebuilt; the logic example now uses auto-place seed 3 (seed 2 left one net unrouted).

## 0.1.0-wip (2026-10-29)

First work-in-progress build (packaged, not published).

- Tkinter editor: place, wire, trace and jumper tools; undo/redo; pan and zoom; flip view (component side / copper side).
- Library of 76 through-hole parts (90 from 0.2.0) (resistors, capacitors, diodes, transistors, LEDs, TO-220/TO-247, DIP-4 to DIP-40, headers, terminals, JST-XH, mounting holes and pads, wire links).
- Footprint wizard (pad table, click-to-add canvas, DIP and header presets) and KiCad `.kicad_mod` import.
- Trace width slider 0.4 to 10 mm for a segment, a whole trace or a whole net, with a current-capacity readout.
- Pads: through-hole, deadbug (no hole, extended copper for surface soldering) or both, per part or per pad.
- All trace corners chamfered by construction; DRC flags anything over 46 degrees.
- Auto-placer (simulated annealing) and auto-router (heading-aware A* on a 0.635 mm grid, 0/45/90 moves, rip-up and reroute, wire-link jumper fallback).
- Exports: Gerber RS-274X + Excellon drill (zip), 1:1 PDF and SVG (mirrored for toner transfer or not), BOM CSV, netlist text.
- Laser G-code for the Elegoo Phecda (GRBL-style): negative, isolation and positive modes, adjustable trace compensation and gap, line interval, speed, power, passes, crosshatch, frame file, speed/power and trace/gap test cards, time estimate.
- First-start safety and work-in-progress notice.
- Click-and-launch scripts for Linux, Windows and macOS.

Not yet done or not yet tested: see "Known limitations" in the README.
