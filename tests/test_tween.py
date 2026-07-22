"""Tests for the tween/easing math."""

import pytest
from fernweh.tween import (
    Tween,
    ease_in_cubic,
    ease_in_out_cubic,
    ease_in_out_quad,
    ease_in_quad,
    ease_out_cubic,
    ease_out_quad,
    linear,
)

EASING_FUNCTIONS = [
    linear,
    ease_in_quad,
    ease_out_quad,
    ease_in_out_quad,
    ease_in_cubic,
    ease_out_cubic,
    ease_in_out_cubic,
]


@pytest.mark.parametrize("easing", EASING_FUNCTIONS)
def test_easing_boundaries(easing) -> None:
    assert easing(0.0) == pytest.approx(0.0)
    assert easing(1.0) == pytest.approx(1.0)


@pytest.mark.parametrize("easing", EASING_FUNCTIONS)
def test_easing_is_monotonic(easing) -> None:
    samples = [easing(i / 100) for i in range(101)]
    assert all(a <= b + 1e-9 for a, b in zip(samples, samples[1:]))


def test_ease_in_out_quad_is_symmetric_at_midpoint() -> None:
    assert ease_in_out_quad(0.5) == pytest.approx(0.5)


def test_tween_rejects_nonpositive_duration() -> None:
    with pytest.raises(ValueError):
        Tween(0, 1, duration=0)


def test_tween_interpolates_linearly() -> None:
    tween = Tween(0, 100, duration=2.0, easing=linear)
    assert tween.update(1.0) == pytest.approx(50.0)
    assert tween.update(1.0) == pytest.approx(100.0)


def test_tween_clamps_at_duration() -> None:
    tween = Tween(0, 10, duration=1.0, easing=linear)
    tween.update(5.0)
    assert tween.value == pytest.approx(10.0)
    assert tween.done is True


def test_tween_calls_on_complete_once() -> None:
    calls = []
    tween = Tween(0, 1, duration=1.0, easing=linear, on_complete=lambda: calls.append(1))
    tween.update(0.5)
    assert calls == []
    tween.update(0.5)
    assert calls == [1]
    tween.update(1.0)
    assert calls == [1]


def test_tween_reset_restarts_progress() -> None:
    tween = Tween(0, 10, duration=1.0, easing=linear)
    tween.update(1.0)
    assert tween.done is True
    tween.reset()
    assert tween.done is False
    assert tween.elapsed == 0.0
    assert tween.value == 0


def test_tween_reset_can_change_bounds() -> None:
    tween = Tween(0, 10, duration=1.0, easing=linear)
    tween.update(1.0)
    tween.reset(start=10, end=20)
    assert tween.value == 10
    assert tween.update(1.0) == pytest.approx(20)
