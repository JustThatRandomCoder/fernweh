# Testing

Fernweh's game logic (resources, stage progression, afflictions, ending generation, content
validation) is decoupled from rendering and fully unit-tested with `pytest`, headlessly —
no display is required to run the suite.

## Setup (fresh clone)

```bash
git clone https://github.com/JustThatRandomCoder/fernweh.git fernweh
cd fernweh
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `requirements.txt` (pygame-ce, needed because `game.py` is
imported transitively by some tests) plus `pytest`, `black`, and `ruff`.

## Running the tests

```bash
pytest tests/ -v
```

or, equivalently:

```bash
bash tests/run_all_tests.sh
```

Both run the full suite. A clean run ends with something like:

```
======================== 90 passed in 0.10s =========================
```

## What's covered

- **`test_state.py`** — resource clamping, failure-state detection, companion capacity,
  season boundaries, stage advancement.
- **`test_stages.py`** — content loading and schema validation (valid effect/affliction
  keys, choice count, contiguous stage ids, frostbitten confined to winter), plus
  `apply_choice` stage-progression and fail-state behavior.
- **`test_afflictions.py`** — Exhausted/Ill trigger conditions, drain-multiplier stacking,
  base per-season/per-companion drain math.
- **`test_ending.py`** — procedural ending prose across representative end states (rested
  with companions, exhausted alone, mid-journey failure), keepsakes assembly.
- **`test_tween.py`** — easing function boundaries/monotonicity, `Tween` interpolation,
  completion callbacks, reset behavior.
- **`test_ui.py`** — typewriter reveal timing and hardship-linked speed, intro dialog paging.
- **`test_bootstrap.py`** — the decision logic behind `fernweh.py`'s self-installing
  bootstrap (requirements hashing, marker staleness, platform-dependent venv python path,
  venv-detection via `sys.prefix`), loaded directly from the script by path so it can't
  collide with the `fernweh` package. This does *not* cover the actual venv creation, pip
  install, or re-exec — see "Verifying the bootstrap end-to-end" below for that.

## Verifying the bootstrap end-to-end

`fernweh.py`'s first-run setup (creating `.venv`, installing dependencies, re-launching
itself inside the venv) isn't covered by the automated suite — it spawns real subprocesses,
touches the network, and replaces the running process via `os.execv`, none of which are a
good fit for a fast headless test run. Verify it manually after touching `fernweh.py`:

1. From a completely fresh clone (or `rm -rf .venv` in an existing one):
   ```bash
   python3 fernweh.py
   ```
   Expect to see `Setting up Fernweh for the first time...` then `Installing
   dependencies...`, followed by the game window opening. Confirm `.venv/` now exists and
   contains `.requirements.sha256`.
2. Close the game and run `python3 fernweh.py` again. Expect it to skip straight to the
   game window with no setup messages, and to do so quickly (well under a second before the
   window appears).
3. Append a harmless line to `requirements.txt` (e.g. a comment) and run `python3
   fernweh.py` once more. Expect `Installing dependencies...` to reappear (the hash marker
   is now stale) without `Setting up Fernweh for the first time...` (the venv itself isn't
   recreated). Revert the change afterward.

## Linting and formatting

```bash
black src tests fernweh.py
ruff check src tests fernweh.py
```

Both are expected to run clean before a commit.

## Notes

- Tests resolve the `fernweh` package via `pythonpath = ["src"]` in `pyproject.toml`, so an
  editable install isn't required to run them — `pip install -r requirements-dev.txt` is
  enough.
- No test opens a real window; `pygame` is imported (for type hints and a few rendering-
  adjacent pure functions like the typewriter/dialog logic) but `pygame.display.set_mode` is
  never called from the test suite.
