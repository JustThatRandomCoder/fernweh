"""Lightweight tweening/easing utilities for animation.

A small, dependency-free alternative to a full animation library: easing
functions plus a `Tween` class that interpolates a single float over time
and calls back on completion. No pygame import — this is pure math.
"""

from __future__ import annotations

from collections.abc import Callable

EasingFunction = Callable[[float], float]


def linear(t: float) -> float:
    """No easing, straight interpolation."""
    return t


def ease_in_quad(t: float) -> float:
    """Accelerate from zero velocity."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Decelerate to zero velocity."""
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    """Accelerate then decelerate, quadratic."""
    if t < 0.5:
        return 2 * t * t
    return 1 - ((-2 * t + 2) ** 2) / 2


def ease_in_cubic(t: float) -> float:
    """Accelerate from zero velocity, cubic."""
    return t**3


def ease_out_cubic(t: float) -> float:
    """Decelerate to zero velocity, cubic."""
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    """Accelerate then decelerate, cubic."""
    if t < 0.5:
        return 4 * t**3
    return 1 - ((-2 * t + 2) ** 3) / 2


class Tween:
    """Interpolates a value from `start` to `end` over `duration` seconds."""

    def __init__(
        self,
        start: float,
        end: float,
        duration: float,
        easing: EasingFunction = linear,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if duration <= 0:
            raise ValueError("duration must be positive")
        self.start = start
        self.end = end
        self.duration = duration
        self.easing = easing
        self.on_complete = on_complete
        self.elapsed = 0.0
        self.done = False
        self.value = start

    def update(self, dt: float) -> float:
        """Advance the tween by `dt` seconds and return the current value."""
        if self.done:
            return self.value
        # Clamp elapsed time to duration so a large `dt` (e.g. a stutter) can't
        # overshoot past 1.0 progress or fire on_complete more than once.
        self.elapsed = min(self.duration, self.elapsed + dt)
        eased_t = self.easing(self.elapsed / self.duration)
        self.value = self.start + (self.end - self.start) * eased_t
        if self.elapsed >= self.duration:
            self.done = True
            if self.on_complete:
                self.on_complete()
        return self.value

    def reset(self, start: float | None = None, end: float | None = None) -> None:
        """Restart the tween from zero elapsed time, optionally with new bounds."""
        if start is not None:
            self.start = start
        if end is not None:
            self.end = end
        self.elapsed = 0.0
        self.done = False
        self.value = self.start
