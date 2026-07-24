"""Entry point: `python3 fernweh.py` opens the Fernweh window and starts the game.

On first run this creates a local virtual environment and installs
dependencies automatically, then re-launches itself inside it — there is
nothing to set up by hand. See DOCUMENTATION.md for how this works.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
INSTALL_MARKER = VENV_DIR / ".requirements.sha256"
VENV_MISSING_HINTS = ("ensurepip", "No module named venv", "python3-venv")


def _venv_python() -> Path:
    """Path to the venv's Python executable, platform-dependent."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _fail(message: str) -> None:
    print(f"\nFernweh couldn't finish setting up.\n\n{message}\n", file=sys.stderr, flush=True)
    sys.exit(1)


def _create_venv() -> None:
    print("Setting up Fernweh for the first time...", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        _fail(
            "Could not find a Python interpreter to create the virtual environment.\n"
            "Install Python 3.11+ from https://www.python.org/downloads/, then run "
            "`python3 fernweh.py` again."
        )
        return

    if result.returncode == 0:
        return

    stderr = result.stderr.strip()
    if any(hint in stderr for hint in VENV_MISSING_HINTS):
        _fail(
            "It looks like the `venv` module is missing.\n"
            "On Debian/Ubuntu, run: sudo apt install python3-venv\n"
            "Then run `python3 fernweh.py` again."
        )
    elif "Permission denied" in stderr:
        _fail(
            f"Permission denied creating {VENV_DIR}.\n"
            "Check that you have write access to this folder, or clone the repo "
            "somewhere you own, then run `python3 fernweh.py` again."
        )
    else:
        _fail(
            f"Creating the virtual environment failed:\n\n{stderr}\n\n"
            f"Try running: {sys.executable} -m venv .venv\n"
            "to see the full error and fix it manually."
        )


def _requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS_FILE.read_bytes()).hexdigest()


def _dependencies_up_to_date() -> bool:
    if not INSTALL_MARKER.exists():
        return False
    return INSTALL_MARKER.read_text().strip() == _requirements_hash()


def _install_dependencies() -> None:
    print("Installing dependencies...", flush=True)
    result = subprocess.run(
        [str(_venv_python()), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_FILE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(
            f"Installing dependencies failed:\n\n{result.stderr.strip()}\n\n"
            "Try running:\n"
            f"  source {VENV_DIR}/bin/activate && pip install -r requirements.txt\n"
            "to see the full error and fix it manually."
        )
    INSTALL_MARKER.write_text(_requirements_hash())


def _running_inside_venv() -> bool:
    # `.venv/bin/python` is often a symlink to the base interpreter, so
    # comparing `sys.executable` against it after resolving symlinks would
    # incorrectly report "already inside the venv" when it's really just the
    # same underlying binary. `sys.prefix` reflects the venv actually being
    # active (set from `.venv/pyvenv.cfg`), regardless of that symlink.
    return Path(sys.prefix).resolve() == VENV_DIR.resolve()


def _bootstrap() -> None:
    """Ensure a venv exists with current dependencies, then re-exec inside it."""
    # Three independent checks, each a no-op if already satisfied — so a
    # second run of this script does nothing but the final re-exec check.
    if not VENV_DIR.exists():
        _create_venv()

    if not _dependencies_up_to_date():
        _install_dependencies()

    # If we're not actually running inside the venv yet (first run, or the
    # venv was just created), replace this process with the venv's own
    # Python running this same script — `pygame` and friends are only
    # importable from inside the venv.
    if not _running_inside_venv():
        venv_python = _venv_python()
        script = str(Path(__file__).resolve())
        os.execv(str(venv_python), [str(venv_python), script, *sys.argv[1:]])


def main() -> None:
    _bootstrap()
    # Only reachable once we're guaranteed to be running inside the venv, so
    # `pygame` (installed there) is now safely importable via the `fernweh`
    # package under `src/`.
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from fernweh.game import run

    run()


if __name__ == "__main__":
    main()
