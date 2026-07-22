"""Tests for affliction trigger conditions and stacking math."""

import random

from fernweh.afflictions import (
    BASE_ENERGY_DRAIN_BY_SEASON,
    BASE_SUPPLIES_DRAIN_BY_SEASON,
    SUPPLIES_DRAIN_PER_COMPANION,
    base_stage_drain,
    energy_drain_multiplier,
    hardship_level,
    maybe_trigger_exhausted,
    roll_ill,
    supplies_drain_multiplier,
)
from fernweh.state import Companion, GameState


def test_exhausted_triggers_below_threshold() -> None:
    state = GameState(energy=24)
    maybe_trigger_exhausted(state)
    assert "exhausted" in state.afflictions


def test_exhausted_does_not_trigger_at_threshold() -> None:
    state = GameState(energy=25)
    maybe_trigger_exhausted(state)
    assert "exhausted" not in state.afflictions


def test_exhausted_persists_once_energy_recovers() -> None:
    state = GameState(energy=10)
    maybe_trigger_exhausted(state)
    state.apply_energy_delta(50)
    assert state.energy == 60
    assert "exhausted" in state.afflictions


def test_roll_ill_uses_higher_chance_below_supplies_threshold() -> None:
    triggered_count = sum(
        roll_ill(GameState(supplies=10), random.Random(seed)) for seed in range(500)
    )
    assert 0.15 < triggered_count / 500 < 0.35


def test_roll_ill_uses_base_chance_above_supplies_threshold() -> None:
    triggered_count = sum(
        roll_ill(GameState(supplies=80), random.Random(seed)) for seed in range(500)
    )
    assert triggered_count / 500 < 0.12


def test_roll_ill_adds_affliction_when_triggered() -> None:
    state = GameState(supplies=10)
    rng = random.Random(1)
    while not roll_ill(state, rng):
        state = GameState(supplies=10)
    assert "ill" in state.afflictions


def test_hardship_level_counts_active_afflictions() -> None:
    state = GameState()
    assert hardship_level(state) == 0
    state.add_affliction("exhausted")
    assert hardship_level(state) == 1
    state.add_affliction("ill")
    assert hardship_level(state) == 2


def test_energy_drain_multiplier_stacks() -> None:
    state = GameState()
    assert energy_drain_multiplier(state) == 1.0
    state.add_affliction("exhausted")
    assert energy_drain_multiplier(state) == 1.20
    state.add_affliction("frostbitten")
    assert round(energy_drain_multiplier(state), 4) == round(1.20 * 1.10, 4)


def test_supplies_drain_multiplier_stacks() -> None:
    state = GameState()
    assert supplies_drain_multiplier(state) == 1.0
    state.add_affliction("ill")
    assert supplies_drain_multiplier(state) == 1.15
    state.add_affliction("frostbitten")
    assert round(supplies_drain_multiplier(state), 4) == round(1.15 * 1.10, 4)


def test_base_stage_drain_matches_season_baseline() -> None:
    state = GameState(stage_index=0)
    energy_drain, supplies_drain = base_stage_drain(state)
    assert energy_drain == BASE_ENERGY_DRAIN_BY_SEASON["spring"]
    assert supplies_drain == BASE_SUPPLIES_DRAIN_BY_SEASON["spring"]


def test_base_stage_drain_scales_with_companions() -> None:
    state = GameState(stage_index=0)
    state.add_companion(Companion(id="a", name="A", one_line_trait="", joined_at_stage=0))
    _, supplies_drain = base_stage_drain(state)
    assert supplies_drain == BASE_SUPPLIES_DRAIN_BY_SEASON["spring"] + SUPPLIES_DRAIN_PER_COMPANION


def test_base_stage_drain_increases_with_afflictions() -> None:
    state = GameState(stage_index=0)
    baseline_energy, _ = base_stage_drain(state)
    state.add_affliction("exhausted")
    afflicted_energy, _ = base_stage_drain(state)
    assert afflicted_energy > baseline_energy


def test_winter_drains_faster_than_spring() -> None:
    spring_energy, spring_supplies = base_stage_drain(GameState(stage_index=0))
    winter_energy, winter_supplies = base_stage_drain(GameState(stage_index=15))
    assert winter_energy > spring_energy
    assert winter_supplies > spring_supplies
