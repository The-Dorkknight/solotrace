<!-- Research note written for SoloTrace 0.5.0 (November 2026) from manufacturer package and land-pattern documents fetched at the time; entries marked unlabelled or unsourced were NOT put in the library. Origin convention here is the package centre; the library moves each pattern so that pin 1 is at the part origin, like every other SoloTrace part. -->

# Hand-solderable SMD land patterns for a single-sided home-etched board ("Pro" library)

## Summary

All numbers below were taken from manufacturer package/land-pattern documents fetched during this session (Diodes Inc package files, TI mechanical drawings, Vishay, Microchip, KEMET, Nichicon, Sumida, TDK, Bourns, onsemi). I could not get a quotable copy of the IPC-7351 tables themselves; where a manufacturer states that its pattern follows IPC-7351 (Vishay chip resistors) or gives IPC-style density levels (KEMET tantalum), that is noted. Several PDFs are drawings whose dimension labels did not survive text extraction; those values are flagged "unlabelled" and must be checked against the drawing before use, and a few packages (4x4 inductor, 6x6 tactile switch, SOIC-16 narrow and SOIC-18W/24W/28W from TI) have no reliably sourced pattern and are marked as such. Convention used throughout: origin at package centre, X to the right and Y up as seen from above (component side); "pad L x W" is length along the lead/terminal direction x width across it. The 0.3 mm copper gap rule rules out SOT-363 (0.65 mm pitch), SOD-323 (pads fine but part very small; see note) and the Diodes-style SOT-23 pattern with 0.8 mm-wide pads; the TI-style SOT-23 pattern (0.6 mm-wide pads on 0.95 pitch = 0.35 mm gap) is the one to use.

## 1. Chip resistors / capacitors (2 terminals, non-polar)

Source: Vishay D/CRCW e3 datasheet, "Recommended solder pad dimensions" (G = gap between pads, Y = pad length along the part, X = pad width, Z = overall span; Vishay states the values follow IEC 61188-5 / IPC-7351). Second source: Panasonic thick-film chip resistor land-pattern table (a = gap, b = overall span, c = pad width; pad length = (b - a)/2), given as ranges. Pin 1 at x = -(G+Y)/2, pin 2 at +(G+Y)/2, both pads Y x X.

| Size (metric) | Body L x W | Vishay reflow G / Y / X / Z | Vishay wave (roomier) G / Y / X / Z | Panasonic a / b / c |
|---|---|---|---|---|
| 0603 (1608) | 1.55 x 0.85 | 0.75 / 0.75 / 1.00 / 2.25 | 0.65 / 1.10 / 1.25 / 2.85 | 0.7-0.9 / 2.0-2.2 / 0.8-1.0 |
| 0805 (2012) | 2.0 x 1.25 | 1.00 / 0.95 / 1.45 / 2.90 | 0.90 / 1.30 / 1.60 / 3.50 | 1.0-1.4 / 3.2-3.8 / 0.9-1.4 |
| 1206 (3216) | 3.2 x 1.6 | 1.50 / 1.05 / 1.80 / 3.60 | 1.40 / 1.40 / 1.95 / 4.20 | 2.0-2.4 / 4.4-5.0 / 1.2-1.8 |
| 1210 (3225) | 3.2 x 2.5 | 1.70 / 1.10 / 2.80 / 3.90 | 1.80 / 1.45 / 2.95 / 4.70 | 2.0-2.4 / 4.4-5.0 / 1.8-2.8 |
| 2010 (5025) | 5.0 x 2.5 | 3.50 / 1.45 / 2.80 / 6.40 | 3.40 / 1.65 / 2.85 / 6.70 | 3.6-4.0 / 6.2-7.0 / 1.8-2.8 |
| 2512 (6432) | 6.3 x 3.15 | 4.75 / 1.45 / 3.50 / 7.65 | 4.60 / 1.60 / 3.65 / 7.80 | 5.0-5.4 / 7.6-8.6 / 2.3-3.5 |

Worked example, 0805 Vishay wave pattern: pad 1 at (-1.10, 0), pad 2 at (+1.10, 0), each 1.30 x 1.60. The wave-solder set is the roomier one and is the better hand-soldering choice; all gaps are >= 0.65 mm. 0603 is the smallest size I would include (gap 0.65-0.75 mm; hobby reports below say toner-transfer accuracy drops below 0805).

## 2. Diodes

Diodes Inc package files use C = pad centre-to-centre, G = gap, X = pad length (along lead), Y = pad width, X1/Z = overall span. Cathode is the banded end; in Diodes' drawings the cathode pad is pad 1 for rectifiers - check the symbol mapping in your library. Pads at x = -C/2 (cathode, pin 1) and +C/2 (anode, pin 2).

| Package (JEDEC) | Body (nominal, Diodes) | C | G | pad L x W | overall | Second source |
|---|---|---|---|---|---|---|
| SMA (DO-214AC) | 4.0-4.6 x 2.29-2.92, lead span 4.8-5.59 | 4.00 | 1.50 | 2.50 x 1.70 | 6.50 | Vishay SMA drawing gives only min/max pad limits (pad width >= 1.68, length >= 1.52) |
| SMB (DO-214AA) | 3.30-3.94 x 4.06-4.57, span 5.0-5.59 | 4.30 | 1.80 | 2.50 x 2.30 | 6.80 | Vishay SMB: pad width >= 2.18, length >= 1.52, gap <= 2.159, overall 5.59 ref |
| SMC (DO-214AB) | 5.59-6.22 x 6.6-7.11, span 7.75-8.13 | 6.90 | 4.40 | 2.50 x 3.30 | 9.40 | Vishay SMC: pad width >= 3.20, length >= 1.52, gap <= 4.69, overall 8.13 ref |
| SOD-123 | 2.65 x 1.55, span 3.65 | 3.15 (derived) | 2.25 (derived) | 0.90 x 0.95 | 4.05 | - |
| SOD-123F / FL | 2.70 x 1.80, span 3.50 | 2.86 | 1.52 | 1.34 x 1.80 | 4.20 | - |
| SOD-323 | 1.70 x 1.30, span 2.50 | 2.11 (derived) | 1.52 (derived) | 0.59 x 0.45 | 2.70 | Gap is fine (1.5 mm) but pads are 0.59 x 0.45 - include only as "advanced" |
| MELF (DO-213AB) | 5.0 x 2.5 dia | 4.80 | 3.30 | 1.50 x 2.70 | 6.30 | - |
| MiniMELF (DO-213AA) | 3.5 x 1.45 dia | 3.50 | 2.10 | 1.30 x 1.70 | 4.70 (Diodes' own figures are 0.1 mm inconsistent: C-X = 2.2, not 2.1) | - |

Diodes' note on every file: for wave soldering add 0.2 mm to the Z (overall) dimension; hand soldering benefits from the same lengthening of the toe.

## 3. Transistors and small power packages

### SOT-23 (3-pin, TO-236AB)
Top view: pin 3 alone at the top centre; pins 1 (left) and 2 (right) along the bottom; numbering counter-clockwise. Pitch 0.95 mm, body 2.9 x 1.3 (Diodes typ), lead span 2.8-3.0.
- TI DBV0005A/DBV0006A land pattern (same body and pitch, JEDEC MO-178): pads 1.1 (L) x 0.6 (W), pitch 0.95, row centre-to-centre 2.6. Gap between adjacent pads 0.35 mm: OK.
- Diodes SOT23 file: C (row c-c) 2.0, X (pad width) 0.8, Y (pad length) 0.9, Y1 (overall) 2.9, plus an "X1 = 1.35" value I could not interpret. Pad width 0.8 on 0.95 pitch leaves only 0.15 mm: do NOT use on this board.

| pin | x | y | pad L x W (TI) |
|---|---|---|---|
| 1 | -0.95 | -1.30 | 1.1 x 0.6 |
| 2 | +0.95 | -1.30 | 1.1 x 0.6 |
| 3 | 0 | +1.30 | 1.1 x 0.6 |

### SOT-23-5 (SOT-25 / SC-74A) and SOT-23-6 (SOT-26)
Pins 1-3 along the bottom left-to-right, then 4 (and 5, 6) along the top right-to-left (counter-clockwise). Pitch 0.95, body 3.0 x 1.6.
- TI DBV0005A / DBV0006A: pads 1.1 x 0.6, pitch 0.95, row c-c 2.6 (outer span 3.7).
- Diodes SOT25 / SOT26: C1 (pitch) 0.95, C (row c-c) 2.40, G 1.60, X (width) 0.55, Y (length) 0.80, Z/Y1 (overall) 3.20. Gap 0.40 mm: OK.

| pin (SOT-23-6) | x | y | pad L x W (TI) |
|---|---|---|---|
| 1 | -0.95 | -1.30 | 1.1 x 0.6 |
| 2 | 0 | -1.30 | 1.1 x 0.6 |
| 3 | +0.95 | -1.30 | 1.1 x 0.6 |
| 4 | +0.95 | +1.30 | 1.1 x 0.6 |
| 5 | 0 | +1.30 | 1.1 x 0.6 |
| 6 | -0.95 | +1.30 | 1.1 x 0.6 |
SOT-23-5 omits pin 5 at (0, +1.3) and renumbers the top-left pad as 5.

### SOT-89 (3 leads + tab, pitch 1.5)
Body 4.5 x 2.5 (Diodes). Pins 1, 2, 3 along the bottom at x = -1.5, 0, +1.5; the centre pin 2 is continuous with the tab that extends up the body. Diodes suggested pad layout (raw labels): C 1.500 (pitch), X 0.580 (outer pad width), Y 1.630 (outer pad length), X1 0.760 (centre lead width), X2 1.933 (tab width), Y2 1.500, Y3 0.635, Y4 4.530 (overall length), Y5 2.265, G 0.244, Y1 3.030. The 0.244 gap is between the widened tab section and the outer pads; for this board narrow the tab to the 0.76 mm lead width over its lower part so the outer pads keep >= 0.3 mm (outer pads at 0.58 wide on 1.5 pitch leave 0.92 mm to a 0.76 mm centre pad... i.e. (1.5 - 0.29 - 0.38) = 0.83 mm). Treat the raw list as needing a look at the drawing.

### SOT-223 (3 leads + tab, pitch 2.3)
Pins 1, 2, 3 along the bottom (left to right), tab (pin 4, internally pin 2) at the top. Body 6.5 x 3.5, lead span 7.0.
- Diodes SOT223: C 2.30 (pitch), C1 6.40 (lead row to tab c-c), X 1.20 (lead pad width), Y 1.60 (lead pad length), X1 3.30 (tab width), Y1 1.60 (tab length), Y2 8.00 (overall).
- TI DCY0004A (LM317 datasheet drawing): lead pads 2.15 x 0.95 (3x), pitch 2.3, tab pad 2.15 x 3.25, row c-c 5.8 (outer span 7.95). Labels partly inferred from the drawing text.

| pin | x | y | pad L x W (Diodes / TI) |
|---|---|---|---|
| 1 | -2.3 | -3.2 / -2.9 | 1.6 x 1.2 / 2.15 x 0.95 |
| 2 | 0 | -3.2 / -2.9 | same |
| 3 | +2.3 | -3.2 / -2.9 | same |
| 4 (tab) | 0 | +3.2 / +2.9 | 1.6 x 3.3 / 2.15 x 3.25 |
Gaps 1.1 mm (Diodes) or 1.35 mm (TI): fine.

### SOT-363 (SC-70-6)
Diodes: pitch 0.65, pads 0.60 x 0.42, gap between adjacent pads 0.23 mm. Below the 0.3 mm rule: OUT of scope (say so in the library).

### TO-252 (DPAK), 2 leads + tab, pitch 2.28
Top view: tab at the top (pin 4 / tied to pin 2); leads 1 (left) and 3 (right) at the bottom at x = +/-2.28 (the centre lead is cut off). Body 6.1 x 6.58 (Diodes typ), lead span 9.4-10.41.
- Diodes TO252-3L (DMN4040SK3 datasheet, newer format): E1 2.3 (pitch), X1 1.5 (lead pad width), Y1 2.5 (lead pad length), X2 7.0 (tab width), Y2 7.0 (tab length), C 6.9 (lead-pad to tab-pad c-c), Z 11.6 (overall).
- Diodes TO252 (MJD31C datasheet, older format): C 4.572 (pin 1 to pin 3 c-c), X 1.060 (lead pad width), X1 5.632, Y 2.600 (lead pad length), Y1 5.700, Y2 10.700 (overall); tab width not extracted.
- Vishay DPAK land pattern (doc 62165) and onsemi case 369AE were fetched but their labels did not survive extraction (Vishay values seen: 4.329, 2.333, 2.28, 1.524; onsemi 5-lead: 10.5, 6.0, 5.7, 2.1, 0.8, 1.27 pitch, 5.04 ref, 2.74 ref) - not usable without the drawing.

| pin | x | y | pad L x W (Diodes new) |
|---|---|---|---|
| 1 | -2.28 | -4.70 | 2.5 x 1.5 |
| 3 | +2.28 | -4.70 | 2.5 x 1.5 |
| 2/4 tab | 0 | +2.20 | 7.0 x 7.0 |
(y values from C = 6.9 c-c split about the origin; lead gap 0.8 mm, lead-to-tab gap 2.15 mm.)

### TO-263 (D2PAK), 3 leads (or 2) + tab, pitch 2.54
Body 8.39-9.65 x 9.66-10.66, lead span 14.61-15.87 (Diodes TO263AB). Leads at x = -2.54, 0, +2.54 (pin 2 cut on the 2-lead version), tab at top.
- Diodes TO263AB file: C 5.08 (pin 1 to pin 3), X 1.10 (lead pad width), Y 3.50 (lead pad length), X1 10.41 (tab width), Y1 7.01 (tab length), Y2 15.99 (overall).
- Diodes TO263 (alldatasheet copy, different revision): X 10.9 (tab width), X1 1.05 (lead width), Y 15.7 (overall), Y1 9.1 (tab length), Y2 2.5 (lead pad length), C 1.7 (lead-pad to tab gap). The two revisions disagree on tab length (7.0 vs 9.1) and lead length (3.5 vs 2.5); give both.
- onsemi case 418 (D2PAK-3) outline fetched (pitch 2.54 BSC, body 8.64-9.65 x 9.65-10.29) but no footprint in that drawing.
TO-268 (D3PAK): not sourced in this session.

## 4. ICs - SOIC family (gull-wing, pitch 1.27)

Top view: pin 1 top-left (dot / bevelled edge), count down the left side, then from bottom-right up the right side (counter-clockwise). Pad centres: left row at x = -S/2, right row at +S/2, where S is the row centre-to-centre span; pin k (k <= N/2) at y = +((N/2 - 1)/2 - (k - 1)) x 1.27; pin N+1-k at the same y on the right. Pad L x W given as length (along X) x width (along Y). Gaps between adjacent pads are 0.67 mm for 0.6-wide pads, 0.62 mm for Microchip's 0.65.

| Package | JEDEC / body | Pad L x W | Row c-c S | Source |
|---|---|---|---|---|
| SOIC-8 narrow (D) | MS-012, 4.9 x 3.9 | 1.55 x 0.60 | 5.4 | TI D0008A drawing (msoi002) |
| SOIC-14 narrow | MS-012, 8.65 x 3.9 | 1.55 x 0.60 | 5.4 | TI D0014A (SN74HC00 datasheet); Microchip 14-lead SL: 1.55 x 0.60, C 5.40 |
| SOIC-16 narrow | MS-012, 9.9 x 3.9 | not fetched | - | TI's D0016A drawing was not in any datasheet I could retrieve; the D family shares one pattern (1.55 x 0.6, 5.4) in the D8 and D14 drawings, but confirm before adding |
| SOIC-16 wide (DW) | MS-013, 10.3 x 7.5 | 2.0 x 0.60 | 9.3 | TI DW0016A (SN74HC595 datasheet) |
| SOIC-20 wide | MS-013, 12.8 x 7.5 | 2.0 x 0.60 | 9.3 | TI DW0020A (SN74HC245 datasheet) |
| SOIC-18W / 24W / 28W | MS-013 | not fetched | 9.3 expected | TI datasheets I tried (ULN2803A, PCA9555, MAX3243) did not include the DW drawings; the DW family uses the same 2.0 x 0.6 @ 9.3 pattern in the two drawings retrieved, but not verified for these pin counts |
| SOP-8 "EIAJ" 5.3 mm (SOIJ, 208 mil) | body 5.25 x 5.26, lead span 7.94 | 1.70 x 0.65 | 7.30 | Microchip 8-lead SM (SOIJ) drawing C04-056/2056: X 0.65, Y 1.70, C 7.30, Z 9.00, G1 5.60 |
| SOP-16 5.3 mm (TI NS) | 10.2 x 5.3 | 1.85 x 0.60 | (7) | TI NS0016A (TL494 / SN74HC165 datasheets); the "(7)" span is the only parenthesised value and is inferred to be the row c-c |
| SOIC-8 PowerPAD (TI DDA) | MS-012, 4.9 x 3.9 | 1.55 x 0.60 | 5.4 | TI DDA0008B (pptd058): PCB thermal pad 2.71 x 3.4 (same as stencil aperture); exposed-pad callouts (2.95) x (4.9) also appear, flagged "metal pad size may vary" |

SOIC-8 narrow full table (TI):

| pin | x | y | pad L x W |
|---|---|---|---|
| 1 | -2.7 | +1.905 | 1.55 x 0.6 |
| 2 | -2.7 | +0.635 | 1.55 x 0.6 |
| 3 | -2.7 | -0.635 | 1.55 x 0.6 |
| 4 | -2.7 | -1.905 | 1.55 x 0.6 |
| 5 | +2.7 | -1.905 | 1.55 x 0.6 |
| 6 | +2.7 | -0.635 | 1.55 x 0.6 |
| 7 | +2.7 | +0.635 | 1.55 x 0.6 |
| 8 | +2.7 | +1.905 | 1.55 x 0.6 |

Note: SOIC vs SOIJ confusion - a 5.3 mm-body SOP-8 on a 3.9 mm SOIC pattern will not fit (row span 7.3 vs 5.4); keep them as separate footprints.

## 5. Capacitors

### Tantalum, moulded (EIA 535BAAC cases)
Source: KEMET T491 datasheet, Table 2 "Land Dimensions/Courtyard": X = land width, Y = land length, C = land spacing (gap between the two pads), V1/V2 = courtyard. KEMET's density levels: A = most land (recommended for wave soldering, widest reflow window), B = median/nominal, C = least. For hand soldering use A. Pads at x = +/-(C/2 + Y/2). Polarity: KEMET and Vishay 293D both mark the anode (+) end with a stripe/band (KEMET adds a bevel on the + end on taller cases); Kyocera-AVX TAJ: "polarity band on the anode (positive) end". Library convention: pin 1 = anode (+) = banded end.

| Case | Body L x W x H | Level A: X / Y / C | Level B: X / Y / C | Level C: X / Y / C |
|---|---|---|---|---|
| A (3216-18) | 3.2 x 1.6 x 1.6 | 1.35 / 2.15 / 1.45 | 1.25 / 1.75 / 1.35 | 1.15 / 1.35 / 1.25 |
| B (3528-21) | 3.5 x 2.8 x 1.9 | 2.35 / 2.15 / 1.45 | 2.25 / 1.75 / 1.35 | 2.15 / 1.35 / 1.25 |
| C (6032-28) | 6.0 x 3.2 x 2.5 | 2.35 / 2.65 / 2.60 | 2.25 / 2.25 / 2.50 | 2.15 / 1.85 / 2.40 |
| D (7343-31) | 7.3 x 4.3 x 2.8 | 2.55 / 3.75 / 2.70 | 2.45 / 3.35 / 2.60 | 2.35 / 2.95 / 2.50 |

Example, case B level A: pads 2.15 x 2.35 at x = +/-1.80. Caution: for case D the extracted level-B/C values give an overall span (2Y + C) slightly larger than the listed courtyard V1, so re-check the D row against the PDF (the Farnell copy of the datasheet was the one read). Body sizes from Vishay 293D / Kyocera-AVX TAJ. Secondary: Kyocera-AVX MLCC-substitution sheet gives IPC-style pads for 3216 (pad 1.6 L x 1.8 W, gap 1.2, Z 4.4) and 3528 (1.6 x 2.7, gap 1.2, Z 4.4).

### SMD aluminium electrolytic (V-chip)
Source: Nichicon "Recommended land size, soldering by reflow" (X, Y, a labelled on a drawing only; reading them as X = pad width, Y = pad length, a = gap between pads - interpretation, verify). Pads at x = +/-(a/2 + Y/2), size Y x X. Nichicon UWX case data: phi 4: base 4.3 sq, pitch-related E 1.0; phi 5: 5.3 sq; phi 6.3: 6.6 sq; phi 8: 8.3 sq. Polarity: Nichicon labels one terminal "Negative", marking is "black print on the case top" - the datasheet text does not state which terminal the band marks (industry practice is the negative; confirm in your own datasheets). The base plate has a chamfered corner on one side (visible in Nichicon's drawing as the A/B/C/E dimensions) which most CAD libraries use for orientation.

| Size (D x L) | X (width) | Y (length) | a (gap) |
|---|---|---|---|
| 4 x 5.4/5.5 | 1.6 | 2.6 | 1.0 |
| 5 x 5.4/5.5 | 1.6 | 3.0 | 1.4 |
| 6.3 x 5.4/5.5 and 6.3 x 7.7 (Nichicon lists "phi 6.3" once) | 1.6 | 3.5 | 2.1 |
| 8 x 6.2 (and 8 x 5.5) | 2.5 | 4.0 | 2.1 |
| 8 x 10 | 2.5 / 4.3 | 3.5 / 5.3 | 3.0 / 2.0 (two tables in the same document; second set from the heavier-terminal types) |
| 10 x 10 | 2.5 / 4.3 | 4.0 / 5.6 | 4.0 / 3.3 (likewise) |

Panasonic's SMD-aluminium land-pattern sheet (AL_landP_e) was fetched but its table is an image; only the letters a/b/c are in the text, so no Panasonic numbers are quoted.

## 6. Shielded power inductors (patterns vary by maker - always check the part's own datasheet)

| Family / example | Body | Pattern (pad L x W, gap, overall) | Status |
|---|---|---|---|
| 4 x 4 (SRN4018 type) | 4 x 4 x 1.8 | not obtained (Bourns SRN4018 PDF blocked from both Bourns and Mouser) | unsourced |
| 6 x 6, Sumida CDRH6D28 | 7.0 x 7.0 x 3.0 max (6.7 sq body) | pads 2.65 long, gap 2.0, overall 7.3; width not labelled (6.5 appears in the drawing) | labels inferred |
| 6 x 6, TDK VLS6045EX | 6.0 x 6.0 x 4.5 | values printed "1.9 2.3 1.9" and "5.1" -> pads 1.9 x 5.1, gap 2.3 | unlabelled |
| 7 x 7, Bourns SRR7045 | 7.0 x 7.0 x 4.5 | overall 7.80, gap 4.2, pad length 1.8, pad width 2.4 (ref) | labels inferred |
| 10 x 10, Sumida CDRH104R | 10.5 x 10.3 x 4.0 max | pads 1.6 long x 3.2 wide, gap 7.3, overall 10.5 | labels inferred |
| 10 x 10, Bourns SRR1005 | height 5.2 max | values 12.7, 10.0, 7.6, 7.3, 3.0, 2.8, 2.4, 2.2, 1.95 seen, no labels | unusable |
| Wurth WE-PD 7447789004 (7332) | 7.3 x 7.3 x 3.2 | values 4.0, 2.0, 1.7, 2.0 seen, no labels | unusable |

Only CDRH104R and CDRH6D28 have internally consistent numbers (pad + gap + pad = overall); treat all of these as "check the drawing" entries.

## 7. Connectors / other
- 6 x 6 SMD tactile switch: Omron B3FS datasheet has a "PCB Pad (Top View)" drawing (values seen: 6.3, 4.5 +/-0.2, 3.1, 6.4, 9.6, 2.6, 5.9, 8, 0.7) and C&K/Littelfuse PTS645 SMT has a "Recommended PCB layout" (values 5.8, 3.2, 6.4, 9.5, 2.4, 1.8, 1.4, 1.6 for the G type), but neither set is labelled in the text, so no pattern is given. Omron pin numbering: with the logo at the top, the terminal right of the logo is 1 and bottom-right is 3 (left side 2 and 4).
- SMD pin header, USB-C, micro-USB: skipped as requested / no standard pattern.

## 8. Short answers

(a) IPC-7351 density levels. IPC-7351 defines three land-pattern sizes per package family: Level A = Maximum/"Most" (largest toe/heel/side solder-joint goals and courtyard excess; intended for low-density boards, wave soldering and maximum rework room), Level B = Median/"Nominal" (the default for a general reflow process), Level C = Minimum/"Least" (smallest, for dense boards with a proven process); these are not the same as IPC product Classes 1/2/3. The pad size is computed from the component's min/max lead dimensions plus a toe, heel and side "solder joint goal" and fabrication/placement tolerances; "nominal" means the Level B goals (for gull-wing leads IPC-7351B uses 0.35 mm toe and heel at nominal, with the levels stepping in roughly 0.2 mm increments). KEMET labels the same three levels A/B/C in its tantalum table. Sources: bestpcbs IPC-7351 explainer; PCB Libraries forum (Tom Hausherr); KEMET T491 Table 2.

(b) No solder mask, 0.3 mm gaps, SOIC-8 by hand. SOIC pads at 1.27 mm pitch with 0.6 mm pads leave 0.67 mm of bare copper between pads, well above 0.3 mm, and hobby reports confirm SOIC (and even 0.8 mm TQFP) is routinely hand-soldered on unmasked home-etched boards: "I regularly use some SMD devices (TQFP with 0.8 mm pitch) without a solder mask and it's no problem" (EEVblog thread), while the same thread warns that toner transfer "starts to fail" below 0805 and that side-etching makes pads smaller than drawn (so draw the roomier wave-solder/level-A pads and keep gaps at or above 0.3 mm). The practical guides agree on technique: tack one corner pin, check alignment, then solder each pin from the side with a thin tip (josepheoff), or flux liberally and drag-solder, clearing bridges with more flux or wick ("touch it with the iron tip and some wick"); liquid/gel flux is "essential" without a mask because nothing else stops solder wandering along bare copper (trxe guide). Limit iron contact to 3-5 s per joint to avoid lifting pads on home boards. Without mask, also keep ground pours well clear of SOIC pads (0.3 mm is enough for etching but 0.5 mm+ makes bridging to the pour less likely) - this last point is my inference from the gap data, not a quoted guide.

(c) Bottom-side footprints are mirrored. A PCB layout is always drawn as seen from the top (component side) looking through the board. A part placed on the bottom therefore appears mirrored (pin order reversed left-to-right) in that view, because you are seeing its underside; the footprint definition itself is not changed, only its presentation. KiCad: the Flip command (F) moves a footprint to the opposite side and swaps every front layer to the corresponding back layer; the footprint is then displayed mirrored in the normal top view, and View > Flip Board View shows the board "as if you are looking from the bottom (that is, mirrored around the Y-axis)" (KiCad manual; KiCad forum: "as the layout is seen from top, the footprint on bottom is seen mirrored"). Eagle: the MIRROR command moves a part to the bottom side, moving tPlace/tNames/tValues to bPlace/bNames/bValues and showing the part horizontally mirrored in the top view (Autodesk Eagle forum). For your single-sided program this means: if the copper is on the bottom and parts are on the top, draw footprints un-mirrored in the top view (as all the tables above are) and mirror the whole artwork once when printing the etch mask; if parts are soldered on the copper (bottom) side, the footprints must be mirrored in the top view, or the user must select "bottom" and the program mirror them.

## Sources

Diodes Inc package files: https://www.diodes.com/assets/Package-Files/SMA.pdf ; https://www.diodes.com/assets/Package-Files/SMB.pdf ; https://www.diodes.com/assets/Package-Files/SMC.pdf ; https://www.diodes.com/assets/Package-Files/SOD123.pdf ; https://www.diodes.com/assets/Package-Files/SOD123F.pdf ; https://www.diodes.com/assets/Package-Files/SOD323.pdf ; https://www.diodes.com/assets/Package-Files/SOT23.pdf ; https://www.diodes.com/assets/Package-Files/SOT25.pdf ; https://www.diodes.com/assets/Package-Files/SOT26.pdf ; https://www.diodes.com/assets/Package-Files/SOT89.pdf ; https://www.diodes.com/assets/Package-Files/SOT223.pdf ; https://www.diodes.com/assets/Package-Files/SOT363.pdf ; https://www.diodes.com/assets/Package-Files/MELF.pdf ; https://www.diodes.com/assets/Package-Files/MiniMELF.pdf ; https://www.diodes.com/assets/Package-Files/TO263AB%20(D2PAK).pdf
Diodes TO252 via datasheet mirrors: https://www.manualsdir.com/manuals/307290/diodes-dmn4040sk3.html?page=5 ; https://www.manualsdir.com/manuals/307699/diodes-mjd31c.html?page=6 ; Diodes TO263 alt revision: https://www.alldatasheet.pl/html-pdf/458084/DIODES/TO263/4614/21/TO263.html
Vishay: SMA https://www.vishay.com/docs/95400/sma.pdf ; SMB https://www.vishay.com/docs/95401/smb.pdf ; SMC https://www.vishay.com/docs/95402/smc.pdf ; CRCW resistors https://www.vishay.com/docs/20035/dcrcwe3.pdf ; DPAK outline https://www.vishay.com/docs/95627/d-pakto-252aa-m.pdf ; DPAK land pattern https://www.vishay.com/docs/62165/_pad_pattern_recommended_land_pattern_dpakto252_3lr.pdf ; 293D tantalum https://www.vishay.com/docs/40002/293d.pdf
onsemi: DPAK-5 case 369AE https://www.onsemi.com/download/package-drawing/pdf/369ae.pdf ; D2PAK case 418 https://www.onsemi.com/download/package-drawing/pdf/418.pdf
TI: SOIC D8 https://ti.com/lit/pdf/msoi002 ; SOIC D14 (SN74HC00) https://www.ti.com/lit/ds/symlink/sn74hc00.pdf ; DW16 (SN74HC595) https://www.ti.com/lit/ds/symlink/sn74hc595.pdf ; DW20 (SN74HC245) https://www.ti.com/lit/ds/symlink/sn74hc245.pdf ; NS16 (TL494) https://www.ti.com/lit/ds/symlink/tl494.pdf and https://www.ti.com/lit/ds/symlink/sn74hc165.pdf ; DDA PowerPAD https://www.ti.com/lit/pdf/pptd058 ; DBV6 https://ti.com/lit/pdf/mpds026 ; DBV5 https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/14/DBV_2D00_5_5F00_footprint.pdf ; DCY SOT-223 (LM317) https://www.ti.com/lit/ds/symlink/lm317.pdf ; also fetched: https://ti.com/lit/pdf/mpss116 (DWL8), https://ti.com/lit/pdf/mpss140 (DWZ8), https://ti.com/lit/pdf/mpss148 (DFG4), https://ti.com/lit/pdf/mpds025 (DCK5)
Microchip: SOIJ 8-lead https://onlinedocs.microchip.com/oxy/GUID-EF5727DA-42CC-4107-8984-4D8EAF42FF5D-en-US-1/GUID-CBD37C9E-CEF8-4839-8BF2-6384E10FF89E-high.pdf and https://sigma.octopart.com/165809000/technical_drawing/Microchip-24AA64-E-SM.pdf ; SOIC 14-lead SL https://onlinedocs.microchip.com/g/GUID-417F9387-DF9B-42E5-AA91-108A8C58208B-en-US-8/GUID-2B9B5754-8BE1-4DF5-B9CF-1D109505625A-high.pdf
Panasonic resistors (land pattern ranges) https://industrial.panasonic.com/cdbs/www-data/pdf/RDN0000/AOA0000C90.pdf ; body sizes https://www.digikey.cn/zh/htmldatasheets/production/2707648/0/0/1/erj-1gef10r0c.html ; Panasonic SMD aluminium land sheet (image only) https://industrial.panasonic.cn/content/data/CP/PDF/Alumi/AL_landP_e.pdf
KEMET T491 (Farnell copy) https://www.farnell.com/datasheets/1698764.pdf ; https://elcodis.com/parts/90462/T491B335M035AT_p15.html ; Kyocera-AVX TAJ https://datasheets.kyocera-avx.com/TAJ.pdf ; AVX substitution footprints https://lv.mouser.com/pdfdocs/AVXMLCC-TaSubstitution-Footprints.pdf
Nichicon: land sizes https://www.nichicon.co.jp/english/products/pdf/e-ch_ref.pdf and https://www.digikey.cn/htmldatasheets/production/1475100/0/0/1/uwx0g220mcl2gb.html ; UWX dimensions https://uploadcdn.oneyac.com/attachments/files/brand_pdf/nichicon/e-uwx.pdf
Inductors: Sumida https://products.sumida.com/products/pdf/CDRH6D28.pdf ; https://products.sumida.com/products/pdf/CDRH104R.pdf ; TDK https://product.tdk.com/system/files/dam/doc/product/inductor/inductor/smd/catalog/inductor_commercial_power_vls6045ex_en.pdf ; Bourns https://www.bourns.com/docs/Product-Datasheets/SRR7045.pdf ; https://www.bourns.com/docs/Product-Datasheets/SRR1005.pdf ; https://www.bourns.com/docs/Product-Datasheets/SRN6045.pdf ; Wurth https://www.we-online.com/components/products/datasheet/7447789004.pdf
Tactile switches: Omron B3FS https://dtsheet.com/doc/236028/omron-b3fs ; C&K PTS645 https://www.littelfuse.com/assetdocs/littelfuse-ck-tactile-pts645-series-datasheet?assetguid=d58fc8a8-f6e1-4527-ab68-27635e632e39
IPC-7351 density levels: https://www.bestpcbs.com/blog/2026/09/ipc-7351/?format=md ; https://pcblibraries.com/FORUM/topic2587.html
Hand soldering / no mask: https://eevblog.com/forum/projects/home-made-smd-pcbs/msg57091 ; https://josepheoff.github.io/posts/howtosolder-13soldersmdic ; https://www.trxe.com/smd-soldering-at-home-guide-south-africa
Bottom-side mirroring: KiCad manual https://docs.kicad.org/8.0/en/pcbnew/pcbnew.html ; KiCad forum https://forum.kicad.info/t/flip-components-pin-1-wrong/15743 ; Eagle forum https://forums.autodesk.com/t5/eagle-forum/layout-for-double-sided-components-pcb/td-p/7849002 ; DPAK pin-numbering discussion https://forum.kicad.info/t/ipc-7351b-to252-question/65826
