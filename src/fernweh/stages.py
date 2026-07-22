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

from fernweh.afflictions import base_stage_drain, maybe_trigger_exhausted
from fernweh.state import SEASONS, STAGES_PER_SEASON, Companion, GameState

VALID_EFFECT_KEYS = frozenset({"energy", "supplies"})
VALID_AFFLICTIONS = frozenset({"exhausted", "ill", "frostbitten"})

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


@dataclass(frozen=True)
class Stage:
    """A single stage: a scene, a situation, and its choices."""

    index: int
    season: str
    scene: dict[str, str]
    situation: str
    choices: tuple[Choice, ...]


def load_stages(path: Path | None = None) -> list[Stage]:
    """Load, validate, and return all stages from a JSON content file."""
    source = path or DEFAULT_CONTENT_PATH
    data = json.loads(Path(source).read_text())
    stages = [_parse_stage(raw) for raw in data["stages"]]
    _validate_stage_sequence(stages)
    return stages


def stage_season(stage_index: int) -> str:
    """Return the season name expected for a given stage index."""
    season_number = min(stage_index // STAGES_PER_SEASON, len(SEASONS) - 1)
    return SEASONS[season_number]


def choice_is_available(choice: Choice, active_afflictions: set[str]) -> bool:
    """Whether a choice can currently be selected given active afflictions."""
    return choice.unavailable_if is None or choice.unavailable_if not in active_afflictions


def apply_choice(state: GameState, choice: Choice, rng: random.Random | None = None) -> None:
    """Resolve one selected choice against `state` and advance to the next stage.

    Order of operations: base per-stage drain first (so afflictions reflect the
    stage just lived through), then the choice's own effects, memory/companion
    pickups, cures, and affliction rolls, then advance the stage index. A no-op
    if the journey has already ended.
    """
    if state.ended:
        return

    rng = rng or random.Random()

    energy_drain, supplies_drain = base_stage_drain(state)
    state.apply_energy_delta(-energy_drain)
    state.apply_supplies_delta(-supplies_drain)
    if state.ended:
        return

    state.apply_energy_delta(choice.effects.get("energy", 0))
    state.apply_supplies_delta(choice.effects.get("supplies", 0))
    if state.ended:
        return

    if choice.memory:
        state.add_memory(choice.memory)
    if choice.companion:
        state.add_companion(Companion(joined_at_stage=state.stage_index, **choice.companion))
    for affliction_id in choice.cures:
        state.remove_affliction(affliction_id)
    for affliction_id, chance in choice.affliction_chance.items():
        if rng.random() < chance:
            state.add_affliction(affliction_id)

    maybe_trigger_exhausted(state)
    state.advance_stage()


def _parse_stage(raw: dict[str, Any]) -> Stage:
    choices = tuple(_parse_choice(c, raw["season"]) for c in raw["choices"])
    if not 2 <= len(choices) <= 3:
        raise ContentError(f"stage {raw.get('id')} must have 2-3 choices, got {len(choices)}")
    expected_season = stage_season(raw["id"])
    if raw["season"] != expected_season:
        raise ContentError(
            f"stage {raw['id']} declares season '{raw['season']}', expected '{expected_season}'"
        )
    return Stage(
        index=raw["id"],
        season=raw["season"],
        scene=raw["scene"],
        situation=raw["situation"],
        choices=choices,
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
    )


def _validate_stage_sequence(stages: list[Stage]) -> None:
    if [s.index for s in stages] != list(range(len(stages))):
        raise ContentError("stage ids must be a contiguous sequence starting at 0")
