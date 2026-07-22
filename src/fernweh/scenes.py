"""Season palettes and procedural scene backgrounds.

No art assets — every scene is a vertical sky gradient plus a ground band,
using pygame primitives only. Palette choice is keyed purely off season name,
so adding a new season/palette never touches the game loop.
"""

from __future__ import annotations

import pygame

Color = tuple[int, int, int]


class Palette:
    """The colors used to render one season's scenes."""

    def __init__(self, sky_top: Color, sky_bottom: Color, ground: Color, text: Color) -> None:
        self.sky_top = sky_top
        self.sky_bottom = sky_bottom
        self.ground = ground
        self.text = text


SEASON_PALETTES: dict[str, Palette] = {
    "spring": Palette(
        sky_top=(198, 224, 205),
        sky_bottom=(232, 240, 214),
        ground=(150, 181, 137),
        text=(48, 58, 46),
    ),
    "summer": Palette(
        sky_top=(247, 214, 150),
        sky_bottom=(255, 236, 196),
        ground=(196, 168, 96),
        text=(66, 50, 24),
    ),
    "autumn": Palette(
        sky_top=(214, 150, 96),
        sky_bottom=(236, 190, 120),
        ground=(140, 84, 48),
        text=(56, 34, 18),
    ),
    "winter": Palette(
        sky_top=(202, 214, 224),
        sky_bottom=(232, 238, 244),
        ground=(214, 222, 230),
        text=(40, 48, 56),
    ),
}

GROUND_HEIGHT_RATIO = 0.28


def palette_for_season(season: str) -> Palette:
    """Return the rendering palette for a season name."""
    return SEASON_PALETTES[season]


def draw_scene(surface: pygame.Surface, season: str, desaturation: float = 0.0) -> None:
    """Draw a static seasonal scene: a sky gradient over a ground band.

    `desaturation` in [0, 1] pulls all colors toward grey, expressing hardship
    level without any per-affliction special-casing.
    """
    palette = palette_for_season(season)
    width, height = surface.get_size()
    ground_height = int(height * GROUND_HEIGHT_RATIO)
    sky_height = height - ground_height

    top = _desaturate(palette.sky_top, desaturation)
    bottom = _desaturate(palette.sky_bottom, desaturation)
    for y in range(sky_height):
        t = y / max(1, sky_height - 1)
        color = _lerp_color(top, bottom, t)
        pygame.draw.line(surface, color, (0, y), (width, y))

    ground_color = _desaturate(palette.ground, desaturation)
    pygame.draw.rect(surface, ground_color, (0, sky_height, width, ground_height))


def _lerp_color(a: Color, b: Color, t: float) -> Color:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _desaturate(color: Color, amount: float) -> Color:
    grey = sum(color) / 3
    return _lerp_color(color, (grey, grey, grey), max(0.0, min(1.0, amount)))
