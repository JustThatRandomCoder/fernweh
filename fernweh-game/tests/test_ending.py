"""Tests for the procedural ending summary generator."""

from fernweh.ending import energy_tier, generate_ending
from fernweh.state import Companion, GameState


def test_energy_tier_boundaries() -> None:
    assert energy_tier(100) == "rested"
    assert energy_tier(70) == "rested"
    assert energy_tier(69) == "tired"
    assert energy_tier(35) == "tired"
    assert energy_tier(34) == "exhausted"
    assert energy_tier(0) == "exhausted"


def test_rested_with_companions_ending() -> None:
    state = GameState(stage_index=19, energy=85, supplies=60, ended=True, end_reason="completed")
    state.add_companion(Companion(id="mira", name="Mira", one_line_trait="", joined_at_stage=1))
    state.add_memory("a smooth river stone")
    state.add_memory("a note from a stranger")
    state.add_memory("the sound of the first snow")
    summary = generate_ending(state)
    assert "rested" in summary.prose
    assert "Mira" in summary.prose
    assert "Mira" in summary.keepsakes
    assert "a smooth river stone" in summary.keepsakes
    assert not summary.prose.startswith("The path goes on without you")


def test_exhausted_alone_ending() -> None:
    state = GameState(stage_index=19, energy=20, supplies=15, ended=True, end_reason="completed")
    summary = generate_ending(state)
    assert "alone" in summary.prose
    assert "exhausted" in summary.prose
    assert summary.keepsakes == []


def test_mid_journey_failure_ending() -> None:
    state = GameState(stage_index=7, energy=0, supplies=40, ended=True, end_reason="failure")
    summary = generate_ending(state)
    assert summary.prose.startswith("The path goes on without you")
    assert "summer" in summary.prose


def test_active_afflictions_are_mentioned() -> None:
    state = GameState(stage_index=19, energy=50, supplies=50, ended=True, end_reason="completed")
    state.add_affliction("ill")
    state.add_affliction("frostbitten")
    summary = generate_ending(state)
    assert "recovering from illness" in summary.prose
    assert "frostbitten fingers" in summary.prose
    assert ", and" in summary.prose


def test_no_afflictions_omits_affliction_sentence() -> None:
    state = GameState(stage_index=19, energy=50, supplies=50, ended=True, end_reason="completed")
    summary = generate_ending(state)
    assert "You are" not in summary.prose


def test_two_companions_uses_singular_other() -> None:
    state = GameState(stage_index=19, energy=50, supplies=50, ended=True, end_reason="completed")
    state.add_companion(Companion(id="a", name="Ren", one_line_trait="", joined_at_stage=0))
    state.add_companion(Companion(id="b", name="Sol", one_line_trait="", joined_at_stage=0))
    summary = generate_ending(state)
    assert "Ren and 1 other" in summary.prose


def test_prose_is_two_to_four_sentences() -> None:
    state = GameState(stage_index=19, energy=50, supplies=50, ended=True, end_reason="completed")
    summary = generate_ending(state)
    sentence_count = summary.prose.count(". ") + 1
    assert 2 <= sentence_count <= 4
