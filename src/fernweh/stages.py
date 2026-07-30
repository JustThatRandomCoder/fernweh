"""Stage content loading, schema validation, and progression helpers.

Narrative content lives entirely in `content/stages.json`. This module knows how
to load and validate that file into typed, immutable `Stage`/`Choice` objects —
it has no pygame import and no knowledge of rendering.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fernweh.afflictions import base_stage_drain, maybe_trigger_exhausted, roll_ill
from fernweh.state import SEASONS, STAGES_PER_SEASON, Companion, GameState

VALID_EFFECT_KEYS = frozenset({"energy", "supplies"})
VALID_AFFLICTIONS = frozenset({"exhausted", "ill", "frostbitten"})

# Each stage plays one of three structural roles within its season, which is
# what lets a journey be reshuffled without the story falling apart:
#   - "opener": the season's fixed first beat (arriving into the season).
#   - "closer": the season's fixed last beat (the transition into the next).
#   - "middle": interchangeable beats in between, drawn from a pool.
# `build_journey` keeps opener first and closer last, and randomly picks which
# middles fill the slots between them — so the arc of each season (and the
# spring -> winter order overall) is always coherent while the specific
# middle stages differ from one playthrough to the next.
VALID_STAGE_ROLES = frozenset({"opener", "middle", "closer"})
# How many interchangeable middle stages sit between a season's opener and
# closer. Derived from STAGES_PER_SEASON so the selected journey still has
# exactly STAGES_PER_SEASON stages per season (1 opener + middles + 1 closer),
# which keeps season boundaries on the STAGES_PER_SEASON grid the rest of the
# engine (season derivation, save summaries) already assumes.
MIDDLE_SLOTS_PER_SEASON = STAGES_PER_SEASON - 2

# A scene character's look/pose vocabulary. Kept as plain strings validated
# against these fixed sets rather than raw colors, since this module can't
# import `scenes.py` (the pure content/logic layer never imports the
# pygame-dependent rendering layer) — `scenes.py` separately defines a
# NAMED_*_COLORS dict using these exact same keys, the same "shared name,
# duplicated by convention" relationship SEASONS already has with
# SEASON_PALETTES.
VALID_ROLES = frozenset({"woman", "man"})
VALID_POSES = frozenset({"standing", "sitting", "crouching"})
VALID_SKIN_TONES = frozenset({"light", "tan", "deep", "dark"})
VALID_HAIR_COLORS = frozenset({"black", "auburn", "sandy", "grey"})
VALID_TUNIC_COLORS = frozenset({"red", "blue", "green", "gold", "purple"})
VALID_PROPS = frozenset({"well"})
# A scene's optional landmark: a concrete feature the situation text names (a
# bridge to cross, a stream, a lone tree, a building) that the rendering layer
# draws into the landscape so the picture matches the words. Kept as a fixed
# vocabulary validated here, the same "shared name, duplicated by convention"
# relationship the character vocabularies above have with `scenes.py` — which
# maps each of these keys to an actual draw routine in `LANDMARK_DRAWERS`.
# Absent on stages whose scenery the generic season landscape already conveys.
VALID_LANDMARKS = frozenset(
    {
        "stream",
        "bridge",
        "lone_tree",
        "market",
        "dry_riverbed",
        "orchard",
        "cabin",
        "stone_house",
        "shelter",
        "depot",
        "frozen_lake",
    }
)

DEFAULT_CONTENT_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "stages.json"


class ContentError(ValueError):
    """Raised when stage content fails schema validation."""


@dataclass(frozen=True)
class Choice:
    """One selectable option within a stage."""

    id: str
    text: str
    outcome: str
    effects: dict[str, int]
    affliction_chance: dict[str, float]
    cures: tuple[str, ...]
    memory: str | None
    companion: dict[str, str] | None
    unavailable_if: str | None
    unavailable_reason: str | None
    # When true, choosing this option is the player deciding to sit and rest
    # (on a bench, a bank, in the shade) before moving on — so the travel
    # sequence that follows shows the party seated on a bench rather than
    # walking the path. Pure content flag; the rendering layer reads it to
    # pick which passage animation to play. Defaults to False for the vast
    # majority of choices, which are ordinary "keep walking" decisions.
    rest: bool


@dataclass(frozen=True)
class SceneCharacter:
    """The NPC a stage's situation text describes, if any — rendered as a close-up portrait.

    Optional: most stages describe an empty landscape, not a person, so most
    stages have no `character` block at all in content and this stays absent.
    """

    role: str
    pose: str
    skin: str
    hair: str
    tunic: str
    prop: str | None


@dataclass(frozen=True)
class Stage:
    """A single stage: a scene, a situation, and its choices."""

    # A stable string id (e.g. "spring_stream"), used to reference a stage from
    # a saved journey plan — journeys no longer run the stages in file order,
    # so a positional integer index would be meaningless across playthroughs.
    id: str
    season: str
    # This stage's structural role within its season: "opener", "middle", or
    # "closer" (see VALID_STAGE_ROLES). Drives how `build_journey` places it.
    role: str
    scene: dict[str, str]
    situation: str
    choices: tuple[Choice, ...]
    character: SceneCharacter | None
    # The concrete landscape feature this stage's scene names (a bridge, a
    # stream, a building), drawn by the rendering layer on top of the generic
    # season landscape. None on the many stages that need no specific landmark.
    landmark: str | None


def load_stages(path: Path | None = None) -> list[Stage]:
    """Load, validate, and return the full stage pool from a JSON content file.

    The result is the whole authored pool, not a single playthrough's sequence
    — `build_journey` selects one journey's worth of stages from it. Validation
    guarantees every season has the pieces `build_journey` needs (exactly one
    opener and closer, and enough middles to fill the slots between them).
    """
    source = path or DEFAULT_CONTENT_PATH
    data = json.loads(Path(source).read_text())
    stages = [_parse_stage(raw) for raw in data["stages"]]
    _validate_pool(stages)
    return stages


def stages_by_id(stages: list[Stage]) -> dict[str, Stage]:
    """Index a stage pool by id, for resolving a journey plan's ids back to stages."""
    return {stage.id: stage for stage in stages}


def build_journey(stages: list[Stage], rng: random.Random) -> list[str]:
    """Pick one playthrough's ordered sequence of stage ids from the full pool.

    Walks the seasons in their fixed SEASONS order (spring -> winter) and, for
    each, lays down its single opener, then a random selection of its middle
    stages shuffled into the slots between, then its single closer. The result
    is always exactly STAGES_PER_SEASON stages per season in season order, so
    the overall arc stays coherent while which middles appear — and in what
    order — differs from one journey to the next. Returns stage ids (not Stage
    objects) because that's what a save persists to reconstruct the journey.
    """
    plan: list[str] = []
    for season in SEASONS:
        season_stages = [s for s in stages if s.season == season]
        opener = next(s for s in season_stages if s.role == "opener")
        closer = next(s for s in season_stages if s.role == "closer")
        middles = [s for s in season_stages if s.role == "middle"]
        chosen = rng.sample(middles, MIDDLE_SLOTS_PER_SEASON)
        plan.append(opener.id)
        plan.extend(stage.id for stage in chosen)
        plan.append(closer.id)
    return plan


def canonical_journey(stages: list[Stage]) -> list[str]:
    """A deterministic journey plan (opener + first middles + closer, in pool order).

    Same shape as `build_journey` but with no randomness, so it's stable. Used
    to migrate a pre-randomization save that has no stored plan: it keeps the
    game from crashing on `plan[stage_index]` while preserving the season
    structure, at the cost of the remaining stages possibly differing slightly
    from that old save's original fixed order.
    """
    plan: list[str] = []
    for season in SEASONS:
        season_stages = [s for s in stages if s.season == season]
        opener = next(s for s in season_stages if s.role == "opener")
        closer = next(s for s in season_stages if s.role == "closer")
        middles = [s for s in season_stages if s.role == "middle"]
        plan.append(opener.id)
        plan.extend(stage.id for stage in middles[:MIDDLE_SLOTS_PER_SEASON])
        plan.append(closer.id)
    return plan


def choice_is_available(choice: Choice, active_afflictions: set[str]) -> bool:
    """Whether a choice can currently be selected given active afflictions."""
    return choice.unavailable_if is None or choice.unavailable_if not in active_afflictions


def apply_choice(state: GameState, choice: Choice, rng: random.Random | None = None) -> None:
    """Resolve one selected choice against `state` and advance to the next stage.

    Order of operations: base per-stage drain first (so afflictions reflect the
    stage just lived through), then the choice's own effects, memory/companion
    pickups, cures, and affliction rolls, then advance the stage index and roll
    for Ill at the start of the new stage. A no-op if the journey has already
    ended.
    """
    if state.ended:
        return

    # Tests pass a seeded rng so affliction rolls are deterministic; real play
    # just gets fresh randomness.
    rng = rng or random.Random()

    # 1. The stage itself costs resources before the player's choice does —
    # this is the "the road drains you regardless" baseline.
    energy_drain, supplies_drain = base_stage_drain(state)
    state.apply_energy_delta(-energy_drain)
    state.apply_supplies_delta(-supplies_drain)
    # A fatal drain here ends the journey immediately — the choice's own
    # effects below never get to apply to an already-ended game.
    if state.ended:
        return

    # 2. The choice's own resource cost/reward.
    state.apply_energy_delta(choice.effects.get("energy", 0))
    state.apply_supplies_delta(choice.effects.get("supplies", 0))
    if state.ended:
        return

    # 3. Non-resource consequences: collectibles, a new companion, cures, and
    # any affliction this specific choice risks (e.g. a risky winter shortcut).
    if choice.memory:
        state.add_memory(choice.memory)
    if choice.companion:
        state.add_companion(Companion(joined_at_stage=state.stage_index, **choice.companion))
    for affliction_id in choice.cures:
        state.remove_affliction(affliction_id)
    for affliction_id, chance in choice.affliction_chance.items():
        if rng.random() < chance:
            state.add_affliction(affliction_id)

    # 4. Exhausted is a threshold check (not a roll), then move to the next
    # stage, then roll Ill "at the start of" the stage just arrived at.
    maybe_trigger_exhausted(state)
    state.advance_stage()
    if not state.ended:
        roll_ill(state, rng)


def _parse_stage(raw: dict[str, Any]) -> Stage:
    stage_id = raw["id"]
    choices = tuple(_parse_choice(c, raw["season"]) for c in raw["choices"])
    if not 2 <= len(choices) <= 3:
        raise ContentError(f"stage {stage_id} must have 2-3 choices, got {len(choices)}")
    # Season and role are both declared explicitly and validated against their
    # fixed vocabularies — a mistyped season would silently misplace a stage in
    # the journey, and a mistyped role would break `build_journey`'s selection.
    if raw["season"] not in SEASONS:
        raise ContentError(f"stage {stage_id} declares unknown season '{raw['season']}'")
    if raw["role"] not in VALID_STAGE_ROLES:
        raise ContentError(f"stage {stage_id} declares unknown role '{raw['role']}'")
    return Stage(
        id=stage_id,
        season=raw["season"],
        role=raw["role"],
        scene=raw["scene"],
        situation=raw["situation"],
        choices=choices,
        character=_parse_character(raw["scene"].get("character"), stage_id),
        landmark=_parse_landmark(raw["scene"].get("landmark"), stage_id),
    )


def _parse_landmark(landmark: str | None, stage_id: Any) -> str | None:
    """Validate a scene's optional landmark name against the known vocabulary."""
    if landmark is None:
        return None
    if landmark not in VALID_LANDMARKS:
        raise ContentError(f"stage {stage_id} references unknown landmark '{landmark}'")
    return landmark


def _parse_character(raw: dict[str, Any] | None, stage_id: Any) -> SceneCharacter | None:
    if raw is None:
        return None
    for field, valid in (
        ("role", VALID_ROLES),
        ("pose", VALID_POSES),
        ("skin", VALID_SKIN_TONES),
        ("hair", VALID_HAIR_COLORS),
        ("tunic", VALID_TUNIC_COLORS),
    ):
        if raw.get(field) not in valid:
            raise ContentError(
                f"stage {stage_id} character has invalid '{field}' value {raw.get(field)!r}"
            )
    prop = raw.get("prop")
    if prop is not None and prop not in VALID_PROPS:
        raise ContentError(f"stage {stage_id} character references unknown prop '{prop}'")
    return SceneCharacter(
        role=raw["role"],
        pose=raw["pose"],
        skin=raw["skin"],
        hair=raw["hair"],
        tunic=raw["tunic"],
        prop=prop,
    )


def _parse_choice(raw: dict[str, Any], season: str) -> Choice:
    effects = raw.get("effects", {})
    for key in effects:
        if key not in VALID_EFFECT_KEYS:
            raise ContentError(f"choice {raw.get('id')} has invalid effect key '{key}'")

    affliction_chance = raw.get("affliction_chance", {})
    for affliction_id in affliction_chance:
        if affliction_id not in VALID_AFFLICTIONS:
            raise ContentError(
                f"choice {raw.get('id')} references unknown affliction '{affliction_id}'"
            )
        # Frostbitten is a winter-only risk by design — this is the load-time
        # enforcement that keeps it from ever being attached to a non-winter stage.
        if affliction_id == "frostbitten" and season != "winter":
            raise ContentError(
                f"choice {raw.get('id')} can only risk frostbitten in a winter stage"
            )

    cures = tuple(raw.get("cures", ()))
    for affliction_id in cures:
        if affliction_id not in VALID_AFFLICTIONS:
            raise ContentError(f"choice {raw.get('id')} cures unknown affliction '{affliction_id}'")

    unavailable_if = raw.get("unavailable_if")
    if unavailable_if is not None and unavailable_if not in VALID_AFFLICTIONS:
        raise ContentError(f"choice {raw.get('id')} gates on unknown affliction '{unavailable_if}'")

    return Choice(
        id=raw["id"],
        text=raw["text"],
        outcome=raw["outcome"],
        effects=effects,
        affliction_chance=affliction_chance,
        cures=cures,
        memory=raw.get("memory"),
        companion=raw.get("companion"),
        unavailable_if=unavailable_if,
        unavailable_reason=raw.get("unavailable_reason"),
        # Optional in content; only the rest/sit choices set it, everything
        # else defaults to a normal walking passage.
        rest=bool(raw.get("rest", False)),
    )


def _validate_pool(stages: list[Stage]) -> None:
    """Check the stage pool has everything `build_journey` needs, per season.

    Rather than a contiguous integer sequence (journeys no longer run stages in
    file order), the invariant now is: ids are unique, every season is present,
    and each season has exactly one opener, exactly one closer, and at least
    MIDDLE_SLOTS_PER_SEASON middles to choose from. Anything else would make
    `build_journey` unable to lay down a full, coherent season.
    """
    ids = [s.id for s in stages]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ContentError(f"duplicate stage ids: {sorted(duplicates)}")

    for season in SEASONS:
        season_stages = [s for s in stages if s.season == season]
        openers = [s for s in season_stages if s.role == "opener"]
        closers = [s for s in season_stages if s.role == "closer"]
        middles = [s for s in season_stages if s.role == "middle"]
        if len(openers) != 1:
            raise ContentError(f"season '{season}' must have exactly 1 opener, got {len(openers)}")
        if len(closers) != 1:
            raise ContentError(f"season '{season}' must have exactly 1 closer, got {len(closers)}")
        if len(middles) < MIDDLE_SLOTS_PER_SEASON:
            raise ContentError(
                f"season '{season}' needs at least {MIDDLE_SLOTS_PER_SEASON} middles, "
                f"got {len(middles)}"
            )
