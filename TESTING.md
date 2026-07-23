# Testing

Fernweh's game logic (resources, stage progression, afflictions, ending generation, content
validation) is decoupled from rendering and fully unit-tested with `pytest`, headlessly —
no display is required to run the suite.

## Setup (fresh clone)

```bash
git clone https://github.com/JustThatRandomCoder/seasons-game.git fernweh
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
======================== 83 passed in 0.10s =========================
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
