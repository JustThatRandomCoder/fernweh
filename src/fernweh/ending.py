"""Procedural ending summary generator.

Composes a short narrative summary from the end state — final energy tier,
companions, active afflictions, and memory count — rather than a stats screen
with numbers. This is deliberately a small rules-based text generator, not a
lookup table of hardcoded endings.
"""

from __future__ import annotations

from dataclasses import dataclass

from fernweh.state import GameState

REST_ENERGY_THRESHOLD = 70
TIRED_ENERGY_THRESHOLD = 35

_ENERGY_PHRASES = {
    "rested": "you arrive steady, rested enough to feel it",
    "tired": "you arrive tired, the road still heavy in your legs",
    "exhausted": "you arrive exhausted, barely upright",
}

_AFFLICTION_PHRASES = {
    "exhausted": "still worn thin from exhaustion",
    "ill": "still recovering from illness",
    "frostbitten": "nursing frostbitten fingers",
}


@dataclass(frozen=True)
class EndingSummary:
    """A composed narrative ending: prose plus a keepsakes list."""

    prose: str
    keepsakes: list[str]


def energy_tier(energy: int) -> str:
    """Classify final energy into a coarse descriptive tier."""
    if energy >= REST_ENERGY_THRESHOLD:
        return "rested"
    if energy >= TIRED_ENERGY_THRESHOLD:
        return "tired"
    return "exhausted"


def generate_ending(state: GameState) -> EndingSummary:
    """Build the narrative ending summary for a finished or failed journey."""
    # Each sentence comes from one independent axis of the end state (failure,
    # energy, companions, afflictions, memories) — composed here rather than
    # picked from a table of pre-written endings, so the combinations don't
    # need to be hand-enumerated.
    sentences = []

    # A failed run gets a leading sentence naming the season it ended in;
    # a completed run skips straight to the energy/companion sentence.
    if state.is_failed:
        sentences.append(
            f"The path goes on without you. Your journey ends here, somewhere in {state.season}."
        )

    tier = energy_tier(state.energy)
    energy_phrase = _ENERGY_PHRASES[tier]
    sentences.append(
        f"{energy_phrase[0].upper()}{energy_phrase[1:]}, and {_companion_phrase(state)}."
    )

    affliction_phrase = _affliction_phrase(state)
    if affliction_phrase:
        sentences.append(f"You are {affliction_phrase}.")

    sentences.append(f"Of the road behind you, {_memory_phrase(state)}.")

    # Keepsakes are just memories + companion names, in the order collected —
    # deliberately unranked, since none of this carries gameplay weight.
    keepsakes = list(state.memories) + [companion.name for companion in state.companions]
    return EndingSummary(prose=" ".join(sentences), keepsakes=keepsakes)


def _companion_phrase(state: GameState) -> str:
    # Names the first companion by name and folds any remaining ones into an
    # "and N others" tail rather than listing every name — keeps the prose
    # readable at 4 companions the same as at 1.
    names = [companion.name for companion in state.companions]
    if not names:
        return "you made this stretch of the road alone"
    if len(names) == 1:
        return f"you had {names[0]} beside you"
    others = len(names) - 1
    noun = "other" if others == 1 else "others"
    return f"you had {names[0]} and {others} {noun} beside you"


def _affliction_phrase(state: GameState) -> str | None:
    # `sorted()` gives a stable phrase order regardless of the (unordered) set
    # iteration order, so the same end state always reads the same way.
    phrases = [
        _AFFLICTION_PHRASES[affliction_id]
        for affliction_id in sorted(state.afflictions)
        if affliction_id in _AFFLICTION_PHRASES
    ]
    if not phrases:
        return None
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def _memory_phrase(state: GameState) -> str:
    # A handful of hand-picked bands rather than a formula — memory count has
    # no gameplay weight, so the thresholds just need to read naturally.
    count = len(state.memories)
    if count == 0:
        return "you remember the road only in outline"
    if count <= 2:
        return "a few moments of it stayed with you"
    if count <= 5:
        return "much of the road, you remember clearly"
    return "you remember nearly every step of it"
