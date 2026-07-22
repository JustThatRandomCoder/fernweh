"""Main game loop tying rendering to the pure logic layer."""

from __future__ import annotations

import random

import pygame

from fernweh import scenes, ui
from fernweh.afflictions import hardship_level
from fernweh.particles import ParticleSystem, particle_kind_for_weather
from fernweh.stages import load_stages
from fernweh.state import GameState

WINDOW_SIZE = (960, 600)
MARGIN = 48
FPS = 60
MAX_DESATURATION_AFFLICTIONS = 4


class Game:
    """Owns the pygame window, the game loop, and the current playthrough state."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Fernweh")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.rng = random.Random()
        self.stages = load_stages()
        self.state = GameState()
        self.running = True
        self.particle_system: ParticleSystem | None = None
        self._synced_stage_index: int | None = None
        self._sync_particle_system()

    def run(self) -> None:
        """Run the main loop until the window is closed."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def _update(self, dt: float) -> None:
        self._sync_particle_system()
        if self.particle_system:
            self.particle_system.update(dt)

    def _sync_particle_system(self) -> None:
        if self.state.stage_index == self._synced_stage_index:
            return
        self._synced_stage_index = self.state.stage_index
        stage = self.stages[self.state.stage_index]
        kind_name = particle_kind_for_weather(stage.scene["weather"])
        self.particle_system = (
            ParticleSystem(kind_name, *WINDOW_SIZE, rng=self.rng) if kind_name else None
        )

    def _draw(self) -> None:
        desaturation = hardship_level(self.state) / MAX_DESATURATION_AFFLICTIONS
        scenes.draw_scene(self.screen, self.state.season, desaturation)

        if self.particle_system:
            self.particle_system.draw(self.screen)

        stage = self.stages[self.state.stage_index]
        text_rect = pygame.Rect(MARGIN, MARGIN, WINDOW_SIZE[0] - 2 * MARGIN, 200)
        palette = scenes.palette_for_season(self.state.season)
        ui.draw_wrapped_text(self.screen, stage.situation, self.font, palette.text, text_rect)

        pygame.display.flip()


def run() -> None:
    """Start Fernweh. Used as the sole entry point from `main.py`."""
    Game().run()
