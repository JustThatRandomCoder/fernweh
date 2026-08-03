@echo off
rem One-click launcher for Fernweh on Windows — the twin of the macOS
rem START-GAME-FERNWEH-MAC.command file. Double-click it in File Explorer. The first
rem time, it builds a small private Python environment and installs everything
rem the game needs (this can take a minute — that's the "loading"); every time
rem after that it opens straight into the game.
rem
rem Why this is shaped the way it is: on Windows, letting fernweh.py re-launch
rem itself inside the virtual environment (its os.execv step) spawns a NEW,
rem DETACHED process and lets the original exit — so this window would close
rem immediately while the real game ran orphaned in the background (and any
rem startup error would be invisible). To avoid that, this launcher builds the
rem environment itself when needed and then runs the game with the environment's
rem OWN Python directly. That interpreter is already "inside" the venv, so
rem fernweh.py skips the re-launch entirely, the game stays attached to this
rem window, and any error is shown instead of vanishing.
setlocal

rem Step into the game folder next to this launcher — the code (fernweh.py, its
rem environment) all lives in fernweh-game\, and only the startup files sit out
rem here at the top level. %~dp0 ends with a backslash, so this appends cleanly.
cd /d "%~dp0fernweh-game"

cls
echo ==================================================
echo                     F E R N W E H
echo         a quiet walk from spring to winter
echo ==================================================
echo.

rem Sanity check: make sure we actually landed in the game folder.
if not exist "fernweh.py" (
  echo Could not find the game files ^(fernweh-game\fernweh.py^).
  echo Keep this launcher in the same folder as the "fernweh-game" folder.
  echo.
  pause
  exit /b 1
)

rem The Python that lives inside the game's private environment. Once this
rem exists, running it directly is all that's needed.
set "VENV_PY=.venv\Scripts\python.exe"

rem Already set up? Skip straight to launching.
if exist "%VENV_PY%" goto :launch

rem ---- First-time setup: build the private environment ------------------------
echo First time setup - preparing the game. This can take a minute...
echo.

rem Find a system Python 3 to build the environment with. `py -3` (the Windows
rem Python launcher) is the most reliable when present; fall back to `python` /
rem `python3` on PATH. Note: each detection sets PYTHON but never uses it inside
rem the same parenthesised block, so plain %%-expansion is safe here.
set "PYTHON="
where py >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON (
  where python >nul 2>nul && set "PYTHON=python"
)
if not defined PYTHON (
  where python3 >nul 2>nul && set "PYTHON=python3"
)

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

rem Create the environment. (Dependencies are installed on the first real run
rem below, by fernweh.py, which shows its own progress bar.)
%PYTHON% -m venv .venv

if not exist "%VENV_PY%" (
  echo.
  echo Setting up the game environment didn't finish.
  echo Try these, then double-click START-GAME-FERNWEH-WINDOWS again:
  echo   - Install Python 3 from https://www.python.org/downloads/
  echo     ^(during setup, tick "Add Python to PATH"^)
  echo   - Move this whole folder somewhere you own, like Documents or Desktop,
  echo     in case the current location is write-protected.
  echo.
  pause
  exit /b 1
)

:launch
echo Starting Fernweh...
echo.

rem Run the game with the environment's own Python. Because this interpreter is
rem already inside .venv, fernweh.py installs any missing dependencies (showing
rem its progress bar) and then opens the game directly — no re-launch, so this
rem window stays with the running game instead of closing out from under it.
"%VENV_PY%" fernweh.py

rem If the game exited with an error, keep the window open so it can be read
rem rather than closing instantly.
if errorlevel 1 (
  echo.
  echo Fernweh closed unexpectedly.
  pause
)
