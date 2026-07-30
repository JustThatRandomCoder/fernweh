"""Main game loop tying rendering to the pure logic layer."""

from __future__ import annotations

import random

import pygame

from fernweh import save, scenes, ui
from fernweh.afflictions import hardship_level
from fernweh.ending import generate_ending
from fernweh.particles import ParticleSystem, particle_kind_for_weather
from fernweh.stages import Choice, SceneCharacter, apply_choice, choice_is_available, load_stages
from fernweh.state import MAX_COMPANIONS, GameState
from fernweh.tween import Passage, Tween, ease_in_out_quad, ease_out_quad

COMPANY_FULL_REASON = "your company is already full"

WINDOW_SIZE = (960, 600)
MARGIN = 48
FPS = 60
MAX_DESATURATION_AFFLICTIONS = 4
TRANSITION_DURATION = 0.6
TRANSITION_START_ALPHA = 255
# How long a between-stage passage plays before the next question appears,
# and the horizontal span (as fractions of the window width) the traveler
# silhouette walks across during it — kept well inside the edges so the
# figure never clips off-screen mid-stride.
PASSAGE_DURATION = 3.2
PASSAGE_X_START = 0.08
PASSAGE_X_END = 0.92
TEXT_AREA_HEIGHT = 200
TEXT_PANEL_PADDING = 20
BUTTON_HEIGHT = 56
BUTTON_SPACING = 20
BUTTON_TOP_GAP = 28
KEEPSAKES_AREA_HEIGHT = 120
RESTART_LABEL = "Begin a new journey"
# The close-up portrait sits inset in the top-right corner of the text panel,
# for stages whose situation describes a specific NPC — the wrapped
# situation text narrows to make room for it only on those stages.
PORTRAIT_SIZE = 132
PORTRAIT_GAP = 20
# How far behind the leading traveler each companion walks, as a fraction of
# window width, staggered by their position in the party — keeps a growing
# roster from clumping into one silhouette.
PARTY_TRAIL_GAP = 0.045
# A rest passage seats the whole party in a row on a bench instead of walking
# them. `REST_SEAT_SPACING` is the horizontal gap between neighbours (as a
# fraction of window width), `REST_SEAT_Y_RATIO` the height of the bench seat
# (as a fraction of window height, tuned so seated feet land on the path), and
# the width fractions bound the bench so a solo traveler still gets a real
# bench and a full party still fits on one.
REST_SEAT_SPACING = 0.06
REST_SEAT_Y_RATIO = 0.9
REST_BENCH_MIN_WIDTH_RATIO = 0.16
REST_BENCH_PADDING_RATIO = 0.05
# The start menu shows at most this many of the most-recently-updated saves,
# so a long play history never pushes the "begin a new journey" button (or
# the oldest, least-relevant saves) off the bottom of the window.
MAX_VISIBLE_SAVES = 5
MENU_TOP = 150


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
        # A placeholder journey exists from the very first frame (so the menu
        # has a season/scene to render behind it), but it isn't "the" game
        # until `_start_new_game`/`_continue_game` replaces it — no autosave
        # happens until then.
        self.state = GameState()
        self.save_id = ""
        self._save_created_at: str | None = None
        self.running = True
        self.particle_system: ParticleSystem | None = None
        self.typewriter = ui.TypewriterText("")
        self.choices: list[Choice] = []
        self.buttons: list[ui.ChoiceButton] = []
        # No intro dialog until a game actually starts — the start menu comes
        # first, and only "Begin a new journey" shows the dialog afterward;
        # continuing a save skips straight into play.
        self.dialog: ui.IntroDialog | None = None
        self.keepsakes: list[str] = []
        self._synced_stage_index: int | None = None
        self._synced_ended = False
        self._previous_frame: pygame.Surface | None = None
        self._transition: Tween | None = None
        # Set while a between-stage travel sequence is playing — no question
        # is on screen and no logic-layer state changes, just the traveler
        # silhouette walking the path. None the rest of the time.
        self._passage: Passage | None = None
        # Whether the current passage is a "rest" sequence (the party seated on
        # a bench) rather than the usual walk. Set from the chosen option's
        # `rest` flag when the passage starts; only meaningful while
        # `self._passage` is not None.
        self._passage_resting = False
        # Rolled once per journey (and re-rolled on restart in `_restart`) so
        # the traveler has a consistent look across every passage within one
        # playthrough, but a different one from the last playthrough.
        self.traveler_appearance = scenes.random_person_appearance(self.rng)
        # The current stage's NPC portrait, if its scene describes one — a
        # (SceneCharacter, PersonAppearance) pair rebuilt each stage sync, or
        # None on stages with an empty landscape (most of them).
        self._stage_character: tuple[SceneCharacter, scenes.PersonAppearance] | None = None
        # The current stage's landmark (bridge, stream, building), drawn into
        # the landscape so the scene matches the situation text — None on
        # stages the generic season landscape already covers, and on the
        # ending screen. Set each stage sync.
        self._stage_landmark: str | None = None
        # The landmark carried through the current passage: whatever the stage
        # the player just left showed, so the walk/rest sequence keeps that
        # feature on screen (you walk across the bridge you chose to cross)
        # rather than blanking it the instant a choice resolves.
        self._passage_landmark: str | None = None
        # Every companion's appearance, keyed by id, learned the moment their
        # recruiting stage's portrait is first shown — so a companion who
        # joins keeps looking exactly like their portrait once they start
        # walking with the traveler in later passages (see `_start_passage`).
        self._companion_appearances: dict[str, scenes.PersonAppearance] = {}
        # Seconds since startup, fed to scenes.draw_scene so clouds can drift
        # continuously — tracked here rather than in scenes.py, which stays a
        # pure function of its arguments with no state of its own.
        self._elapsed = 0.0
        # Shown first, before any stage: lets the player start fresh or pick
        # up a previous journey instead of always dropping them at stage 0.
        self.menu_active = True
        self.menu_saves: list[save.SaveSummary] = []
        self.menu_buttons: list[ui.ChoiceButton] = []
        self._build_menu()

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
        # the start menu swallows all input until a journey is chosen, then
        # an open dialog swallows all input, then a playing passage swallows
        # input too (any key/click just skips straight to the next stage),
        # then "H" reopens the dialog, then any key/click first skips an
        # in-progress typewriter reveal before it's allowed to do anything
        # else (like clicking a choice).
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif self.menu_active:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_menu_click(event.pos)
            elif self.dialog is not None:
                self._handle_dialog_event(event)
            elif self._passage is not None:
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self._passage.skip()
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

    def _handle_menu_click(self, pos: tuple[int, int]) -> None:
        for index, button in enumerate(self.menu_buttons):
            if not button.contains(pos):
                continue
            if index == 0:
                self._start_new_game()
            else:
                self._continue_game(self.menu_saves[index - 1].id)
            return

    def _build_menu(self) -> None:
        """Lay out the start menu: "begin a new journey" plus recent saves."""
        self.menu_saves = save.list_saves()[:MAX_VISIBLE_SAVES]
        self.menu_buttons = []
        button_width = WINDOW_SIZE[0] - 2 * MARGIN
        top = MENU_TOP
        labels = ["Begin a new journey", *(s.describe() for s in self.menu_saves)]
        for label in labels:
            rect = pygame.Rect(MARGIN, top, button_width, BUTTON_HEIGHT)
            self.menu_buttons.append(ui.ChoiceButton(rect, label))
            top += BUTTON_HEIGHT + BUTTON_SPACING

    def _handle_choice_click(self, pos: tuple[int, int]) -> None:
        if self.state.ended:
            if self.buttons and self.buttons[0].contains(pos):
                self._restart()
            return
        for button, choice in zip(self.buttons, self.choices):
            if button.contains(pos):
                apply_choice(self.state, choice, self.rng)
                # Every choice is saved to disk the instant it resolves, not
                # batched or delayed — so killing the process (closing the
                # terminal, Ctrl+C) a moment later, even mid-passage, never
                # loses the choice that was just made.
                self._autosave()
                # A fatal choice ends the journey immediately — no travel
                # sequence, the ending sync below (via the normal _update
                # loop) takes over right away. Otherwise, the walk to the
                # next stage plays before its question appears.
                if not self.state.ended:
                    self._start_passage(resting=choice.rest)
                return

    def _autosave(self) -> None:
        """Persist the current playthrough to `self.save_id` on disk."""
        companion_appearances = {
            companion.id: scenes.person_appearance_to_dict(
                self._companion_appearances.get(
                    companion.id, scenes.appearance_for_seed(companion.id)
                )
            )
            for companion in self.state.companions
        }
        save.save_game(
            self.save_id,
            self.state,
            scenes.person_appearance_to_dict(self.traveler_appearance),
            companion_appearances,
            created_at=self._save_created_at,
        )

    def _start_new_game(self) -> None:
        """Begin a fresh journey under a brand-new save id."""
        self.save_id = save.new_save_id()
        self._save_created_at = save.now_iso()
        self.state = GameState()
        self.traveler_appearance = scenes.random_person_appearance(self.rng)
        self._companion_appearances = {}
        self._stage_character = None
        self._synced_stage_index = None
        self._synced_ended = False
        self.menu_active = False
        self.dialog = ui.IntroDialog()
        self._sync_stage()

    def _continue_game(self, save_id: str) -> None:
        """Resume a previously saved journey exactly where it was left off."""
        loaded = save.load_game(save_id)
        self.save_id = save_id
        self._save_created_at = loaded.created_at
        self.state = loaded.state
        self.traveler_appearance = scenes.person_appearance_from_dict(loaded.traveler_appearance)
        self._companion_appearances = {
            companion_id: scenes.person_appearance_from_dict(data)
            for companion_id, data in loaded.companion_appearances.items()
        }
        self._stage_character = None
        self._synced_stage_index = None
        self._synced_ended = False
        self.menu_active = False
        # A returning player already knows how to play — no intro dialog,
        # and the situation/ending text they're resuming into shows fully
        # revealed immediately rather than replaying the typewriter.
        self.dialog = None
        self._sync_stage()
        self.typewriter.skip()

    def _start_passage(self, resting: bool = False) -> None:
        """Begin the text-free travel sequence shown between two stages.

        `resting` picks which sequence plays: the default walk along the path,
        or — when the player chose a sit/rest option — the party seated on a
        bench for a beat before the next stage. Both are the same timed,
        skippable `Passage`; only what `_draw_passage` renders differs.
        """
        self._passage = Passage(PASSAGE_DURATION, rng=self.rng)
        self._passage_resting = resting
        # Carry the just-left stage's landmark through the walk/rest so its
        # scenery (the bridge, the stream) stays on screen while the traveler
        # crosses it, instead of vanishing the moment the choice resolved.
        self._passage_landmark = self._stage_landmark
        self.buttons = []
        self.choices = []

    def _restart(self) -> None:
        # A restart from the ending screen is a new journey under a new save
        # id — it doesn't overwrite the finished one, which stays in the
        # start menu's list as something the player can still revisit.
        self._start_new_game()

    def _update(self, dt: float) -> None:
        self._elapsed += dt
        if self.menu_active:
            mouse_pos = pygame.mouse.get_pos()
            mouse_down = pygame.mouse.get_pressed()[0]
            for button in self.menu_buttons:
                button.update(dt, mouse_pos, mouse_down)
            return
        if self._passage is not None:
            # Weather keeps animating through the walk (it's still the same
            # season until the new stage loads), but nothing else about the
            # old stage's UI does — there's no typewriter or buttons showing.
            self._passage.update(dt)
            if self.particle_system:
                self.particle_system.update(dt)
            if self._passage.done:
                self._passage = None
                self._sync_stage()
            return
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
        self._stage_landmark = stage.landmark

        if stage.character is None:
            self._stage_character = None
        else:
            appearance = scenes.person_appearance_from_names(
                stage.character.skin, stage.character.hair, stage.character.tunic
            )
            self._stage_character = (stage.character, appearance)
            # If this stage's NPC is also recruitable this turn, remember
            # their exact look now — so if the player invites them, the
            # companion who starts walking in passages afterward is visibly
            # the same person as the portrait that was just on screen.
            for choice in stage.choices:
                if choice.companion is not None:
                    self._companion_appearances[choice.companion["id"]] = appearance

    def _sync_ending(self) -> None:
        # A parallel sync path to _sync_stage: reaching the ending doesn't
        # necessarily mean stage_index changed (a mid-stage failure ends the
        # game without advancing), so it needs its own "have we already
        # synced this?" flag rather than reusing _synced_stage_index.
        if self._synced_ended:
            return
        self._synced_ended = True
        self._stage_character = None
        # The journey's end is an open snow field, not any single stage's
        # landmark — clear it so no bridge/building lingers behind the ending.
        self._stage_landmark = None
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
        # A real gap below the text panel, not just the panel's own bottom
        # edge, so buttons read as a separate group rather than sitting flush
        # against the panel's border.
        top = MARGIN + TEXT_AREA_HEIGHT + BUTTON_TOP_GAP
        for choice in self.choices:
            rect = pygame.Rect(MARGIN, top, WINDOW_SIZE[0] - 2 * MARGIN, BUTTON_HEIGHT)
            company_full = (
                choice.companion is not None and len(self.state.companions) >= MAX_COMPANIONS
            )
            available = choice_is_available(choice, self.state.afflictions) and not company_full
            reason = COMPANY_FULL_REASON if company_full else choice.unavailable_reason
            self.buttons.append(ui.ChoiceButton(rect, choice.text, available, reason))
            top += BUTTON_HEIGHT + BUTTON_SPACING

    def _draw_menu(self, palette: scenes.Palette) -> None:
        """Draw the start menu: title, then "begin a new journey" plus recent saves."""
        title = self.font.render("Fernweh", True, palette.text)
        self.screen.blit(title, title.get_rect(midtop=(WINDOW_SIZE[0] // 2, 56)))
        subtitle_text = (
            "choose a journey to continue, or begin a new one"
            if self.menu_saves
            else "a walk from spring to winter"
        )
        subtitle = self.hint_font.render(subtitle_text, True, ui.dim_color(palette.text))
        self.screen.blit(subtitle, subtitle.get_rect(midtop=(WINDOW_SIZE[0] // 2, 96)))
        for button in self.menu_buttons:
            button.draw(self.screen, self.font, palette)

    def _draw_passage(self, palette: scenes.Palette) -> None:
        """Draw the current travel sequence — a walk, or a seated rest — no UI on screen.

        Dispatches on `self._passage_resting`: a rest passage seats the party
        on a bench, every other passage walks them along the path. Both share
        the "click to continue" hint and the empty (panel-free) screen.
        """
        assert self._passage is not None
        if self._passage_resting:
            self._draw_rest_passage(palette)
        else:
            self._draw_walk_passage(palette)
        hint = self.hint_font.render("click to continue", True, ui.dim_color(palette.text))
        self.screen.blit(hint, (MARGIN, WINDOW_SIZE[1] - MARGIN))

    def _draw_rest_passage(self, palette: scenes.Palette) -> None:
        """Draw the party seated on a bench during a rest passage.

        The traveler and every companion sit in a row on a single bench,
        centered in the foreground — the resting counterpart to the walking
        party in `_draw_walk_passage`. Recruitment order is preserved left to
        right (traveler first), so a party that grows over the journey fills
        the bench in the same order it forms on the road.
        """
        # The seated party is the traveler plus each companion, in the order
        # they joined — appearances pulled from the same per-companion cache
        # the walking passage uses, so a companion looks identical sitting or
        # walking.
        seated = [self.traveler_appearance]
        for companion in self.state.companions:
            seated.append(
                self._companion_appearances.get(
                    companion.id, scenes.appearance_for_seed(companion.id)
                )
            )

        # Center the row horizontally and size the bench to span it, with a
        # little padding past the outermost sitter on each side and a floor so
        # a solo traveler still gets a proper bench rather than a stool.
        spacing = WINDOW_SIZE[0] * REST_SEAT_SPACING
        row_width = spacing * (len(seated) - 1)
        center_x = WINDOW_SIZE[0] / 2
        first_x = center_x - row_width / 2
        seat_y = WINDOW_SIZE[1] * REST_SEAT_Y_RATIO
        bench_width = max(
            WINDOW_SIZE[0] * REST_BENCH_MIN_WIDTH_RATIO,
            row_width + WINDOW_SIZE[0] * REST_BENCH_PADDING_RATIO * 2,
        )
        scenes.draw_bench(self.screen, palette, center_x, seat_y, bench_width)
        # Each sitter gets a different idle-breathing phase so the row doesn't
        # rise and fall in unison — the seated equivalent of the walkers'
        # staggered gait offsets.
        for index, appearance in enumerate(seated):
            scenes.draw_person_seated(
                self.screen,
                palette,
                first_x + index * spacing,
                seat_y,
                appearance,
                self._elapsed,
                idle_phase=index * 1.7,
            )

    def _draw_walk_passage(self, palette: scenes.Palette) -> None:
        """Draw the traveler mid-walk, with no text panel or buttons on screen.

        `ease_in_out_quad` on the walk fraction means the traveler starts and
        ends each passage slowly (as if stepping off from and settling into
        a stop) rather than moving at a robotic constant speed. Every
        companion currently in the party walks along too, trailing behind in
        recruitment order — this is what makes a choice to invite someone
        keep showing up on the road for the rest of the journey, not just in
        the one passage right after they join.
        """
        assert self._passage is not None
        walked = ease_in_out_quad(self._passage.progress)
        x_ratio = PASSAGE_X_START + (PASSAGE_X_END - PASSAGE_X_START) * walked

        # Companions are drawn furthest-back first, the leading traveler
        # last, so nearer figures correctly overlap those trailing behind
        # them rather than the other way around. `trailing` counts from 1
        # (the most recently recruited companion, walking right behind the
        # traveler) up to the party size (the very first companion, walking
        # furthest back) — drawn in descending `trailing` order.
        party_size = len(self.state.companions)
        for trailing in range(party_size, 0, -1):
            companion = self.state.companions[party_size - trailing]
            companion_x = x_ratio - trailing * PARTY_TRAIL_GAP
            if companion_x < 0.0:
                continue
            appearance = self._companion_appearances.get(
                companion.id, scenes.appearance_for_seed(companion.id)
            )
            scenes.draw_traveler(
                self.screen,
                palette,
                companion_x,
                self._elapsed,
                appearance,
                gait_offset=self._passage.gait_offset + trailing * 1.3,
                gait_speed=self._passage.gait_speed,
            )

        scenes.draw_traveler(
            self.screen,
            palette,
            x_ratio,
            self._elapsed,
            self.traveler_appearance,
            gait_offset=self._passage.gait_offset,
            gait_speed=self._passage.gait_speed,
        )

    def _draw(self) -> None:
        # `desaturation` is the one number driving all hardship visuals: 0 at
        # full health, capping out at MAX_DESATURATION_AFFLICTIONS active
        # afflictions. It's used both for the background (via draw_scene) and
        # for every UI surface below (via the desaturated `palette`).
        desaturation = hardship_level(self.state) / MAX_DESATURATION_AFFLICTIONS
        # Which landmark (if any) belongs in the landscape depends on what's on
        # screen: the menu shows none, a passage keeps the stage it's leaving,
        # and a live stage shows its own. Computed here so the single
        # draw_scene call stays the one place the background is drawn.
        if self.menu_active:
            scene_landmark = None
        elif self._passage is not None:
            scene_landmark = self._passage_landmark
        else:
            scene_landmark = self._stage_landmark
        scenes.draw_scene(
            self.screen, self.state.season, desaturation, self._elapsed, landmark=scene_landmark
        )

        if self.particle_system:
            self.particle_system.draw(self.screen)

        # Same desaturation applied to the palette used for UI drawing below,
        # so buttons/panels darken and mute in step with the background —
        # `text` stays untouched inside desaturate_palette, so labels stay
        # legible no matter how harsh the journey has gotten.
        palette = scenes.desaturate_palette(
            scenes.palette_for_season(self.state.season), desaturation
        )

        if self.menu_active:
            self._draw_menu(palette)
            pygame.display.flip()
            return

        if self._passage is not None:
            self._draw_passage(palette)
            pygame.display.flip()
            return

        # The backing panel behind the situation text grows to also cover the
        # keepsakes list once the journey has ended and that text is showing.
        panel_height = TEXT_AREA_HEIGHT
        if self.typewriter.done and self.state.ended:
            panel_height += KEEPSAKES_AREA_HEIGHT
        # Now that buttons start BUTTON_TOP_GAP below the text area instead of
        # flush against it, the panel can pad symmetrically on all sides
        # without touching the first button.
        text_panel_rect = pygame.Rect(
            MARGIN - TEXT_PANEL_PADDING,
            MARGIN - TEXT_PANEL_PADDING,
            WINDOW_SIZE[0] - 2 * MARGIN + 2 * TEXT_PANEL_PADDING,
            panel_height + 2 * TEXT_PANEL_PADDING,
        )
        # Fully opaque: with weather particles now animating behind it (visible
        # rain streaks, not near-invisible dots), any translucency here would
        # let their motion bleed through and animate inside the text card —
        # the same ghosting problem the intro dialog's card already fixed.
        ui.draw_panel(self.screen, text_panel_rect, palette.panel, ui.dim_color(palette.panel))
        text_width = WINDOW_SIZE[0] - 2 * MARGIN
        if self._stage_character is not None:
            text_width -= PORTRAIT_SIZE + PORTRAIT_GAP
        text_rect = pygame.Rect(MARGIN, MARGIN, text_width, TEXT_AREA_HEIGHT)
        ui.draw_wrapped_text(
            self.screen, self.typewriter.visible_text(), self.font, palette.text, text_rect
        )
        if self._stage_character is not None:
            character, appearance = self._stage_character
            portrait_rect = pygame.Rect(
                WINDOW_SIZE[0] - MARGIN - PORTRAIT_SIZE, MARGIN, PORTRAIT_SIZE, PORTRAIT_SIZE
            )
            scenes.draw_portrait(
                self.screen,
                portrait_rect,
                palette,
                appearance,
                character.pose,
                self._elapsed,
                prop=character.prop,
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
