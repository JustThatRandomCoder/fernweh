"""Main game loop tying rendering to the pure logic layer."""

from __future__ import annotations

import random

import pygame

from fernweh import scenes, ui
from fernweh.afflictions import hardship_level
from fernweh.particles import ParticleSystem, particle_kind_for_weather
from fernweh.stages import Choice, apply_choice, choice_is_available, load_stages
from fernweh.state import GameState
from fernweh.tween import Tween, ease_out_quad

WINDOW_SIZE = (960, 600)
MARGIN = 48
FPS = 60
MAX_DESATURATION_AFFLICTIONS = 4
TRANSITION_DURATION = 0.6
TRANSITION_START_ALPHA = 255
TEXT_AREA_HEIGHT = 200
BUTTON_HEIGHT = 56
BUTTON_SPACING = 16


class Game:
    """Owns the pygame window, the game loop, and the current playthrough state."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Fernweh")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.hint_font = pygame.font.Font(None, 20)
        self.rng = random.Random()
        self.stages = load_stages()
        self.state = GameState()
        self.running = True
        self.particle_system: ParticleSystem | None = None
        self.typewriter = ui.TypewriterText("")
        self.choices: list[Choice] = []
        self.buttons: list[ui.ChoiceButton] = []
        self.dialog: ui.IntroDialog | None = ui.IntroDialog()
        self._synced_stage_index: int | None = None
        self._previous_frame: pygame.Surface | None = None
        self._transition: Tween | None = None
        self._sync_stage()

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
            elif self.dialog is not None:
                self._handle_dialog_event(event)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                self.dialog = ui.IntroDialog()
            elif event.type == pygame.KEYDOWN and not self.typewriter.done:
                self.typewriter.skip()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if not self.typewriter.done:
                    self.typewriter.skip()
                else:
                    self._handle_choice_click(event.pos)

    def _handle_dialog_event(self, event: pygame.event.Event) -> None:
        if event.type not in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            return
        self.dialog.advance()
        if self.dialog.done:
            self.dialog = None

    def _handle_choice_click(self, pos: tuple[int, int]) -> None:
        for button, choice in zip(self.buttons, self.choices):
            if button.contains(pos):
                apply_choice(self.state, choice, self.rng)
                return

    def _update(self, dt: float) -> None:
        self._sync_stage()
        if self.particle_system:
            self.particle_system.update(dt)
        if self._transition:
            self._transition.update(dt)
        self.typewriter.update(dt, hardship_level(self.state))
        mouse_pos = pygame.mouse.get_pos()
        mouse_down = pygame.mouse.get_pressed()[0]
        for button in self.buttons:
            button.update(dt, mouse_pos, mouse_down)

    def _sync_stage(self) -> None:
        if self.state.stage_index == self._synced_stage_index:
            return
        if self._synced_stage_index is not None:
            self._previous_frame = self.screen.copy()
            self._transition = Tween(
                TRANSITION_START_ALPHA, 0, TRANSITION_DURATION, easing=ease_out_quad
            )
        self._synced_stage_index = self.state.stage_index

        stage = self.stages[self.state.stage_index]
        kind_name = particle_kind_for_weather(stage.scene["weather"])
        self.particle_system = (
            ParticleSystem(kind_name, *WINDOW_SIZE, rng=self.rng) if kind_name else None
        )
        self.typewriter.reset(stage.situation)
        self._build_buttons(stage.choices)

    def _build_buttons(self, choices: tuple[Choice, ...]) -> None:
        self.choices = [] if self.state.ended else list(choices)
        self.buttons = []
        top = MARGIN + TEXT_AREA_HEIGHT
        for choice in self.choices:
            rect = pygame.Rect(MARGIN, top, WINDOW_SIZE[0] - 2 * MARGIN, BUTTON_HEIGHT)
            available = choice_is_available(choice, self.state.afflictions)
            self.buttons.append(
                ui.ChoiceButton(rect, choice.text, available, choice.unavailable_reason)
            )
            top += BUTTON_HEIGHT + BUTTON_SPACING

    def _draw(self) -> None:
        desaturation = hardship_level(self.state) / MAX_DESATURATION_AFFLICTIONS
        scenes.draw_scene(self.screen, self.state.season, desaturation)

        if self.particle_system:
            self.particle_system.draw(self.screen)

        text_rect = pygame.Rect(MARGIN, MARGIN, WINDOW_SIZE[0] - 2 * MARGIN, TEXT_AREA_HEIGHT)
        palette = scenes.palette_for_season(self.state.season)
        ui.draw_wrapped_text(
            self.screen, self.typewriter.visible_text(), self.font, palette.text, text_rect
        )

        if self.typewriter.done:
            for button in self.buttons:
                button.draw(self.screen, self.font, palette)

        if self._transition and not self._transition.done and self._previous_frame:
            self._previous_frame.set_alpha(round(self._transition.value))
            self.screen.blit(self._previous_frame, (0, 0))

        if self.dialog is not None:
            self.dialog.draw(self.screen, self.font, self.hint_font, palette)
        else:
            help_hint = self.hint_font.render("press H for help", True, ui.dim_color(palette.text))
            self.screen.blit(help_hint, (MARGIN, WINDOW_SIZE[1] - MARGIN))

        pygame.display.flip()


def run() -> None:
    """Start Fernweh. Used as the sole entry point from `main.py`."""
    Game().run()
