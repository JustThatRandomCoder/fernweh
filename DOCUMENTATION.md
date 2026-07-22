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

### Afflictions (`afflictions.py`)

Three afflictions exist: **Exhausted** (energy < 25), **Ill** (a probabilistic roll each
stage, weighted higher — 25% vs. a 5% baseline — when supplies are below 30), and
**Frostbitten** (winter-only, triggered by specific choices via their `affliction_chance`,
validated by content loading so it can't be attached to a non-winter stage).

Rather than hardcoding "if exhausted, do X visual thing" and "if ill, do Y visual thing",
every affliction's mechanical effect is expressed as a drain multiplier
(`energy_drain_multiplier`, `supplies_drain_multiplier`) and the visual/animation harshness
is driven by a single derived `hardship_level` (currently just the count of active
afflictions). This satisfies the design requirement that hardship be a *general* system, not
a set of per-affliction visual hacks — a new affliction only needs to plug into the
multiplier functions to affect drain, and hardship level picks it up automatically.

Exhausted does not clear itself once energy recovers — the design calls for it to take a
deliberate rest/recovery choice to cure (via a choice's `cures` list), so it persists across
stages until content removes it. This mirrors the real cost being asked of the player: you
can't outrun exhaustion by resting one one-off numbers tick, you have to choose to address
it.

### Choice resolution (`stages.apply_choice`)

`apply_choice(state, choice, rng)` is the single function that turns "player picked this
choice" into a fully resolved `GameState` update, in a fixed order: base per-season/per-
companion drain first (via `afflictions.base_stage_drain`), then the choice's own resource
effects, then memory/companion pickups, cures, and affliction rolls, then
`state.advance_stage()`. It exits early at any point `state.ended` becomes true, so a fatal
drain from the base stage cost stops the rest of the choice's effects from applying to an
already-ended journey. Accepting an optional `rng: random.Random` (defaulting to a fresh
instance) keeps affliction rolls testable — tests inject a fixed-value stand-in rather than
depending on real randomness.

## Rendering & Animation

*(to be filled in once the rendering scaffold, tween module, and particle system exist)*

## Data Format

Stages live in `content/stages.json` as a single `{"stages": [...]}` array, one entry per
stage index (0-based, contiguous, no gaps — enforced by `stages._validate_stage_sequence`).
Each stage declares its `season`, a `scene` dict (`description` + `weather`, used later by
the renderer to pick a palette/particle effect), a `situation` string, and 2–3 `choices`.

A choice's `effects` dict may only use the keys in `stages.VALID_EFFECT_KEYS` (`energy`,
`supplies`); `affliction_chance`, `cures`, and `unavailable_if` may only reference ids in
`stages.VALID_AFFLICTIONS`. `stages.load_stages()` validates all of this at load time and
raises `ContentError` with a specific message rather than letting bad content fail silently
or crash deep in game logic. This is deliberately stricter than "just parse the JSON" —
content is written by hand and the validation step catches typos in effect/affliction names
before they'd otherwise surface as a silent no-op during play.

`season` is declared per-stage in the JSON *and* cross-checked against the value computed
from the stage index (`stages.stage_season`) — this catches a copy-paste error where a
stage is filed under the wrong season heading.

Only 3 stages exist so far (milestone 4 — proving the schema); the full 20-stage script is
written in a later milestone.

## Testing

*(to be filled in once the test suite exists)*

## Tooling

- **black** and **ruff** are run before each commit for formatting and linting.
- **pytest** runs the test suite.

## Known Limitations

*(to be filled in as they're discovered)*
