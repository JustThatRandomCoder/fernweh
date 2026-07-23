"""Entry point: `python3 fernweh.py` opens the Fernweh window and starts the game."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fernweh.game import run  # noqa: E402

if __name__ == "__main__":
    run()
