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

**Scenes (`scenes.py`).** Every season maps to a `Palette` (sky top/bottom, ground, panel,
text color). `draw_scene` renders a vertical sky gradient over a ground band using only
`pygame.draw` primitives — there are no image assets anywhere in this project. A single
`desaturation` parameter (0–1) pulls every color toward grey; `game.py` derives this from
`afflictions.hardship_level` divided by a cap, so visual harshness scales with active
afflictions generically rather than through per-affliction rendering branches.

**`ground` vs. `panel`.** These were originally the same color (`ground` doubled as both
terrain fill and UI button fill), which is what produced a real contrast bug: autumn's
`ground` (140, 84, 48) against its `text` (56, 34, 18) measures 2.44:1, well under WCAG AA's
4.5:1 floor, making autumn choice buttons hard to read. `panel` is a separate, near-white
tone tuned per season so `text` always clears >10:1 against it (verified for all four
seasons); `ground` stays tuned purely for how outdoor terrain should look. UI surfaces
(buttons, the intro dialog, the text backing behind situation text) use `panel`, never
`ground`. `desaturate_palette(palette, amount)` is the single function that applies hardship
desaturation to `sky_top`/`sky_bottom`/`ground`/`panel` — `text` is deliberately excluded, so
hardship can darken and mute the world without ever eroding the contrast that keeps prose and
UI labels readable. `draw_scene` and `game.py`'s UI drawing both call it, rather than each
desaturating colors independently.

**Panels (`ui.draw_panel`).** One helper (rounded rect, flat drop shadow, thin border, all
in a season's `panel`/dimmed-`panel` colors) is the single surface treatment shared by
`ChoiceButton`, `IntroDialog`, and the backing behind the situation text in `game.py` — so
every "card" in the game reads as one visual language instead of each screen inventing its
own box. `IntroDialog` in particular used to fill the whole screen with a translucent wash
(`sky_bottom` at 235/255 alpha) and draw text directly on it; at that alpha, the game screen
underneath — its own situation text, its own choice buttons — bled through faintly behind the
dialog's text, reading as ghosting/visual noise more than a specific contrast failure. The
fix draws a translucent full-screen scrim (dims the scene, carries no text) and a fully
opaque `panel` card on top for the actual page text, so nothing behind can bleed through.

The situation-text backing panel in `game.py` hit the same bleed-through problem a second
time, for a different reason: it was drawn at partial alpha (225/255) for a soft "parchment"
look, which was harmless while the scene behind it was static. Once drizzle became a visible
animated rain streak (see Particles below) rather than a near-invisible dot, that same
translucency let the moving rain show through and animate inside the text card. The fix is the
same lesson applied twice — the panel is now fully opaque; only the drop shadow beneath it (a
separate, deliberately translucent layer in `draw_panel`) keeps any softness.

**Scene depth (`scenes.draw_scene`).** The original scene was a flat sky gradient over a flat
ground rectangle — visibly bare, and the reason the game read as unpolished rather than as a
contrast bug. Two additions give it real depth using only `pygame.draw` primitives, no art
assets: a soft sun/moon glow (`_draw_sun`, concentric SRCALPHA circles drawn outer-to-inner so
each smaller/brighter circle overwrites the previous one's center, faking a radial falloff)
positioned via `SUN_POSITION_RATIO`/`SUN_RADIUS_RATIO`, and two rolling-hill silhouette layers
(`_draw_hill`, a sine-wave polygon) configured by `HILL_LAYERS` — a lightened, higher "far"
layer and a darkened, lower "near" layer, satisfying the design brief's "soft parallax
backgrounds (2-3 layers)" without needing actual parallax scrolling (the scene is static per
stage). Both the sun/moon color and the hill shades derive from the palette's `accent` and
`ground` fields respectively (via `_lighten`/`_darken`), so every season gets a different
scene automatically rather than needing per-season drawing code.

The first version of this had a real bug, not just a subtlety problem: the flat ground
`pygame.draw.rect` was drawn *after* the hill polygons, which completely erased them — the
hills existed in code but were invisible on screen, which is why an initial pass at this
looked like nothing had changed at all. The fix draws the ground rect first as a base fill,
then layers the hills on top of it, with each hill's amplitude deliberately larger than its
baseline offset so the crest rises above the sky/ground line into the sky itself — that's what
makes it read as a silhouette rather than a bump hidden inside the ground band. A thin
anti-aliased stroke (`pygame.draw.aalines`, not `lines` — antialiasing keeps it a soft edge
rather than a technical-looking outline) along just the hill's crest line adds definition in
low-contrast seasons (winter's pale hill color against a similarly pale sky nearly disappeared
without it). Clouds (`_draw_clouds`/`_draw_cloud`) are the one continuously-animated part of
the background itself, distinct from the particle system's weather — each cloud's x position
is computed directly from an `elapsed` seconds-since-startup value passed into `draw_scene`
(tracked in `Game._elapsed`, accumulated in `_update`), rather than the cloud holding any
mutable state of its own, so `draw_scene` stays a pure function of its arguments.

**Trees (`_draw_trees`).** A foreground layer of procedural trees, positioned by the `TREES`
constant (`x_ratio, scale, sway_phase` tuples) mostly near the left/right edges of the window —
outside where `game.py` draws choice buttons (`MARGIN` to `width - MARGIN`) — so they stay
visible once the button list is on screen, plus a couple of smaller ones nearer the middle for
depth wherever the UI leaves them visible. Each tree is a trunk (`pygame.draw.line`) topped
with either a canopy (`_draw_canopy`, the same overlapping-circles technique as clouds) or, for
winter, a bare three-branch fork (`_draw_bare_branches`) — winter's `Palette.foliage` is `None`
specifically to drive that branch, rather than winter getting a colorless canopy. The canopy
color comes from a new `Palette.foliage` field (separate from `accent`, since a tree's canopy
and the sky's sun/moon glow are different "characters" of the same season). Sway is applied
only to the canopy/branch offset, not the trunk's root point, using the same `elapsed`-driven
sine approach as cloud drift — a real tree flexes at the top, it doesn't pivot from the ground.

**Particles (`particles.py`).** One `ParticleSystem` class parameterized by a
`ParticleKind` (color, size range, fall speed range, horizontal drift range, count, shape)
covers all three weather effects (`drizzle`, `snow`, `falling_leaves`). Adding a new weather
effect is adding one `ParticleKind` entry to `WEATHER_KINDS`, not a new class. Drizzle
originally drew as 1-2px near-invisible dots in a low-contrast color — barely readable as rain
at all. It now uses a `shape="streak"` (a short line trailing the particle's own velocity,
reading as a rain streak rather than a static dot) plus a darker, more saturated color and a
larger size range; `ParticleSystem.draw` branches on `kind.shape` to draw streaks or filled
circles. Particles that fall
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
automatically the moment illness is cured. Buttons originally started immediately at
`MARGIN + TEXT_AREA_HEIGHT`, flush against the text panel's own bottom edge with zero gap —
combined with the panel's rounded-rect border sitting right up against the first button's
square-ish top edge, this read as misaligned rather than intentionally stacked. `BUTTON_TOP_GAP`
(28px) now separates the button group from the text panel, and the panel's own padding was
restored to be symmetric (top and bottom) now that there's room for it without overlapping.

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

**Path (`_draw_path`/`path_y_ratio`).** A winding dirt path drawn as a bounded-width ribbon
through the foreground of the ground band, using the same "sample points along a sine wave"
technique as the hills but with a near *and* far edge instead of filling to the bottom of the
screen. `path_y_ratio(x_ratio)` is exposed as a standalone pure function (not folded into
`_draw_path`) specifically so `Game._draw_passage` can walk the traveler silhouette along the
exact same curve — computing the curve twice risked the path and the traveler's feet drifting
out of sync the moment either one's constants changed.

**Third hill layer and vignette.** A third, most-distant hill layer was added to `HILL_LAYERS`
for more parallax depth. A radial vignette (`_vignette_surface`, cached per screen size in
`_VIGNETTE_CACHE` since its rings never change frame to frame) darkens the screen edges by
drawing concentric full-size circles largest-alpha-first — each smaller circle overwrites the
previous one's center with a lower alpha, which is only correct because `pygame.draw` on an
`SRCALPHA` surface replaces pixels rather than blending with what's already there; blending
would have produced the opposite (edges darkest where fewest circles overlap) of what's
intended.

**Birds and fireflies.** Birds (`_draw_birds`, spring/summer only) reuse the clouds' wrap-
around drift technique but render a flapping "M" silhouette instead of a puff cluster, with
wingtip position driven by a fast sine so it reads as a flap rather than a bob. Fireflies
(`_draw_fireflies`, summer only) deliberately do *not* reuse the particle system — particles
model falling weather, but fireflies wander in small local loops around a fixed anchor point
(`cos`/`sin` of `elapsed` at a slow frequency) with a pulsing alpha (`sin` at a per-firefly
`flicker_speed`, cubed to make the flash read as a snap rather than a smooth fade).

**Traveler and passages.** Two new pieces work together to give the player a break from
questions between stages, since a wall of choice-after-choice was the main reason the game
read as flat despite the scene rendering already having depth. `scenes.draw_traveler` draws a
blocky pixel-art figure — a grid of `_pixel_rect` blocks at a `TRAVELER_PIXEL` unit size,
not thin lines — whose feet are pinned to `path_y_ratio` at whatever `x_ratio` it's given.
It's a standalone function, not folded into `draw_scene`, because only a passage needs the
traveler in motion; every other screen (a stage's question, the ending) has no use for it.

The figure isn't one fixed look: `TravelerAppearance` bundles skin/hair/tunic/trouser colors
plus a `bob_scale`/`stride_scale` pair, and `random_traveler_appearance(rng)` rolls one from
small curated palettes (`SKIN_TONES`, `HAIR_COLORS`, `TUNIC_COLORS`, `TROUSER_COLORS`) rather
than arbitrary RGB — arbitrary random color would occasionally land on an ugly or unreadable
combination, where drawing from a curated set of plausible tones never does. `Game` rolls one
`traveler_appearance` at startup and again in `_restart`, so the traveler looks consistent for
one playthrough but different across playthroughs. Beyond appearance, each individual
`Passage` (see below) also rolls its own `gait_offset`/`gait_speed`, so even two walks by the
*same*-looking traveler don't animate in exact lockstep — `draw_traveler` folds those into the
walk-cycle phase, and quantizes the resulting sine into eighths before placing limbs, which
gives the stride a slight stepped snap closer to a low-frame sprite than a perfectly smooth
interpolation.

`tween.Passage` is a bare elapsed/duration timer with a `progress` fraction and a `skip()` —
deliberately not a `Tween`, since nothing here is interpolating a value the class itself would
own; the caller (the traveler's x position, the game loop's decision to move on) derives
whatever it needs from `progress` itself. Its optional `rng` argument is what rolls
`gait_offset`/`gait_speed` on construction; omitting it (as a test can) yields the neutral
defaults `(0.0, 1.0)` instead of requiring every caller to care about gait variation.

`Game._start_passage` fires after a non-fatal choice, clearing the buttons/typewriter and
setting `Game._passage`; `_update` then branches early while a passage is active — the
particle system and `_elapsed` keep advancing (so weather and the traveler's stride stay
smooth), but nothing else about the old stage's UI does, since it's no longer showing. Once
the passage completes (naturally or via a click/key that calls `skip()`), `_sync_stage` runs
for the first time since the choice was made, which is what actually swaps in the new stage's
text, particle system (new weather), and buttons, plus the existing crossfade transition — so
the passage's last frame dissolves into the next question rather than cutting. A fatal choice
skips the passage entirely (`_sync_ending` fires immediately from the normal `_update` path):
walking scenery doesn't fit the moment a journey ends. `_draw` mirrors this branching, calling
`Game._draw_passage` (which just positions the traveler along `PASSAGE_X_START`–
`PASSAGE_X_END`, eased with `ease_in_out_quad` so the walk starts and stops gradually instead
of at a constant robotic speed) and returning early — the text panel, buttons, and keepsakes
never draw while a passage is on screen.

**Rest passages (the party seated on a bench).** Not every between-stage beat is a walk. A
choice can set a `rest` flag in `content/stages.json` (the sit/rest/make-camp options — "Sit on
the bank a while before crossing", "Rest in the shade", etc.); `stages._parse_choice` reads it
onto `Choice.rest`, defaulting `False` for the overwhelming majority of "keep walking" choices.
When the player picks a rest choice, `Game._handle_choice_click` passes `resting=choice.rest`
into `_start_passage`, which records it on `Game._passage_resting`. The passage timer, skip, and
early-return `_update`/`_draw` branching are all identical to a walk — only what gets drawn
differs: `Game._draw_passage` dispatches to `_draw_rest_passage`, which seats the traveler and
every companion in a row on a single bench (`scenes.draw_bench` + `scenes.draw_person_seated`)
instead of walking them along the path. The seated row preserves recruitment order left to
right (traveler first), reuses the exact same per-companion appearance cache the walk uses so a
companion looks identical sitting or walking, and staggers each sitter's slow idle-breathing
phase the way the walkers stagger gait offsets. `scenes.draw_bench` sizes the bench to span the
row (with a minimum width so a solo traveler still gets a real bench) and derives its wood tone
from the season palette's `ground`, so it sits naturally in any season; the seat height
(`REST_SEAT_Y_RATIO`) is tuned so the seated figures' hanging shins land their feet on the drawn
path, the same grounding the walking figure gets from `path_y_ratio`. `draw_person_seated` is a
seated front pose built from the same `_pixel_rect` blocks as `draw_traveler`: hips on the seat,
torso and head upright, arms resting at the sides, and shins dropping off the seat's front edge
to plant the feet — the read that says "sitting" rather than "standing".

**NPC portraits (`scenes.draw_portrait`, `stages.SceneCharacter`).** A stage whose situation
describes a specific person (the woman at the well, the trader at the market) can declare an
optional `character` block in `content/stages.json`; `stages._parse_character` validates it
against fixed vocabularies (`VALID_ROLES`/`VALID_POSES`/`VALID_SKIN_TONES`/etc.) and produces a
`SceneCharacter`, kept `None` on the majority of stages that describe an empty landscape rather
than a person. Content can't reference raw RGB — it can't, and shouldn't have to, know how the
rendering layer represents color — so the block uses plain strings ("woman", "sitting", "tan",
"auburn", "green"); `stages.py` validates those strings against its own fixed sets, and
`scenes.py` separately maps the same string keys to actual `Color` tuples via
`NAMED_SKIN_TONES`/`NAMED_HAIR_COLORS`/`NAMED_TUNIC_COLORS`. This is the same "shared vocabulary,
duplicated by convention across the logic/rendering boundary" relationship `SEASONS` already has
with `SEASON_PALETTES` — `stages.py` still imports nothing pygame-related.

`draw_portrait` renders a close-up bust — head, neck, cropped shoulders — at a larger block
scale than `draw_traveler`'s full-body walk, visual-novel style, since a stage's layout has room
for a close-up beside the situation text but not a full figure once the text panel and choice
buttons are laid out. It isn't a still image: a slow sine drives an idle "breathing" bob, and the
eyes blink shut for a brief window on a repeating cycle — the one detail that reads as "alive"
in a blocky close-up regardless of resolution. `pose` ("sitting"/"crouching"/"standing") leans
the head slightly via `POSE_HEAD_LEAN` rather than attempting actual rotation (`pygame.draw.rect`
has no rotation), which is enough to read as resting vs. standing at attention. An optional
`prop` (currently just `"well"`) draws a small matching set piece beside the portrait so a
stage's described setting isn't only conveyed through the panel description text.

`Game._sync_stage` builds the portrait's `PersonAppearance` once per stage sync via
`scenes.person_appearance_from_names` (deterministic, unlike the player traveler's randomly
rolled look, since a named recurring character's portrait shouldn't change between runs) and
stores it alongside the `SceneCharacter` in `self._stage_character`; `_draw` narrows the wrapped
situation-text rect by `PORTRAIT_SIZE + PORTRAIT_GAP` only on stages that have one, so the text
reflows around the portrait rather than either overlapping it or leaving unused space on stages
with no NPC. `_sync_ending` explicitly clears `_stage_character` to `None`, since reaching the
ending doesn't necessarily go through `_sync_stage` (a mid-stage failure can end the game without
one) and a stale portrait would otherwise persist onto the ending screen.

**A companion's portrait is who shows up on the road.** The four stages that offer a
companion (Mira, Sable, Talia, Emet, Wren — five characters, one is declined depending on
choices) are exactly the stages that declare a `character` block, and `_sync_stage` uses that
overlap deliberately: for every choice on the current stage with a `companion` field, it records
that companion's id against the exact `PersonAppearance` just built for the portrait, in
`Game._companion_appearances`. If the player recruits them, `_draw_passage` (see Traveler and
passages above) looks their appearance up by id when drawing the party, so the person walking
behind the traveler in every later passage is visibly the same person whose portrait was just on
screen — not a second, unrelated random look. A companion recruited through any future content
that *doesn't* pair a portrait with an invite choice still renders correctly: `_draw_passage`
falls back to `scenes.appearance_for_seed(companion.id)`, a deterministic-but-unauthored look
keyed off their id, so nothing crashes and they still look consistent across passages — just
without the guaranteed portrait match.

## Save/Continue (`save.py`)

**No pygame import, by the same rule as `state.py`.** `save.py` turns a `GameState` (plus the
cosmetic traveler/companion appearance info `game.py` tracks) into JSON on disk and back. It
deliberately doesn't know about `scenes.PersonAppearance` — appearances cross the save
boundary as plain dicts of RGB lists and floats (`scenes.person_appearance_to_dict`/
`_from_dict` do the conversion on the `game.py` side), so this module never needs to import
the rendering layer just to save or load a look. Saves live in `saves/` at the repo root,
which `.gitignore` excludes entirely — a player's progress is local runtime data, not
version-controlled content, the same reasoning `.venv/` already gets.

**Atomic writes.** `save_game` writes to a `.json.tmp` file and `os.replace`s it into place
rather than writing the target file directly. This matters specifically because of *when*
saves happen: `Game._autosave` fires synchronously right after every single choice resolves,
including the moment just before a player might close the terminal or hit Ctrl+C. A write
interrupted mid-flight by that kill must never leave a half-written, corrupt save behind —
`os.replace` is atomic on both POSIX and Windows, so the on-disk file is always either the old
complete save or the new complete save, never something in between.

**Why autosave lives where it does.** `Game._handle_choice_click` calls `_autosave()`
immediately after `apply_choice(...)`, before deciding whether to start a passage or let the
ending sync take over. `apply_choice` already mutates `GameState` (and advances
`stage_index`) synchronously and completely by the time it returns — nothing about a passage
animation playing afterward changes any logic-layer state, it's pure rendering. So the choice
that was just made is durably on disk before the passage even begins, which is what makes "the
process can be killed at any point after a choice, even mid-animation" a safe operation rather
than a race.

**The start menu.** `Game.__init__` no longer goes straight into stage 0: `self.menu_active`
gates the loop into a small menu screen first (`_build_menu`/`_draw_menu`/`_handle_menu_click`),
listing "Begin a new journey" plus up to `MAX_VISIBLE_SAVES` (5) of `save.list_saves()`'s most
recently updated saves, each labeled by `SaveSummary.describe()` (season, day number, current
party — or, for a finished journey, whether it was reached or cut short). `_start_new_game`
rolls a fresh `save.new_save_id()` and traveler look and shows the intro dialog, same as a
first-ever launch always did; `_continue_game` reconstructs `GameState` and both appearance
maps from `save.load_game`, skips the intro dialog (a returning player doesn't need it again),
and calls `self.typewriter.skip()` right after syncing so the situation or ending text they're
resuming into is shown fully revealed rather than replaying the reveal animation. Restarting
from the ending screen (`_restart`) now calls `_start_new_game()` too, rather than duplicating
its own reset logic — a restart is a new journey under a new save id, and the finished one it
came from stays in the menu's list as something still revisitable, not overwritten.

## Data Format

Stages live in `content/stages.json` as a single `{"stages": [...]}` array, one entry per
stage index (0-based, contiguous, no gaps — enforced by `stages._validate_stage_sequence`).
Each stage declares its `season`, a `scene` dict (`description` + `weather`, used later by
the renderer to pick a palette/particle effect), a `situation` string, and 2–3 `choices`.
`scene` may also declare an optional `character` block (see NPC portraits above) describing
an NPC the situation text mentions, with an optional `prop`; most stages omit it entirely.

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
