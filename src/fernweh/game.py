"""Main game loop tying rendering to the pure logic layer."""

from __future__ import annotations

import random

import pygame

from fernweh import scenes, ui
from fernweh.afflictions import hardship_level
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

    def run(self) -> None:
        """Run the main loop until the window is closed."""
        while self.running:
            self._handle_events()
            self._draw()
            self.clock.tick(FPS)
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def _draw(self) -> None:
        desaturation = hardship_level(self.state) / MAX_DESATURATION_AFFLICTIONS
        scenes.draw_scene(self.screen, self.state.season, desaturation)

        stage = self.stages[self.state.stage_index]
        text_rect = pygame.Rect(MARGIN, MARGIN, WINDOW_SIZE[0] - 2 * MARGIN, 200)
        palette = scenes.palette_for_season(self.state.season)
        ui.draw_wrapped_text(self.screen, stage.situation, self.font, palette.text, text_rect)

        pygame.display.flip()


def run() -> None:
    """Start Fernweh. Used as the sole entry point from `main.py`."""
    Game().run()
