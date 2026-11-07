# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Rebuild everything in examples/ from the built-in demo boards.

Run:  python3 tools/make_examples.py
Each demo is auto-placed (fixed random seed), auto-routed, checked, and exported.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from solotrace import demos, gerber, laser, render      # noqa: E402
from solotrace.drc import run_drc, summarize             # noqa: E402
from solotrace.placer import auto_place                  # noqa: E402
from solotrace.router import AutoRouter, RouteOptions    # noqa: E402
from solotrace.board import Via                          # noqa: E402
from solotrace import plane                              # noqa: E402

OUT = os.path.join(ROOT, "examples")


def build(name, fn, place=True, seed=2, backplane=False):
    b = fn()
    if place:
        auto_place(b, time_limit=20, seed=seed)
    res = AutoRouter(b, RouteOptions(algorithm=b.settings.router)).route_all()
    if backplane:
        b.settings.backplane = True
        b.touch()
        for x, y in plane.via_at_ground_pins(b):
            b.vias.append(Via(x, y))
        b.touch()
        for x, y in plane.stitch_points(b):
            b.vias.append(Via(x, y))
        b.touch()
    issues = run_drc(b)
    folder = os.path.join(OUT, name)
    os.makedirs(folder, exist_ok=True)
    b.save(os.path.join(folder, name + ".solotrace"))
    gerber.write_zip(b, os.path.join(folder, name + "-gerber.zip"))
    with open(os.path.join(folder, name + "-copper-side-1to1.svg"), "w", encoding="utf-8") as fh:
        fh.write(render.to_svg(b, mirror=True))
    with open(os.path.join(folder, name + "-copper-side-1to1.pdf"), "wb") as fh:
        fh.write(render.to_pdf(b, mirror=True))
    with open(os.path.join(folder, name + "-bom.csv"), "w", encoding="utf-8") as fh:
        fh.write(render.to_bom_csv(b))
    for mode in ("isolation", "negative"):
        job = laser.generate(b, laser.LaserOptions(mode=mode), b.name)
        with open(os.path.join(folder, "%s-laser-%s.gcode" % (name, mode)), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(job.gcode)
        print("  laser %-9s %s" % (mode, job.summary()))
    if backplane:
        with open(os.path.join(folder, name + "-back-plane-1to1.svg"), "w", encoding="utf-8") as fh:
            fh.write(render.to_svg(b, layer="top"))
        with open(os.path.join(folder, name + "-back-plane-1to1.pdf"), "wb") as fh:
            fh.write(render.to_pdf(b, layer="top"))
        job = laser.generate(b, laser.LaserOptions(mode="negative"), b.name, layer="top")
        with open(os.path.join(folder, name + "-laser-back-plane.gcode"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(job.gcode)
        rows = plane.countersink_list(b)
        with open(os.path.join(folder, name + "-countersink.txt"), "w", encoding="utf-8") as fh:
            fh.write("Holes to countersink when the back is left solid (x, y, drill, what); ground leads and vias are "
                     "soldered to the plane instead.\n")
            for x, y, dr, what in rows:
                fh.write("%7.2f %7.2f %.2f %s\n" % (x, y, dr, what))
        print("  back plane: %d via(s), %d countersink hole(s)" % (len(b.vias), len(rows)))
    print("%s: %s | DRC: %s" % (name, res.summary(), summarize(issues)))


if __name__ == "__main__":
    build("555-led-flasher", demos.flasher_555)
    build("5v-regulator", demos.regulator_7805)
    build("555-power-oscillator", demos.power_oscillator, seed=4)
    build("logic-mix", demos.logic_dip14, seed=3)     # seed 2 leaves net G unrouted; see DESIGN_NOTES.md
    build("rf-oscillator-ground-fill", demos.rf_oscillator, place=False)
    build("manhattan-rf-amplifier", demos.manhattan_amp, place=False)
    build("smd-regulator-pro", demos.smd_regulator, place=False)
    build("xiao-logger-mirrored-oled", demos.xiao_logger, seed=1)

    def flasher_fill():
        # the 555 flasher with the ground fill AND the back-side plane: through-hole leads get clearance
        # rings (or a countersink), the fill is stitched to the plane
        b = demos.flasher_555()
        b.settings.island_mode = True
        b.touch()
        return b
    build("555-flasher-back-plane", flasher_fill, backplane=True)
    folder = os.path.join(OUT, "test-cards")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "speed-power-test.gcode"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(laser.speed_power_card().gcode)
    with open(os.path.join(folder, "trace-gap-test.gcode"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(laser.trace_ladder_card().gcode)
    print("test cards written")
