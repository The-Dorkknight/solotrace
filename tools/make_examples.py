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
from solotrace.router import AutoRouter                  # noqa: E402

OUT = os.path.join(ROOT, "examples")


def build(name, fn, place=True, seed=2):
    b = fn()
    if place:
        auto_place(b, time_limit=20, seed=seed)
    res = AutoRouter(b).route_all()
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
    print("%s: %s | DRC: %s" % (name, res.summary(), summarize(issues)))


if __name__ == "__main__":
    build("555-led-flasher", demos.flasher_555)
    build("5v-regulator", demos.regulator_7805)
    build("555-power-oscillator", demos.power_oscillator, seed=4)
    build("logic-mix", demos.logic_dip14, seed=3)     # seed 2 leaves net G unrouted; see DESIGN_NOTES.md
    build("rf-oscillator-ground-fill", demos.rf_oscillator, place=False)
    build("manhattan-rf-amplifier", demos.manhattan_amp, place=False)
    folder = os.path.join(OUT, "test-cards")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "speed-power-test.gcode"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(laser.speed_power_card().gcode)
    with open(os.path.join(folder, "trace-gap-test.gcode"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(laser.trace_ladder_card().gcode)
    print("test cards written")
