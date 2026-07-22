# Documentation

A running technical log of Fernweh's architecture and the decisions behind it. This is
written for a technical reader who wants to understand the system without reading every
line of code — it grows alongside the build, one entry per non-trivial decision.

## Architecture

**Logic/rendering split.** `src/fernweh/state.py` (and the other pure modules that follow
it — `stages.py`, `afflictions.py`, `ending.py`) import nothing from `pygame`. This is
enforced by convention, not tooling, but it's the single most important structural rule in
the codebase: it's what makes the rules engine testable without a display and keeps content
changes from ever touching rendering code.

**Import path.** The project uses a `src/` layout with `pyproject.toml` declaring the
`fernweh` package. An editable install (`pip install -e .`) is the documented setup path,
but pytest is additionally configured with `pythonpath = ["src"]` in `pyproject.toml` so the
test suite resolves the package reliably across environments regardless of editable-install
quirks. `main.py` inserts `src/` onto `sys.path` directly for the same reason — this keeps
"one command to launch" working even if the editable install step is skipped.

## Game Systems

### State (`state.py`)

`GameState` is a single mutable dataclass holding: `energy` and `supplies` (0–100, clamped
on every update), a `companions` list (capped at 4, matching the design spec), a `memories`
list of flavor strings, and an `afflictions` set of active affliction ids (the trigger rules
for *which* afflictions activate live in `afflictions.py`, not here — `state.py` only stores
the resulting set).

`season` is derived from `stage_index // 5` rather than stored redundantly, so there's no
way for season and stage index to drift out of sync. Season boundaries land at stage indices
5, 10, and 15 (i.e. stages 6, 11, 16 in 1-based terms), matching the four 5-stage seasons.

Failure is detected automatically inside `apply_energy_delta` / `apply_supplies_delta`
whenever a resource clamps to 0 — there's no separate "check failure" step the caller has to
remember to run. Once `ended` is `True`, further resource deltas and `advance_stage()` calls
are no-ops, so a stray update after the journey ends can't resurrect it or skip stages.

## Rendering & Animation

*(to be filled in once the rendering scaffold, tween module, and particle system exist)*

## Data Format

*(to be filled in once `content/stages.json` and its loader exist)*

## Testing

*(to be filled in once the test suite exists)*

## Tooling

- **black** and **ruff** are run before each commit for formatting and linting.
- **pytest** runs the test suite.

## Known Limitations

*(to be filled in as they're discovered)*
