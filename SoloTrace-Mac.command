#!/usr/bin/env bash
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# SoloTrace 0.3.5-wip - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
# Double-click launcher for macOS. First time only: right-click > Open, then click Open.
cd "$(dirname "$0")" || exit 1

show_msg() {
  echo
  echo "=============================================================="
  echo "$1"
  echo "=============================================================="
  osascript -e "display dialog \"$(printf '%s' "$1" | sed 's/"/\\"/g' | tr '\n' ' ')\" with title \"SoloTrace\" buttons {\"OK\"} default button \"OK\" with icon stop" >/dev/null 2>&1
  read -r -p "Press Enter to close. " _
}

PY=""
for c in python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) and tkinter.TkVersion >= 8.6 else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done

if [ -z "$PY" ]; then
  show_msg "SoloTrace needs Python 3.8 or newer with Tk 8.6 or newer. The Python that comes with macOS has an old, buggy Tk.

Fix: install Python from https://www.python.org/downloads/macos/ (it includes a working Tk), then double-click this file again."
  exit 1
fi

"$PY" src/main.py "$@"
code=$?
if [ $code -ne 0 ]; then
  show_msg "SoloTrace stopped with an error (code $code). Run it from Terminal to read the message:  $PY src/main.py"
fi
exit $code
