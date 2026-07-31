#!/bin/bash
#
# One-click launcher for Fernweh on macOS — for people who don't want to touch a
# terminal. Its Windows twin is START-GAME-FERNWEH-WINDOWS.bat.
#
# Double-click this file in Finder. The very first time, it quietly builds a
# little private Python environment and installs everything the game needs
# (this can take a minute — that's the "loading"); every time after that it
# just opens straight into the game. All the real work is done by fernweh.py,
# which this script simply finds a Python for and runs from the game's folder.

# Step into the game folder next to this launcher, no matter where it's launched
# from — the code (fernweh.py, its environment) all lives in fernweh-game/, and
# only the startup files sit out here at the top level.
cd "$(dirname "${BASH_SOURCE[0]}")/fernweh-game" || exit 1

# A clean screen and a friendly banner, so a non-technical player sees
# something calm and intentional rather than a bare terminal prompt.
clear
echo "=================================================="
echo "                    F E R N W E H"
echo "        a quiet walk from spring to winter"
echo "=================================================="
echo ""

# Find a Python 3 interpreter. `python3` on PATH is the normal case; the
# explicit fallbacks cover common install locations (Homebrew on Apple
# Silicon and Intel, and the system framework build) for a machine whose
# PATH doesn't include them in a double-click launch context.
PYTHON=""
for candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

# No Python at all: explain plainly what to install, and keep the window open
# so the message can actually be read instead of vanishing.
if [ -z "$PYTHON" ]; then
  echo "Fernweh needs Python 3 to run, and it isn't installed yet."
  echo ""
  echo "  1. Open https://www.python.org/downloads/ in your browser"
  echo "  2. Download and install Python 3 (the big yellow button)"
  echo "  3. Double-click START-GAME-FERNWEH-MAC again"
  echo ""
  read -n 1 -s -r -p "Press any key to close this window."
  echo ""
  exit 1
fi

# On a first run there's no .venv yet, so warn that the wait is expected
# (installing) rather than a hang. On later runs it starts immediately.
if [ ! -d ".venv" ]; then
  echo "First time setup — installing everything the game needs."
  echo "This can take a minute. Please leave this window open..."
else
  echo "Starting Fernweh..."
fi
echo ""

# Hand off to the real entry point, which creates/reuses the environment and
# opens the game window. Its own progress messages ("Setting up...",
# "Installing dependencies...") stream here as the loading indication.
"$PYTHON" fernweh.py
STATUS=$?

# If the game exited with an error, don't let the window snap shut before the
# player can see why — pause so the message stays readable.
if [ $STATUS -ne 0 ]; then
  echo ""
  echo "Fernweh closed unexpectedly (error code $STATUS)."
  read -n 1 -s -r -p "Press any key to close this window."
  echo ""
fi
