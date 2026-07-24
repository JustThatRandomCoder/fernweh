"""Season palettes and procedural scene backgrounds.

No art assets — every scene is a vertical sky gradient plus a ground band,
using pygame primitives only. Palette choice is keyed purely off season name,
so adding a new season/palette never touches the game loop.
"""

from __future__ import annotations

import pygame

Color = tuple[int, int, int]


class Palette:
    """The colors used to render one season's scenes.

    `ground` and `panel` are deliberately separate: `ground` is tuned to look
    right as outdoor terrain and is not guaranteed to contrast against `text`,
    while `panel` is a near-white card tone tuned per season purely so that
    `text` reaches WCAG AA (>=4.5:1) against it — UI surfaces (buttons,
    dialogs, text backings) always use `panel`, never `ground`.
    """

    def __init__(
        self,
        sky_top: Color,
        sky_bottom: Color,
        ground: Color,
        panel: Color,
        text: Color,
    ) -> None:
        self.sky_top = sky_top
        self.sky_bottom = sky_bottom
        self.ground = ground
        self.panel = panel
        self.text = text


SEASON_PALETTES: dict[str, Palette] = {
    "spring": Palette(
        sky_top=(198, 224, 205),
        sky_bottom=(232, 240, 214),
        ground=(150, 181, 137),
        panel=(240, 244, 232),
        text=(48, 58, 46),
    ),
    "summer": Palette(
        sky_top=(247, 214, 150),
        sky_bottom=(255, 236, 196),
        ground=(196, 168, 96),
        panel=(250, 240, 214),
        text=(66, 50, 24),
    ),
    "autumn": Palette(
        sky_top=(214, 150, 96),
        sky_bottom=(236, 190, 120),
        ground=(140, 84, 48),
        panel=(247, 228, 202),
        text=(56, 34, 18),
    ),
    "winter": Palette(
        sky_top=(202, 214, 224),
        sky_bottom=(232, 238, 244),
        ground=(214, 222, 230),
        panel=(240, 245, 250),
        text=(40, 48, 56),
    ),
}

GROUND_HEIGHT_RATIO = 0.28


def palette_for_season(season: str) -> Palette:
    """Return the rendering palette for a season name."""
    return SEASON_PALETTES[season]


def desaturate_palette(palette: Palette, amount: float) -> Palette:
    """Return a copy of `palette` with its scenery/UI colors pulled toward grey.

    `text` is deliberately left untouched: hardship should darken and mute the
    world around the player, but never erode the contrast that keeps the
    prose and UI labels readable.
    """
    return Palette(
        sky_top=_desaturate(palette.sky_top, amount),
        sky_bottom=_desaturate(palette.sky_bottom, amount),
        ground=_desaturate(palette.ground, amount),
        panel=_desaturate(palette.panel, amount),
        text=palette.text,
    )


def draw_scene(surface: pygame.Surface, season: str, desaturation: float = 0.0) -> None:
    """Draw a static seasonal scene: a sky gradient over a ground band.

    `desaturation` in [0, 1] pulls all colors toward grey, expressing hardship
    level without any per-affliction special-casing.
    """
    palette = desaturate_palette(palette_for_season(season), desaturation)
    width, height = surface.get_size()
    ground_height = int(height * GROUND_HEIGHT_RATIO)
    sky_height = height - ground_height

    for y in range(sky_height):
        t = y / max(1, sky_height - 1)
        color = _lerp_color(palette.sky_top, palette.sky_bottom, t)
        pygame.draw.line(surface, color, (0, y), (width, y))

    pygame.draw.rect(surface, palette.ground, (0, sky_height, width, ground_height))


def _lerp_color(a: Color, b: Color, t: float) -> Color:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _desaturate(color: Color, amount: float) -> Color:
    grey = sum(color) / 3
    return _lerp_color(color, (grey, grey, grey), max(0.0, min(1.0, amount)))
