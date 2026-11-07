<!-- Research note written for SoloTrace 0.5.0 (November 2026) with web sources. (S) = sourced number, (R) = recommendation. The IPC texts themselves were not accessible; their figures come via vendor summaries. -->

# Thermal-relief connections for hand-etched single-sided boards: research note

## Summary

A thermal relief is a ring gap round a pad with a few copper "spokes" bridging it to the surrounding fill, so the iron does not have to heat the whole ground plane before solder will wet the pad. Every mainstream EDA tool defaults to four spokes; KiCad's shipped defaults are a 0.5 mm gap and 0.5 mm spokes, LibrePCB's are 0.3 mm / 0.3 mm, and Altium's own design guide suggests 8 mil (0.2 mm) spokes with 10 mil (0.25 mm) clearance. A single 0.5 mm spoke in 1 oz copper is good for roughly 1.5 A at a 10 °C rise by the IPC-2221 formula, and four spokes carry roughly four times that, so for a hobby board nearly every ground pad can keep its relief; the exceptions are pads above a few amps (industry articles put the "go solid" line at 2–3 A continuous, up to 10 A) and pads whose job is low-inductance return (decoupling-capacitor grounds, RF). Below are sourced numbers and, clearly separated, my recommended defaults for the generator.

## 1. Thermal-relief geometry as used by EDA tools and IPC

**KiCad (from source, master branch).** The zone defaults are defined in `pcbnew/zones.h`: `ZONE_THERMAL_RELIEF_GAP_MM 0.5`, `ZONE_THERMAL_RELIEF_COPPER_WIDTH_MM 0.5` (spoke width), `ZONE_CLEARANCE_MM 0.5` and `ZONE_THICKNESS_MM 0.25` (minimum fill width) ([zones.h](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/pcbnew/zones.h)). New zones default to `ZONE_CONNECTION::THERMAL` ([zone_settings.cpp](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/pcbnew/zone_settings.cpp)). Spoke angle is per pad shape: `DefaultThermalSpokeAngleForShape` returns `ANGLE_45` for circular pads and `ANGLE_90` (spokes on the pad's axes) for every other shape ([padstack.cpp](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/pcbnew/padstack.cpp)). KiCad always tries four spokes; the DRC constraint "minimum thermal relief spoke count" defaults to `DEFAULT_MINRESOLVEDSPOKES 2`, i.e. a pad is only flagged as a "starved thermal" if fewer than two spokes resolve ([board_design_settings_defaults.h](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/include/board_design_settings_defaults.h)). There is no two-spoke setting; users who want two spokes set the pad to "none" and draw tracks ([KiCad forum](https://forum.kicad.info/t/number-of-spokes-in-thermal-relief/5135)).

**Why 45° on round pads and 90° on others.** On a round pad the spoke direction is arbitrary, and 45° keeps spokes out of the horizontal/vertical routing channels between pads in a row; KiCad users report that rotating to 45° "may give 4 good spokes instead of only 2" where neighbouring pads are close ([KiCad forum](https://forum.kicad.info/t/thermal-bridge-angle-45/45956)). On an oval or rectangular pad 45° spokes land on the corners and "would not really work", so spokes come off the flat sides or arc centres ([KiCad forum](https://forum.kicad.info/t/thermal-spoke-orientation/21626)). LibrePCB made the same choice: four spokes hard-coded, 45° for circular pads, 0° for other shapes, gap and spoke width both 0.3 mm by default ([LibrePCB forum, PR #1160](https://librepcb.discourse.group/t/how-to-create-a-thermally-relieved-connection-to-a-plane/347)).

**Altium.** The Polygon Connect Style rule offers Relief Connect / Direct Connect / No Connect, 2 or 4 conductors, a conductor width, an air-gap width and a rotation angle; Advanced mode allows separate settings for through-hole pads, SMD pads and vias ([Altium documentation](https://www.altium.com/documentation/altium-designer/pcb-plane-rule-polygon-connect-style)). The documentation page does not print the numeric defaults, but Altium's own design guide says "Typically, 8 mil traces with 10 mil clearance will be fine for the majority of components" (0.2 mm spokes, 0.25 mm gap), four spokes on the four sides of the pad, with width and clearance reduced for small dense passives ([Altium resources](https://resources.altium.com/p/thermal-relief-design)).

**Eagle.** Spoke width is derived from the pad, not set directly: "Spoke width is 50% of the pad drill diameter or the smallest side of SMD with a minimum width of 1 polygon wire width and a maximum of 2 wire widths"; CadSoft support added that a 10 mil polygon width gives 10 mil spokes ([element14 Eagle forum](https://community.element14.com/products/eagle/f/eagle-user-support-english/42609/question-about-thermal-relief-spoke-widths); [element14](https://community.element14.com/products/eagle/f/eagle-user-support-english/4887/how-can-i-change-the-width-of-thermal-ties)). This "half the drill, bounded by polygon width" rule is the only tool default I found that scales spokes with pad size, and it is a sensible model for a generator.

**IPC.** I could not read IPC-2221 or IPC-7351 directly (paywalled). Secondary sources attribute a 0.2 mm (8 mil) minimum spoke width to IPC-2221B and give class tables: through-hole pins on a plane 0.30–0.50 mm spokes with 0.40–0.60 mm gap; general SMD 0.20–0.30 mm spokes, 0.25–0.40 mm gap; fine-pitch passives 0.10–0.20 mm spokes, 0.20–0.30 mm gap ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design)). Another vendor article recommends 0.25 mm spokes (0.20 mm minimum) and a 0.30 mm gap, and says four spokes at 90° intervals is the default in "virtually all EDA tools" ([AtlasPCB](https://atlaspcb.com/blog/pcb-thermal-relief-pad-design)). Treat these as industry consensus rather than verbatim IPC text.

## 2. Why reliefs help hand soldering

Copper conducts heat at about 400 W/m·K against about 0.3 W/m·K for FR-4, so a pad fused to a plane dumps the iron's heat into the whole sheet ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design)). onsemi's THT soldering note says to "use thermal relief patterns on circuit board pads"; without them assembly is "impractical and unreliable" and needs "far excessive solder time". The same note gives the target: hand joints "can be consistently made or removed in less than 5 seconds" and "should never take longer than 10 seconds", with tip temperatures that "commonly far exceed 300 °C", and it stresses that minimising time matters more than minimising tip temperature ([onsemi AND90331](https://www.onsemi.com/download/application-notes/pdf/and90331-d.pdf)). A heavy-copper article notes that a 45-second iron hold often still fails to wet a pad on a solid plane ([Bester PCBA](https://www.besterpcba.com/heavy-copper-thermal-reliefs)).

Practical hand-soldering numbers from KiCad users: 0.4 mm spokes with a 0.4 mm gap were hard to solder even at 370 °C, while a 0.6 mm gap with 0.4 mm spokes worked well; a "decent 60 W+" temperature-controlled iron copes with spokes under 1 mm; a 50 W Weller at 315 °C manages ordinary reliefs ([KiCad forum](https://forum.kicad.info/t/effective-thermal-relief-settings-for-hand-soldering/42802)). The lesson for a generator is that gap length matters as much as spoke width: a longer gap means a longer, higher-resistance heat path.

Tombstoning is the SMD counterpart: when one end of a chip part sits on a plane and the other on a thin trace, the plane end wets later, and the surface tension of the first joint stands the part up ([Autodesk Fusion blog](https://www.autodesk.com/products/fusion-360/blog/what-is-pcb-tombstoning/)); relieving the pour end is the standard fix ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design)). Altium's guide links tombstoning and cold joints to the same cause, heat leaving the pad ([Altium](https://resources.altium.com/p/thermal-relief-design)).

## 3. Current carrying of spokes

**Formula.** IPC-2221 external layers: I = 0.048 · ΔT^0.44 · A^0.725, with I in A, ΔT in °C and A in mil²; internal layers use k = 0.024. Valid for ΔT of 10–100 °C, up to 35 A, traces up to 400 mil wide, 0.5–3 oz copper ([Bittele trace-width calculator](https://www.7pcb.com/trace-width-calculator)). 1 oz copper is 1.378 mil thick (the calculator's own conversion).

**Per-spoke values (my arithmetic from that formula, 1 oz copper, ΔT 10 / 20 / 30 °C):**

| Spoke width | A (mil²) | 10 °C | 20 °C | 30 °C |
|---|---|---|---|---|
| 0.3 mm | 16 | 1.0 A | 1.4 A | 1.6 A |
| 0.5 mm | 27 | 1.5 A | 2.0 A | 2.4 A |
| 0.8 mm | 43 | 2.0 A | 2.8 A | 3.3 A |
| 1.0 mm | 54 | 2.4 A | 3.2 A | 3.9 A |
| 1.5 mm | 81 | 3.2 A | 4.4 A | 5.2 A |

**Do spokes add?** Yes, by the standard sizing method: the heavy-copper article sizes "100 mil of copper width at a 10 °C rise, split across four spokes, each spoke 25 mil wide" ([Bester PCBA](https://www.besterpcba.com/heavy-copper-thermal-reliefs)), and a KiCad user's rule is to match total spoke width to the feeding trace ("four 1 mm spokes for a 4 mm trace") ([KiCad forum](https://forum.kicad.info/t/a-good-start-to-filled-zones-and-thermal-reliefs/65504)). The IPC formula is conservative for spokes because it assumes an infinitely long trace; a short spoke bonded to a copper mass at both ends runs cooler, so each spoke can carry more than the table says ([same thread](https://forum.kicad.info/t/a-good-start-to-filled-zones-and-thermal-reliefs/65504); plane proximity cut required trace area by a factor 0.47 in the IPC-2152 worked example at [Olson, How to use IPC-2152](https://blog.mbedded.ninja/pdfs/JackOlson-HowTo2152.pdf)). Caution: the formula does not scale to 10+ A through one spoke; a vendor article says default 10 mil spokes "can fuse at about 20 A" ([Bester PCBA](https://www.besterpcba.com/heavy-copper-thermal-reliefs)).

**Resistance and when to go solid.** A four-spoke relief with 0.25 mm spokes adds roughly 1–3 mΩ per pad, i.e. 5–15 mV drop and 25–75 mW at 5 A, and about 300 mW at 10 A ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design)). Thresholds quoted: direct-connect any pad above 3 A continuous ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design)); "evaluate" direct connect above 2–3 A ([AtlasPCB](https://atlaspcb.com/blog/pcb-thermal-relief-pad-design)); standard four-spoke reliefs fine below 5 A, wider spokes or six to eight spokes above 5 A, omit reliefs on power planes above 10 A ([Aivon](https://www.aivon.com/blog/pcb-design/high-current-pcb-design-how-thermal-relief-impacts-power-delivery)). Exposed/thermal pads under QFN, DPAK and the like are always solid ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design)).

## 4. RF and low-inductance grounds

ADI's decoupling tutorial: "All decoupling capacitors must connect directly to a low impedance ground plane in order to be effective. Short traces or vias are required for this connection to minimize additional series inductance" ([ADI MT-101](https://www.analog.com/media/en/training-seminars/tutorials/MT-101.pdf)). LearnEMC: "On boards with a solid GND plane, the GND pad of a decoupling capacitor should always connect directly to the plane" ([LearnEMC](https://learnemc.com/qotw-240930)). TI layout guidance for its ICs repeats "tied to the PCB ground plane at the terminal of the IC" and "minimize the loop area formed by the bypass-capacitor connection" ([TI TPS25925 layout](https://www.ti.com/document-viewer/TPS25925/datasheet/layout)). JLCPCB and Bester both list RF reference pads and controlled-impedance return vias as direct-connect exceptions ([JLCPCB](https://jlcpcb.com/blog/thermal-relief-pad-design); [Bester PCBA](https://www.besterpcba.com/heavy-copper-thermal-reliefs)); AtlasPCB says two-spoke reliefs have higher inductance than four-spoke and that spokes cause impedance discontinuities above 5 GHz ([AtlasPCB](https://atlaspcb.com/blog/pcb-thermal-relief-pad-design)).

Numbers for the extra inductance of a spoke are scarce. For scale: a half-inch (12.7 mm) PCB trace is "about 3.5 nH" and a single via about 1.3 nH ([All About Circuits](https://www.allaboutcircuits.com/technical-articles/pcb-layout-tips-and-tricks-how-to-optimize-your-decoupling-connection/)); a 50 Ω microstrip works out at about 6.7 nH/inch, and Cadence warns there is no general per-length rule of thumb ([Cadence](https://resources.system-analysis.cadence.com/blog/msa2021-is-there-a-pcb-trace-inductance-rule-of-thumb)). A 0.5 mm spoke is therefore a fraction of a nanohenry, and four in parallel less again, against the capacitor's own ~5 nH mounted parasitic ([EMC FastPass](https://emcfastpass.com/wp-content/uploads/2017/04/Using_decoupling_caps.pdf)). On a single-sided hobby board the relief is not the dominant inductance, but the industry rule is still: decoupling-cap and RF ground pads solid.

## 5. Recommended software defaults for a hand-etched single-sided board

Sourced numbers are marked (S); the rest is my recommendation (R) built on them and on the 0.6 mm clearance already used for other nets.

**(a) Small through-hole pads (round, 1.6–2 mm):** four spokes (S: all tools), at 45° (S: KiCad/LibrePCB default for circular pads, keeps spokes out of pin-row channels). Gap 0.5 mm (S: KiCad default; 0.4–0.6 mm vendor range) and spoke width 0.5 mm (S: KiCad default; Eagle rule gives ~0.5 mm for a 1 mm drill). (R) For a hand-etched board I would not go below 0.4 mm spokes or 0.5 mm gap, since etch undercut narrows thin features and hand-soldering reports found 0.4/0.4 hard and 0.4/0.6 easy. Four 0.5 mm spokes are good for about 5–6 A at a 10 °C rise by the IPC table above, far more than any DIP or TO-92 pin.

**(b) Deadbug oval pads (1.6 × 4 mm):** spokes at 90° off the flat sides and arc centres, not the corners (S: KiCad/LibrePCB behaviour for non-circular pads). (R) Default two spokes on the long sides plus one at each end, 0.6 mm wide, gap 0.6 mm to match the board's net clearance. A lead soldered flat along the pad sits over the long edges, so the side spokes are the ones that matter for wetting; leaving the end spokes off would make the pad a pure two-spoke relief and KiCad treats two resolved spokes as acceptable (S).

**(c) Large copper islands (5–15 mm):** (R) yes, keep a relief ring but scale it: gap 0.6 mm, spoke width = 10 % of the island's shorter side, clamped to 0.6–1.5 mm, with one spoke per 5 mm of perimeter rounded to a minimum of four. Rationale: Eagle's "half the pad size, bounded by polygon width" is the only tool rule that scales with pad size (S); the island itself is a heat sink, so what the relief protects is the ability to heat the island's solder point without heating the whole board; an island of 10 × 10 mm with eight 1 mm spokes carries about 19 A at 10 °C rise by the table above, so current is never the limit.

**Rule for a solid connection instead:** (R, from S thresholds) make the pad solid when its net current exceeds 3 A continuous (S: JLCPCB, AtlasPCB), when the pad is a decoupling-capacitor or RF ground (S: ADI, LearnEMC), or when it is an exposed thermal pad. Between 1.5 A and 3 A, widen spokes so total spoke width equals the feeding trace width (S: Bester / KiCad-forum method). Let the user override per pad, as KiCad does (S). Always compute the per-spoke current from the IPC-2221 external formula with ΔT = 10 °C and 1 oz copper, flag any pad whose summed spoke rating is below its net current, and remember the formula is conservative for short spokes (S).

## Sources

- https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/pcbnew/zones.h
- https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/pcbnew/zone_settings.cpp
- https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/pcbnew/padstack.cpp
- https://raw.githubusercontent.com/KiCad/kicad-source-mirror/master/include/board_design_settings_defaults.h
- https://forum.kicad.info/t/number-of-spokes-in-thermal-relief/5135
- https://forum.kicad.info/t/thermal-bridge-angle-45/45956
- https://forum.kicad.info/t/thermal-spoke-orientation/21626
- https://forum.kicad.info/t/effective-thermal-relief-settings-for-hand-soldering/42802
- https://forum.kicad.info/t/a-good-start-to-filled-zones-and-thermal-reliefs/65504
- https://librepcb.discourse.group/t/how-to-create-a-thermally-relieved-connection-to-a-plane/347
- https://www.altium.com/documentation/altium-designer/pcb-plane-rule-polygon-connect-style
- https://resources.altium.com/p/thermal-relief-design
- https://community.element14.com/products/eagle/f/eagle-user-support-english/42609/question-about-thermal-relief-spoke-widths
- https://community.element14.com/products/eagle/f/eagle-user-support-english/4887/how-can-i-change-the-width-of-thermal-ties
- https://jlcpcb.com/blog/thermal-relief-pad-design
- https://atlaspcb.com/blog/pcb-thermal-relief-pad-design
- https://www.besterpcba.com/heavy-copper-thermal-reliefs
- https://www.aivon.com/blog/pcb-design/high-current-pcb-design-how-thermal-relief-impacts-power-delivery
- https://www.onsemi.com/download/application-notes/pdf/and90331-d.pdf
- https://www.autodesk.com/products/fusion-360/blog/what-is-pcb-tombstoning/
- https://www.7pcb.com/trace-width-calculator
- https://blog.mbedded.ninja/pdfs/JackOlson-HowTo2152.pdf
- https://www.analog.com/media/en/training-seminars/tutorials/MT-101.pdf
- https://learnemc.com/qotw-240930
- https://www.ti.com/document-viewer/TPS25925/datasheet/layout
- https://www.allaboutcircuits.com/technical-articles/pcb-layout-tips-and-tricks-how-to-optimize-your-decoupling-connection/
- https://resources.system-analysis.cadence.com/blog/msa2021-is-there-a-pcb-trace-inductance-rule-of-thumb
- https://emcfastpass.com/wp-content/uploads/2017/04/Using_decoupling_caps.pdf
