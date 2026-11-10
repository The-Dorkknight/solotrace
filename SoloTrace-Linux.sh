#!/usr/bin/env bash
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# SoloTrace 0.10.1-wip - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
# Double-click launcher for Linux. If your file manager asks, choose "Run" (not "Display").
# Needs Python 3.8 or newer and nothing else: SoloTrace opens in your web browser (a small server
# on 127.0.0.1 only). The old tkinter desktop window: python3 src/main.py desktop
cd "$(dirname "$0")" || exit 1

show_msg() {
  echo
  echo "=============================================================="
  echo "$1"
  echo "=============================================================="
  if command -v zenity >/dev/null 2>&1; then zenity --error --title "SoloTrace" --text "$1" 2>/dev/null
  elif command -v kdialog >/dev/null 2>&1; then kdialog --error "$1" 2>/dev/null
  elif command -v xmessage >/dev/null 2>&1; then xmessage -center "$1" 2>/dev/null
  fi
  if [ -t 0 ]; then read -r -p "Press Enter to close. " _; fi
}

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done

if [ -z "$PY" ]; then
  show_msg "Python 3.8 or newer was not found.

Install it, then double-click this file again:
  Linux Mint / Ubuntu / Debian:  sudo apt install python3
  Fedora:                        sudo dnf install python3
  Arch:                          sudo pacman -S python

Or use SoloTrace in your browser with nothing installed:
  https://the-dorkknight.github.io/solotrace/app/"
  exit 1
fi

echo "Starting SoloTrace: it opens in your web browser. Keep this window open while you work; File > Quit in the page stops it."
"$PY" src/main.py "$@"
code=$?
if [ $code -ne 0 ]; then
  show_msg "SoloTrace stopped with an error (code $code). Run it from a terminal to read the message:
  $PY src/main.py"
fi
exit $code
