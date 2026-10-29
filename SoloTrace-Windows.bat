@echo off
rem Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
rem Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
rem SoloTrace 0.3.4-wip - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
rem Double-click launcher for Windows.
cd /d "%~dp0"
set "PYCMD="
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if not defined PYCMD (
  python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
  echo.
  echo ==============================================================
  echo  SoloTrace needs Python 3.8 or newer WITH tkinter.
  echo.
  echo  Fix: install Python from https://www.python.org/downloads/windows/
  echo  On the first installer screen tick "Add python.exe to PATH" and
  echo  keep "tcl/tk and IDLE" ticked. Then double-click this file again.
  echo ==============================================================
  echo.
  pause
  exit /b 1
)
%PYCMD% src\main.py %*
if errorlevel 1 (
  echo.
  echo SoloTrace stopped with an error. The message above says why.
  pause
)
