"""Affliction trigger rules, stacking effects, and per-stage resource drain.

Afflictions are status conditions that make the journey slower and visually
harsher the more of them are active. `state.GameState` only stores which
affliction ids are currently active — the trigger conditions and their effect
on drain rates live here.
"""

from __future__ import annotations

import random

from fernweh.state import GameState

EXHAUSTED_ENERGY_THRESHOLD = 25
EXHAUSTED_ENERGY_DRAIN_MULTIPLIER = 1.20

ILL_BASE_CHANCE = 0.05
ILL_LOW_SUPPLIES_CHANCE = 0.25
ILL_LOW_SUPPLIES_THRESHOLD = 30
ILL_SUPPLIES_DRAIN_MULTIPLIER = 1.15

FROSTBITTEN_SEASON = "winter"
FROSTBITTEN_DRAIN_MULTIPLIER = 1.10

BASE_ENERGY_DRAIN_BY_SEASON = {"spring": 5, "summer": 6, "autumn": 7, "winter": 9}
BASE_SUPPLIES_DRAIN_BY_SEASON = {"spring": 4, "summer": 5, "autumn": 6, "winter": 7}
SUPPLIES_DRAIN_PER_COMPANION = 2


def maybe_trigger_exhausted(state: GameState) -> None:
    """Apply the Exhausted affliction once energy drops below the threshold.

    Exhausted does not clear itself when energy recovers — it's only cured by
    a choice that explicitly cures it, per the design's "1-2 stages to clear".
    """
    if state.energy < EXHAUSTED_ENERGY_THRESHOLD:
        state.add_affliction("exhausted")


def roll_ill(state: GameState, rng: random.Random) -> bool:
    """Roll whether Ill triggers this stage, weighted by low supplies."""
    chance = (
        ILL_LOW_SUPPLIES_CHANCE if state.supplies < ILL_LOW_SUPPLIES_THRESHOLD else ILL_BASE_CHANCE
    )
    triggered = rng.random() < chance
    if triggered:
        state.add_affliction("ill")
    return triggered


def hardship_level(state: GameState) -> int:
    """Number of active afflictions, used to scale visual/animation harshness."""
    return len(state.afflictions)


def energy_drain_multiplier(state: GameState) -> float:
    """Combined energy-drain multiplier from all active afflictions."""
    multiplier = 1.0
    if "exhausted" in state.afflictions:
        multiplier *= EXHAUSTED_ENERGY_DRAIN_MULTIPLIER
    if "frostbitten" in state.afflictions:
        multiplier *= FROSTBITTEN_DRAIN_MULTIPLIER
    return multiplier


def supplies_drain_multiplier(state: GameState) -> float:
    """Combined supplies-drain multiplier from all active afflictions."""
    multiplier = 1.0
    if "ill" in state.afflictions:
        multiplier *= ILL_SUPPLIES_DRAIN_MULTIPLIER
    if "frostbitten" in state.afflictions:
        multiplier *= FROSTBITTEN_DRAIN_MULTIPLIER
    return multiplier


def base_stage_drain(state: GameState) -> tuple[int, int]:
    """Base (energy, supplies) drain for the current stage, before choice effects.

    Supplies drain scales with companion count (more mouths to feed) before
    affliction multipliers are applied.
    """
    season = state.season
    energy_drain = BASE_ENERGY_DRAIN_BY_SEASON[season] * energy_drain_multiplier(state)
    supplies_drain = (
        BASE_SUPPLIES_DRAIN_BY_SEASON[season] + SUPPLIES_DRAIN_PER_COMPANION * len(state.companions)
    ) * supplies_drain_multiplier(state)
    return round(energy_drain), round(supplies_drain)
