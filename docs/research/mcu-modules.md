# Microcontroller modules, OLEDs and SD modules: sourced physical data

Research notes behind the module footprints added in SoloTrace 0.7.0 (`src/solotrace/library.py`, `_build_modules`). The tests in `tests/test_modules.py` check the footprints against the row spacings and pin orders below. Where this file says *single source*, *disagree* or *not found*, the part's note in the app says so too.

Researched 2026-11-06. Every number below comes from a text source that was actually read (a parsed KiCad `.kicad_mod`/`.kicad_sym` file, an Eagle `.brd` XML file, a Fritzing part file, an Arduino core header, or the text of a wiki or datasheet page). Where nothing could be found in text, the entry says **not found**. Nothing was filled in from memory.

## How to read this file

- **Confidence words:** `verified-from-text` means read directly from an official or manufacturer text source (vendor KiCad library, vendor wiki text, vendor Eagle board file, datasheet text). `two sources agree` means two independent text sources give the same value. `single source` means only one community text file gives it. `not found` means no text source was found.
- **Coordinates:** these are KiCad footprint coordinates in mm. They use the top (component-side) view, and **+y points DOWN** (KiCad convention). Eagle coordinates (Pro Mini, Pro Micro) use **+y UP**. I converted those into the "top to bottom" lists myself.
- **"Row spacing"** is the centre-to-centre distance between the two rows of header holes.
- The repositories were cloned for reading during the research; the URLs are in the source table.
- The pin pitch is 2.54 mm everywhere unless a section says otherwise.

### Sources (short names used below)

| Short name | What it is | URL |
|---|---|---|
| SEEED-KICAD | Seeed official KiCad library (XIAO footprints + symbols) | https://github.com/Seeed-Studio/OPL_Kicad_Library (folder "Seeed Studio XIAO Series Library") |
| SEEED-WIKI-C3 | Seeed wiki, XIAO ESP32C3 | https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/ |
| SEEED-WIKI-S3 | Seeed wiki, XIAO ESP32S3 | https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/ |
| SEEED-WIKI-RP | Seeed wiki, XIAO RP2040 | https://wiki.seeedstudio.com/XIAO-RP2040/ |
| AE32-C3 / AE32-S3 / AE32-SM / AE32-WS / AE32-DOIT | arduino-esp32 `pins_arduino.h` variants XIAO_ESP32C3, XIAO_ESP32S3, nologo_esp32c3_super_mini, waveshare_esp32_s3_zero, doitESP32devkitV1 | https://github.com/espressif/arduino-esp32/tree/master/variants |
| SM-MRTNVGR | ESP32-C3 SuperMini KiCad lib | https://github.com/mrtnvgr/KiCad_ESP32-C3-SuperMini |
| SM-DED811 | Recreated ESP32-C3 SuperMini KiCad PCB (board itself, header nets) | https://github.com/ded811/ESP32-C3-Super-Mini-Kicad |
| SM-ELECROW | Elecrow ESP32-C3 SuperMini KiCad lib | https://github.com/zentarot/Elecrow-ESP32-C3-SuperMini-KiCad |
| SM-PROTO | ProtoSupplies product page (text spec table) | https://protosupplies.com/product/esp32c3-supermini/ |
| SM-ESPBOARDS | espboards.dev page | https://www.espboards.dev/esp32/esp32-c3-super-mini/ |
| SM-MAKERGUIDES | makerguides page | https://www.makerguides.com/esp32-c3-supermini-board/ |
| RP0-CP | RP2040-Zero KiCad lib | https://github.com/CountParadox/RP2040-Zero-Kicad |
| RP0-DJ | RP2040-Zero KiCad lib | https://github.com/dj505/RP2040-Zero-KiCAD |
| WS-WIKI-RP0 / WS-WIKI-S3Z | Waveshare wiki pages | https://www.waveshare.com/wiki/RP2040-Zero , https://www.waveshare.com/wiki/ESP32-S3-Zero |
| S3Z-JT | ESP32-S3-Zero KiCad lib (identical copy also in tomkooij/e07-900m10s-esp32s3zero) | https://github.com/jtomka/kicad-esp32-s3-zero |
| S3Z-FX | ESP32-S3-Zero KiCad lib | https://github.com/formix/formix-kicad-libraries |
| PICO-DS / PICOW-DS | Raspberry Pi Pico / Pico W datasheet text (via WebFetch) | https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf , https://datasheets.raspberrypi.com/picow/pico-w-datasheet.pdf |
| PICO-NC | Community Pico KiCad lib (footprint with silk pin labels + symbol) | https://github.com/ncarandini/KiCad-RP-Pico |
| DOIT-SB | DOIT ESP32 DevKit V1 30-pin KiCad (fixed BlackCoffee version) | https://github.com/syauqibilfaqih/ESP32-DevKit-V1-DOIT |
| DOIT-DK | DOIT DevKit KiCad (36-pin variant) | https://github.com/davidkleymann/doit-esp32-devkit-kicad |
| ESP-KICAD | Espressif official KiCad library | https://github.com/espressif/kicad-libraries |
| ESP-DOC-DKC | Espressif ESP32-DevKitC V4 user guide (J2/J3 tables) | https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html |
| ESP-DIM-DKC | Espressif DevKitC V4 dimensions PDF (text layer) | https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf |
| ND-ESP8266 | NightDragon1 kicad-ESP8266 (NodeMCU, LoLin, ESP-01 footprints + symbols) | https://github.com/NightDragon1/kicad-ESP8266 |
| ETECH | etechnophiles NodeMCU article | https://www.etechnophiles.com/nodemcu-esp8266-pinout-specs-board-layout |
| FRITZ-FORUM | Fritzing forum, NodeMCU V3 part thread | https://forum.fritzing.org/t/nodemcu-v3-parts-library/3422 |
| KICAD-MIRROR | Old official KiCad Module.pretty (GitHub mirror) + official kicad-symbols (MCU_Module.lib) | the old official KiCad Module.pretty (GitHub mirror KiCad/kicad-footprints) ; https://github.com/KiCad/kicad-symbols |
| WEMOS-D1 / WEMOS-D1-310 | WEMOS D1 mini pages | https://www.wemos.cc/en/latest/d1/d1_mini.html , https://www.wemos.cc/en/latest/d1/d1_mini_3.1.0.html |
| ARD-NANO | Arduino Nano docs | https://docs.arduino.cc/hardware/nano/ |
| SF-PROMINI | SparkFun Arduino Pro Mini 328 Eagle files | https://github.com/sparkfun/Arduino_Pro_Mini_328 |
| SF-PROMICRO | SparkFun Pro Micro Eagle files (v13 .brd) + Documentation/ProMicro.csv | https://github.com/sparkfun/Pro_Micro |
| KEEBIO | Keebio-Parts.pretty ArduinoProMicro-TopSide | https://github.com/keebio/Keebio-Parts.pretty |
| OLED-LS | LibreSolar OLED_SSD1306_I2C_0.96 footprint | https://github.com/LibreSolar/kicad-footprints |
| OLED-TG | TG9541 Display_128x64_096_I2C footprint | https://github.com/TG9541/kicad-footprints |
| OLED-V01D | V01Ddev SSD1306 lib | https://github.com/V01Ddev/kicad-ssd1306-oled-library |
| OLED-TTP | the-this-pointer SSD1306 + GME12864 lib | https://github.com/the-this-pointer/kicad-oled-ssd1306-128x64 |
| OLED-YK | yakipote SSD1306 footprint | https://github.com/yakipote/SSD1306_footprint |
| OLED91-GB | gorbachev 0.91" 128x32 footprint | https://github.com/gorbachev/KiCad-SSD1306-0.91-OLED-4pin-128x32.pretty |
| LCDWIKI-SPI | LCDwiki 0.96" SPI OLED (MSP096X) page + user manual PDF text | https://www.lcdwiki.com/0.96inch_SPI_OLED_Module , https://www.lcdwiki.com/res/MSP096X/0.96inch_OLED_SPI_Module_MSP096X_User_Manual_EN.pdf |
| LCDWIKI-091 | LCDwiki 0.91" IIC OLED (MC091GX) | https://www.lcdwiki.com/0.91inch_IIC_OLED_Module_SSD1306_SKU:MC091GX |
| EASYEDA-096 | EasyEDA/LCKFB open-kits wiki, 0.96" IIC screen | https://openkits-wiki.easyeda.com/en/coloreasyduino/module/screen/0-96-iic-single-screen.html |
| OZDISAN-091 | 0.91" OLED datasheet PDF (text) | https://cdn.ozdisan.com/ETicaret_Dosya/575597_4245715.PDF |
| FRITZ-SD | Fritzing core part `microsdmodule.fzp` + `svg/core/pcb/microsdmodule_pcb.svg` | https://github.com/fritzing/fritzing-parts |
| ELECTROKIT-SD | Electrokit microSD 5V module page | https://electrokit.com/en/microsd-lasare-5v |
| CG-SD | CGrassin kicad_parts SD_Card_Module | https://github.com/CGrassin/kicad_parts |

---

## 1. Seeed XIAO ESP32-C3 / XIAO ESP32-S3 / XIAO RP2040

**Shared footprint:** yes. In SEEED-KICAD, `XIAO-ESP32-C3-DIP`, `XIAO-ESP32-S3-DIP` and `XIAO-RP2040-DIP` have identical pad numbers, coordinates and drills. I parsed all three to check (verified-from-text). The Seeed symbols use the same pad numbering for D0 to D10, 3V3, GND and 5V (VBUS) on all three.

**Castellated:** yes. Each pad is a 1.524 mm through-hole (0.889 mm drill) plus an SMD castellation pad (2.432 x 1.524) at the board edge (y = +/-8.455). Source: SEEED-KICAD, verified-from-text.

### Key dimensions

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board outline | 21 x 17.8 mm | SEEED-WIKI-C3, SEEED-WIKI-S3, SEEED-WIKI-RP. KiCad Fab layer is 20.975 x 17.8 (x -10.425..10.55, y -8.9..8.9) | verified-from-text (wiki + KiCad agree) |
| Pins | 2 rows x 7 along the 21 mm length | SEEED-KICAD | verified-from-text |
| Row spacing | 15.24 mm (rows at y = -7.62 and +7.62) | SEEED-KICAD | verified-from-text |
| Pin pitch | 2.54 mm | SEEED-KICAD | verified-from-text |
| Header position | 7 pins centred on the length (x = -7.62..+7.62, board centre x ~ 0.06). Hole centres are 1.28 mm in from the long edges | SEEED-KICAD | verified-from-text |
| USB-C | Overhangs the short edge at +x in the footprint (silk extends to x = 12.05, about 9 mm wide). Pad 1 (D0) is at the USB end | SEEED-KICAD | verified-from-text |

### Pin order, top view, USB-C pointing UP

(This is the KiCad footprint rotated 90 degrees so that +x points up.)

| Position from USB end | LEFT row (pads 1-7) | RIGHT row (pads 14-8) |
|---|---|---|
| 1 (next to USB) | pad 1 = D0 | pad 14 = 5V (VBUS) |
| 2 | pad 2 = D1 | pad 13 = GND |
| 3 | pad 3 = D2 | pad 12 = 3V3 (3V3_OUT) |
| 4 | pad 4 = D3 | pad 11 = D10 |
| 5 | pad 5 = D4 | pad 10 = D9 |
| 6 | pad 6 = D5 | pad 9 = D8 |
| 7 (far end) | pad 7 = D6 | pad 8 = D7 |

Source: SEEED-KICAD symbol pin names (1:D0 ... 7:D6, 8:D7, 9:D8, 10:D9, 11:D10, 12:3V3_OUT, 13:GND, 14:VBUS) mapped onto the footprint coordinates. Confidence: verified-from-text.

So D0 to D6 run down one side. The other side, starting at the USB end, is 5V, GND, 3V3, D10, D9, D8, D7.

### D pin to GPIO

| Pin | XIAO ESP32-C3 | XIAO ESP32-S3 | XIAO RP2040 |
|---|---|---|---|
| D0 | GPIO2 | GPIO1 | GPIO26 |
| D1 | GPIO3 | GPIO2 | GPIO27 |
| D2 | GPIO4 | GPIO3 | GPIO28 |
| D3 | GPIO5 | GPIO4 | GPIO29 |
| D4 (SDA) | GPIO6 | GPIO5 | GPIO6 |
| D5 (SCL) | GPIO7 | GPIO6 | GPIO7 |
| D6 (TX) | GPIO21 | GPIO43 | GPIO0 |
| D7 (RX) | GPIO20 | GPIO44 | GPIO1 |
| D8 (SCK) | GPIO8 | GPIO7 | GPIO2 |
| D9 (MISO) | GPIO9 | GPIO8 | GPIO4 |
| D10 (MOSI) | GPIO10 | GPIO9 | GPIO3 |

Sources: C3 from SEEED-WIKI-C3 and AE32-C3 (two sources agree). S3 from SEEED-WIKI-S3 and AE32-S3 (two sources agree). RP2040 from SEEED-WIKI-RP (verified-from-text, single official source).

Extra pads on the underside are not part of the 14-pin footprint:
- C3: SMD symbol pins 15-22 (MTDI, MTDO, EN, GND, MTMS, MTCK, VBAT, GND).
- S3: MTDI, MTDO, EN, GND, MTMS, MTCK, USB_DN, USB_DP, VBAT, GND.

Source: SEEED-KICAD `XIAO-*-SMD` symbols. Their positions were not extracted.

---

## 2. ESP32-C3 SuperMini (16-pin, about 22.5 x 18 mm)

### Key dimensions

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board outline | 22.52 x 18 mm | SM-ESPBOARDS text "22.52 x 18 mm". SM-MAKERGUIDES "22.52x18mm". SM-PROTO "22.5 x 18mm". SM-MRTNVGR Fab 18.0 x 22.52. SM-DED811 Edge.Cuts 18.000 x 22.520 | two sources agree (several) |
| Pins | 2 x 8 along the 22.52 mm length | SM-MRTNVGR, SM-DED811 | two sources agree |
| Row spacing | 15.24 mm | SM-PROTO "15.24mm (0.6″)" row-to-row. SM-MRTNVGR rows at x = +/-7.62. SM-DED811 inner header holes at x 43.430 and 58.645 (15.215, effectively 15.24) | two sources agree |
| Pitch | 2.54 mm | SM-PROTO, SM-ESPBOARDS, both KiCad files | two sources agree |
| Castellated | SM-DED811 uses a castellated edge-mount header: a half-hole exactly on the board edge plus a header hole 1.38 mm inboard. SM-MRTNVGR has plain through-holes (1.14 pad / 0.84 drill) | SM-DED811 | single source |
| Header position along length | **Sources disagree.** SM-MRTNVGR: pins centred (y = -8.89..+8.89 in a +/-11.26 outline, so 2.37 mm margin at both ends). SM-DED811: first pin 1.275 mm from the USB edge and last pin 3.465 mm from the far edge | | disagree, check against a real board |
| USB-C | At the end of the 5V / GPIO5 pins (top) | SM-DED811 (J1 USB-C at the y = 30..36 edge) | single source |

### Pin order, top (component) view, USB-C UP

| Pos from USB end | LEFT row | RIGHT row |
|---|---|---|
| 1 | GPIO5 | 5V |
| 2 | GPIO6 | GND |
| 3 | GPIO7 | 3V3 |
| 4 | GPIO8 | GPIO4 |
| 5 | GPIO9 | GPIO3 |
| 6 | GPIO10 | GPIO2 |
| 7 | GPIO20 (RX) | GPIO1 |
| 8 | GPIO21 (TX) | GPIO0 |

- **SM-DED811:** header H1 (left, x about 43) pads 1-8 have nets GPIO5, GPIO6, GPIO7, GPIO8, GPIO9/BOOT, GPIO10, GPIO20, GPIO21. Header H2 (right, x about 58.6) has VBUS, GND, +3.3V, GPIO4, GPIO3, GPIO2, GPIO1, GPIO0. Both run top (USB) to bottom.
- **SM-MRTNVGR:** pads 1-8 at x = +7.62 from y = +8.89 (bottom) to -8.89 (top) are GPIO0, 1, 2, 3, 4, 3V3, GND, 5V. Pads 9-16 at x = -7.62 from top to bottom are GPIO5, 6, 7, 8, 9, 10, 20, 21.

These two files are independent and give an identical physical layout. Confidence: **two sources agree**.

**Disagreeing sources**
- **SM-ELECROW** `ESP32-C3-SuperMini_Elecrow_2.54mm` puts 5V, GND, 3V3, GPIO20/RX, GPIO21/TX, GPIO2, GPIO1, GPIO0 on the LEFT. It puts GPIO10, 9, 8, 7, 6, 5, 4, 3 on the RIGHT, and uses an 18.6 mm row spacing (x = +/-9.3). Its own description says "Verify pitch against physical board before PCB fabrication". I treat it as unreliable.
- **SM-ESPBOARDS** gives a 1..16 pin table: 5V, GND, 3V3, IO0, IO1, IO2, IO3, IO4, IO5, IO6, IO7, IO8, IO9, IO10, IO21, IO20. It does not say which side each pin is on. This is a numbering list, not a physical order.

**Arduino aliases:** AE32-SM gives TX = 21, RX = 20, SDA = 8, SCL = 9, SCK = 4, MISO = 5, MOSI = 6, SS = 7, LED_BUILTIN = 8, A0-A5 = GPIO0-5 (verified-from-text).

---

## 3. Waveshare RP2040-Zero and ESP32-S3-Zero

The Waveshare wiki pages (WS-WIKI-RP0, WS-WIKI-S3Z) give dimensions and pinouts **only as images**. Their text confirms "castellated" for both boards. For RP2040-Zero the text says "29 GPIO pins ... 20 can be led out through pin headers, the rest can be led out only by soldering". For ESP32-S3-Zero the text says "TX is GPIO43, and RX is GPIO44" and "Pins GPIO33 ~ GPIO37 are not led out". The data below therefore comes from community KiCad files.

### 3a. RP2040-Zero (23 pins on the edges: 9 left + 9 right + 5 on the bottom edge)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board outline | **not found** in text (wiki dimension drawing is an image). Footprint-author numbers only: RP0-DJ Fab 18.29 x 25.65 mm (x 1.016..19.304, y -26.543..-0.889, probably including the USB overhang). RP0-CP silk 18.0 x 23.5 (x 1.15..19.16, y -24.45..-0.95) plus a USB Fab box above it | RP0-DJ, RP0-CP | single source each; not verified |
| Row spacing (side rows) | 15.24 mm (RP0-CP x = 2.54 and 17.78; RP0-DJ x = 2.54 and 17.78) | RP0-CP, RP0-DJ | two sources agree |
| Pitch | 2.54 mm on all three edges | both | two sources agree |
| Bottom-edge pins | 5 pins at x = 5.08, 7.62, 10.16, 12.7, 15.24. They sit on the same grid row as the lowest side pins (y about -2.33 / -2.54 in RP0-CP, -2.667 in RP0-DJ), filling the gap between the two side rows | both | two sources agree |
| USB-C | Top edge (RP0-CP Fab USB box at y -25.45..-24.45 above the 5V / GP0 end) | RP0-CP | single source |
| Castellated | yes (RP0-DJ has SMD castellation pads plus through-holes; Waveshare text says castellated) | WS-WIKI-RP0, RP0-DJ | two sources agree |
| 10 extra pads under the board (GP16-GP25 area) | positions **not found** (Waveshare FAQ answer is an image) | | not found |

Pin order, top view, USB-C UP:

| Pos from top | LEFT row | RIGHT row |
|---|---|---|
| 1 (USB end) | 5V | GP0 |
| 2 | GND | GP1 |
| 3 | 3V3 | GP2 |
| 4 | GP29 | GP3 |
| 5 | GP28 | GP4 |
| 6 | GP27 | GP5 |
| 7 | GP26 | GP6 |
| 8 | GP15 | GP7 |
| 9 (bottom) | GP14 | GP8 |

Bottom edge, left to right (between GP14 and GP8): **GP13, GP12, GP11, GP10, GP9**.

Sources:
- **RP0-CP:** symbol 1:GP0 ... 9:GP8 on the right column (top to bottom), 10-14 = GP9..GP13 on the bottom row (right to left), 15-23 = GP14, GP15, GP26, GP27, GP28, GP29, 3V3, GND, 5V on the left column (bottom to top).
- **RP0-DJ:** symbol 1-9 = 5V, GND, 3V3, GP29, GP28, GP27, GP26, GP15, GP14 on the left (top to bottom), 10-18 = GP0..GP8 on the right (top to bottom), 19-23 = GP13, GP12, GP11, GP10, GP9 on the bottom (left to right).

The two files are independent and use different numbering, but give the same physical result. Confidence: **two sources agree**.

### 3b. ESP32-S3-Zero (18 edge pins: 9 left + 9 right)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board outline | **not found** in text. Footprint-author numbers: S3Z-JT silk 18.06 x 25.03 (x 0..18.06, y -1.5..23.53, including the USB end). S3Z-FX silk 18.0 x 25.0 (x -9..9, y -13.25..11.75) | S3Z-JT, S3Z-FX | single source each; not verified |
| Row spacing | 15.24 mm between hole centres (S3Z-JT through-holes at x = 1.38 and 16.62). S3Z-FX is SMD-only, with castellation pad centres at x = +/-8.7 (17.4 mm apart; these are edge pads, not hole centres) | S3Z-JT, S3Z-FX | single source for the 15.24 hole spacing; the edge-pad positions agree with an 18 mm board |
| Pitch | 2.54 mm | both | two sources agree |
| Castellated | yes | WS-WIKI-S3Z text | verified-from-text |
| USB-C | Top, at the 5V / TX end (silk extends above pad 1 in both files) | S3Z-JT, S3Z-FX | two sources agree |
| Bottom-edge or underside pads | **not found** in either footprint. Neither file has pins on the bottom edge. AE32-WS lists further GPIO aliases D9-D16 = GPIO40, 39, 38, 37, 36, 35, 34, 33, but gives no positions | | not found |

Pin order, top view, USB-C UP:

| Pos from top | LEFT row | RIGHT row |
|---|---|---|
| 1 (USB end) | 5V | TX (GPIO43) |
| 2 | GND | RX (GPIO44) |
| 3 | 3V3 (out) | GPIO13 |
| 4 | GPIO1 | GPIO12 |
| 5 | GPIO2 | GPIO11 |
| 6 | GPIO3 | GPIO10 |
| 7 | GPIO4 | GPIO9 |
| 8 | GPIO5 | GPIO8 |
| 9 (bottom) | GPIO6 | GPIO7 |

Sources:
- **S3Z-JT:** symbol 1:VDD, 2:GND, 3:3V3(OUT), 4-9:GPIO1-6, 10-16:GPIO7-13, 17:RX, 18:TX. Pads 1-9 at x = 1.38 (top to bottom), pads 10-18 at x = 16.62 (bottom to top).
- **S3Z-FX:** symbol 1:5V, 2:GND, 3:3V3, 4-16 = 1..13, 17:RX, 18:TX, with the same pad geometry pattern.

Confidence: **two sources agree**. TX = 43 / RX = 44 is also in WS-WIKI-S3Z text and AE32-WS.

---

## 4. Raspberry Pi Pico / Pico W

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board | 51 x 21 mm, 1 mm thick | PICO-DS "single sided 51×21 mm 1 mm thick PCB". PICOW-DS "51 mm × 21 mm × 1 mm". PICO-NC Fab 21 x 51 | two sources agree |
| Pins | 2 x 20, 2.54 mm pitch, 1 mm holes | PICO-DS and PICOW-DS "40 main user pins on a 2.54 mm (0.1″) pitch grid with 1 mm holes" | verified-from-text |
| Row spacing | **17.78 mm** (PICO-NC rows at x = +/-8.89). The datasheet does not give a number, only "one 0.1″ pitch wider than a standard 40-pin DIP package". A 600 mil DIP + 100 mil = 700 mil = 17.78 mm, which is consistent | PICO-NC (+ PICO-DS consistent) | two sources agree |
| Castellated | yes, "dual castellated/through-hole pins" | PICO-DS, PICOW-DS | verified-from-text |
| Header position | Pins y = -24.13..+24.13 in a +/-25.5 outline (1.37 mm end margins). Columns 1.61 mm in from the long edges | PICO-NC | single source |
| Mounting holes | 4 x 2.1 mm (+/-0.05) diameter | PICO-DS, PICOW-DS | verified-from-text |
| Mounting hole positions | **not found** in text (Figure 3 only) | | not found |
| SWD debug header (3 pins, bottom edge) | PICO-NC pads 41 = SWCLK (x -2.54), 42 = GND (x 0), 43 = SWDIO (x +2.54), all at y = 23.9 | PICO-NC | single source (datasheets confirm 3-pin SWD at the lower edge but do not name the order) |
| USB | Micro-USB overhangs the top edge (PICO-DS). PICO-NC USB NPTH holes at y = -24 / -20.97, which is the pin 1 end | | two sources agree |
| Pin 1 | GP0, top-left with USB up (PICO-NC pad 1 at x -8.89, y -24.13; silk text "GP0") | PICO-NC | single source for the full mapping |
| Pico W | Same 51 x 21 x 1 mm, same pitch/holes/castellations, same named pins 30/33/35/36/37/39/40. The datasheet does not state "same footprint" in words | PICOW-DS | verified-from-text for the listed items |

Full pin list (pins 1-20 = left column top to bottom, pins 21-40 = right column bottom to top, USB up). Source: PICO-NC symbol + footprint silk labels. Pins marked * are also named in PICO-DS / PICOW-DS text (two sources agree). The others are single source.

| Pin | Name | Pin | Name |
|---|---|---|---|
| 1 | GP0 | 40* | VBUS |
| 2 | GP1 | 39* | VSYS |
| 3 | GND | 38 | GND |
| 4 | GP2 | 37* | 3V3_EN |
| 5 | GP3 | 36* | 3V3 (OUT) |
| 6 | GP4 | 35* | ADC_VREF |
| 7 | GP5 | 34 | GP28 / ADC2 |
| 8 | GND | 33* | AGND |
| 9 | GP6 | 32 | GP27 / ADC1 |
| 10 | GP7 | 31 | GP26 / ADC0 |
| 11 | GP8 | 30* | RUN |
| 12 | GP9 | 29 | GP22 |
| 13 | GND | 28 | GND |
| 14 | GP10 | 27 | GP21 |
| 15 | GP11 | 26 | GP20 |
| 16 | GP12 | 25 | GP19 |
| 17 | GP13 | 24 | GP18 |
| 18 | GND | 23 | GND |
| 19 | GP14 | 22 | GP17 |
| 20 | GP15 | 21 | GP16 |

(Each table row is one physical row: pin 1 is opposite pin 40, and pin 20 is opposite pin 21.)

Pico W internal-use GPIOs (not on the header): GPIO23 = wireless power, GPIO24 = wireless SPI data/IRQ, GPIO25 = wireless SPI CS, GPIO29 = wireless SPI CLK / ADC3 (VSYS/3). The LED is on WL_GPIO0. Source: PICOW-DS, verified-from-text.

---

## 5. ESP32 DevKit boards

### 5a. DOIT ESP32 DEVKIT V1, 30-pin

| Item | Value | Source | Confidence |
|---|---|---|---|
| Row spacing | **25.4 mm** (x = -11.928 and 13.472) | DOIT-SB | single source (the 36-pin DOIT-DK file also uses 25.4: x = +/-12.7) |
| Pitch | 2.54 mm, 15 per side | DOIT-SB | single source |
| Board outline | **not found** in text. Footprint silk is 28.3 x 52.5 mm (x -13.33..14.97, y -26.4..26.11) | DOIT-SB | single source, not verified |
| USB | Bottom (silk text "USB" at y = 24.5; antenna end at the EN / GPIO23 end) | DOIT-SB | single source |

Pin order, top view, antenna UP / USB DOWN (from DOIT-SB symbol pin names mapped to pads plus the footprint silk labels; the two agree inside the file):

| Pos from top | LEFT (pads 15..1) | RIGHT (pads 30..16) |
|---|---|---|
| 1 | EN | GPIO23 |
| 2 | GPIO36 (VP) | GPIO22 |
| 3 | GPIO39 (VN) | GPIO1 (TX0) |
| 4 | GPIO34 | GPIO3 (RX0) |
| 5 | GPIO35 | GPIO21 |
| 6 | GPIO32 | GPIO19 |
| 7 | GPIO33 | GPIO18 |
| 8 | GPIO25 | GPIO5 |
| 9 | GPIO26 | GPIO17 |
| 10 | GPIO27 | GPIO16 |
| 11 | GPIO14 | GPIO4 |
| 12 | GPIO12 | GPIO2 |
| 13 | GPIO13 | GPIO15 |
| 14 | GND | GND |
| 15 (USB end) | VIN | 3V3 |

Confidence: single source. The README says it is a corrected version of the KiCad-forum file, whose pad numbering was wrong. AE32-DOIT confirms LED_BUILTIN = 2, TX = 1, RX = 3, SDA = 21, SCL = 22 and the SPI pins, but it has no physical positions.

DOIT-DK (`ESP32-DOIT-DEVKIT.kicad_mod`) is a **36-pin** variant (18 per side, also 25.4 mm). Its extra pins are GPIO9, 10, 11, 6, 7, 8. Do not use it for the 30-pin board.

### 5b. Espressif ESP32-DevKitC (V4), 38-pin

| Item | Value | Source | Confidence |
|---|---|---|---|
| Row spacing | **25.40 mm** (ESP-KICAD x = 0 and 25.4; ESP-DIM-DKC text layer contains "25.40") | ESP-KICAD, ESP-DIM-DKC | two sources agree |
| Board width | 27.94 mm (the value "27.94" is in the ESP-DIM-DKC text. ESP-KICAD Fab width is 27.9, x -1.25..26.65) | ESP-DIM-DKC, ESP-KICAD | two sources agree (label inferred) |
| Header length | 48.26 mm = 19 x 2.54 (value in ESP-DIM-DKC text) | ESP-DIM-DKC | single source (unlabeled number) |
| Board length | **not found** (the dimension PDF text layer has only unlabeled numbers: 48.26 27.94 1.29 2.54 18.00 25.40 6.04 1.30. The DXF download was blocked) | | not found |
| Pitch | 2.54 mm, 19 per side | ESP-KICAD, ESP-DOC-DKC | two sources agree |
| Orientation | Antenna at the top (silk extends to y = -7.0 above pad 1). Pin 1 of J2 (3V3) and pin 1 of J3 (GND) are at the antenna end. 5V and CLK are at the USB end | ESP-KICAD (+ ESP-DOC-DKC numbering) | two sources agree |

Pin order, top view, antenna UP. J2 = left (pads 1-19). J3 = right (footprint pads 38..20, which are J3 pins 1..19).

| Pos | J2 LEFT | J3 RIGHT |
|---|---|---|
| 1 | 3V3 | GND |
| 2 | EN | IO23 |
| 3 | VP / GPIO36 | IO22 |
| 4 | VN / GPIO39 | TX / GPIO1 |
| 5 | IO34 | RX / GPIO3 |
| 6 | IO35 | IO21 |
| 7 | IO32 | GND |
| 8 | IO33 | IO19 |
| 9 | IO25 | IO18 |
| 10 | IO26 | IO5 |
| 11 | IO27 | IO17 |
| 12 | IO14 | IO16 |
| 13 | IO12 | IO4 |
| 14 | GND | IO0 |
| 15 | IO13 | IO2 |
| 16 | D2 / GPIO9 | IO15 |
| 17 | D3 / GPIO10 | D1 / GPIO8 |
| 18 | CMD / GPIO11 | D0 / GPIO7 |
| 19 | 5V | CLK / GPIO6 |

Sources: ESP-DOC-DKC J2/J3 tables (verified-from-text), plus ESP-KICAD footprint silk labels and symbol (pad 1 = 3V3 ... 19 = 5V, 20 = CLK ... 38 = GND). Confidence: two sources agree.

Note: in ESP-KICAD, pads 20 and 21 are at x = 25.39632 / y = 45.71728 and 43.17728, not exactly on the 25.4 grid. This looks like an author nudge. Treat them as 25.4.

**Answer to "25.4 vs 22.86":** both DevKit boards use **25.4 mm** in the files found. 22.86 mm did not appear for either board.

---

## 6. ESP8266 boards

### 6a. NodeMCU v2 "Amica" (narrow) and NodeMCU v3 "LoLin" (wide)

| Item | Amica (v2) | LoLin (v3) | Source | Confidence |
|---|---|---|---|---|
| Row spacing | **22.86 mm (0.9")** | **27.94 mm (1.1")** | ETECH "0.9″ between rows" / "1.1″ between rows". FRITZ-FORUM "LoLin ... 27,94mm", ".9 x 25.4" for the narrow board, "moves the pins from .9 inch wide to 1.1 inch wide". ND-ESP8266 LoLin footprint x = +/-13.97 = 27.94 | two sources agree |
| Board size | 49 x 26 mm | 58 x 32 mm (same page also says 5.8 x 3.1 cm). FRITZ-FORUM says 31 x 58 mm | ETECH, FRITZ-FORUM | Amica single source; LoLin two sources, 31 vs 32 mm width disagreement |
| Pins | 2 x 15, 2.54 mm | 2 x 15, 2.54 mm | ND-ESP8266; FRITZ-FORUM "number of pins per pin row are exactly the same" | two sources agree |

**Warning (disagreement):** ND-ESP8266 `NodeMCU1.0(12-E).kicad_mod`, which is named for the Amica / NodeMCU 1.0, also uses 27.94 mm rows (x = +/-13.97). That contradicts ETECH and FRITZ-FORUM (22.86 mm for Amica). Use 22.86 for Amica.

Header position on LoLin (ND-ESP8266): pins y = -20.32..+15.24 inside silk y -30.5..+26.5. The header sits closer to the USB end. Single source, silk only.

Pin order, top view, antenna UP / USB DOWN (ND-ESP8266 footprint silk labels; for Amica pins 2-3, the NodeMCU1.0 symbol pin names):

| Pos | LEFT, Amica (NodeMCU 1.0) | LEFT, LoLin V3 | RIGHT (both) |
|---|---|---|---|
| 1 | A0 | A0 | D0 (GPIO16) |
| 2 | RSV | G (GND) | D1 (GPIO5) |
| 3 | RSV | VU (USB 5V) | D2 (GPIO4) |
| 4 | SD3 (GPIO10) | S3 | D3 (GPIO0) |
| 5 | SD2 (GPIO9) | S2 | D4 (GPIO2) |
| 6 | SD1 | S1 | 3V3 |
| 7 | CMD | SC | GND |
| 8 | SD0 | SO | D5 (GPIO14) |
| 9 | CLK | SK | D6 (GPIO12) |
| 10 | GND | G | D7 (GPIO13) |
| 11 | 3V3 | 3V | D8 (GPIO15) |
| 12 | EN | EN | RX (GPIO3) |
| 13 | RST | RST | TX (GPIO1) |
| 14 | GND | G | GND |
| 15 (USB end) | VIN | VIN | 3V3 |

Confidence: single source (ND-ESP8266) for the physical order. The Amica footprint silk in that library also prints G/VU at positions 2-3 (apparently copied from LoLin), while its symbol says RSV/RSV. The D-to-GPIO numbers come from the ND-ESP8266 NodeMCU1.0 symbol and agree with WEMOS-D1-310 (same D-pin convention).

### 6b. WEMOS / LOLIN D1 mini

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board | 34.2 x 25.6 mm | WEMOS-D1 "34.2*25.6mm". KICAD-MIRROR Fab x -1.37..24.23 (25.6), y -8.21..25.99 (34.2) | two sources agree |
| Row spacing | 22.86 mm (900 mil) | KICAD-MIRROR descr "column spacing 22.86 mm (900 mils)", pads x = 0 and 22.86 | verified-from-text (official KiCad) |
| Pins | 2 x 8, 2.54 mm | KICAD-MIRROR | verified-from-text |
| Header position | Pins y = 0..17.78. Top pin 8.21 mm below the antenna-end edge, bottom pin 8.21 mm above the USB-end edge. Columns 1.37 mm in from the long edges. Copper keep-out (antenna) y = -8.2..-1.4 | KICAD-MIRROR | verified-from-text |

Pin order, top view, antenna UP / USB DOWN (KICAD-MIRROR footprint + official `MCU_Module.lib` WeMos_D1_mini symbol, which points at that footprint):

| Pos | LEFT (pads 1-8) | RIGHT (pads 16-9) | GPIO (WEMOS-D1-310 table) |
|---|---|---|---|
| 1 | RST | TX | TX = TXD |
| 2 | A0 | RX | RX = RXD |
| 3 | D0 | D1 (SCL) | D0 = GPIO16, D1 = GPIO5 |
| 4 | D5 (SCK) | D2 (SDA) | D5 = GPIO14, D2 = GPIO4 |
| 5 | D6 (MISO) | D3 | D6 = GPIO12, D3 = GPIO0 |
| 6 | D7 (MOSI) | D4 (LED) | D7 = GPIO13, D4 = GPIO2 |
| 7 | D8 (SS) | GND | D8 = GPIO15 |
| 8 | 3V3 | 5V | |

Confidence: verified-from-text (official KiCad symbol + footprint; GPIO from the WEMOS table).

### 6c. ESP-01 / ESP-01S

| Item | Value | Source | Confidence |
|---|---|---|---|
| Header | 2 x 4, 2.54 mm pitch, 2.54 mm between the two rows | ND-ESP8266 ESP-01 footprint | single source |
| Board | 24.64 x 14.22 mm (Fab x -1.778..22.86, y -3.302..10.922) | ND-ESP8266 | single source |
| Header position | At one short end. First column 1.78 mm from the end edge. The four pins are centred across the 14.22 mm width (3.30 mm margins). The antenna is at the opposite end (x about 22.9) | ND-ESP8266 | single source |

Grid as drawn in the footprint (top view, header at the left end, antenna to the right):

| | column x = 0 | column x = 2.54 (toward the antenna) |
|---|---|---|
| y = 0 | pad 1 UTXD (TX, GPIO1) | pad 2 GND |
| y = 2.54 | pad 3 CH_PD (EN) | pad 4 GPIO2 |
| y = 5.08 | pad 5 RST | pad 6 GPIO0 |
| y = 7.62 | pad 7 VCC (3.3 V) | pad 8 URXD (RX, GPIO3) |

Source: ND-ESP8266 ESP-01v090 symbol names (1:UTXD, 2:GND, 3:CH_PD, 4:GPIO2, 5:RST, 6:GPIO0, 7:VCC, 8:URXD) on the ESP-01 footprint. Confidence: single source.

ESP-01S: **not found**. No separate text source confirms that its header is identical.

---

## 7. Arduino Nano, Pro Mini, Pro Micro

### 7a. Arduino Nano (KiCad mirror `Arduino_Nano.kicad_mod`)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Row spacing | 15.24 mm (x = 0 and 15.24) | KICAD-MIRROR | verified-from-text |
| Pins | 2 x 15, 2.54 mm | KICAD-MIRROR | verified-from-text |
| Board | 45 x 18 mm (ARD-NANO "length of 45 mm and a width of 18 mm"). The KiCad Fab outline is 17.78 x 43.18 (x -1.27..16.51, y -3.81..39.37), with the USB drawn sticking out to y = 41.91 | ARD-NANO, KICAD-MIRROR | Arduino text verified; KiCad outline is slightly smaller (it disagrees by about 1.8 mm in length) |
| Header position | Columns 1.27 mm in from the long edges (Fab). Pad 1 is 3.81 mm from the non-USB end. Pads 15/16 are 3.81 mm from the USB-end edge | KICAD-MIRROR | verified-from-text |
| USB | At the pad 15/16 end (Fab rectangle x 3.81..11.43, y 31.75..41.91) | KICAD-MIRROR | verified-from-text |

Pad names (official `MCU_Module.lib` symbol Arduino_Nano_v2.x / alias Arduino_Nano_v3.x, footprint "Module:Arduino_Nano"):

| Pad | Name | Pad | Name |
|---|---|---|---|
| 1 | D1/TX | 30 | VIN |
| 2 | D0/RX | 29 | GND |
| 3 | RESET | 28 | RESET |
| 4 | GND | 27 | +5V |
| 5 | D2 | 26 | A7 |
| 6 | D3 | 25 | A6 |
| 7 | D4 | 24 | A5 |
| 8 | D5 | 23 | A4 |
| 9 | D6 | 22 | A3 |
| 10 | D7 | 21 | A2 |
| 11 | D8 | 20 | A1 |
| 12 | D9 | 19 | A0 |
| 13 | D10 | 18 | AREF |
| 14 | D11 | 17 | 3V3 |
| 15 | D12 | 16 | D13 |

Each table row is one physical row. Pad 1 is at (0, 0) and pad 30 at (15.24, 0), at the end away from USB. Pad 15 is at (0, 35.56) and pad 16 at (15.24, 35.56), at the USB end. In KiCad's top view, pads 1-15 are the left column (x = 0) and pads 16-30 the right column. With USB pointing DOWN in that view: left column top to bottom D1/TX ... D12; right column top to bottom VIN ... D13. Confidence: verified-from-text.

### 7b. Arduino Pro Mini (SparkFun Arduino_Pro_Mini_328 Eagle `.brd`; one board design covers 5 V/16 MHz and 3.3 V/8 MHz, see the repo Documentation ProMini16MHzv2 / ProMini8MHzv2)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board | 17.78 x 33.02 mm (0.7" x 1.3"), Eagle dimension layer | SF-PROMINI | verified-from-text |
| Side rows | 2 x 12, 2.54 mm. **Row spacing 15.24 mm** (JP7 at x = 1.27, JP6 at x = 16.51) | SF-PROMINI | verified-from-text |
| Side header position | Pins y = 1.27..29.21. The bottom pin is 1.27 mm from the bottom edge. The top pin is 3.81 mm from the FTDI-end edge. Columns 1.27 mm in from the sides | SF-PROMINI | verified-from-text |
| FTDI end header JP1 | 6 pins along the top edge, y = 31.75 (1.27 mm from the top edge), x = 2.54..15.24 | SF-PROMINI | verified-from-text |
| Inner pins | A4 (13.589, 17.907), A5 (13.589, 20.447), A6 (13.589, 7.493), A7 (13.589, 10.033). These are **not** on the 0.1" grid of the side rows | SF-PROMINI | verified-from-text |

(Eagle +y is up. "Top" here means the FTDI end at y = 33.02.)

Pin order, top view, FTDI header UP:

| Pos from top | LEFT (x = 1.27, JP7 pad 12..1) | RIGHT (x = 16.51, JP6 pad 1..12) |
|---|---|---|
| 1 | TXO | RAW |
| 2 | RXI | GND |
| 3 | RESET | RESET |
| 4 | GND | VCC |
| 5 | D2 | A3 |
| 6 | D3 | A2 |
| 7 | D4 | A1 |
| 8 | D5 | A0 |
| 9 | D6 | D13 / SCK |
| 10 | D7 | D12 / MISO |
| 11 | D8 | D11 / MOSI |
| 12 | D9 | D10 |

FTDI header, left to right (top view): **GND, GND, VCC, RXI, TXO, DTR** (JP1 pad 6..1).

Source: SF-PROMINI `.brd` element positions and signal (net) names. Confidence: verified-from-text. Clone boards: **not verified**. CG-SD's library also has an `Arduino_Pro_Mini_China` symbol, but its footprint geometry was not checked.

### 7c. Arduino Pro Micro (SparkFun Pro_Micro v13 Eagle `.brd` + `Documentation/ProMicro.csv`)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board | 17.78 x 33.02 mm (0.7" x 1.3") | SF-PROMICRO .brd | verified-from-text |
| Rows | 2 x 12, 2.54 mm, **row spacing 15.24 mm** (x = 1.27 and 16.51) | SF-PROMICRO .brd. KEEBIO footprint rows at y = +/-7.62 = 15.24 | two sources agree |
| Header position | Pins y = 1.27..29.21. The top pin is 3.81 mm from the USB-end edge (USB X1 at y = 31.75). The bottom pin is 1.27 mm from the bottom edge | SF-PROMICRO | verified-from-text |
| USB | Micro-B at the top (TXO / RAW end) | SF-PROMICRO | verified-from-text |

Pin order, top view, USB UP:

| Pos from top | LEFT | RIGHT |
|---|---|---|
| 1 | TXO (D1) | RAW |
| 2 | RXI (D0) | GND |
| 3 | GND | RST |
| 4 | GND | VCC |
| 5 | D2 (SDA) | A3 |
| 6 | D3 (SCL) | A2 |
| 7 | D4 / A6 | A1 |
| 8 | D5 | A0 |
| 9 | D6 / A7 | D15 (SCK) |
| 10 | D7 | D14 (MISO) |
| 11 | D8 / A8 | D16 (MOSI) |
| 12 | D9 / A9 | D10 / A10 |

Sources:
- **SF-PROMICRO .brd nets:** JP7 pad 12..1 = TXO, RXI, GND, GND, D2..D9. JP6 pad 1..12 = RAW, GND, RESET, VCC, A3, A2, A1, A0, SCK, MISO, MOSI, D10.
- **ProMicro.csv** lists "Left: TXO, RXI, GND, GND, 2..9" and "Right: RAW, GND, RST, VCC, A3, A2, A1, A0, 15, 14, 16, 10".
- **KEEBIO** silk: pad 1 = TX0 and pad 24 = RAW at the same end.

Confidence: two sources agree.

---

## 8. OLED modules

### 8a. 0.96" 128x64 I2C (SSD1306), 4-pin

| Item | Value | Source | Confidence |
|---|---|---|---|
| PCB size | 27.3 x 27.8 mm | EASYEDA-096 "Module Dimensions: 27.3 x 27.8 MM". OLED-LS Fab x -9.84..17.46 (27.3), y -1.5..26.3 (27.8). (The SPI version is the same size: LCDWIKI-SPI.) Other files: OLED-V01D outline 27.4 x 27.3; OLED-TG silk 27.4 x 27.2; OLED-YK silk 25.2 x 26.0 | two sources agree (27.3 x 27.8); some footprints differ slightly |
| Header | 1 x 4, 2.54 mm, along one edge, centred left to right (OLED-LS header centre x = 3.81 = board centre) | OLED-LS, OLED-TG, OLED-V01D | two sources agree |
| Header row distance from the PCB edge | OLED-LS 1.5 mm; OLED-V01D 1.7 mm; OLED-TG about 1.4 mm (silk) | | sources differ by about 0.3 mm |
| Mounting holes | **Sources disagree.** OLED-LS: 4 holes, drill 2.0 mm (3 mm keep-out), centres 23.3 mm apart horizontally (x -7.84 / 15.46) and 23.8 mm apart vertically (y 0.5 / 24.3, so the top holes sit 0.5 mm below the header row). OLED-TG: 4 oval slots 3.8 x 2.9 mm, centres 22.352 mm apart (x +/-11.176) and 23.114 mm apart (y 0.635 / 23.749) | OLED-LS, OLED-TG | disagree; no vendor text found |
| Pin order (most common) | **GND, VCC, SCL, SDA** (left to right, display facing you, header at the top) | OLED-V01D symbol, OLED-TTP SSD1306 symbol, OLED-TG silk (GND, VDD, SCL, SDA), OLED-YK (pad 4..1 = GND, VCC, SCL, SDA) | two sources agree (4 files) |
| Variant: VCC/GND swapped | **VCC, GND, SCL, SDA** is in OLED-TTP for the 1.3" GME12864 module (its footprint says "dimensions are based on 0.96 inch"). No text source was found for a 0.96" board with swapped pins | OLED-TTP | single source (1.3" only); 0.96" swapped: not found |

### 8b. 0.91" 128x32 I2C (SSD1306), 4-pin

| Item | Value | Source | Confidence |
|---|---|---|---|
| PCB size | 38.0 x 12.0 mm | LCDWIKI-091 "Module PCB Size 12.00x38.00(mm)". OLED91-GB outline 38 x 12. OZDISAN-091 "38.0mm x 12.0mm x 11.5mm (including header pins)" | two sources agree |
| Header | 1 x 4, 2.54 mm, on one SHORT (12 mm) edge. Pin centres 1.5 mm in from that edge (x = 36.5 of 38). Pins centred across the 12 mm width (y = 2.19..9.81) | OLED91-GB | single source |
| Pin order | **GND, VCC, SCL, SDA** (pad 1..4 from y = 2.19 to 9.81) | LCDWIKI-091 table order, OLED91-GB silk | two sources agree |
| Mounting holes | **not found** (none in either source) | | not found |

### 8c. 0.96" SPI OLED, 7-pin (GND VCC D0 D1 RES DC CS)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Pin order | 1 GND, 2 VCC, 3 D0 (SCK), 4 D1 (MOSI/SDA), 5 RES, 6 DC, 7 CS | LCDWIKI-SPI page and MSP096X user manual text | verified-from-text (vendor) |
| PCB size | 27.3 x 27.8 mm | LCDWIKI-SPI ("Module PCB Size 27.3x27.8") | verified-from-text |
| Header position, pitch, mounting holes | **not found** (the manual text gives no hole or header data; the size drawing is an image) | | not found |
| Variations | **not found** in text | | not found |

---

## 9. Micro SD card SPI modules

### 9a. Common blue 6-pin "Catalex"-style module (with regulator / level shifter, about 42 x 24 mm)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board | 42 x 24 mm. FRITZ-SD PCB svg is 68.029 x 119.061 pt (72 pt/inch) = 24.0 x 42.0 mm. ELECTROKIT-SD "42 x 24.2 x 3.5mm" | FRITZ-SD, ELECTROKIT-SD | two sources agree |
| Header | 1 x 6, 2.54 mm (7.2 pt spacing), along a SHORT (24 mm) edge, pin centres 3.98 mm from that edge (y = 11.28 pt). Pin x centres from the left edge (top view, header at the top): 5.47, 8.01, 10.55, 13.09, 15.63, 18.17 mm. The header is roughly centred (centre 11.82 vs board centre 12.0) | FRITZ-SD | single source |
| Pin order | Top view, header at the TOP edge, left to right: **CS, SCK, MOSI, MISO, VCC, GND**. Equivalently, with the header at the BOTTOM edge, left to right: GND, VCC, MISO, MOSI, SCK, CS | FRITZ-SD (connector names mapped to pad positions). The Scribd summary lists the labels in the order "GND, VCC, MISO, MOSI, SCK, CS" with no positions | single source for positions; label order consistent with a second |
| Mounting holes | **not found** (not in the Fritzing PCB svg; ELECTROKIT-SD says only "Pin headers") | | not found |
| Pin-order variants | **not found** in text | | not found |

### 9b. Small 6-pin micro-SD module (3.3 V, no level shifter)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Pin order | pad 1..6: **3V3, CS, MOSI, CLK, MISO, GND** | CG-SD symbol + footprint | single source |
| Header | 1 x 6, 2.54 mm, along a short edge (column at x = 0, 1.27 mm from that edge). Pins y = 0..12.7, centred in the 17.78 mm width | CG-SD | single source |
| Board | 30.48 x 17.78 mm (silk x -1.27..29.21, y -2.54..15.24) | CG-SD | single source, footprint author only |
| Mounting holes | **not found** | | not found |

---

## Not found / unresolved (summary)

- XIAO underside pad positions (not extracted; not needed for the 14-pin footprint).
- ESP32-C3 SuperMini: where exactly the header sits along the 22.52 mm length (SM-MRTNVGR says centred, SM-DED811 says 1.275 / 3.465 mm from the ends). The Elecrow file conflicts on both order and spacing.
- RP2040-Zero and ESP32-S3-Zero board outlines (the Waveshare text has none; footprint numbers only). RP2040-Zero's 10 underside pads. ESP32-S3-Zero underside pads.
- Pico mounting-hole positions (diameter 2.1 mm is verified).
- DOIT DevKit V1 board outline. DevKitC board length.
- NodeMCU Amica: no KiCad file with the correct 22.86 mm spacing was found. The spacing comes from two text pages; pin order is single source.
- ESP-01S header identity with ESP-01.
- 0.96" OLED: no vendor text for mounting holes (the two KiCad files disagree). No 0.96" text for the VCC/GND-swapped variant.
- 0.91" OLED mounting holes. 0.96" SPI OLED header position and holes.
- Micro-SD modules: mounting holes; pin-order variants.

---

## Appendix: KiCad pad coordinate listings

Units: mm. KiCad coordinates use +y down, top view. "size" is the copper pad size and "drill" the hole diameter. Pads with an empty name are NPTH (non-plated mounting/locating holes).

Extra non-KiCad listing: the SM-DED811 recreated SuperMini PCB, header holes (absolute board coordinates, board Edge.Cuts x 42.05..60.05, y 30.0..52.52, USB-C at the top):
```
H1 (left)  inner hole x=43.430 (castellation at x=42.050): y=31.275 GPIO5, 33.815 GPIO6, 36.355 GPIO7, 38.895 GPIO8, 41.435 GPIO9, 43.975 GPIO10, 46.515 GPIO20, 49.055 GPIO21
H2 (right) inner hole x=58.645 (castellation at x=60.025): y=31.275 5V(VBUS), 33.815 GND, 36.355 3V3, 38.895 GPIO4, 41.435 GPIO3, 43.975 GPIO2, 46.515 GPIO1, 49.055 GPIO0
```

Eagle-derived listings (+y UP, origin at the bottom-left board corner, top view):
```
Pro Mini (SF-PROMINI) board 0..17.78 x 0..33.02
 Left  x=1.27 : y=29.21 TXO, 26.67 RXI, 24.13 RESET, 21.59 GND, 19.05 D2, 16.51 D3, 13.97 D4, 11.43 D5, 8.89 D6, 6.35 D7, 3.81 D8, 1.27 D9
 Right x=16.51: y=29.21 RAW, 26.67 GND, 24.13 RESET, 21.59 VCC, 19.05 A3, 16.51 A2, 13.97 A1, 11.43 A0, 8.89 SCK/D13, 6.35 MISO/D12, 3.81 MOSI/D11, 1.27 D10
 FTDI  y=31.75: x=2.54 GND, 5.08 GND, 7.62 VCC, 10.16 RXI, 12.70 TXO, 15.24 DTR
 Inner x=13.589: y=17.907 A4, 20.447 A5, 7.493 A6, 10.033 A7
 drill 1.016 for all
Pro Micro (SF-PROMICRO v13) board 0..17.78 x 0..33.02, USB X1 at (8.89, 31.75)
 Left  x=1.27 : y=29.21 TXO, 26.67 RXI, 24.13 GND, 21.59 GND, 19.05 D2, 16.51 D3, 13.97 D4, 11.43 D5, 8.89 D6, 6.35 D7, 3.81 D8, 1.27 D9
 Right x=16.51: y=29.21 RAW, 26.67 GND, 24.13 RESET, 21.59 VCC, 19.05 A3, 16.51 A2, 13.97 A1, 11.43 A0, 8.89 SCK, 6.35 MISO, 3.81 MOSI, 1.27 D10
 drill 1.016
```

Fritzing SD module (FRITZ-SD) pad centres, converted from pt to mm (top view, header at the top, origin at the top-left):
```
CS (5.47, 3.98)  SCK (8.01, 3.98)  MOSI (10.55, 3.98)  MISO (13.09, 3.98)  VCC (15.63, 3.98)  GND (18.17, 3.98)   board 24.0 x 42.0
```

### XIAO ESP32-C3 (Seeed OPL_Kicad_Library, XIAO-ESP32-C3-DIP.kicad_mod), through-hole pads only (each also has an SMD castellation pad at y = +/-8.455)

```
1       x=7.62       y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
2       x=5.08       y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
3       x=2.54       y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
4       x=0          y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
5       x=-2.54      y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
6       x=-5.08      y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
7       x=-7.62      y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.889
8       x=-7.62      y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
9       x=-5.08      y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
10      x=-2.54      y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
11      x=0          y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
12      x=2.54       y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
13      x=5.08       y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
14      x=7.62       y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.889
```

XIAO-ESP32-S3-DIP.kicad_mod and XIAO-RP2040-DIP.kicad_mod have identical pad numbers/coordinates/drills to the C3 file above (checked by parsing all three).

### ESP32-C3 SuperMini (mrtnvgr/KiCad_ESP32-C3-SuperMini)

```
1       x=7.62       y=8.89       thru_hole    circle    size 1.14 1.14    drill 0.84
2       x=7.62       y=6.35       thru_hole    circle    size 1.14 1.14    drill 0.84
3       x=7.62       y=3.81       thru_hole    circle    size 1.14 1.14    drill 0.84
4       x=7.62       y=1.27       thru_hole    circle    size 1.14 1.14    drill 0.84
5       x=7.62       y=-1.27      thru_hole    circle    size 1.14 1.14    drill 0.84
6       x=7.62       y=-3.81      thru_hole    circle    size 1.14 1.14    drill 0.84
7       x=7.62       y=-6.35      thru_hole    circle    size 1.14 1.14    drill 0.84
8       x=7.62       y=-8.89      thru_hole    circle    size 1.14 1.14    drill 0.84
9       x=-7.62      y=-8.89      thru_hole    circle    size 1.14 1.14    drill 0.84
10      x=-7.62      y=-6.35      thru_hole    circle    size 1.14 1.14    drill 0.84
11      x=-7.62      y=-3.81      thru_hole    circle    size 1.14 1.14    drill 0.84
12      x=-7.62      y=-1.27      thru_hole    circle    size 1.14 1.14    drill 0.84
13      x=-7.62      y=1.27       thru_hole    circle    size 1.14 1.14    drill 0.84
14      x=-7.62      y=3.81       thru_hole    circle    size 1.14 1.14    drill 0.84
15      x=-7.62      y=6.35       thru_hole    circle    size 1.14 1.14    drill 0.84
16      x=-7.62      y=8.89       thru_hole    circle    size 1.14 1.14    drill 0.84
```

### ESP32-C3 SuperMini (zentarot/Elecrow-ESP32-C3-SuperMini-KiCad, 2.54 mm variant), DISAGREES with the other two, see section 2

```
1       x=-9.300     y=-8.890     thru_hole    circle    size 1.8 1.8      drill 1.0
2       x=-9.300     y=-6.350     thru_hole    circle    size 1.8 1.8      drill 1.0
3       x=-9.300     y=-3.810     thru_hole    circle    size 1.8 1.8      drill 1.0
4       x=-9.300     y=-1.270     thru_hole    circle    size 1.8 1.8      drill 1.0
5       x=-9.300     y=1.270      thru_hole    circle    size 1.8 1.8      drill 1.0
6       x=-9.300     y=3.810      thru_hole    circle    size 1.8 1.8      drill 1.0
7       x=-9.300     y=6.350      thru_hole    circle    size 1.8 1.8      drill 1.0
8       x=-9.300     y=8.890      thru_hole    circle    size 1.8 1.8      drill 1.0
9       x=9.300      y=-8.890     thru_hole    circle    size 1.8 1.8      drill 1.0
10      x=9.300      y=-6.350     thru_hole    circle    size 1.8 1.8      drill 1.0
11      x=9.300      y=-3.810     thru_hole    circle    size 1.8 1.8      drill 1.0
12      x=9.300      y=-1.270     thru_hole    circle    size 1.8 1.8      drill 1.0
13      x=9.300      y=1.270      thru_hole    circle    size 1.8 1.8      drill 1.0
14      x=9.300      y=3.810      thru_hole    circle    size 1.8 1.8      drill 1.0
15      x=9.300      y=6.350      thru_hole    circle    size 1.8 1.8      drill 1.0
16      x=9.300      y=8.890      thru_hole    circle    size 1.8 1.8      drill 1.0
```

### Waveshare RP2040-Zero (CountParadox/RP2040-Zero-Kicad)

```
1       x=17.78      y=-22.86     thru_hole    roundrect size 2.6 1.6      drill 0.8
2       x=17.78      y=-20.32     thru_hole    roundrect size 2.6 1.6      drill 0.8
3       x=17.78      y=-17.78     thru_hole    roundrect size 2.6 1.6      drill 0.8
4       x=17.78      y=-15.24     thru_hole    roundrect size 2.6 1.6      drill 0.8
5       x=17.78      y=-12.7      thru_hole    roundrect size 2.6 1.6      drill 0.8
6       x=17.78      y=-10.16     thru_hole    roundrect size 2.6 1.6002   drill 0.8
7       x=17.78      y=-7.62      thru_hole    roundrect size 2.6 1.6002   drill 0.8
8       x=17.78      y=-5.08      thru_hole    roundrect size 2.6 1.6002   drill 0.8
9       x=17.78      y=-2.54      thru_hole    roundrect size 2.6 1.6002   drill 0.8
10      x=15.24      y=-2.33      thru_hole    roundrect size 1.6 2.6      drill 0.8
11      x=12.7       y=-2.33      thru_hole    roundrect size 1.5748 2.6   drill 0.8
12      x=10.16      y=-2.33      thru_hole    roundrect size 1.5748 2.6   drill 0.8
13      x=7.62       y=-2.33      thru_hole    roundrect size 1.5748 2.6   drill 0.8
14      x=5.08       y=-2.33      thru_hole    roundrect size 1.5748 2.6   drill 0.8
15      x=2.54       y=-2.54      thru_hole    roundrect size 2.6 1.6002   drill 0.8
16      x=2.54       y=-5.08      thru_hole    roundrect size 2.6 1.6002   drill 0.8
17      x=2.54       y=-7.62      thru_hole    roundrect size 2.6 1.6002   drill 0.8
18      x=2.54       y=-10.16     thru_hole    roundrect size 2.6 1.6002   drill 0.8
19      x=2.54       y=-12.7      thru_hole    roundrect size 2.6 1.6002   drill 0.8
20      x=2.54       y=-15.24     thru_hole    roundrect size 2.6 1.6002   drill 0.8
21      x=2.54       y=-17.78     thru_hole    roundrect size 2.6 1.6002   drill 0.8
22      x=2.54       y=-20.32     thru_hole    roundrect size 2.6 1.6002   drill 0.8
23      x=2.54       y=-22.86     thru_hole    roundrect size 2.6 1.6002   drill 0.8
```

### Waveshare RP2040-Zero (dj505/RP2040-Zero-KiCAD), through-hole pads only

```
1       x=2.54       y=-22.987    thru_hole    circle    size 1.7 1.7      drill 0.8
2       x=2.54       y=-20.447    thru_hole    circle    size 1.7 1.7      drill 0.8
3       x=2.54       y=-17.907    thru_hole    circle    size 1.7 1.7      drill 0.8
4       x=2.54       y=-15.367    thru_hole    circle    size 1.7 1.7      drill 0.8
5       x=2.54       y=-12.827    thru_hole    circle    size 1.7 1.7      drill 0.8
6       x=2.54       y=-10.287    thru_hole    circle    size 1.7 1.7      drill 0.8
7       x=2.54       y=-7.747     thru_hole    circle    size 1.7 1.7      drill 0.8
8       x=2.54       y=-5.207     thru_hole    circle    size 1.7 1.7      drill 0.8
9       x=2.54       y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
10      x=17.78      y=-22.987    thru_hole    circle    size 1.7 1.7      drill 0.8
11      x=17.78      y=-20.447    thru_hole    circle    size 1.7 1.7      drill 0.8
12      x=17.78      y=-17.907    thru_hole    circle    size 1.7 1.7      drill 0.8
13      x=17.78      y=-15.367    thru_hole    circle    size 1.7 1.7      drill 0.8
14      x=17.78      y=-12.827    thru_hole    circle    size 1.7 1.7      drill 0.8
15      x=17.78      y=-10.287    thru_hole    circle    size 1.7 1.7      drill 0.8
16      x=17.78      y=-7.747     thru_hole    circle    size 1.7 1.7      drill 0.8
17      x=17.78      y=-5.207     thru_hole    circle    size 1.7 1.7      drill 0.8
18      x=17.78      y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
19      x=5.08       y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
20      x=7.62       y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
21      x=10.16      y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
22      x=12.7       y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
23      x=15.24      y=-2.667     thru_hole    circle    size 1.7 1.7      drill 0.8
```

### Waveshare ESP32-S3-Zero (jtomka/kicad-esp32-s3-zero; byte-identical copy in tomkooij/e07-900m10s-esp32s3zero)

```
1       x=1.38       y=1.59       thru_hole    rect      size 1.524 1.524  drill 0.762
2       x=1.38       y=4.13       thru_hole    circle    size 1.524 1.524  drill 0.762
3       x=1.38       y=6.67       thru_hole    circle    size 1.524 1.524  drill 0.762
4       x=1.38       y=9.21       thru_hole    circle    size 1.524 1.524  drill 0.762
5       x=1.38       y=11.75      thru_hole    circle    size 1.524 1.524  drill 0.762
6       x=1.38       y=14.29      thru_hole    circle    size 1.524 1.524  drill 0.762
7       x=1.38       y=16.83      thru_hole    circle    size 1.524 1.524  drill 0.762
8       x=1.38       y=19.37      thru_hole    circle    size 1.524 1.524  drill 0.762
9       x=1.38       y=21.91      thru_hole    circle    size 1.524 1.524  drill 0.762
10      x=16.62      y=21.91      thru_hole    circle    size 1.524 1.524  drill 0.762
11      x=16.62      y=19.37      thru_hole    circle    size 1.524 1.524  drill 0.762
12      x=16.62      y=16.83      thru_hole    circle    size 1.524 1.524  drill 0.762
13      x=16.62      y=14.29      thru_hole    circle    size 1.524 1.524  drill 0.762
14      x=16.62      y=11.75      thru_hole    circle    size 1.524 1.524  drill 0.762
15      x=16.62      y=9.21       thru_hole    circle    size 1.524 1.524  drill 0.762
16      x=16.62      y=6.67       thru_hole    circle    size 1.524 1.524  drill 0.762
17      x=16.62      y=4.13       thru_hole    circle    size 1.524 1.524  drill 0.762
18      x=16.62      y=1.59       thru_hole    circle    size 1.524 1.524  drill 0.762
```

### Waveshare ESP32-S3-Zero (formix/formix-kicad-libraries, SMD castellation pads only)

```
1       x=-8.7       y=-10.16     smd          roundrect size 3 1.5        drill -
2       x=-8.7       y=-7.62      smd          roundrect size 3 1.5        drill -
3       x=-8.7       y=-5.08      smd          roundrect size 3 1.5        drill -
4       x=-8.7       y=-2.54      smd          roundrect size 3 1.5        drill -
5       x=-8.7       y=0          smd          roundrect size 3 1.5        drill -
6       x=-8.7       y=2.54       smd          roundrect size 3 1.5        drill -
7       x=-8.7       y=5.08       smd          roundrect size 3 1.5        drill -
8       x=-8.7       y=7.62       smd          roundrect size 3 1.5        drill -
9       x=-8.7       y=10.16      smd          roundrect size 3 1.5        drill -
10      x=8.7        y=10.16      smd          roundrect size 3 1.5        drill -
11      x=8.7        y=7.62       smd          roundrect size 3 1.5        drill -
12      x=8.7        y=5.08       smd          roundrect size 3 1.5        drill -
13      x=8.7        y=2.54       smd          roundrect size 3 1.5        drill -
14      x=8.7        y=0          smd          roundrect size 3 1.5        drill -
15      x=8.7        y=-2.54      smd          roundrect size 3 1.5        drill -
16      x=8.7        y=-5.08      smd          roundrect size 3 1.5        drill -
17      x=8.7        y=-7.62      smd          roundrect size 3 1.5        drill -
18      x=8.7        y=-10.16     smd          roundrect size 3 1.5        drill -
```

### Raspberry Pi Pico (ncarandini/KiCad-RP-Pico RPi_Pico_SMD_TH), through-hole + NPTH (castellation SMD pads omitted)

```
(NPTH)  x=2.725      y=-24        np_thru_hole oval      size 1.8 1.8      drill 1.8
(NPTH)  x=-2.725     y=-24        np_thru_hole oval      size 1.8 1.8      drill 1.8
(NPTH)  x=-2.425     y=-20.97     np_thru_hole oval      size 1.5 1.5      drill 1.5
(NPTH)  x=2.425      y=-20.97     np_thru_hole oval      size 1.5 1.5      drill 1.5
1       x=-8.89      y=-24.13     thru_hole    oval      size 1.7 1.7      drill 1.02
2       x=-8.89      y=-21.59     thru_hole    oval      size 1.7 1.7      drill 1.02
3       x=-8.89      y=-19.05     thru_hole    rect      size 1.7 1.7      drill 1.02
4       x=-8.89      y=-16.51     thru_hole    oval      size 1.7 1.7      drill 1.02
5       x=-8.89      y=-13.97     thru_hole    oval      size 1.7 1.7      drill 1.02
6       x=-8.89      y=-11.43     thru_hole    oval      size 1.7 1.7      drill 1.02
7       x=-8.89      y=-8.89      thru_hole    oval      size 1.7 1.7      drill 1.02
8       x=-8.89      y=-6.35      thru_hole    rect      size 1.7 1.7      drill 1.02
9       x=-8.89      y=-3.81      thru_hole    oval      size 1.7 1.7      drill 1.02
10      x=-8.89      y=-1.27      thru_hole    oval      size 1.7 1.7      drill 1.02
11      x=-8.89      y=1.27       thru_hole    oval      size 1.7 1.7      drill 1.02
12      x=-8.89      y=3.81       thru_hole    oval      size 1.7 1.7      drill 1.02
13      x=-8.89      y=6.35       thru_hole    rect      size 1.7 1.7      drill 1.02
14      x=-8.89      y=8.89       thru_hole    oval      size 1.7 1.7      drill 1.02
15      x=-8.89      y=11.43      thru_hole    oval      size 1.7 1.7      drill 1.02
16      x=-8.89      y=13.97      thru_hole    oval      size 1.7 1.7      drill 1.02
17      x=-8.89      y=16.51      thru_hole    oval      size 1.7 1.7      drill 1.02
18      x=-8.89      y=19.05      thru_hole    rect      size 1.7 1.7      drill 1.02
19      x=-8.89      y=21.59      thru_hole    oval      size 1.7 1.7      drill 1.02
20      x=-8.89      y=24.13      thru_hole    oval      size 1.7 1.7      drill 1.02
21      x=8.89       y=24.13      thru_hole    oval      size 1.7 1.7      drill 1.02
22      x=8.89       y=21.59      thru_hole    oval      size 1.7 1.7      drill 1.02
23      x=8.89       y=19.05      thru_hole    rect      size 1.7 1.7      drill 1.02
24      x=8.89       y=16.51      thru_hole    oval      size 1.7 1.7      drill 1.02
25      x=8.89       y=13.97      thru_hole    oval      size 1.7 1.7      drill 1.02
26      x=8.89       y=11.43      thru_hole    oval      size 1.7 1.7      drill 1.02
27      x=8.89       y=8.89       thru_hole    oval      size 1.7 1.7      drill 1.02
28      x=8.89       y=6.35       thru_hole    rect      size 1.7 1.7      drill 1.02
29      x=8.89       y=3.81       thru_hole    oval      size 1.7 1.7      drill 1.02
30      x=8.89       y=1.27       thru_hole    oval      size 1.7 1.7      drill 1.02
31      x=8.89       y=-1.27      thru_hole    oval      size 1.7 1.7      drill 1.02
32      x=8.89       y=-3.81      thru_hole    oval      size 1.7 1.7      drill 1.02
33      x=8.89       y=-6.35      thru_hole    rect      size 1.7 1.7      drill 1.02
34      x=8.89       y=-8.89      thru_hole    oval      size 1.7 1.7      drill 1.02
35      x=8.89       y=-11.43     thru_hole    oval      size 1.7 1.7      drill 1.02
36      x=8.89       y=-13.97     thru_hole    oval      size 1.7 1.7      drill 1.02
37      x=8.89       y=-16.51     thru_hole    oval      size 1.7 1.7      drill 1.02
38      x=8.89       y=-19.05     thru_hole    rect      size 1.7 1.7      drill 1.02
39      x=8.89       y=-21.59     thru_hole    oval      size 1.7 1.7      drill 1.02
40      x=8.89       y=-24.13     thru_hole    oval      size 1.7 1.7      drill 1.02
41      x=-2.54      y=23.9       thru_hole    oval      size 1.7 1.7      drill 1.02
42      x=0          y=23.9       thru_hole    rect      size 1.7 1.7      drill 1.02
43      x=2.54       y=23.9       thru_hole    oval      size 1.7 1.7      drill 1.02
```

### ESP32 DOIT DevKit V1 30-pin (syauqibilfaqih/ESP32-DevKit-V1-DOIT ESP32_30pin)

```
1       x=-11.92754  y=17.019813  thru_hole    oval      size 1.524 1.9    drill 0.8
2       x=-11.92754  y=14.479813  thru_hole    oval      size 1.524 1.9    drill 0.8
3       x=-11.92754  y=11.939813  thru_hole    oval      size 1.524 1.9    drill 0.8
4       x=-11.92754  y=9.399813   thru_hole    oval      size 1.524 1.9    drill 0.8
5       x=-11.92754  y=6.859813   thru_hole    oval      size 1.524 1.9    drill 0.8
6       x=-11.92754  y=4.319813   thru_hole    oval      size 1.524 1.9    drill 0.8
7       x=-11.92754  y=1.779813   thru_hole    oval      size 1.524 1.9    drill 0.8
8       x=-11.92754  y=-0.760187  thru_hole    oval      size 1.524 1.9    drill 0.8
9       x=-11.92754  y=-3.300187  thru_hole    oval      size 1.524 1.9    drill 0.8
10      x=-11.92754  y=-5.840187  thru_hole    oval      size 1.524 1.9    drill 0.8
11      x=-11.92754  y=-8.380187  thru_hole    oval      size 1.524 1.9    drill 0.8
12      x=-11.92754  y=-10.920187 thru_hole    oval      size 1.524 1.9    drill 0.8
13      x=-11.92754  y=-13.460187 thru_hole    oval      size 1.524 1.9    drill 0.8
14      x=-11.92754  y=-16.000187 thru_hole    oval      size 1.524 1.9    drill 0.8
15      x=-11.92754  y=-18.540187 thru_hole    oval      size 1.524 1.9    drill 0.8
16      x=13.47246   y=17.019813  thru_hole    oval      size 1.524 1.9    drill 0.8
17      x=13.47246   y=14.479813  thru_hole    oval      size 1.524 1.9    drill 0.8
18      x=13.47246   y=11.939813  thru_hole    oval      size 1.524 1.9    drill 0.8
19      x=13.47246   y=9.399813   thru_hole    oval      size 1.524 1.9    drill 0.8
20      x=13.47246   y=6.859813   thru_hole    oval      size 1.524 1.9    drill 0.8
21      x=13.47246   y=4.319813   thru_hole    oval      size 1.524 1.9    drill 0.8
22      x=13.47246   y=1.779813   thru_hole    oval      size 1.524 1.9    drill 0.8
23      x=13.47246   y=-0.760187  thru_hole    oval      size 1.524 1.9    drill 0.8
24      x=13.47246   y=-3.300187  thru_hole    oval      size 1.524 1.9    drill 0.8
25      x=13.47246   y=-5.840187  thru_hole    oval      size 1.524 1.9    drill 0.8
26      x=13.47246   y=-8.380187  thru_hole    oval      size 1.524 1.9    drill 0.8
27      x=13.47246   y=-10.920187 thru_hole    oval      size 1.524 1.9    drill 0.8
28      x=13.47246   y=-13.460187 thru_hole    oval      size 1.524 1.9    drill 0.8
29      x=13.47246   y=-16.000187 thru_hole    oval      size 1.524 1.9    drill 0.8
30      x=13.47246   y=-18.540187 thru_hole    oval      size 1.524 1.9    drill 0.8
```

### Espressif ESP32-DevKitC 38-pin (espressif/kicad-libraries ESP32-DevKitC)

```
1       x=0          y=0          thru_hole    rect      size 1.2 2        drill 0.8
2       x=0          y=2.54       thru_hole    oval      size 1.2 2        drill 0.8
3       x=0          y=5.08       thru_hole    oval      size 1.2 2        drill 0.8
4       x=0          y=7.62       thru_hole    oval      size 1.2 2        drill 0.8
5       x=0          y=10.16      thru_hole    oval      size 1.2 2        drill 0.8
6       x=0          y=12.7       thru_hole    oval      size 1.2 2        drill 0.8
7       x=0          y=15.24      thru_hole    oval      size 1.2 2        drill 0.8
8       x=0          y=17.78      thru_hole    oval      size 1.2 2        drill 0.8
9       x=0          y=20.32      thru_hole    oval      size 1.2 2        drill 0.8
10      x=0          y=22.86      thru_hole    oval      size 1.2 2        drill 0.8
11      x=0          y=25.4       thru_hole    oval      size 1.2 2        drill 0.8
12      x=0          y=27.94      thru_hole    oval      size 1.2 2        drill 0.8
13      x=0          y=30.48      thru_hole    oval      size 1.2 2        drill 0.8
14      x=0          y=33.02      thru_hole    oval      size 1.2 2        drill 0.8
15      x=0          y=35.56      thru_hole    oval      size 1.2 2        drill 0.8
16      x=0          y=38.1       thru_hole    oval      size 1.2 2        drill 0.8
17      x=0          y=40.64      thru_hole    oval      size 1.2 2        drill 0.8
18      x=0          y=43.18      thru_hole    oval      size 1.2 2        drill 0.8
19      x=0          y=45.72      thru_hole    oval      size 1.2 2        drill 0.8
20      x=25.39632   y=45.71728   thru_hole    oval      size 1.2 2        drill 0.8
21      x=25.39632   y=43.17728   thru_hole    oval      size 1.2 2        drill 0.8
22      x=25.4       y=40.64      thru_hole    oval      size 1.2 2        drill 0.8
23      x=25.4       y=38.1       thru_hole    oval      size 1.2 2        drill 0.8
24      x=25.4       y=35.56      thru_hole    oval      size 1.2 2        drill 0.8
25      x=25.4       y=33.02      thru_hole    oval      size 1.2 2        drill 0.8
26      x=25.4       y=30.48      thru_hole    oval      size 1.2 2        drill 0.8
27      x=25.4       y=27.94      thru_hole    oval      size 1.2 2        drill 0.8
28      x=25.4       y=25.4       thru_hole    oval      size 1.2 2        drill 0.8
29      x=25.4       y=22.86      thru_hole    oval      size 1.2 2        drill 0.8
30      x=25.4       y=20.32      thru_hole    oval      size 1.2 2        drill 0.8
31      x=25.4       y=17.78      thru_hole    oval      size 1.2 2        drill 0.8
32      x=25.4       y=15.24      thru_hole    oval      size 1.2 2        drill 0.8
33      x=25.4       y=12.7       thru_hole    oval      size 1.2 2        drill 0.8
34      x=25.4       y=10.16      thru_hole    oval      size 1.2 2        drill 0.8
35      x=25.4       y=7.62       thru_hole    oval      size 1.2 2        drill 0.8
36      x=25.4       y=5.08       thru_hole    oval      size 1.2 2        drill 0.8
37      x=25.4       y=2.54       thru_hole    oval      size 1.2 2        drill 0.8
38      x=25.4       y=0          thru_hole    oval      size 1.2 2        drill 0.8
```

### NodeMCU 1.0 (ESP-12E) (NightDragon1/kicad-ESP8266), 27.94 mm rows, see section 6

```
1       x=-13.97     y=-17.78     thru_hole    circle    size 1.524 1.524  drill 0.762
2       x=-13.97     y=-15.24     thru_hole    circle    size 1.524 1.524  drill 0.762
3       x=-13.97     y=-12.7      thru_hole    circle    size 1.524 1.524  drill 0.762
4       x=-13.97     y=-10.16     thru_hole    circle    size 1.524 1.524  drill 0.762
5       x=-13.97     y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.762
6       x=-13.97     y=-5.08      thru_hole    circle    size 1.524 1.524  drill 0.762
7       x=-13.97     y=-2.54      thru_hole    circle    size 1.524 1.524  drill 0.762
8       x=-13.97     y=0          thru_hole    circle    size 1.524 1.524  drill 0.762
9       x=-13.97     y=2.54       thru_hole    circle    size 1.524 1.524  drill 0.762
10      x=-13.97     y=5.08       thru_hole    circle    size 1.524 1.524  drill 0.762
11      x=-13.97     y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.762
12      x=-13.97     y=10.16      thru_hole    circle    size 1.524 1.524  drill 0.762
13      x=-13.97     y=12.7       thru_hole    circle    size 1.524 1.524  drill 0.762
14      x=-13.97     y=15.24      thru_hole    circle    size 1.524 1.524  drill 0.762
15      x=-13.97     y=17.78      thru_hole    circle    size 1.524 1.524  drill 0.762
16      x=13.97      y=17.78      thru_hole    circle    size 1.524 1.524  drill 0.762
17      x=13.97      y=15.24      thru_hole    circle    size 1.524 1.524  drill 0.762
18      x=13.97      y=12.7       thru_hole    circle    size 1.524 1.524  drill 0.762
19      x=13.97      y=10.16      thru_hole    circle    size 1.524 1.524  drill 0.762
20      x=13.97      y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.762
21      x=13.97      y=5.08       thru_hole    circle    size 1.524 1.524  drill 0.762
22      x=13.97      y=2.54       thru_hole    circle    size 1.524 1.524  drill 0.762
23      x=13.97      y=0          thru_hole    circle    size 1.524 1.524  drill 0.762
24      x=13.97      y=-2.54      thru_hole    circle    size 1.524 1.524  drill 0.762
25      x=13.97      y=-5.08      thru_hole    circle    size 1.524 1.524  drill 0.762
26      x=13.97      y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.762
27      x=13.97      y=-10.16     thru_hole    circle    size 1.524 1.524  drill 0.762
28      x=13.97      y=-12.7      thru_hole    circle    size 1.524 1.524  drill 0.762
29      x=13.97      y=-15.24     thru_hole    circle    size 1.524 1.524  drill 0.762
30      x=13.97      y=-17.78     thru_hole    circle    size 1.524 1.524  drill 0.762
```

### NodeMCU LoLin V3 (NightDragon1/kicad-ESP8266)

```
1       x=-13.97     y=-20.32     thru_hole    circle    size 1.524 1.524  drill 0.762
2       x=-13.97     y=-17.78     thru_hole    circle    size 1.524 1.524  drill 0.762
3       x=-13.97     y=-15.24     thru_hole    circle    size 1.524 1.524  drill 0.762
4       x=-13.97     y=-12.7      thru_hole    circle    size 1.524 1.524  drill 0.762
5       x=-13.97     y=-10.16     thru_hole    circle    size 1.524 1.524  drill 0.762
6       x=-13.97     y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.762
7       x=-13.97     y=-5.08      thru_hole    circle    size 1.524 1.524  drill 0.762
8       x=-13.97     y=-2.54      thru_hole    circle    size 1.524 1.524  drill 0.762
9       x=-13.97     y=0          thru_hole    circle    size 1.524 1.524  drill 0.762
10      x=-13.97     y=2.54       thru_hole    circle    size 1.524 1.524  drill 0.762
11      x=-13.97     y=5.08       thru_hole    circle    size 1.524 1.524  drill 0.762
12      x=-13.97     y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.762
13      x=-13.97     y=10.16      thru_hole    circle    size 1.524 1.524  drill 0.762
14      x=-13.97     y=12.7       thru_hole    circle    size 1.524 1.524  drill 0.762
15      x=-13.97     y=15.24      thru_hole    circle    size 1.524 1.524  drill 0.762
16      x=13.97      y=15.24      thru_hole    circle    size 1.524 1.524  drill 0.762
17      x=13.97      y=12.7       thru_hole    circle    size 1.524 1.524  drill 0.762
18      x=13.97      y=10.16      thru_hole    circle    size 1.524 1.524  drill 0.762
19      x=13.97      y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.762
20      x=13.97      y=5.08       thru_hole    circle    size 1.524 1.524  drill 0.762
21      x=13.97      y=2.54       thru_hole    circle    size 1.524 1.524  drill 0.762
22      x=13.97      y=0          thru_hole    circle    size 1.524 1.524  drill 0.762
23      x=13.97      y=-2.54      thru_hole    circle    size 1.524 1.524  drill 0.762
24      x=13.97      y=-5.08      thru_hole    circle    size 1.524 1.524  drill 0.762
25      x=13.97      y=-7.62      thru_hole    circle    size 1.524 1.524  drill 0.762
26      x=13.97      y=-10.16     thru_hole    circle    size 1.524 1.524  drill 0.762
27      x=13.97      y=-12.7      thru_hole    circle    size 1.524 1.524  drill 0.762
28      x=13.97      y=-15.24     thru_hole    circle    size 1.524 1.524  drill 0.762
29      x=13.97      y=-17.78     thru_hole    circle    size 1.524 1.524  drill 0.762
30      x=13.97      y=-20.32     thru_hole    circle    size 1.524 1.524  drill 0.762
```

### WEMOS D1 mini (old KiCad official library mirror, Module.pretty/WEMOS_D1_mini_light)

```
2       x=0          y=2.54       thru_hole    oval      size 2 1.6        drill 1
1       x=0          y=0          thru_hole    rect      size 2 2          drill 1
3       x=0          y=5.08       thru_hole    oval      size 2 1.6        drill 1
4       x=0          y=7.62       thru_hole    oval      size 2 1.6        drill 1
5       x=0          y=10.16      thru_hole    oval      size 2 1.6        drill 1
6       x=0          y=12.7       thru_hole    oval      size 2 1.6        drill 1
7       x=0          y=15.24      thru_hole    oval      size 2 1.6        drill 1
8       x=0          y=17.78      thru_hole    oval      size 2 1.6        drill 1
9       x=22.86      y=17.78      thru_hole    oval      size 2 1.6        drill 1
10      x=22.86      y=15.24      thru_hole    oval      size 2 1.6        drill 1
11      x=22.86      y=12.7       thru_hole    oval      size 2 1.6        drill 1
12      x=22.86      y=10.16      thru_hole    oval      size 2 1.6        drill 1
13      x=22.86      y=7.62       thru_hole    oval      size 2 1.6        drill 1
14      x=22.86      y=5.08       thru_hole    oval      size 2 1.6        drill 1
15      x=22.86      y=2.54       thru_hole    oval      size 2 1.6        drill 1
16      x=22.86      y=0          thru_hole    oval      size 2 1.6        drill 1
```

### ESP-01 (NightDragon1/kicad-ESP8266)

```
1       x=0          y=0          thru_hole    rect      size 1.7272 1.7272 drill 1.016
2       x=2.54       y=0          thru_hole    oval      size 1.7272 1.7272 drill 1.016
3       x=0          y=2.54       thru_hole    oval      size 1.7272 1.7272 drill 1.016
4       x=2.54       y=2.54       thru_hole    oval      size 1.7272 1.7272 drill 1.016
5       x=0          y=5.08       thru_hole    oval      size 1.7272 1.7272 drill 1.016
6       x=2.54       y=5.08       thru_hole    oval      size 1.7272 1.7272 drill 1.016
7       x=0          y=7.62       thru_hole    oval      size 1.7272 1.7272 drill 1.016
8       x=2.54       y=7.62       thru_hole    oval      size 1.7272 1.7272 drill 1.016
```

### Arduino Nano (old KiCad official library mirror, Module.pretty/Arduino_Nano)

```
1       x=0          y=0          thru_hole    rect      size 1.6 1.6      drill 1.0
17      x=15.24      y=33.02      thru_hole    oval      size 1.6 1.6      drill 1.0
2       x=0          y=2.54       thru_hole    oval      size 1.6 1.6      drill 1.0
18      x=15.24      y=30.48      thru_hole    oval      size 1.6 1.6      drill 1.0
3       x=0          y=5.08       thru_hole    oval      size 1.6 1.6      drill 1.0
19      x=15.24      y=27.94      thru_hole    oval      size 1.6 1.6      drill 1.0
4       x=0          y=7.62       thru_hole    oval      size 1.6 1.6      drill 1.0
20      x=15.24      y=25.4       thru_hole    oval      size 1.6 1.6      drill 1.0
5       x=0          y=10.16      thru_hole    oval      size 1.6 1.6      drill 1.0
21      x=15.24      y=22.86      thru_hole    oval      size 1.6 1.6      drill 1.0
6       x=0          y=12.7       thru_hole    oval      size 1.6 1.6      drill 1.0
22      x=15.24      y=20.32      thru_hole    oval      size 1.6 1.6      drill 1.0
7       x=0          y=15.24      thru_hole    oval      size 1.6 1.6      drill 1.0
23      x=15.24      y=17.78      thru_hole    oval      size 1.6 1.6      drill 1.0
8       x=0          y=17.78      thru_hole    oval      size 1.6 1.6      drill 1.0
24      x=15.24      y=15.24      thru_hole    oval      size 1.6 1.6      drill 1.0
9       x=0          y=20.32      thru_hole    oval      size 1.6 1.6      drill 1.0
25      x=15.24      y=12.7       thru_hole    oval      size 1.6 1.6      drill 1.0
10      x=0          y=22.86      thru_hole    oval      size 1.6 1.6      drill 1.0
26      x=15.24      y=10.16      thru_hole    oval      size 1.6 1.6      drill 1.0
11      x=0          y=25.4       thru_hole    oval      size 1.6 1.6      drill 1.0
27      x=15.24      y=7.62       thru_hole    oval      size 1.6 1.6      drill 1.0
12      x=0          y=27.94      thru_hole    oval      size 1.6 1.6      drill 1.0
28      x=15.24      y=5.08       thru_hole    oval      size 1.6 1.6      drill 1.0
13      x=0          y=30.48      thru_hole    oval      size 1.6 1.6      drill 1.0
29      x=15.24      y=2.54       thru_hole    oval      size 1.6 1.6      drill 1.0
14      x=0          y=33.02      thru_hole    oval      size 1.6 1.6      drill 1.0
30      x=15.24      y=0          thru_hole    oval      size 1.6 1.6      drill 1.0
15      x=0          y=35.56      thru_hole    oval      size 1.6 1.6      drill 1.0
16      x=15.24      y=35.56      thru_hole    oval      size 1.6 1.6      drill 1.0
```

### Arduino Pro Micro (keebio/Keebio-Parts.pretty ArduinoProMicro-TopSide)

```
1       x=-13.97     y=7.62       thru_hole    rect      size 1.7526 1.7526 drill 1.0922
2       x=-11.43     y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
3       x=-8.89      y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
4       x=-6.35      y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
5       x=-3.81      y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
6       x=-1.27      y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
7       x=1.27       y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
8       x=3.81       y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
9       x=6.35       y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
10      x=8.89       y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
11      x=11.43      y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
13      x=13.97      y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
14      x=11.43      y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
15      x=8.89       y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
16      x=6.35       y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
17      x=3.81       y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
18      x=1.27       y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
19      x=-1.27      y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
20      x=-3.81      y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
21      x=-6.35      y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
22      x=-8.89      y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
23      x=-11.43     y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
12      x=13.97      y=7.62       thru_hole    circle    size 1.7526 1.7526 drill 1.0922
24      x=-13.97     y=-7.62      thru_hole    circle    size 1.7526 1.7526 drill 1.0922
```

### 0.96in I2C OLED (LibreSolar/kicad-footprints OLED_SSD1306_I2C_0.96)

```
1       x=0          y=0          thru_hole    rect      size 1.7 1.7      drill 1
2       x=2.54       y=0          thru_hole    oval      size 1.7 1.7      drill 1
3       x=5.08       y=0          thru_hole    oval      size 1.7 1.7      drill 1
4       x=7.62       y=0          thru_hole    oval      size 1.7 1.7      drill 1
(NPTH)  x=-7.84      y=0.5        np_thru_hole circle    size 3 3          drill 2
(NPTH)  x=15.46      y=0.5        np_thru_hole circle    size 3 3          drill 2
(NPTH)  x=15.46      y=24.3       np_thru_hole circle    size 3 3          drill 2
(NPTH)  x=-7.84      y=24.3       np_thru_hole circle    size 3 3          drill 2
```

### 0.96in I2C OLED (TG9541/kicad-footprints Display_128x64_096_I2C)

```
(NPTH)  x=-11.176    y=0.635      np_thru_hole oval      size 3.8 2.9      drill oval 3.8 2.9
(NPTH)  x=11.176     y=0.635      np_thru_hole oval      size 3.8 2.9      drill oval 3.8 2.9
(NPTH)  x=11.176     y=23.749     np_thru_hole oval      size 3.8 2.9      drill oval 3.8 2.9
(NPTH)  x=-11.176    y=23.749     np_thru_hole oval      size 3.8 2.9      drill oval 3.8 2.9
2       x=-1.27      y=0          thru_hole    oval      size 1.7 1.7      drill 1
1       x=-3.81      y=0          thru_hole    rect      size 1.7 1.7      drill 1
3       x=1.27       y=0          thru_hole    oval      size 1.7 1.7      drill 1
4       x=3.81       y=0          thru_hole    oval      size 1.7 1.7      drill 1
```

### 0.96in I2C OLED (V01Ddev/kicad-ssd1306-oled-library 128x64OLED)

```
1       x=-3.62      y=-10.6      thru_hole    rect      size 2 1.6        drill 1
2       x=-1.08      y=-10.6      thru_hole    oval      size 2 1.6        drill 1
3       x=1.46       y=-10.6      thru_hole    oval      size 2 1.6        drill 1
4       x=4          y=-10.6      thru_hole    oval      size 2 1.6        drill 1
```

### 0.96in I2C OLED (yakipote/SSD1306_footprint)

```
1       x=3.81       y=-12        thru_hole    circle    size 1.7 1.7      drill 1
2       x=1.27       y=-12        thru_hole    circle    size 1.7 1.7      drill 1
3       x=-1.27      y=-12        thru_hole    circle    size 1.7 1.7      drill 1
4       x=-3.81      y=-12        thru_hole    circle    size 1.7 1.7      drill 1
```

### 0.91in I2C OLED 128x32 (gorbachev/KiCad-SSD1306-0.91-OLED-4pin-128x32.pretty)

```
1       x=36.5       y=2.19       thru_hole    rect      size 1.7 1.7      drill 1
2       x=36.5       y=4.73       thru_hole    oval      size 1.7 1.7      drill 1
3       x=36.5       y=7.27       thru_hole    oval      size 1.7 1.7      drill 1
4       x=36.5       y=9.81       thru_hole    oval      size 1.7 1.7      drill 1
```

### Small 6-pin micro-SD module (CGrassin/kicad_parts SD_Card_Module)

```
1       x=0          y=0          thru_hole    rect      size 1.524 1.524  drill 0.762
2       x=0          y=2.54       thru_hole    circle    size 1.524 1.524  drill 0.762
3       x=0          y=5.08       thru_hole    circle    size 1.524 1.524  drill 0.762
4       x=0          y=7.62       thru_hole    circle    size 1.524 1.524  drill 0.762
5       x=0          y=10.16      thru_hole    circle    size 1.524 1.524  drill 0.762
6       x=0          y=12.7       thru_hole    circle    size 1.524 1.524  drill 0.762
```

