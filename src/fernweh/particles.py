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


WEATHER_KINDS: dict[str, ParticleKind] = {
    "drizzle": ParticleKind(
        color=(150, 170, 190),
        size_range=(1, 2),
        fall_speed_range=(220, 340),
        drift_range=(-10, 10),
        count=90,
    ),
    "snow": ParticleKind(
        color=(255, 255, 255),
        size_range=(2, 4),
        fall_speed_range=(25, 65),
        drift_range=(-20, 20),
        count=70,
    ),
    "falling_leaves": ParticleKind(
        color=(196, 120, 48),
        size_range=(3, 5),
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
            if particle.y > self.height or particle.x < -10 or particle.x > self.width + 10:
                self._respawn(particle)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all particles as small filled circles onto `surface`."""
        color = self.kind.color
        for particle in self.particles:
            pygame.draw.circle(
                surface, color, (int(particle.x), int(particle.y)), max(1, round(particle.size))
            )

    def _spawn(self, scattered: bool) -> Particle:
        kind = self.kind
        x = self.rng.uniform(0, self.width)
        y = self.rng.uniform(0, self.height) if scattered else -10.0
        vy = self.rng.uniform(*kind.fall_speed_range)
        vx = self.rng.uniform(*kind.drift_range)
        size = self.rng.uniform(*kind.size_range)
        return Particle(x, y, vx, vy, size)

    def _respawn(self, particle: Particle) -> None:
        fresh = self._spawn(scattered=False)
        particle.x, particle.y = fresh.x, fresh.y
        particle.vx, particle.vy, particle.size = fresh.vx, fresh.vy, fresh.size
