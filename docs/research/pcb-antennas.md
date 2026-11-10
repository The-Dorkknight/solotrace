# PCB antennas and the coil generator (0.10.0)

Notes behind the antenna parts (`src/solotrace/antennas.py`), the keep-out boxes and the coil generator
(`src/solotrace/coil.py`). Written down so that nobody has to take the numbers on trust. **None of this has been built,
etched or measured.** Everything here is a starting point for a person with a NanoVNA or an LCR meter.

## What was added

| Part | What it is |
|---|---|
| `ANT_MEANDER_315`, `_433`, `_868`, `_915`, `_2G4` | A meander monopole: one 1 mm trace, a stub up from the feed pad, then runs back and forth. Pin 1 = feed, pins 2 and 3 = ground, either side of the feed. A hatched keep-out box round it. |
| `ANT_WIRE_315` ... `_2G4` | A straight quarter-wave wire (a normal part in the parts list): its length is in the name, pin 1 = the wire, pin 2 = ground. |
| `ANT_KEEPOUT_10x10`, `20x10`, `20x20`, `30x15`, `40x20` | A bare keep-out rectangle with no pins: mark where a module's own antenna sits. |
| Coil from *Parts > PCB coil generator...* | A rectangular spiral sized by area plus inductance, or area plus turns. |

Bands: 315 MHz, 433.92 MHz, 868 MHz, 915 MHz and 2.45 GHz (the common licence-exempt bands for cheap remote-control
modules, LoRa modules and 2.4 GHz radios). The list is common knowledge of which bands such modules use; it is not a
list of what any given module uses, so check your module's datasheet.

## The formula

The trace is a quarter-wave monopole. The length of copper is

    L = c / (4 f sqrt(eps_eff))        eps_eff = (eps_r + 1) / 2 = 2.7   (FR4, eps_r taken as 4.4)

`(eps_r + 1) / 2` is a rule of thumb for a trace on a board with air above it and nothing underneath. It is not
a field solution. Real boards differ (laminate, thickness, copper, case, hand, battery). So each meander gets **10 %
extra copper** past the formula length, with a silk tick every 2 mm back from the tip (the longer tick is the formula
length). The idea is to measure the antenna and scratch copper back from the tip. If the resonance is too high, you
need copper added, not removed.

| Band | Formula length (mm) | Copper drawn (+10 %) |
|---|---|---|
| 315 MHz | 144.8 | 159.3 |
| 433.92 MHz | 105.1 | 115.6 |
| 868 MHz | 52.5 | 57.8 |
| 915 MHz | 49.8 | 54.8 |
| 2450 MHz | 18.6 | 20.5 |

(The test `tests/test_antenna.py` checks the drawn length against the formula.)

The wire whip is the free-space quarter wave, `c / (4 f)` (172.8 mm at 433.92 MHz). The part's note says a common rule
of thumb is to cut about 5 % shorter and trim while measuring.

## The keep-out

Every antenna part carries a keep-out box. Inside it, SoloTrace:

* reports **any copper** (a trace, a pad, a jumper, a via, an island) as a DRC error, kind `keepout`;
* cuts the **ground fill** and the **back-side ground plane** away from it;
* keeps the **autorouter** out (the box is a hard obstacle, so routes go round it, never through).

Why: antenna manuals from chip makers tell you to keep ground planes and other copper out from under and round a
printed antenna. For example, the TI application notes that were consulted while planning this (see below) say no ground
plane or traces beneath the antenna. The box sizes here are my own: the length of the meander plus a 5 mm margin below
1 GHz and 3 mm at 2.4 GHz. They are not copied from any datasheet. **Ground copper beside the feed is still needed**
(a monopole works against ground), so pins 2 and 3 are ground pads either side of the feed, and the ground fill in the
rest of the board does the job. Keep ground out of the box and beside the feed.

## What was left out, and why

* **Other people's layouts are not copied.** The TI documents that describe tested antenna layouts (AN043 meander
  inverted-F, 15.2 x 5.7 mm; DN007 inverted-F, 25.7 x 7.5 mm on a 1 mm board; DN024 meander monopole, 38 x 25 mm with a
  2.0 mm trace on 1.6 mm FR4, in 868/915 MHz and dual-band versions; AN058 with a table of sizes for several antenna
  types) are listed here **for comparison only**. Those numbers were read from search results and web summaries: the TI
  PDFs themselves could not be downloaded here, so nothing was traced from them, and their layouts are the maker's
  copyright. Do not treat the sizes above as verified. Notice that those designs are also much more compact than the
  textbook quarter-wave length would suggest; the generated antennas are plain meanders, they are **not** as small.
* **No matching network.** Real antennas need a matching network (a pi network of small SMD parts, or a series part)
  tuned with a VNA. SoloTrace has no such part for this; the note on the part says to feed it through any matching
  parts. Hand-soldering a pi network onto the feed is a normal approach.
* **Not included:** inverted-F antennas, chip antennas, GPS patch antennas, 125 kHz coils, loop antennas. Say if you want
  any of them.
* **ESP32 / Wi-Fi module keep-outs.** Many modules need a clear area past the module's antenna end. The size is in each
  module's datasheet. I did not enter numbers from memory. Use the bare keep-out box and size it from your datasheet.
* **No antenna performance claims.** No gain, bandwidth or range is claimed anywhere.
* **Nothing has been simulated or measured**, not even with a field solver.

## The coil generator

Choose the **outer size** and either **the inductance wanted** (the generator finds the number of turns and the pitch
that come closest) or **the number of turns** (it works out the inductance, spreading the turns over the area). Track
width, the smallest gap between turns (default 0.4 mm), copper thickness (default 35 um) and an optional frequency
(it then prints the parallel capacitor that would resonate the coil) are the other settings.

### How the inductance is worked out

The spiral is a chain of straight rectangular bars.

* Each bar has the self inductance of a straight flat conductor (Rosa; Grover, *Inductance Calculations*):
  `L = mu0/(2 pi) * l * [ln(2l/(w+t)) + 0.50049 + (w+t)/(3l)]`.
* Every pair of **parallel** bars has a mutual inductance (Grover), summed with `+` when the currents run the same
  way and `-` when they run opposite ways. Bars at right angles do not couple.
* The total is the sum of the self terms plus twice the sum of the mutual terms.

That is a textbook method that needs no fitted coefficient. **Cross-check:** `tests/test_coil.py` compares the result for
three square coils with the square-spiral current-sheet formula of Mohan, Hershenson, Boyd and Lee (IEEE Journal of
Solid-State Circuits 34, 1999): `L = mu0 n^2 d_avg (c1/2) [ln(c2/rho) + c3 rho + c4 rho^2]` with the square values
`c1 = 1.27`, `c2 = 2.07`, `c3 = 0.18`, `c4 = 0.13`. The test accepts a difference up to 8 %; the three cases come out +1.3 %, +1.4 % and +2.5 % above the
formula. That agreement shows the two calculations are consistent, it does not show the real coil will measure that.

**What the estimate leaves out:** the coil's own capacitance and self-resonance, skin effect and proximity effect (the
DC resistance is shown, the AC one is not), a ground fill or plane under or near it, ferrite, metal, a case, and the
tolerances of a home-etched board. It is a single-layer coil in air. Measure the real coil and trim.

### The single-sided problem

On a one-sided board the inner end of a spiral has to cross the turns to come out. The generated part therefore has
three pins:

* **pin 1**: the outer end;
* **pin 2**: the inner end, in the middle of the hollow;
* **pin 3**: a landing pad outside the coil.

You solder an **insulated wire** (enamelled or sleeved, so it cannot touch the turns) from pin 2 to pin 3. The part
ties 2 and 3 into one net and counts them as already joined, so the router does not try to run a trace across the coil
and nothing is reported as unrouted. Wire your circuit to pins 1 and 3. A 2 mm copper-free keep-out box surrounds the
coil.

### Not provided

No reader-IC matching (for NFC or RFID), no tuning-capacitor selection beyond the single parallel value, no
multi-layer or round coils.

## Sources

* F. W. Grover, *Inductance Calculations*, 1946 (reprinted by Dover): self and mutual inductance of straight bars.
* S. S. Mohan, M. del Mar Hershenson, S. P. Boyd, T. H. Lee, "Simple accurate expressions for planar spiral
  inductances", IEEE JSSC 34 (10), 1999.
* The rule-of-thumb effective permittivity `(eps_r + 1) / 2` for microstrip is textbook material; it is a rule of thumb
  here, not a result.
* Texas Instruments application notes AN043, AN058, DN007, DN024 (names only, see "What was left out").
