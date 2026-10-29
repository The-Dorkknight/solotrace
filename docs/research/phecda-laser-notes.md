# Elegoo Phecda laser: facts, discrepancies and assumptions

Checked 2026-10-29 from the pages below. SoloTrace's laser output is built on these, **but it has never been run on a real Phecda.** Everything marked "assumed" is a guess to be confirmed on the machine.

## What the sources say

| Fact | Source | Notes |
| --- | --- | --- |
| Engraving area 400 x 400 mm | [3D With Us review of the 20 W model](https://3dwithus.com/elegoo-phecda-20w-review-laser-engraver-cutter-testing) | Used as the default work-area check (the app warns if a board is bigger) |
| Software named: LaserGRBL and LightBurn ("compatible with a variety of slicing software ... such as LaserGRBL, LightBurn") | [Elegoo Phecda user manual (Oct 2023)](https://download.elegoo.com/07%20Laser%20Engraver%20&%20Cutter/01%20PHECDA/2.%20User's%20Guide/1.User%20Manual/PHECDA%20Laser%20Engraver%20User%20Manual-20231020.pdf) | LaserGRBL and LightBurn both talk G-code to GRBL-style controllers, which is why GRBL is **assumed** |
| The manual does not mention "GRBL" or "G-code" by name | same manual | So "GRBL-compatible" is an inference, not a documented fact |
| Manual says to "set the origin" before engraving; it does not mention homing or limit switches | same manual | Hence SoloTrace's G-code starts from a **work zero you set by hand** (lower-left of the board as seen from the copper side), no `$H` homing |
| Max engraving speed X 25 000 mm/min, Y 18 000 mm/min | same manual, spec table | The module page and review quote 25 000 mm/min |
| Spot size 0.06 x 0.06 mm (10 W) and 0.07 x 0.13 mm (20 W) | same manual, spec table; the [module page](https://www.elegoo.com/collections/phecda-series-accessories/products/10w-20w-laser-module-for-elegoo-phecda-laser-engraver) says 0.06 x 0.06 mm for the 10 W module; the review says 0.07 x 0.13 mm for the 20 W | The 20 W spot is **not square**: the 0.13 mm direction is wider. SoloTrace's default scan-line interval is 0.08 mm; for fine traces rotate the board 90 degrees if one axis gives thinner lines (untested) |
| Input files: SVG, DXF, JPG, PNG, BMP, TIF | manual | SoloTrace outputs G-code, not these. Rasters/SVG are possible via the 1:1 SVG export if your software prefers them |

## Discrepancies worth knowing

- Press material quotes a lower top speed than the spec table (the press figure of 160 mm/s is 9 600 mm/min against 25 000 mm/min in the spec). SoloTrace warns above 9 600 mm/min and its default is 1 500 mm/min, which is a starting point for painted copper, not a measured value.
- Spot size differs between the 10 W and 20 W modules and between the pages.

## Assumptions built into the G-code (all untested)

1. GRBL-style controller: `G21 G90`, `G0` rapids, `G1 X.. Y.. S.. F..`, `M4` (dynamic power) by default or `M3` with overscan.
2. `$30` (max spindle value) equals the S max set in the dialog (default 1000) and laser mode `$32=1` is on. If not, the power percentage will be wrong.
3. Work zero is set by hand at the lower-left corner of the board, viewed from the **copper** side. The exporter mirrors X because the design view is the component side.
4. A diode laser does **not** remove bare copper. The workflow is: paint the copper, burn the paint away where copper must go (negative mode), etch, then clean the paint. Isolation mode burns only a band around the copper.

## How to find out the truth

Use the **speed/power test card** and the **trace/gap ladder card** (Export > Laser G-code, or `examples/test-cards/`) on a scrap board first. Please report what you find in an issue.

## Safety (not optional)

Laser safety glasses rated for the module's wavelength, never leave it running unattended, ventilate (burnt paint and etchant fumes), keep a fire extinguisher or damp cloth near, and check the preview in your laser software before pressing start. Etchants (ferric chloride, sodium persulfate, hydrogen-peroxide/acid mixes) damage skin, eyes and surfaces: follow the maker's safety sheet.
