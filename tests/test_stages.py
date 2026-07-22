"""Tests for stage content loading and validation."""

import json

import pytest
from fernweh.stages import (
    VALID_AFFLICTIONS,
    VALID_EFFECT_KEYS,
    ContentError,
    DEFAULT_CONTENT_PATH,
    choice_is_available,
    load_stages,
    stage_season,
)


def test_loads_real_content_file() -> None:
    stages = load_stages()
    assert len(stages) >= 3
    assert stages[0].index == 0
    assert stages[0].season == "spring"


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
