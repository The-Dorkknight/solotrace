# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""SoloTrace: a simple single-sided PCB designer with a jumper-aware autorouter and laser output."""

APP_NAME = "SoloTrace"
__version__ = "0.8.0-wip"
__build_date__ = "2026-11-06 22:30"


def title() -> str:
    return "%s v%s (Built %s)" % (APP_NAME, __version__, __build_date__)
