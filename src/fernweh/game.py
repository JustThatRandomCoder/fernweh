"""Main game loop tying rendering to the pure logic layer."""

from __future__ import annotations

import random

import pygame

from fernweh import scenes, ui
from fernweh.afflictions import hardship_level
from fernweh.ending import generate_ending
from fernweh.particles import ParticleSystem, particle_kind_for_weather
from fernweh.stages import Choice, apply_choice, choice_is_available, load_stages
from fernweh.state import MAX_COMPANIONS, GameState
from fernweh.tween import Tween, ease_out_quad

COMPANY_FULL_REASON = "your company is already full"

WINDOW_SIZE = (960, 600)
MARGIN = 48
FPS = 60
MAX_DESATURATION_AFFLICTIONS = 4
TRANSITION_DURATION = 0.6
TRANSITION_START_ALPHA = 255
TEXT_AREA_HEIGHT = 200
TEXT_PANEL_PADDING = 20
TEXT_PANEL_ALPHA = 225
BUTTON_HEIGHT = 56
BUTTON_SPACING = 16
KEEPSAKES_AREA_HEIGHT = 120
RESTART_LABEL = "Begin a new journey"


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
        self.keepsakes: list[str] = []
        self._synced_stage_index: int | None = None
        self._synced_ended = False
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
        # Branches are checked in priority order: quitting always wins, then
        # an open dialog swallows all input, then "H" reopens the dialog,
        # then any key/click first skips an in-progress typewriter reveal
        # before it's allowed to do anything else (like clicking a choice).
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
        if self.state.ended:
            if self.buttons and self.buttons[0].contains(pos):
                self._restart()
            return
        for button, choice in zip(self.buttons, self.choices):
            if button.contains(pos):
                apply_choice(self.state, choice, self.rng)
                return

    def _restart(self) -> None:
        self.state = GameState()
        self._synced_stage_index = None
        self._synced_ended = False
        self._sync_stage()

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
        # The single source of truth for "the displayed stage changed": it's
        # keyed off comparing state.stage_index to the last-synced value, so
        # it runs exactly once per stage change no matter how many events
        # (or frames) triggered the underlying state update.
        if self.state.ended:
            self._sync_ending()
            return
        if self.state.stage_index == self._synced_stage_index:
            return
        # Snapshot the current frame and start a crossfade — skipped on the
        # very first sync (there's no previous stage to fade from yet).
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

    def _sync_ending(self) -> None:
        # A parallel sync path to _sync_stage: reaching the ending doesn't
        # necessarily mean stage_index changed (a mid-stage failure ends the
        # game without advancing), so it needs its own "have we already
        # synced this?" flag rather than reusing _synced_stage_index.
        if self._synced_ended:
            return
        self._synced_ended = True
        self._previous_frame = self.screen.copy()
        self._transition = Tween(
            TRANSITION_START_ALPHA, 0, TRANSITION_DURATION, easing=ease_out_quad
        )

        summary = generate_ending(self.state)
        self.keepsakes = summary.keepsakes
        self.typewriter.reset(summary.prose)

        restart_rect = pygame.Rect(
            MARGIN,
            WINDOW_SIZE[1] - MARGIN - BUTTON_HEIGHT,
            WINDOW_SIZE[0] - 2 * MARGIN,
            BUTTON_HEIGHT,
        )
        self.buttons = [ui.ChoiceButton(restart_rect, RESTART_LABEL)]
        self.choices = []

    def _build_buttons(self, choices: tuple[Choice, ...]) -> None:
        self.choices = [] if self.state.ended else list(choices)
        self.buttons = []
        top = MARGIN + TEXT_AREA_HEIGHT
        for choice in self.choices:
            rect = pygame.Rect(MARGIN, top, WINDOW_SIZE[0] - 2 * MARGIN, BUTTON_HEIGHT)
            company_full = (
                choice.companion is not None and len(self.state.companions) >= MAX_COMPANIONS
            )
            available = choice_is_available(choice, self.state.afflictions) and not company_full
            reason = COMPANY_FULL_REASON if company_full else choice.unavailable_reason
            self.buttons.append(ui.ChoiceButton(rect, choice.text, available, reason))
            top += BUTTON_HEIGHT + BUTTON_SPACING

    def _draw(self) -> None:
        # `desaturation` is the one number driving all hardship visuals: 0 at
        # full health, capping out at MAX_DESATURATION_AFFLICTIONS active
        # afflictions. It's used both for the background (via draw_scene) and
        # for every UI surface below (via the desaturated `palette`).
        desaturation = hardship_level(self.state) / MAX_DESATURATION_AFFLICTIONS
        scenes.draw_scene(self.screen, self.state.season, desaturation)

        if self.particle_system:
            self.particle_system.draw(self.screen)

        # Same desaturation applied to the palette used for UI drawing below,
        # so buttons/panels darken and mute in step with the background —
        # `text` stays untouched inside desaturate_palette, so labels stay
        # legible no matter how harsh the journey has gotten.
        palette = scenes.desaturate_palette(
            scenes.palette_for_season(self.state.season), desaturation
        )

        # The backing panel behind the situation text grows to also cover the
        # keepsakes list once the journey has ended and that text is showing.
        panel_height = TEXT_AREA_HEIGHT
        if self.typewriter.done and self.state.ended:
            panel_height += KEEPSAKES_AREA_HEIGHT
        text_panel_rect = pygame.Rect(
            MARGIN - TEXT_PANEL_PADDING,
            MARGIN - TEXT_PANEL_PADDING,
            WINDOW_SIZE[0] - 2 * MARGIN + 2 * TEXT_PANEL_PADDING,
            panel_height + TEXT_PANEL_PADDING,
        )
        ui.draw_panel(
            self.screen,
            text_panel_rect,
            palette.panel,
            ui.dim_color(palette.panel),
            alpha=TEXT_PANEL_ALPHA,
        )
        text_rect = pygame.Rect(MARGIN, MARGIN, WINDOW_SIZE[0] - 2 * MARGIN, TEXT_AREA_HEIGHT)
        ui.draw_wrapped_text(
            self.screen, self.typewriter.visible_text(), self.font, palette.text, text_rect
        )

        if self.typewriter.done and self.state.ended:
            keepsakes_rect = pygame.Rect(
                MARGIN,
                MARGIN + TEXT_AREA_HEIGHT,
                WINDOW_SIZE[0] - 2 * MARGIN,
                KEEPSAKES_AREA_HEIGHT,
            )
            keepsakes_text = (
                "Keepsakes: " + ", ".join(self.keepsakes)
                if self.keepsakes
                else "You carry no keepsakes from this road."
            )
            ui.draw_wrapped_text(
                self.screen,
                keepsakes_text,
                self.hint_font,
                ui.dim_color(palette.text),
                keepsakes_rect,
            )

        if self.typewriter.done:
            for button in self.buttons:
                button.draw(self.screen, self.font, palette)

        # Crossfade: the previous stage's frozen frame is blitted on top of
        # the newly-drawn current stage, fading its own alpha from opaque to
        # 0 over the transition — the "new" content is drawn once and simply
        # revealed underneath as the old frame fades out.
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
    """Start Fernweh. Used as the sole entry point from `fernweh.py`."""
    Game().run()
