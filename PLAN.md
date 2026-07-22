# PLAN — Fernweh

A calm, single-player narrative journey game for desktop, built with Python and pygame-ce.
The player walks a fixed path from spring to winter — 4 seasons, 5 stages each, 20 stages
total — making choices that trade off two resources (Energy, Supplies) while collecting
companions and memories along the way. No combat, no branching map, no visible score during
play. This document is the build plan, expanded from the original design brief into concrete
milestones and technical decisions.

## Tech stack

- Python 3.11+
- [pygame-ce](https://github.com/pygame-community/pygame-ce) for windowing, rendering, input
- pytest for tests
- Standard library `json` for all narrative content (stages, choices, effects) — no content
  hardcoded in engine code
- A small hand-rolled tweening/easing module for animation — no external animation library

## Architecture principle

Game logic and rendering are strictly separated:

- `src/fernweh/state.py`, `stages.py`, `afflictions.py`, `ending.py` — pure Python, **zero
  pygame imports**, fully unit-testable without a display.
- `src/fernweh/tween.py`, `particles.py`, `scenes.py`, `ui.py`, `game.py` — rendering and
  the game loop, which import and drive the logic layer but are never imported by it.

This lets the entire rules engine (resource math, affliction triggers, stage progression,
ending generation, content validation) be tested headlessly in CI-less local runs, and keeps
content changes (writing more stages) from ever touching engine code.

## Project layout

```
fernweh/
  main.py
  requirements.txt
  LICENSE
  README.md
  PLAN.md
  DOCUMENTATION.md
  CLAUDE.md
  content/
    stages.json
  src/fernweh/
    __init__.py
    state.py
    stages.py
    afflictions.py
    ending.py
    tween.py
    particles.py
    scenes.py
    ui.py
    game.py
  tests/
    test_state.py
    test_stages.py
    test_afflictions.py
    test_ending.py
    run_all_tests.sh
  TESTING.md
```

## Milestones

Each milestone is functional on its own and ends in a commit before the next begins.

1. **Repo init** — `.gitignore`, MIT `LICENSE` (Julius Grimm, 2026), `README.md` stub,
   `PLAN.md` (this file). *(current milestone)*
2. **Doc skeletons** — `DOCUMENTATION.md` and `CLAUDE.md`, structured with headings that
   will grow as the build proceeds.
3. **Pure logic layer: `state.py`** — `GameState` dataclass: Energy/Supplies bounds and
   clamping, companion list (max 4), memory list, resource apply/drain helpers. Unit tests.
4. **Content format + loader** — `content/stages.json` with 2–3 real stages to prove the
   schema, `stages.py` to load/validate it and drive stage → stage progression. Tests
   include schema validation (every choice references a real effect key).
5. **Affliction system** — `afflictions.py`: trigger conditions (Exhausted, Ill,
   Frostbitten), stacking rules, a single derived "hardship level" used later by rendering.
   Tests for trigger thresholds and stacking math.
6. **Ending generator** — `ending.py`: rules-based prose composer driven by final resource
   tier, companion roster, active afflictions, and memory count. Tests across a few
   representative end states (rested+companions, exhausted+alone, mid-journey failure).
7. **Full content pass** — all 20 stages across the 4 seasons written into `stages.json`,
   in-tone (short, evocative, understated). Can land as one commit per season.
8. **Rendering scaffold** — window setup, main loop skeleton, season palettes, static scene
   rendering, no animation yet.
9. **Tween/easing module** — `tween.py`: ease-in/out helper functions and a `Tween` class
   interpolating a value over time with a completion callback. Tests on the interpolation
   math itself, not visuals.
10. **Particle system** — `particles.py`: a small reusable emitter parameterized by season
    (snow, rain, falling leaves, drifting pollen/fireflies), integrated into scene rendering.
11. **Scene transitions** — crossfade between stages using the tween module, no hard cuts.
12. **Typewriter text reveal** — reveal speed tied to the hardship level derived in
    milestone 5, so affliction stacking is felt, not just seen.
13. **Choice UI** — buttons with hover/press easing, wired to real `GameState` transitions
    instead of placeholder callbacks.
14. **Intro/tutorial dialog** — short click-through explanation shown before stage 1 and
    reachable again from a pause/help option; skip-on-replay is a runtime flag, not persisted.
15. **Ending screen** — wires the ending generator to a real screen, including the
    early-failure path (Energy or Supplies hits 0).
16. **Playthrough polish pass** — pacing, palette consistency, and bug fixes found by
    actually playing the game start to finish, in both success and failure paths.
17. **Finalize docs** — `README.md`, `DOCUMENTATION.md`, `TESTING.md` brought up to date
    with the finished project, not written from scratch at the end.
18. **Final review** — fresh clone + venv sanity check (`pip install -r requirements.txt`,
    `python main.py`, `pytest tests/ -v`), last cleanup commit.

## Testing strategy

- `pytest` covers: resource drain/restore math, affliction trigger conditions and stacking,
  stage progression and season boundaries (stage 5/10/15), the fail-state path, ending
  generation across representative end states, and content validation of `stages.json`.
- `tests/run_all_tests.sh` runs the whole suite with one command.
- `TESTING.md` gives a copy-pasteable setup for someone who has never touched this repo.

## Code quality bar

- `black` and `ruff` run before each commit (noted as tooling in `DOCUMENTATION.md`).
- Type hints on all function signatures; concise docstrings on every module, class, and
  public function — describing purpose/args/returns, not restating the name.
- No filler comments, no leftover scaffolding or commented-out code, no decorative banner
  comments. If something written earlier turns out sloppy once a later milestone exposes
  it, it gets its own small cleanup commit rather than being left alone.
