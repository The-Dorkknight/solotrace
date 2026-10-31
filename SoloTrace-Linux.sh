#!/usr/bin/env bash
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# SoloTrace 0.3.5-wip - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
# Double-click launcher for Linux. If your file manager asks, choose "Run" (not "Display").
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
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done

if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then
    show_msg "Python 3 was found, but its tkinter window toolkit is missing (or Python is older than 3.8).

Install it, then double-click this file again:
  Linux Mint / Ubuntu / Debian:  sudo apt install python3-tk
  Fedora:                        sudo dnf install python3-tkinter
  Arch:                          sudo pacman -S tk"
  else
    show_msg "Python 3 was not found.

Install it, then double-click this file again:
  Linux Mint / Ubuntu / Debian:  sudo apt install python3 python3-tk
  Fedora:                        sudo dnf install python3 python3-tkinter
  Arch:                          sudo pacman -S python tk"
  fi
  exit 1
fi

"$PY" src/main.py "$@"
code=$?
if [ $code -ne 0 ]; then
  show_msg "SoloTrace stopped with an error (code $code). Run it from a terminal to read the message:
  $PY src/main.py"
fi
exit $code
