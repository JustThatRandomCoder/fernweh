"""Text layout and UI primitives: wrapped text rendering, buttons, dialogs."""

from __future__ import annotations

import pygame

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
