# Working notes for Claude Code

Conventions for working in this repo. Keep this file in sync as conventions solidify.

## Layout

- `src/fernweh/state.py`, `stages.py`, `afflictions.py`, `ending.py` are pure Python —
  no `pygame` import, ever. They must stay importable and testable with no display
  available.
- `src/fernweh/tween.py`, `particles.py`, `scenes.py`, `ui.py`, `game.py` are the
  rendering/game-loop layer. They import the logic layer; the logic layer never imports
  them.
- Narrative content (stages, choices, effects) lives in `content/stages.json`, not in
  Python. Engine code should never need to change when content is added or edited.

## Workflow

- Commit per coherent unit of work, imperative mood messages ("add X", "fix Y"), following
  the milestone order in `PLAN.md` unless a milestone needs to be reordered for a documented
  reason.
- Run `black` and `ruff` before each commit.
- Update `DOCUMENTATION.md` whenever a non-trivial decision is made (architecture, data
  format, library choice, tradeoff) — not saved up for the end.
- Type hints on all function signatures. Docstrings on every module, class, and public
  function/method, describing purpose/args/returns.
- No filler comments, no scaffolding/TODO placeholders, no decorative comment banners.

## Reference docs

`GAME-PLAN.md` and `GAME-DESIGN.md` at the repo root are local working references (build
brief and design spec). They are intentionally gitignored and must never be committed.
