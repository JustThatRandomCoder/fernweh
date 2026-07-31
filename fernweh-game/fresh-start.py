"""fresh-start.py: reset Fernweh to a just-cloned state, to test first-run setup.

Removes the local virtual environment (the installed dependencies), every saved
game, and the generated caches — that is, everything a fresh `git clone` would
*not* contain — so the next launch reruns the whole first-time setup exactly as
a brand-new player would experience it. It only ever touches gitignored,
regenerable paths; tracked source and narrative content are never removed.

Usage:
    python3 fresh-start.py            # lists what it will remove, then asks
    python3 fresh-start.py --yes      # remove without the confirmation prompt
    python3 fresh-start.py --dry-run  # only show what would be removed
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Directories at the repo root that hold installed dependencies, saved games,
# or tool caches. None are tracked by git, and all are recreated on demand —
# `.venv` by the first-run bootstrap, `saves` by playing, the caches by their
# tools — so removing them only forces a clean rebuild.
ROOT_DIRS = (".venv", "saves", ".pytest_cache", ".ruff_cache")


def _collect_targets() -> list[Path]:
    """Gather every path fresh-start should remove, de-duplicated, in a stable order."""
    targets: list[Path] = []

    def add(path: Path) -> None:
        if not path.exists() or path in targets:
            return
        # Don't list a cache that already sits inside a directory we're about to
        # delete wholesale (e.g. the hundreds of `__pycache__` dirs under
        # `.venv`) — removing the parent takes them with it, and listing them
        # all just buries the meaningful output.
        if any(parent in targets for parent in path.parents):
            return
        targets.append(path)

    for name in ROOT_DIRS:
        add(REPO_ROOT / name)
    # Bytecode caches and build metadata can appear anywhere under the tree
    # (notably `src/fernweh/__pycache__` and `src/*.egg-info`), so sweep for
    # them recursively rather than only at the root — but `add` skips any that
    # fall inside a directory already queued for removal above.
    for cache in sorted(REPO_ROOT.rglob("__pycache__")):
        add(cache)
    for egg_info in sorted(REPO_ROOT.rglob("*.egg-info")):
        add(egg_info)
    return targets


def _remove(path: Path) -> None:
    """Delete one target, refusing anything that resolves outside the repo."""
    resolved = path.resolve()
    # A defensive guard: even though every path came from inside REPO_ROOT, a
    # stray symlink could point elsewhere — never delete outside the game folder.
    if resolved != REPO_ROOT and REPO_ROOT not in resolved.parents:
        print(f"  skipped (outside repo): {path}")
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def main() -> None:
    # Refuse to run anywhere but the game's own folder, so this can never be
    # mistaken for a general-purpose "delete these dirs" tool in a wrong cwd.
    if not (REPO_ROOT / "fernweh.py").exists():
        print("fresh-start.py must sit next to fernweh.py in the Fernweh folder.")
        sys.exit(1)

    args = sys.argv[1:]
    dry_run = any(a in ("-n", "--dry-run") for a in args)
    assume_yes = any(a in ("-y", "--yes", "--force") for a in args)

    targets = _collect_targets()
    if not targets:
        print("Already fresh — nothing to remove. The next run will set up from scratch.")
        return

    label = "Would remove" if dry_run else "This will remove"
    print(f"{label} (all regenerated automatically on the next run):")
    for target in targets:
        print(f"  - {target.relative_to(REPO_ROOT)}")

    if dry_run:
        print("\nDry run — nothing was removed.")
        return

    if not assume_yes:
        answer = input("\nRemove these and reset to a fresh install? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Cancelled — nothing was removed.")
            return

    for target in targets:
        _remove(target)

    print("\nDone — Fernweh is reset to a fresh, just-cloned state.")
    print(
        "Launch it again to test the first-run setup: double-click START-GAME-FERNWEH, "
        "or run `python3 fernweh.py`."
    )


if __name__ == "__main__":
    main()
