"""Tests for the pure GameState model."""

from fernweh.state import (
    MAX_COMPANIONS,
    MAX_ENERGY,
    MAX_SUPPLIES,
    Companion,
    GameState,
)


def test_energy_delta_clamps_to_bounds() -> None:
    state = GameState(energy=10)
    state.apply_energy_delta(-50)
    assert state.energy == 0
    state.apply_energy_delta(1000)
    assert state.energy == MAX_ENERGY


def test_supplies_delta_clamps_to_bounds() -> None:
    state = GameState(supplies=5)
    state.apply_supplies_delta(-50)
    assert state.supplies == 0
    state.apply_supplies_delta(1000)
    assert state.supplies == MAX_SUPPLIES


def test_energy_zero_triggers_failure() -> None:
    state = GameState(energy=10)
    state.apply_energy_delta(-10)
    assert state.ended is True
    assert state.is_failed is True
    assert state.is_complete is False


def test_supplies_zero_triggers_failure() -> None:
    state = GameState(supplies=5)
    state.apply_supplies_delta(-5)
    assert state.ended is True
    assert state.is_failed is True


def test_resource_updates_after_failure_are_inert() -> None:
    state = GameState(energy=0, ended=True, end_reason="failure")
    state.apply_energy_delta(50)
    assert state.end_reason == "failure"


def test_companions_respect_max_capacity() -> None:
    state = GameState()
    for i in range(MAX_COMPANIONS):
        added = state.add_companion(
            Companion(id=f"c{i}", name=f"C{i}", one_line_trait="", joined_at_stage=0)
        )
        assert added is True
    overflow_added = state.add_companion(
        Companion(id="overflow", name="Overflow", one_line_trait="", joined_at_stage=0)
    )
    assert overflow_added is False
    assert len(state.companions) == MAX_COMPANIONS


def test_add_memory_appends() -> None:
    state = GameState()
    state.add_memory("a smooth river stone")
    assert state.memories == ["a smooth river stone"]


def test_affliction_add_and_remove() -> None:
    state = GameState()
    state.add_affliction("exhausted")
    assert "exhausted" in state.afflictions
    state.remove_affliction("exhausted")
    assert "exhausted" not in state.afflictions


def test_season_boundaries() -> None:
    assert GameState(stage_index=0).season == "spring"
    assert GameState(stage_index=4).season == "spring"
    assert GameState(stage_index=5).season == "summer"
    assert GameState(stage_index=9).season == "summer"
    assert GameState(stage_index=10).season == "autumn"
    assert GameState(stage_index=14).season == "autumn"
    assert GameState(stage_index=15).season == "winter"
    assert GameState(stage_index=19).season == "winter"


def test_advance_stage_increments_until_final() -> None:
    state = GameState(stage_index=0)
    state.advance_stage()
    assert state.stage_index == 1
    assert state.ended is False


def test_advance_stage_completes_journey_at_final_stage() -> None:
    state = GameState(stage_index=19)
    state.advance_stage()
    assert state.ended is True
    assert state.is_complete is True
    assert state.stage_index == 19


def test_advance_stage_is_noop_after_failure() -> None:
    state = GameState(stage_index=3, ended=True, end_reason="failure")
    state.advance_stage()
    assert state.stage_index == 3
