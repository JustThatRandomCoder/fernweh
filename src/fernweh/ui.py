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
