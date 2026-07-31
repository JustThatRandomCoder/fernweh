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
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
INSTALL_MARKER = VENV_DIR / ".requirements.sha256"
VENV_MISSING_HINTS = ("ensurepip", "No module named venv", "python3-venv")

# Width of the first-run progress bar, in characters, and the ASCII glyphs it's
# drawn from. ASCII (rather than Unicode block characters) so it renders
# identically in a Windows cmd window and a macOS Terminal without codepage
# surprises. The eased fill approaches — but never quite reaches — full until
# the underlying step actually finishes, so the bar reads as honest progress
# even though pip/venv don't report a real percentage.
_BAR_WIDTH = 30
_BAR_FILLED = "#"
_BAR_EMPTY = "-"
# Seconds for the eased fill to cover ~half the remaining distance to 95% — a
# small value makes the bar move briskly at first and then ease off, which is
# what a setup step that "could take a minute" tends to feel like.
_BAR_HALFLIFE = 2.5


def _draw_progress(label: str, fraction: float, *, done: bool = False) -> None:
    """Redraw the single-line progress bar in place for `label` at `fraction` [0, 1]."""
    fraction = max(0.0, min(1.0, fraction))
    filled = round(_BAR_WIDTH * fraction)
    bar = _BAR_FILLED * filled + _BAR_EMPTY * (_BAR_WIDTH - filled)
    percent = round(fraction * 100)
    # `\r` returns to the start of the line so each frame overwrites the last;
    # only the finished frame ends the line so the bar stays put afterward.
    ending = "  done\n" if done else ""
    sys.stdout.write(f"\r  {label}  [{bar}] {percent:3d}%{ending}")
    sys.stdout.flush()


def _run_with_progress(cmd: list[str], label: str) -> tuple[int, str, str]:
    """Run `cmd`, animating a progress bar while it works; return (returncode, stdout, stderr).

    The subprocess output is drained on a background thread (via `communicate`,
    so a chatty step can never deadlock on a full pipe buffer), while the main
    thread animates the bar until that thread finishes. When stdout isn't a
    real terminal (e.g. output is piped to a file), the animation is skipped in
    favor of a single plain line, so logs don't fill with carriage returns.
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    captured: dict[str, str] = {}

    def _drain() -> None:
        captured["out"], captured["err"] = process.communicate()

    worker = threading.Thread(target=_drain)
    worker.start()

    if sys.stdout.isatty():
        start = time.monotonic()
        while worker.is_alive():
            elapsed = time.monotonic() - start
            # Ease toward 0.95 and hold there — the jump to 100% only happens
            # once the step has genuinely completed, below.
            fraction = 0.95 * (1 - 0.5 ** (elapsed / _BAR_HALFLIFE))
            _draw_progress(label, fraction)
            time.sleep(0.1)
        _draw_progress(label, 1.0, done=True)
    else:
        print(f"  {label}...", flush=True)

    worker.join()
    return process.returncode, captured.get("out", ""), captured.get("err", "")


def _venv_python() -> Path:
    """Path to the venv's Python executable, platform-dependent."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _fail(message: str) -> None:
    print(f"\nFernweh couldn't finish setting up.\n\n{message}\n", file=sys.stderr, flush=True)
    sys.exit(1)


def _create_venv() -> None:
    print("\nSetting up Fernweh for the first time — this only happens once.\n", flush=True)
    try:
        returncode, _stdout, stderr = _run_with_progress(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            "Preparing a private space for the game",
        )
    except FileNotFoundError:
        _fail(
            "Could not find a Python interpreter to create the virtual environment.\n"
            "Install Python 3.11+ from https://www.python.org/downloads/, then run "
            "`python3 fernweh.py` again."
        )
        return

    if returncode == 0:
        return

    stderr = stderr.strip()
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
    returncode, _stdout, stderr = _run_with_progress(
        [str(_venv_python()), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_FILE)],
        "Installing everything the game needs",
    )
    if returncode != 0:
        _fail(
            f"Installing dependencies failed:\n\n{stderr.strip()}\n\n"
            "Try running:\n"
            f"  source {VENV_DIR}/bin/activate && pip install -r requirements.txt\n"
            "to see the full error and fix it manually."
        )
    INSTALL_MARKER.write_text(_requirements_hash())
    # A parting line so the last thing before the window opens is a clear
    # "all set", not a bare progress bar frozen at 100%.
    if sys.stdout.isatty():
        print("\nReady — opening Fernweh...\n", flush=True)


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
