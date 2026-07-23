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
quirks. `fernweh.py` inserts `src/` onto `sys.path` directly for the same reason — this keeps
"one command to launch" working even if the editable install step is skipped.

**Self-installing bootstrap.** `fernweh.py` is both the entry point and its own installer:
running `python3 fernweh.py` from a completely fresh clone, with no `.venv/` and no
dependencies installed anywhere, is enough. Before importing anything that needs `pygame`,
`main()` calls `_bootstrap()`, which:

1. Creates `.venv/` via `python3 -m venv .venv` if it doesn't already exist.
2. Installs `requirements.txt` into that venv if dependencies are missing or stale.
3. Re-launches the script inside the venv's interpreter via `os.execv`, if it isn't already
   running there.

*Staleness check.* Rather than trying to detect "are dependencies installed" by attempting
an import (which would require the check itself to run inside the venv, creating a
chicken-and-egg problem before the venv is even confirmed ready), `_install_dependencies`
writes a marker file (`.venv/.requirements.sha256`) containing a SHA-256 hash of
`requirements.txt` after a successful install. `_dependencies_up_to_date` just compares the
marker against a freshly computed hash — cheap, doesn't need the venv's Python to run, and
naturally invalidates itself the moment `requirements.txt` changes, without needing to parse
or diff the file's contents.

*venv detection.* The re-exec check originally compared `Path(sys.executable).resolve()`
against the venv python's resolved path — and was wrong: `.venv/bin/python` is frequently
just a symlink to the base interpreter, so `.resolve()` on both sides can land on the exact
same real file even when the venv was never activated, silently skipping the re-exec and
leaving the process running with the *system* interpreter's `sys.path` (which doesn't have
the just-installed `pygame-ce`, producing a confusing `ModuleNotFoundError` deep in
`game.py` instead of at the bootstrap step where it'd be obvious). The fix
(`_running_inside_venv`) compares `sys.prefix` — which Python sets from `.venv/pyvenv.cfg`
whenever the venv is genuinely active — against `VENV_DIR`, which reflects reality
regardless of whether the executable used to get there was a symlink. This is covered by
`tests/test_bootstrap.py::test_running_inside_venv_uses_sys_prefix_not_executable_path` as a
regression test.

*Output.* Setup messages (`Setting up Fernweh for the first time...`,
`Installing dependencies...`) are printed with `flush=True`. Without that, they can be lost
entirely: `os.execv` replaces the process image immediately, without flushing Python's
buffered stdout first, so an unflushed message written just before the re-exec simply never
reaches the terminal. `subprocess.run(..., capture_output=True)` is used for both the venv
creation and the pip install themselves, so a successful run stays quiet (no pip progress
spam) and a failed one has the real stderr available to show.

*Failure paths.* Every failure `_bootstrap()` can hit calls `_fail()`, which prints a short
message and exits — never a raw traceback for something anticipated:
- `python3 -m venv .venv` fails because the interpreter can't be found at all → points at
  https://www.python.org/downloads/.
- It fails with `ensurepip`/`No module named venv`/`python3-venv` in stderr (the common
  Debian/Ubuntu case where the `venv` module is a separate package) → tells the user to run
  `sudo apt install python3-venv`.
- It fails with "Permission denied" (no write access to the clone location) → tells the user
  to check folder permissions or clone somewhere they own.
- Any other venv-creation failure → shows the real stderr, then suggests re-running
  `python3 -m venv .venv` manually to see the full error.
- `pip install -r requirements.txt` fails inside the venv → shows the real pip stderr, then
  suggests `source .venv/bin/activate && pip install -r requirements.txt` to reproduce and
  fix it manually.

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

### Ending generator (`ending.py`)

`generate_ending(state)` composes 2–4 sentences from four independent axes — energy tier
(rested/tired/exhausted, thresholds at 70/35), companion roster, active afflictions, and
memory count — plus, for a failed run, a leading "the path goes on without you" sentence
naming the season it ended in. Each axis is a small pure function
(`_companion_phrase`, `_affliction_phrase`, `_memory_phrase`) returning a phrase or `None`,
and `generate_ending` just joins whichever ones apply. This keeps the combinatorial space
(a handful of variables × a few states each) generated rather than enumerated — there's no
lookup table of hardcoded endings to keep in sync as new afflictions or companions appear.

The "keepsakes" list is simply memories followed by companion names — deliberately not
scored or ranked, since memories carry no gameplay weight, only atmosphere.

## Rendering & Animation

**Scenes (`scenes.py`).** Every season maps to a `Palette` (sky top/bottom, ground, text
color). `draw_scene` renders a vertical sky gradient over a ground band using only
`pygame.draw` primitives — there are no image assets anywhere in this project. A single
`desaturation` parameter (0–1) pulls every color toward grey; `game.py` derives this from
`afflictions.hardship_level` divided by a cap, so visual harshness scales with active
afflictions generically rather than through per-affliction rendering branches.

**Particles (`particles.py`).** One `ParticleSystem` class parameterized by a
`ParticleKind` (color, size range, fall speed range, horizontal drift range, count) covers
all three weather effects (`drizzle`, `snow`, `falling_leaves`). Adding a new weather effect
is adding one `ParticleKind` entry to `WEATHER_KINDS`, not a new class. Particles that fall
past the bottom (or drift past the sides) are respawned at the top rather than removed and
recreated, so the system runs at a constant particle count indefinitely. `game.py` rebuilds
the `ParticleSystem` only when the stage's weather changes (tracked via `_synced_stage_index`),
not every frame.

**Text (`ui.py`).** `wrap_text`/`draw_wrapped_text` do simple greedy word-wrapping against a
`pygame.font.Font`'s measured width — this is the rendering primitive later milestones build
the typewriter reveal on top of, rather than a placeholder to be thrown away.

**Tweening (`tween.py`).** A small hand-rolled easing module (`linear` through
`ease_in_out_cubic`) plus a `Tween` class that advances a float value over a duration and
fires an `on_complete` callback once. No pygame import — purely math, which is why it's
unit-tested directly rather than through rendered output. This is what scene crossfades and
UI hover/press animation are built on, instead of pulling in an external animation library.

**Game loop (`game.py`).** `Game` owns the pygame window, clock, loaded stage content, and
the current `GameState`. The loop separates `_update(dt)` (particles, transition tween,
typewriter, button hover) from `_draw()` (season background, particles, text, buttons,
transition overlay, dialog) — a clear seam between simulation and rendering.

**Choice UI.** `ui.ChoiceButton` drives its own hover/press scale via an elapsed-time value
eased with `ease_out_quad` (see Tweening above) rather than a discrete `Tween`, because hover
is a continuous state the mouse can enter or leave at any moment — a one-shot tween doesn't
fit that shape. Buttons are rebuilt from the current stage's choices every time the stage
changes (`_build_buttons`), with availability computed from `stages.choice_is_available`
against the state's active afflictions, so a choice greyed out by illness updates
automatically the moment illness is cured.

**Stage sync (`_sync_stage`).** One method is the single source of truth for "the displayed
stage changed": it snapshots the previous frame for the crossfade, rebuilds the particle
system, resets the typewriter to the new situation text, and rebuilds the choice buttons —
all keyed off comparing `state.stage_index` to a `_synced_stage_index` cache, so it runs
exactly once per stage change regardless of how many events triggered it.

**Ending screen.** Reaching `state.ended` (success or failure) is a separate sync path
(`_sync_ending`), since `stage_index` doesn't necessarily change when the journey ends —
a mid-stage failure ends the game without advancing. It reuses the typewriter for the ending
prose and repurposes the button list for a single "Begin a new journey" button, so the
success and failure paths share one rendering path instead of two screens to keep in sync.
Restarting simply replaces `self.state` with a fresh `GameState()` and re-runs `_sync_stage`.

**Intro/help dialog.** `ui.IntroDialog` is a small paged click-through shown at startup
(`Game.dialog`) and re-openable at any time during play via the `H` key — the same class and
page content both times, rather than a separate "help screen" that could drift out of sync
with the intro. Whether it's been seen is just whether `self.dialog` is `None`, a runtime
flag that resets on every process start (never persisted), matching the "skippable on
replay, not saved" requirement.

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

All 20 stages (5 per season) are now written. Four companions are recruitable across the
journey — Mira (stage 1), Sable (stage 4), Talia (stage 6), Emet (stage 11), Wren (stage
18) — five opportunities for four slots, so a player who wants a full company has to pass
on one. Frostbitten risk is confined to the winter stages (15-19) and content validation
enforces that at load time; Ill risk appears both as a direct per-choice consequence (e.g.
a risky shortcut) and as a per-stage roll (`afflictions.roll_ill`, called from
`stages.apply_choice` immediately after `advance_stage()`, so it fires "at the start of"
the newly-arrived stage as the design calls for).

## Testing

The full suite (`pytest tests/ -v`, see [`TESTING.md`](TESTING.md)) runs headlessly — no
test ever calls `pygame.display.set_mode`. This is possible because `state.py`, `stages.py`,
`afflictions.py`, and `ending.py` never import `pygame`, and the one piece of rendering-
adjacent logic that does get unit-tested (`ui.TypewriterText`, `ui.IntroDialog`) is pure
string/state manipulation with no drawing calls in its test path. Rendering itself (`game.py`,
`scenes.py`, `particles.py`, `ui.ChoiceButton.draw`) is exercised manually with pygame's
`dummy` SDL video/audio drivers during development (`SDL_VIDEODRIVER=dummy python3
fernweh.py`-style smoke runs) rather than through the pytest suite, since asserting on
rendered pixels would be brittle relative to what it protects.

## Tooling

- **black** and **ruff** are run before each commit for formatting and linting.
- **pytest** runs the test suite.

## Known Limitations

**Balance is heuristic-tuned, not mathematically derived.** The base drain rates in
`afflictions.py` were adjusted after simulating hundreds of full playthroughs under a few
scripted choice policies rather than computed from a formula — the first pass (drain rates
copied straight from the design brief's relative ordering) made the journey nearly
unwinnable even under careful play, since 20 stages of compounding base drain outpaced
anything a reasonable choice pattern could restore. With the tuned constants, a careful
policy (avoid recruiting companions, prioritize rest and curing afflictions, weight
resource conservation heavily once either resource drops below 40) completes 300/300
simulated runs; a merely resource-aware policy that doesn't specifically chase cures
completes roughly a third; and fully random choice-picking completes only a few percent.
That spread — attentive play reliably succeeds, careless play risks real failure — is the
intended shape. There's no automated regression test pinning this balance — a future
content change (e.g. adding a 21st stage, or an unusually costly choice) could silently
shift it, and periodic re-simulation is the way to check.

**Companion roster gating happens at the UI layer, not in `apply_choice`.** If a companion
invite choice is applied directly (bypassing `game.py`'s button availability check) while the
roster is already full at `MAX_COMPANIONS`, the choice's resource cost is still paid even
though `GameState.add_companion` silently declines to add them. In normal play this can't
happen — `Game._build_buttons` greys out invite choices once the roster is full — but a test
or script driving `stages.apply_choice` directly should be aware the cost isn't refunded.
