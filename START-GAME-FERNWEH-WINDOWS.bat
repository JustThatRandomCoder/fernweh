@echo off
rem One-click launcher for Fernweh on Windows — the twin of the macOS
rem START-GAME-FERNWEH-MAC.command file. Double-click it in File Explorer. The first
rem time, it builds a small private Python environment and installs everything
rem the game needs (this can take a minute — that's the "loading"); every time
rem after that it opens straight into the game. All the real work is done by
rem fernweh.py, which this script just finds a Python for and runs.
setlocal

rem Always work from the folder this file lives in, whatever the current
rem directory happens to be when it's double-clicked.
cd /d "%~dp0"

cls
echo ==================================================
echo                     F E R N W E H
echo         a quiet walk from spring to winter
echo ==================================================
echo.

rem Find a Python 3. The Windows launcher `py -3` is the most reliable when
rem present; fall back to `python` / `python3` on PATH otherwise.
set "PYTHON="
where py >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON (
  where python >nul 2>nul && set "PYTHON=python"
)
if not defined PYTHON (
  where python3 >nul 2>nul && set "PYTHON=python3"
)

rem No Python at all: explain plainly what to install and keep the window open.
if not defined PYTHON (
  echo Fernweh needs Python 3 to run, and it isn't installed yet.
  echo.
  echo   1. Open https://www.python.org/downloads/ in your browser
  echo   2. Download and install Python 3 ^(tick "Add Python to PATH" during setup^)
  echo   3. Double-click START-GAME-FERNWEH-WINDOWS again
  echo.
  pause
  exit /b 1
)

rem First run has no .venv yet, so say the wait is setup rather than a hang.
if not exist ".venv" (
  echo First time setup - installing everything the game needs.
  echo This can take a minute. Please leave this window open...
) else (
  echo Starting Fernweh...
)
echo.

rem Hand off to the real entry point, which creates/reuses the environment and
rem opens the game window; its own progress messages stream here.
%PYTHON% fernweh.py
if errorlevel 1 (
  echo.
  echo Fernweh closed unexpectedly.
  pause
)
