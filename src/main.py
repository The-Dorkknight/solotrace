# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# SoloTrace - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
"""Start SoloTrace: python3 src/main.py   (use --version to see the version)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solotrace.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
