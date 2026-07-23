"""Text layout and UI primitives: wrapped text rendering, buttons, dialogs."""

from __future__ import annotations

import pygame

from fernweh.scenes import Palette
from fernweh.tween import ease_out_quad

Color = tuple[int, int, int]


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Split `text` into lines that each fit within `max_width` pixels."""
    words = text.split()
    lines: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate = " ".join([*current_words, word])
        if font.size(candidate)[0] <= max_width or not current_words:
            current_words.append(word)
        else:
            lines.append(" ".join(current_words))
            current_words = [word]

    if current_words:
        lines.append(" ".join(current_words))
    return lines


def draw_wrapped_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Color,
    rect: pygame.Rect,
    line_spacing: int = 6,
) -> None:
    """Render `text` word-wrapped inside `rect`, top-aligned."""
    lines = wrap_text(text, font, rect.width)
    y = rect.top
    for line in lines:
        rendered = font.render(line, True, color)
        surface.blit(rendered, (rect.left, y))
        y += rendered.get_height() + line_spacing


class TypewriterText:
    """Reveals a block of text one character at a time.

    Reveal speed scales down with hardship level (see `afflictions.hardship_level`)
    rather than any specific affliction, so a new affliction slows text automatically
    just by being counted, with no per-affliction rendering special case.
    """

    BASE_CHARS_PER_SECOND = 45.0
    SPEED_REDUCTION_PER_HARDSHIP_LEVEL = 0.30
    MIN_SPEED_MULTIPLIER = 0.25

    def __init__(self, text: str) -> None:
        self.text = text
        self.revealed = 0.0
        self.done = len(text) == 0

    def reset(self, text: str) -> None:
        """Start revealing a new block of text from the beginning."""
        self.text = text
        self.revealed = 0.0
        self.done = len(text) == 0

    def update(self, dt: float, hardship_level: int) -> None:
        """Advance the reveal by `dt` seconds at a hardship-scaled speed."""
        if self.done:
            return
        multiplier = max(
            self.MIN_SPEED_MULTIPLIER,
            1 - self.SPEED_REDUCTION_PER_HARDSHIP_LEVEL * hardship_level,
        )
        self.revealed += dt * self.BASE_CHARS_PER_SECOND * multiplier
        if self.revealed >= len(self.text):
            self.revealed = len(self.text)
            self.done = True

    def visible_text(self) -> str:
        """The portion of the text revealed so far."""
        return self.text[: int(self.revealed)]

    def skip(self) -> None:
        """Reveal the remaining text immediately."""
        self.revealed = len(self.text)
        self.done = True


class ChoiceButton:
    """A clickable choice button with eased hover/press feedback.

    Hover/press state is continuous (the mouse can enter or leave at any
    moment), so rather than one-shot `Tween` instances, an elapsed-time value
    is nudged toward 0 or `HOVER_ANIMATION_DURATION` each frame and the same
    `ease_out_quad` used for scene transitions maps it to a scale factor.
    """

    HOVER_ANIMATION_DURATION = 0.15
    HOVER_SCALE = 1.03
    PRESS_SCALE = 0.97

    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        available: bool = True,
        unavailable_reason: str | None = None,
    ) -> None:
        self.rect = rect
        self.text = text
        self.available = available
        self.unavailable_reason = unavailable_reason
        self.pressed = False
        self._hover_elapsed = 0.0

    def update(self, dt: float, mouse_pos: tuple[int, int], mouse_down: bool) -> None:
        """Advance hover/press animation state given the current mouse input."""
        hovering = self.available and self.rect.collidepoint(mouse_pos)
        direction = 1.0 if hovering else -1.0
        self._hover_elapsed = max(
            0.0, min(self.HOVER_ANIMATION_DURATION, self._hover_elapsed + direction * dt)
        )
        self.pressed = hovering and mouse_down

    def contains(self, pos: tuple[int, int]) -> bool:
        """Whether `pos` is inside this button and it can currently be chosen."""
        return self.available and self.rect.collidepoint(pos)

    @property
    def scale(self) -> float:
        """Current visual scale factor from hover/press animation."""
        hover_t = ease_out_quad(self._hover_elapsed / self.HOVER_ANIMATION_DURATION)
        scale = 1.0 + (self.HOVER_SCALE - 1.0) * hover_t
        return scale * self.PRESS_SCALE if self.pressed else scale

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, palette: Palette) -> None:
        """Draw the button, its label, and (if unavailable) the reason why."""
        scale = self.scale
        scaled_rect = self.rect.inflate(
            round(self.rect.width * (scale - 1)), round(self.rect.height * (scale - 1))
        )
        text_color = palette.text if self.available else dim_color(palette.text)
        pygame.draw.rect(surface, palette.ground, scaled_rect, border_radius=10)
        pygame.draw.rect(surface, text_color, scaled_rect, width=1, border_radius=10)

        label = self.text
        if not self.available and self.unavailable_reason:
            label = f"{self.text} — {self.unavailable_reason}"
        rendered = font.render(label, True, text_color)
        surface.blit(rendered, rendered.get_rect(center=scaled_rect.center))


def dim_color(color: Color) -> Color:
    """Darken a color toward black, used for unavailable/secondary text."""
    return tuple(round(channel * 0.5) for channel in color)


INTRO_PAGES: tuple[str, ...] = (
    "Fernweh is a walk from spring to winter, told a few minutes at a time.",
    "There is no combat, no timer, and no score on screen. Every stage is a small "
    "scene followed by a real choice between tradeoffs.",
    "Two things sustain you along the way: Energy and Supplies. Both drain as you "
    "travel, and some choices cost more of one to spare the other.",
    "Hardship follows as afflictions — conditions like exhaustion or illness that "
    "slow the telling and dim the color, until a choice along the road cures them.",
    "Reaching winter's end is the goal, however you arrive. Click or press any key " "to begin.",
)


class IntroDialog:
    """A short, click-through explanation shown before stage 1.

    Also reachable again from a pause/help option during play — the same
    dialog, just re-opened, not a separate help screen to keep in sync.
    """

    OVERLAY_ALPHA = 235

    def __init__(self, pages: tuple[str, ...] = INTRO_PAGES) -> None:
        self.pages = pages
        self.page_index = 0
        self.done = False

    def advance(self) -> None:
        """Move to the next page, or finish the dialog on the last one."""
        self.page_index += 1
        if self.page_index >= len(self.pages):
            self.done = True

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        hint_font: pygame.font.Font,
        palette: Palette,
    ) -> None:
        """Draw the current page over a translucent overlay covering the screen."""
        overlay = pygame.Surface(surface.get_size())
        overlay.fill(palette.sky_bottom)
        overlay.set_alpha(self.OVERLAY_ALPHA)
        surface.blit(overlay, (0, 0))

        margin = 64
        text_rect = pygame.Rect(margin, margin, surface.get_width() - 2 * margin, 240)
        draw_wrapped_text(surface, self.pages[self.page_index], font, palette.text, text_rect)

        hint = f"{self.page_index + 1} / {len(self.pages)}    click or press any key to continue"
        hint_surface = hint_font.render(hint, True, dim_color(palette.text))
        surface.blit(
            hint_surface,
            hint_surface.get_rect(
                midbottom=(surface.get_width() // 2, surface.get_height() - margin // 2)
            ),
        )
