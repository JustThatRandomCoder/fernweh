"""Procedural particle system for seasonal weather (rain, snow, falling leaves).

A single reusable emitter parameterized by a `ParticleKind`, not a bespoke
class per weather effect — adding a new weather effect only means adding an
entry to `WEATHER_KINDS`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

Color = tuple[int, int, int]


@dataclass(frozen=True)
class ParticleKind:
    """Visual and motion parameters for one weather effect."""

    color: Color
    size_range: tuple[float, float]
    fall_speed_range: tuple[float, float]
    drift_range: tuple[float, float]
    count: int
    # "streak" draws a short line trailing behind the particle's motion
    # (reads as rain), "circle" draws a filled dot (reads as snow/leaves).
    shape: str = "circle"


# One entry per weather effect a stage can declare in content/stages.json. Adding a new
# weather effect is adding a new entry here — no new class or renderer branch needed.
WEATHER_KINDS: dict[str, ParticleKind] = {
    "drizzle": ParticleKind(
        # A darker, more saturated blue-grey than the original near-invisible
        # tone, plus a "streak" shape — at this fall speed a dot reads as a
        # barely-visible speck, but a short motion trail reads as rain.
        color=(96, 118, 150),
        size_range=(2, 3),
        fall_speed_range=(220, 340),
        drift_range=(-10, 10),
        count=90,
        shape="streak",
    ),
    "snow": ParticleKind(
        color=(255, 255, 255),
        size_range=(2.5, 5),
        fall_speed_range=(25, 65),
        drift_range=(-20, 20),
        count=70,
    ),
    "falling_leaves": ParticleKind(
        color=(206, 122, 42),
        size_range=(3.5, 6.5),
        fall_speed_range=(35, 85),
        drift_range=(-35, 35),
        count=40,
    ),
}


def particle_kind_for_weather(weather: str) -> str | None:
    """Return the particle kind name for a scene's weather, if it has one."""
    return weather if weather in WEATHER_KINDS else None


class Particle:
    """A single moving point: position, velocity, and render size."""

    __slots__ = ("x", "y", "vx", "vy", "size")

    def __init__(self, x: float, y: float, vx: float, vy: float, size: float) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size


class ParticleSystem:
    """A reusable emitter for one weather effect over a fixed-size viewport."""

    def __init__(
        self,
        kind_name: str,
        width: int,
        height: int,
        rng: random.Random | None = None,
    ) -> None:
        self.kind = WEATHER_KINDS[kind_name]
        self.width = width
        self.height = height
        self.rng = rng or random.Random()
        self.particles = [self._spawn(scattered=True) for _ in range(self.kind.count)]

    def update(self, dt: float) -> None:
        """Advance every particle by `dt` seconds, respawning ones that left the frame."""
        for particle in self.particles:
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            # A particle that's fallen past the bottom or drifted off either
            # side gets respawned at the top instead of removed — this keeps
            # the particle count constant forever, no pooling/GC needed.
            if particle.y > self.height or particle.x < -10 or particle.x > self.width + 10:
                self._respawn(particle)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all particles, as streaks (rain) or filled circles (snow/leaves)."""
        color = self.kind.color
        if self.kind.shape == "streak":
            # A short line trailing back along the particle's own velocity —
            # scaled by size so bigger drops get a slightly longer streak.
            for particle in self.particles:
                trail = 0.03 * max(1.0, particle.size)
                end = (particle.x - particle.vx * trail, particle.y - particle.vy * trail)
                pygame.draw.line(
                    surface, color, (particle.x, particle.y), end, max(1, round(particle.size))
                )
        else:
            for particle in self.particles:
                pygame.draw.circle(
                    surface,
                    color,
                    (round(particle.x), round(particle.y)),
                    max(1, round(particle.size)),
                )

    def _spawn(self, scattered: bool) -> Particle:
        kind = self.kind
        x = self.rng.uniform(0, self.width)
        # `scattered=True` (only used for the initial fill) places particles
        # anywhere in the frame, so the scene doesn't start empty and take a
        # moment to fill up; every respawn afterward starts just above the top.
        y = self.rng.uniform(0, self.height) if scattered else -10.0
        vy = self.rng.uniform(*kind.fall_speed_range)
        vx = self.rng.uniform(*kind.drift_range)
        size = self.rng.uniform(*kind.size_range)
        return Particle(x, y, vx, vy, size)

    def _respawn(self, particle: Particle) -> None:
        # Re-rolls a fresh particle's values into the existing object rather
        # than allocating a new one, so `self.particles` never changes length.
        fresh = self._spawn(scattered=False)
        particle.x, particle.y = fresh.x, fresh.y
        particle.vx, particle.vy, particle.size = fresh.vx, fresh.vy, fresh.size
