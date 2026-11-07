@echo off
rem Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
rem Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
rem SoloTrace 0.8.0-wip - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
rem Double-click launcher for Windows. Needs Python 3.8 or newer and nothing else: SoloTrace opens
rem in your web browser (a small server on 127.0.0.1 only). Old desktop window: py src\main.py desktop
cd /d "%~dp0"
set "PYCMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if not defined PYCMD (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
  echo.
  echo ==============================================================
  echo  SoloTrace needs Python 3.8 or newer.
  echo.
  echo  Fix: install Python from https://www.python.org/downloads/windows/
  echo  On the first installer screen tick "Add python.exe to PATH".
  echo  Then double-click this file again.
  echo.
  echo  Or use SoloTrace in your browser with nothing installed:
  echo  https://the-dorkknight.github.io/solotrace/app/
  echo ==============================================================
  echo.
  pause
  exit /b 1
)
echo Starting SoloTrace: it opens in your web browser. Keep this window open while you work;
echo File ^> Quit in the page stops it.
%PYCMD% src\main.py %*
if errorlevel 1 (
  echo.
  echo SoloTrace stopped with an error. The message above says why.
  pause
)
