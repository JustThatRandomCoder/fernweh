"""Tests for save/continue persistence."""

from pathlib import Path

import pytest

from fernweh import save
from fernweh.state import Companion, GameState


@pytest.fixture(autouse=True)
def _isolated_saves_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Every test gets its own throwaway saves directory instead of touching
    # the real (gitignored) `saves/` folder next to the repo.
    monkeypatch.setattr(save, "SAVES_DIR", tmp_path / "saves")


def _sample_state() -> GameState:
    state = GameState(energy=57, supplies=41, stage_index=6)
    state.companions.append(Companion("mira", "Mira", "practical", joined_at_stage=1))
    state.memories.append("A stranger's quiet thanks.")
    state.afflictions.add("exhausted")
    return state


def test_save_and_load_round_trips_state() -> None:
    save_id = save.new_save_id()
    original = _sample_state()
    save.save_game(save_id, original, {"skin": [1, 2, 3]}, {"mira": {"skin": [4, 5, 6]}})

    loaded = save.load_game(save_id)

    assert loaded.state.energy == original.energy
    assert loaded.state.supplies == original.supplies
    assert loaded.state.stage_index == original.stage_index
    assert loaded.state.companions == original.companions
    assert loaded.state.memories == original.memories
    assert loaded.state.afflictions == original.afflictions
    assert loaded.traveler_appearance == {"skin": [1, 2, 3]}
    assert loaded.companion_appearances == {"mira": {"skin": [4, 5, 6]}}
    assert loaded.created_at


def test_list_saves_is_empty_when_no_saves_dir_exists() -> None:
    assert save.list_saves() == []


def test_list_saves_orders_most_recently_updated_first() -> None:
    older_id = save.new_save_id()
    save.save_game(older_id, _sample_state(), {}, {}, created_at="2020-01-01T00:00:00+00:00")

    newer = _sample_state()
    newer.stage_index = 12
    newer_id = save.new_save_id()
    save.save_game(newer_id, newer, {}, {})

    summaries = save.list_saves()
    assert [s.id for s in summaries] == [newer_id, older_id]
    assert summaries[0].stage_index == 12


def test_list_saves_summarizes_season_and_companions() -> None:
    save_id = save.new_save_id()
    save.save_game(save_id, _sample_state(), {}, {})

    [summary] = save.list_saves()
    assert summary.season == "summer"
    assert summary.companion_names == ("Mira",)
    assert summary.ended is False
    assert summary.end_reason is None


def test_list_saves_skips_corrupt_files() -> None:
    save_id = save.new_save_id()
    save.save_game(save_id, _sample_state(), {}, {})
    save.SAVES_DIR.mkdir(parents=True, exist_ok=True)
    (save.SAVES_DIR / "broken.json").write_text("{not valid json")

    summaries = save.list_saves()
    assert [s.id for s in summaries] == [save_id]


def test_delete_save_removes_file_and_is_safe_when_missing() -> None:
    save_id = save.new_save_id()
    save.save_game(save_id, _sample_state(), {}, {})
    save.delete_save(save_id)

    assert save.list_saves() == []
    save.delete_save(save_id)  # does not raise on a missing file
