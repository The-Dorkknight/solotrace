<!-- Research note written for SoloTrace 0.5.0 (November 2026) with web sources; the figures marked as recommendations are the author's/assistant's choices, not standards. -->

# Using the back copper of a double-clad board as a ground plane: vias, antipads, stitching and the "LC" worry

## Summary

A solid copper plane on the back of a home-etched board, with all traces on the front, is the single most useful upgrade a hobby board can get: it gives every trace a return path directly underneath it, cuts loop inductance, crosstalk and radiated EMI, and costs nothing but a few drilled holes. The "big LC circuit" fear is real physics but only bites at UHF: two copper sheets joined at a single point form a parallel-plate cavity whose first resonance is roughly f = c / (2·L·√εr). For a 100 mm FR4 board that is about 715 MHz, far above where most hobby boards operate. The standard cure, used on every multilayer board, is simply many connections between the two copper areas (stitching vias at λ/10 to λ/20 spacing of the highest frequency of concern) plus ordinary decoupling. For a hobbyist that means: connect the front ground fill and every ground pin to the plane with a bare wire or the component lead soldered on both sides, add a loose grid of extra stitching wires, and stop worrying. The plane should be *etched as little as possible*: the practical hobby approach is to leave the back solid, drill, and clear the copper round non-ground leads with a countersink or an oversize drill, which also sidesteps front-to-back registration error entirely.

## 1. The concern: cavity resonance, "patch antenna" and ground loops

**Does a plane joined at one point form a resonator?** Yes, in principle. Two parallel copper areas separated by dielectric are a parallel-plate capacitor with distributed inductance; when excited they support cavity modes. Circuits Assembly gives the first resonance as "the speed of light divided by twice the longest plane dimension" scaled by √εr, i.e. **f ≈ c / (2·L·√εr)**, and its worked example is a 4-inch (≈100 mm) plane at εr ≈ 4 resonating near **740 MHz** [1]. RF Essentials gives the full two-dimensional form f_mn = (c / (2√εr))·√((m/a)² + (n/b)²), with a and b the plane dimensions [2]. Applying the simple formula to FR4 with εr = 4.4 (√εr = 2.098, my calculation from the cited formula):

- 50 mm board: ≈ 1.43 GHz
- 100 mm board: ≈ 715 MHz
- 160 mm (Eurocard): ≈ 447 MHz

**When it matters.** Only when the circuit contains energy near those frequencies. Hartley's IPC paper gives the bandwidth of a digital edge as **F(GHz) ≈ 0.5 / Tr(ns)** [3]: a 5 ns edge (old HC logic) has significant content to about 100 MHz, a 1 ns edge to about 500 MHz. At audio and low-MHz the board is a tiny fraction of a wavelength and no cavity mode can be excited. The "patch antenna" label describes the same thing: the plane radiates only if something drives it near a mode.

**The standard cure.** Circuits Assembly states that many distributed stitching vias "suppress cavity resonances" by lowering the Q and breaking up the resonant regions, and that a stitching via placed far from where it is needed just adds inductance [1]. Spacing rules quoted across the industry are λ/20 as the general rule, with λ/10 acceptable for lower isolation: RF Essentials calls d_via < λ/20 at the maximum operating frequency "the universal rule", giving >25 dB isolation, and λ/10 for 20+ dB [2]; Flux and AllPCB give the same λ/20 rule with λ/10 as the looser limit [4][5]; AllPCB's example is 1 GHz → λ = 300 mm in air → 15 mm or less [5]. Plane-pair capacitance also keeps decoupling working where ceramic capacitors have gone inductive "above a few hundred megahertz" [1].

**The ground-loop worry, and split vs solid.** The concern that joining the front fill and the back plane at many points creates "ground loops" is the opposite of the EMC consensus. Henry Ott's view is that splitting a ground plane "has many potential problems", that "it is almost always better to have only a single reference plane (ground) for your system", and that high-frequency return current wants to flow in the plane directly under the trace, so a split forces it into a large loop that radiates [6]. Cadence's summary of the same mixed-signal material: "Provide only one reference ground plane to a system, otherwise, you are deliberately creating a dipole antenna" [7]. Hartley's IPC paper: keep forward and return paths tightly coupled, and when moving signals between two ground planes "use a transfer (stitching) via VERY near the signal via" [3]; in his 2019 keynote he repeated that referencing ground on the adjacent layer matters more than anything else and that fields spread through the clearance hole when a signal changes layer without a nearby return via [8]. The hobby experiment by 10maurycy10 measured this directly at 50 MHz: splitting the plane *increased* coupling, a double-sided ground helped only when vias tied the two sides together near the traces, and a stitched grounded guard trace was best (48 mV coupled vs 800 mV with no plane) [9]. In short: one plane, many connections; the "loop" formed by two ground connections is a low-impedance mesh, not a problem, and the real enemy is a single connection that forces return currents to detour.

## 2. What a hobby board gains, and when it is pointless

- **Return path under the trace.** In-Compliance's summary of Ott/Adamczyk: at ~1–100 kHz return current takes the lowest-resistance path; between roughly 500 kHz and 1 MHz it splits; at 10–100 MHz it flows almost entirely under the trace, "the path of least inductance" [10]. Design News' simulation gives the numbers: under-trace return ≈ 10.7 nH, large-loop return ≈ 491 nH, so at 1 MHz the loop is already 3 Ω versus 0.07 Ω [11]. Without a plane the designer has to route a return trace next to every signal to get this.
- **Low ground inductance.** ADI MT-031: wire is unsuitable as ground because of inductance (≈20 nH/inch for #22 wire, ≈200 mV across one inch at 10 mA/ns), and "the current returns must consist of large area ground planes" [12].
- **Crosstalk and EMI.** The 10maurycy10 measurements show a plane cutting capacitive coupling by more than 2× and inductive coupling by about 2.4× on a worst-case layout [9].
- **Where it is pointless.** Pure DC, slow audio with no digital or switching content, or high-impedance nodes where the extra ≈0.7 pF/cm trace-to-plane capacitance [9] is a nuisance (e.g. op-amp inverting inputs, crystal pins). Even there the plane is harmless if clearance is kept round such nodes, and Ott's point stands that a plane also saves etchant and resist problems on big copper areas [13].

## 3. Home-made vias

- **Bare wire soldered both sides** is the method most hobbyists settle on and the EEVblog thread's consensus is "a plain piece of wire soldered on both sides is better in every aspect" than rivets for vias [14]. jpanhalt uses 24 AWG (≈0.51 mm) wire in #72/#75 (0.53–0.64 mm) carbide holes so it stays in by friction [14]; Robotroom uses bare wire pushed through and soldered both sides and warns to keep vias away from DIP sockets so the solder blob does not lift the part [15].
- **Component leads soldered on both sides** work for most through-hole parts but not for relays, ZIF sockets, electrolytics or anything whose body sits flat on the board [14]. The classic RF prototyping note describes topside grounds "connected to the ground plane by periodic via holes soldered on both sides" [16].
- **Via rivets/eyelets.** Fortex PTH400 copper rivets come in 0.4, 0.6, 0.8 and 1.0 mm, 2.2–2.5 mm long for boards to 1.6 mm, about £41 per 1,000 ex VAT at RS [17][18]; the 0.6 mm part is a DIN 7340 tubular rivet with 0.6 mm bore, 0.8 mm outside, 1.3 mm head [19]. MIT's fab-lab tutorial found 0.6 mm rivets need **0.83–0.89 mm** holes and 1.0 mm rivets **1.50–1.55 mm** holes for a press fit, with 2 mm pads, set with two punches, and stresses "you must still solder to these rivets" [20]. Voltera's rule is hole = rivet outside diameter + 0.1 mm (0.7 mm for its 0.4/0.6 rivet, 1.5–1.6 mm for its 1.0/1.4 rivet) with pads at least the head diameter, and it recommends checking every joint with a meter [21]. Hobby opinion: usable for plated-through-style component holes, "ugly" and fiddly for vias [14].
- **Conductive ink/paste** was suggested but untested in the EEVblog thread [14]; Voltera's documentation treats riveted joints as mechanical and recommends soldering afterwards for a reliable bond [21]. I would not rely on it for ground.
- **Vias per ground pin.** No source gives a hobby-specific count; Hartley's rule is a return via *next to* every signal layer change [3][8], and ADI says IC ground pins should be soldered directly to the plane [12]. My recommendation: every ground lead passes through the plane and is soldered on both sides (one via per ground pin, free), plus one extra wire via beside each decoupling capacitor's ground end.

## 4. Antipads, thermal reliefs and whether to etch the plane at all

**Antipad size.** Sierra Circuits quotes IPC-2221 generic clearance as at least finished hole + 20 mil (0.5 mm), i.e. 10 mil (0.25 mm) radial, with drill-to-copper typically 8–10 mil [22]. That assumes factory registration. Home double-sided registration is far worse: Robotroom aims for no more than 1/50 inch (≈0.5 mm) [15], and Softsolder measured up to 25 mil (0.64 mm) offsets on a bad run and "a few mils" on a good one [23]. **My recommendation** for an etched antipad: diameter = hole + 2 × (0.25 mm electrical clearance + 0.3–0.5 mm registration allowance), so a 0.8 mm hole gets a 1.9–2.3 mm antipad and a 1.0 mm hole 2.1–2.5 mm.

**Thermal reliefs.** A plane pulls heat from a joint faster than a small iron supplies it; JLCPCB's table for through-hole pins on a plane is spokes 0.3–0.5 mm wide with a 0.4–0.6 mm gap, four spokes maximum per IPC-2221B, and KiCad's default is 0.508 mm [24]. These are comfortably etchable at home. **My recommendation:** four 0.5 mm spokes, 0.5 mm gap, on every ground lead in an etched plane; for the "solid plane" method below, no relief is possible, so use a hotter iron and accept a longer dwell.

**Should the plane be etched at all?** The long-standing hobby/ham answer is no. The "ugly construction" page records Dick Pattinson VE7GC's variation: the board is placed copper side up and "holes are drilled and countersunk so that the holes are isolated from the ground plane", with ungrounded components wired underneath [25]. The RF prototyping note describes etching one side only with "copper left on the other side to form the ground plane" and "small holes drilled to allow components" through [16]. Manhattan/Islander pad cutters (5 mm diamond cutters in a drill press) are the same idea in reverse [26]. The countersink is self-centred on the hole, so the clearance never suffers registration error, no resist is needed on the plane, and etchant is saved [13]. **My recommendation** for the program: output the plane layer anyway (for users who want to etch or laser it), but make the default workflow "leave solid, drill everything, countersink non-ground holes", with a drill chart listing which holes to countersink. A 2–2.5 mm countersink/drill tip on a 0.8–1.0 mm hole gives the same clearance as the antipads above.

## 5. Registration for home double-sided boards

- **Drill alignment holes through both films and the board at once, then locate on pins** (Robotroom): tape the two films toner-to-toner against a light, drill four holes through film+board+film, then re-register each film on pins; target ≤1/50 inch, holes placed far apart and not in a square so error is visible [15].
- **Glass plates with 6 mm steel locating pins** for photo exposure; the author found the laser printer's non-linearity a bigger error than the jig [27].
- **Pre-drill on CNC, align the sheet on a light table, tape one edge with heat-tolerant labels** (Softsolder); paper distortion in the fuser still gave up to 25 mil error [23].
- **Dowel pins at the board centre**, LPKF/T-Tech style, so the flipped board needs no offset [28].
- **Print both sides on one folded sheet** is suggested in Hackaday comments but without accuracy data [29].
Realistic accuracy: 0.1–0.3 mm with pins and care, 0.5–0.6 mm on a bad day [15][23]. Designing to 0.5 mm is prudent; the countersink method removes the need for plane registration altogether.

## 6. Recommendations for the program (my recommendations unless cited)

| Item | Default | Basis |
|---|---|---|
| Via wire | 0.5–0.6 mm tinned copper | 24 AWG friction-fit practice [14] |
| Via drill | 0.6 mm for 0.5 mm wire, 0.7 mm for 0.6 mm wire | hole ≈ wire + 0.1 mm, as Voltera's rivet rule [21] |
| Via pad, trace side | 1.6–2.0 mm | rivet pad practice [20][21] |
| Rivet option | 0.6 mm rivet → 0.85 mm hole, 2 mm pad; 1.0 mm rivet → 1.5 mm hole | [20][21] |
| Antipad (etched plane) | hole + 1.1 mm (≈1.9 mm for 0.8 mm hole) | §4 |
| Countersink (solid plane) | 2.0–2.5 mm tip diameter on non-ground holes | §4 [25] |
| Thermal relief | 4 spokes, 0.5 mm wide, 0.5 mm gap | [24] |
| Ground pins | every ground lead through the plane, soldered both sides | [12][16] |
| Front fill to plane | at every ground pin **and** a grid at the spacing below, plus one via beside each decoupling cap | [1][3][9] |

**Stitching spacing versus highest frequency of interest**, FR4 εr = 4.4, λ_board = c / (f·√εr) (my arithmetic from the cited λ/10–λ/20 rules [2][4][5]):

| Highest frequency | λ in FR4 | λ/10 | λ/20 (recommended grid) |
|---|---|---|---|
| 1 MHz | 143 m | 14.3 m | 7.2 m (just use ground pins) |
| 10 MHz | 14.3 m | 1.43 m | 715 mm (ground pins suffice) |
| 100 MHz | 1.43 m | 143 mm | 72 mm |
| 500 MHz | 286 mm | 28.6 mm | 14 mm |
| 1 GHz | 143 mm | 14.3 mm | 7.2 mm |

Use 0.5/Tr for digital edges [3]; a practical floor of one stitch per 20–25 mm regardless of frequency keeps the plane Q low on any board and costs almost nothing.

**What to tell the user about the LC concern, in two sentences:** "Two copper sheets joined at one point do form a resonant cavity, but on a 100 mm FR4 board the first resonance is around 700 MHz, far above most hobby circuits. Joining the front ground to the back plane at every ground pin plus a loose grid of stitching wires turns that cavity into a low-impedance mesh, which is exactly how commercial multilayer boards are built."

## Sources

1. Circuits Assembly, "PCB Power Integrity Analysis: Why PDN Behavior Is a Geometry Problem" — https://www.circuitsassembly.com/ca/features-itemid-fix/455-tips-tricks/43487-pcb-power-integrity-analysis-why-pdn-behavior-is-a-geometry-problem.html
2. RF Essentials, "What is the effect of via stitching on the shielding effectiveness of a ground plane?" — https://rfessentials.com/rf-knowledge-base/what-is-the-effect-of-via-stitching-on-the-shielding-effectiveness-of-a-ground-p/
3. Rick Hartley, "Grounding to Control Noise and EMI", IPC Midwest 2007 — https://www.electronics.org/system/files/technical_resource/E14&S03-02.pdf
4. Flux, "Via Stitching PCB Guide" — https://www.flux.ai/p/blog/via-stitching-pcb-guide
5. AllPCB, "Minimum Drill Size and Via Stitching Grounding Techniques for EMC Compliance" — https://www.allpcb.com/allelectrohub/minimum-drill-size-and-via-stitching-grounding-techniques-for-emc-compliance
6. Henry W. Ott, "Partitioning and Layout of a Mixed-Signal PCB", EE Times 2001 — https://www.eetimes.com/?p=1143833
7. Cadence, "The Partitioning and Layout of a Mixed-Signal PCB for Electromagnetic Compatibility" — https://resources.system-analysis.cadence.com/blog/msa2021-the-partitioning-and-layout-of-a-mixed-signal-pcb-for-electromagnetic-compatibility
8. iConnect007, "AltiumLive Frankfurt 2019: Rick Hartley Keynote" — https://iconnect007.com/article/120662/altiumlive-frankfurt-2019-rick-hartley-keynote/120665/design?page=2
9. 10maurycy10, "Testing PCB ground plane myths" — https://10maurycy10-github-io.pages.dev/projects/testing_groundplanes
10. In Compliance Magazine, "Alternative Paths of the Return Current" — https://incompliancemag.com/alternative-paths-of-the-return-current/
11. Design News, "How Current Return Paths Affect Signal Integrity" — https://www.designnews.com/how-current-return-paths-affect-signal-integrity
12. Analog Devices MT-031, "Grounding Data Converters and Solving the Mystery of AGND and DGND" — https://www.analog.com/media/en/training-seminars/tutorials/MT-031.pdf
13. PICBASIC forum, "Etching and ground planes" — https://www.picbasic.co.uk/forum/archive/index.php/t-10952.html
14. EEVblog forum, "Home-made PCBs and vias" — https://eevblog.com/forum/manufacture/home-made-pcbs-and-vias/msg5375840
15. Robotroom, "PCB - Double-Sided Copper" — https://robotroom.com/PCB2.html
16. "RF Prototyping Techniques" (University of San Diego course note) — https://home.sandiego.edu/~ekim/otherjunk/rf_proto.pdf
17. RS Components, Fortex PTH400-RIV0.8 copper rivets — https://uk.rs-online.com/web/p/pcb-rivets-riveting-tools/2157008
18. RS Components, Fortex PTH400-RIV0.4 copper rivets — https://uk.rs-online.com/web/p/pcb-rivets-riveting-tools/2157005
19. element14, Fortex PTH-0.6RIVET — https://my.element14.com/fortex/pth-0-6rivet/rivet-0-6mm-pcb/dp/4049314
20. MIT Fab Academy, "PCB Rivets" — https://fab.cba.mit.edu/classes/863.16/doc/tutorials/PCB_Rivets
21. Voltera, "Working with Rivets" — https://docs.voltera.io/v-one/v-one-fundamentals/working-with-rivets
22. Sierra Circuits, "What are antipads?" — https://www.protoexpress.com/kb/what-are-antipads/
23. Softsolder, "Toner Transfer PCBs: Alignment Accuracy" — https://softsolder.com/2009/10/15/toner-transfer-pcbs-alignment-accuracy/
24. JLCPCB, "Optimizing Thermal Relief Pads" — https://jlcpcb.com/blog/thermal-relief-pad-design
25. "Ugly Construction" (QRP ham construction notes, VE7GC countersink variation) — https://ftp.unpad.ac.id/orari/orari-diklat/teknik/qrp/Ugly%20Construction.htm
26. NJQRP, "Islander Pad Cutter" — https://njqrp.org/islanderpadcutter/index.html
27. Imajeenyus, "Double-sided exposure jig" — https://imajeenyus.com/electronics/20110224_double_sided_exposure/index.shtml
28. Homebrew_PCBs archive, dowel-pin registration thread — https://synth-diy.org/yg-archives2/group/Homebrew_PCBs/thread/3433/
29. Hackaday, "Improved Double-Sided Toner Transfer Method" — https://hackaday.com/2026-09-29/improved-double-sided-toner-transfer-method/
