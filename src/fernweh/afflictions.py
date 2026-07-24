"""Affliction trigger rules, stacking effects, and per-stage resource drain.

Afflictions are status conditions that make the journey slower and visually
harsher the more of them are active. `state.GameState` only stores which
affliction ids are currently active — the trigger conditions and their effect
on drain rates live here.
"""

from __future__ import annotations

import random

from fernweh.state import GameState

# Below this energy, Exhausted sets in automatically (not a random roll).
EXHAUSTED_ENERGY_THRESHOLD = 25
EXHAUSTED_ENERGY_DRAIN_MULTIPLIER = 1.20

# Ill is a per-stage dice roll: a low baseline chance, tripled to 25% (`ILL_LOW_SUPPLIES_CHANCE`)
# once supplies drop below the threshold, so running low on supplies makes you more likely to
# fall ill, not just slower to recover from it.
ILL_BASE_CHANCE = 0.05
ILL_LOW_SUPPLIES_CHANCE = 0.25
ILL_LOW_SUPPLIES_THRESHOLD = 30
ILL_SUPPLIES_DRAIN_MULTIPLIER = 1.15

# Frostbitten can only ever be risked by a winter-stage choice (enforced at content-load time
# in stages.py), so this constant is never referenced as a season check here.
FROSTBITTEN_SEASON = "winter"
FROSTBITTEN_DRAIN_MULTIPLIER = 1.10

# How much energy/supplies the journey costs every stage regardless of what the player
# chooses — winter costs the most, spring the least, matching "the road gets harder".
BASE_ENERGY_DRAIN_BY_SEASON = {"spring": 3, "summer": 4, "autumn": 4, "winter": 5}
BASE_SUPPLIES_DRAIN_BY_SEASON = {"spring": 2, "summer": 3, "autumn": 3, "winter": 4}
SUPPLIES_DRAIN_PER_COMPANION = 1


def maybe_trigger_exhausted(state: GameState) -> None:
    """Apply the Exhausted affliction once energy drops below the threshold.

    Exhausted does not clear itself when energy recovers — it's only cured by
    a choice that explicitly cures it, per the design's "1-2 stages to clear".
    """
    if state.energy < EXHAUSTED_ENERGY_THRESHOLD:
        state.add_affliction("exhausted")


def roll_ill(state: GameState, rng: random.Random) -> bool:
    """Roll whether Ill triggers this stage, weighted by low supplies."""
    # Pick the weighted chance first, then roll a single random number against
    # it — keeps the randomness itself injectable/testable via `rng`.
    chance = (
        ILL_LOW_SUPPLIES_CHANCE if state.supplies < ILL_LOW_SUPPLIES_THRESHOLD else ILL_BASE_CHANCE
    )
    triggered = rng.random() < chance
    if triggered:
        state.add_affliction("ill")
    return triggered


def hardship_level(state: GameState) -> int:
    """Number of active afflictions, used to scale visual/animation harshness."""
    # Just a count — this is the single knob the renderer reads to decide how
    # desaturated the scene looks and how slow the typewriter reveal runs, so
    # a new affliction affects visuals automatically just by being added here.
    return len(state.afflictions)


def energy_drain_multiplier(state: GameState) -> float:
    """Combined energy-drain multiplier from all active afflictions."""
    # Multipliers stack multiplicatively (not additively) so two afflictions
    # compound rather than just summing their individual penalties.
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
    # Energy drain: a flat per-season base, scaled by whatever afflictions are active.
    energy_drain = BASE_ENERGY_DRAIN_BY_SEASON[season] * energy_drain_multiplier(state)
    # Supplies drain: per-season base plus one extra unit per companion (more mouths to
    # feed), and only then scaled by the affliction multiplier.
    supplies_drain = (
        BASE_SUPPLIES_DRAIN_BY_SEASON[season] + SUPPLIES_DRAIN_PER_COMPANION * len(state.companions)
    ) * supplies_drain_multiplier(state)
    return round(energy_drain), round(supplies_drain)
