#!/usr/bin/env bash
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# SoloTrace 0.8.0-wip - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
# Double-click launcher for macOS. First time only: right-click > Open, then click Open.
# Needs Python 3.8 or newer and nothing else: SoloTrace opens in your web browser (a small server
# on 127.0.0.1 only). The old tkinter desktop window: python3 src/main.py desktop
cd "$(dirname "$0")" || exit 1

show_msg() {
  echo
  echo "=============================================================="
  echo "$1"
  echo "=============================================================="
  osascript -e "display dialog \"$(printf '%s' "$1" | sed 's/"/\\"/g' | tr '\n' ' ')\" with title \"SoloTrace\" buttons {\"OK\"} default button \"OK\" with icon stop" >/dev/null 2>&1
  read -r -p "Press Enter to close. " _
}

CANDIDATES="python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3"
PY=""
for c in $CANDIDATES; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done

if [ -z "$PY" ]; then
  show_msg "SoloTrace needs Python 3.8 or newer.

Fix: install Python from https://www.python.org/downloads/macos/ and double-click this file again. Or use SoloTrace in your browser with nothing installed: https://the-dorkknight.github.io/solotrace/app/"
  exit 1
fi
echo "Starting SoloTrace: it opens in your web browser. Keep this window open while you work; File > Quit in the page stops it."

"$PY" src/main.py "$@"
code=$?
if [ $code -ne 0 ]; then
  show_msg "SoloTrace stopped with an error (code $code). Run it from Terminal to read the message:  $PY src/main.py"
fi
exit $code
