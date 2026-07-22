"""Tests for stage content loading, validation, and choice resolution."""

import json

import pytest
from fernweh.stages import (
    VALID_AFFLICTIONS,
    VALID_EFFECT_KEYS,
    Choice,
    ContentError,
    DEFAULT_CONTENT_PATH,
    apply_choice,
    choice_is_available,
    load_stages,
    stage_season,
)
from fernweh.state import GameState


class _FixedRandom:
    """A stand-in rng whose `.random()` always returns the given value."""

    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def _choice(**overrides) -> Choice:
    defaults = dict(
        id="c",
        text="text",
        outcome="outcome",
        effects={},
        affliction_chance={},
        cures=(),
        memory=None,
        companion=None,
        unavailable_if=None,
        unavailable_reason=None,
    )
    defaults.update(overrides)
    return Choice(**defaults)


def test_loads_real_content_file() -> None:
    stages = load_stages()
    assert len(stages) == 20
    assert stages[0].index == 0
    assert stages[0].season == "spring"


def test_full_content_has_five_stages_per_season() -> None:
    stages = load_stages()
    season_counts: dict[str, int] = {}
    for stage in stages:
        season_counts[stage.season] = season_counts.get(stage.season, 0) + 1
    assert season_counts == {"spring": 5, "summer": 5, "autumn": 5, "winter": 5}


def test_companion_ids_are_unique_across_content() -> None:
    companion_ids = [
        choice.companion["id"]
        for stage in load_stages()
        for choice in stage.choices
        if choice.companion
    ]
    assert len(companion_ids) == len(set(companion_ids))


def test_every_choice_uses_valid_effect_keys() -> None:
    for stage in load_stages():
        for choice in stage.choices:
            assert set(choice.effects).issubset(VALID_EFFECT_KEYS)


def test_every_choice_references_valid_afflictions() -> None:
    for stage in load_stages():
        for choice in stage.choices:
            assert set(choice.affliction_chance).issubset(VALID_AFFLICTIONS)
            assert set(choice.cures).issubset(VALID_AFFLICTIONS)


def test_stage_has_two_or_three_choices() -> None:
    for stage in load_stages():
        assert 2 <= len(stage.choices) <= 3


def test_stage_season_matches_index() -> None:
    assert stage_season(0) == "spring"
    assert stage_season(5) == "summer"
    assert stage_season(10) == "autumn"
    assert stage_season(15) == "winter"


def test_rejects_invalid_effect_key(tmp_path) -> None:
    bad_content = {
        "stages": [
            {
                "id": 0,
                "season": "spring",
                "scene": {"description": "x", "weather": "clear"},
                "situation": "x",
                "choices": [
                    {"id": "a", "text": "a", "outcome": "a", "effects": {"nonsense": 1}},
                    {"id": "b", "text": "b", "outcome": "b", "effects": {}},
                ],
            }
        ]
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_content))
    with pytest.raises(ContentError):
        load_stages(path)


def test_rejects_wrong_choice_count(tmp_path) -> None:
    bad_content = {
        "stages": [
            {
                "id": 0,
                "season": "spring",
                "scene": {"description": "x", "weather": "clear"},
                "situation": "x",
                "choices": [{"id": "a", "text": "a", "outcome": "a", "effects": {}}],
            }
        ]
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_content))
    with pytest.raises(ContentError):
        load_stages(path)


def test_rejects_noncontiguous_stage_ids(tmp_path) -> None:
    stage_template = {
        "season": "spring",
        "scene": {"description": "x", "weather": "clear"},
        "situation": "x",
        "choices": [
            {"id": "a", "text": "a", "outcome": "a", "effects": {}},
            {"id": "b", "text": "b", "outcome": "b", "effects": {}},
        ],
    }
    bad_content = {"stages": [{"id": 0, **stage_template}, {"id": 2, **stage_template}]}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_content))
    with pytest.raises(ContentError):
        load_stages(path)


def test_choice_availability_depends_on_afflictions() -> None:
    stages = load_stages()
    choice = stages[0].choices[0]
    assert choice_is_available(choice, active_afflictions=set()) is True


def test_default_content_path_exists() -> None:
    assert DEFAULT_CONTENT_PATH.exists()


def test_rejects_frostbitten_outside_winter(tmp_path) -> None:
    bad_content = {
        "stages": [
            {
                "id": 0,
                "season": "spring",
                "scene": {"description": "x", "weather": "clear"},
                "situation": "x",
                "choices": [
                    {
                        "id": "a",
                        "text": "a",
                        "outcome": "a",
                        "effects": {},
                        "affliction_chance": {"frostbitten": 0.5},
                    },
                    {"id": "b", "text": "b", "outcome": "b", "effects": {}},
                ],
            }
        ]
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_content))
    with pytest.raises(ContentError):
        load_stages(path)


def test_apply_choice_advances_stage_and_applies_effects() -> None:
    state = GameState(stage_index=0, energy=100, supplies=100)
    choice = _choice(effects={"energy": -5, "supplies": -3})
    apply_choice(state, choice, rng=_FixedRandom(1.0))
    assert state.stage_index == 1
    assert state.energy < 100
    assert state.supplies < 100


def test_apply_choice_crosses_season_boundary() -> None:
    state = GameState(stage_index=4, energy=100, supplies=100)
    apply_choice(state, _choice(), rng=_FixedRandom(1.0))
    assert state.stage_index == 5
    assert state.season == "summer"


def test_apply_choice_completes_journey_on_final_stage() -> None:
    state = GameState(stage_index=19, energy=100, supplies=100)
    apply_choice(state, _choice(), rng=_FixedRandom(1.0))
    assert state.is_complete is True


def test_apply_choice_triggers_failure_and_stops_progression() -> None:
    state = GameState(stage_index=0, energy=3, supplies=100)
    apply_choice(state, _choice(effects={"energy": -3}), rng=_FixedRandom(1.0))
    assert state.is_failed is True
    assert state.stage_index == 0


def test_apply_choice_is_noop_once_ended() -> None:
    state = GameState(stage_index=3, ended=True, end_reason="failure")
    apply_choice(state, _choice(effects={"energy": -10}), rng=_FixedRandom(1.0))
    assert state.stage_index == 3


def test_apply_choice_adds_memory_and_companion() -> None:
    state = GameState(stage_index=0, energy=100, supplies=100)
    choice = _choice(
        memory="a smooth river stone",
        companion={"id": "mira", "name": "Mira", "one_line_trait": "practical"},
    )
    apply_choice(state, choice, rng=_FixedRandom(1.0))
    assert state.memories == ["a smooth river stone"]
    assert state.companions[0].name == "Mira"


def test_apply_choice_cures_and_rolls_afflictions() -> None:
    state = GameState(stage_index=0, energy=100, supplies=100)
    state.add_affliction("exhausted")
    choice = _choice(cures=("exhausted",), affliction_chance={"ill": 1.0})
    apply_choice(state, choice, rng=_FixedRandom(0.0))
    assert "exhausted" not in state.afflictions
    assert "ill" in state.afflictions
