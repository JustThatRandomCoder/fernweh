"""Season palettes and procedural scene backgrounds.

No art assets — every scene is a vertical sky gradient plus a ground band,
using pygame primitives only. Palette choice is keyed purely off season name,
so adding a new season/palette never touches the game loop.
"""

from __future__ import annotations

import math

import pygame

Color = tuple[int, int, int]


class Palette:
    """The colors used to render one season's scenes.

    `ground` and `panel` are deliberately separate: `ground` is tuned to look
    right as outdoor terrain and is not guaranteed to contrast against `text`,
    while `panel` is a near-white card tone tuned per season purely so that
    `text` reaches WCAG AA (>=4.5:1) against it — UI surfaces (buttons,
    dialogs, text backings) always use `panel`, never `ground`. `accent` is
    the season's one saturated "character" color, used for the sky's soft
    sun/moon glow — everything else in the palette is deliberately muted.
    `foliage` is the tree canopy color; winter has no foliage (bare branches
    instead), so it's `None` there rather than every season needing one.
    """

    def __init__(
        self,
        sky_top: Color,
        sky_bottom: Color,
        ground: Color,
        panel: Color,
        accent: Color,
        text: Color,
        foliage: Color | None = None,
    ) -> None:
        self.sky_top = sky_top
        self.sky_bottom = sky_bottom
        self.ground = ground
        self.panel = panel
        self.accent = accent
        self.text = text
        self.foliage = foliage


SEASON_PALETTES: dict[str, Palette] = {
    "spring": Palette(
        sky_top=(198, 224, 205),
        sky_bottom=(232, 240, 214),
        ground=(150, 181, 137),
        panel=(240, 244, 232),
        accent=(247, 200, 200),
        text=(48, 58, 46),
        foliage=(240, 196, 206),
    ),
    "summer": Palette(
        sky_top=(247, 214, 150),
        sky_bottom=(255, 236, 196),
        ground=(196, 168, 96),
        panel=(250, 240, 214),
        accent=(255, 221, 133),
        text=(66, 50, 24),
        foliage=(94, 138, 68),
    ),
    "autumn": Palette(
        sky_top=(214, 150, 96),
        sky_bottom=(236, 190, 120),
        ground=(140, 84, 48),
        panel=(247, 228, 202),
        accent=(232, 140, 84),
        text=(56, 34, 18),
        foliage=(198, 92, 56),
    ),
    "winter": Palette(
        sky_top=(202, 214, 224),
        sky_bottom=(232, 238, 244),
        ground=(214, 222, 230),
        panel=(240, 245, 250),
        accent=(226, 236, 246),
        text=(40, 48, 56),
        foliage=None,
    ),
}

GROUND_HEIGHT_RATIO = 0.28
# Rolling-hill silhouette layers, each a (baseline_ratio, amplitude_ratio,
# wave_count, phase, lighten_or_darken_amount) tuple. `baseline_ratio` and
# `amplitude_ratio` are both fractions of ground_height, but measured from
# sky_height — since amplitude is deliberately larger than baseline here, the
# crest rises *above* the sky/ground line, into the sky itself, which is what
# makes the hills read as an actual silhouette rather than a bump hidden
# inside the flat ground band. The far layer is lightened (hazier, distant,
# taller) and drawn first; the near layer is darkened (closer, in front,
# lower) and drawn on top of it — the "2-3 layer parallax" the design brief
# calls for.
HILL_LAYERS = (
    (0.25, 0.85, 1.3, 0.5, 0.32),
    (0.48, 0.55, 1.8, 2.6, -0.16),
)
SUN_POSITION_RATIO = (0.78, 0.16)
SUN_RADIUS_RATIO = 0.075
# Each cloud is (y_ratio within the sky, drift speed in px/second, size scale,
# starting position as a fraction of one screen-width-of-travel) — drawn from
# `elapsed` seconds passed to draw_scene, so clouds drift continuously without
# draw_scene needing to hold any state of its own between frames.
CLOUDS = (
    (0.16, 7.0, 1.0, 0.05),
    (0.32, 4.5, 0.7, 0.45),
    (0.08, 9.5, 0.55, 0.78),
)
# Trees stand in the foreground, each a (x_ratio, scale, sway_phase) tuple.
# Placed mostly near the left/right edges (outside where choice buttons sit,
# which run from MARGIN to width - MARGIN in game.py) so they stay visible
# once the button list is drawn on top of the scene, plus a couple of smaller
# ones nearer the middle for depth wherever the UI leaves them visible (the
# ending screen, the dialog, the gap above the buttons).
TREES = (
    (0.025, 1.0, 0.4),
    (0.075, 0.72, 2.1),
    (0.40, 0.5, 3.4),
    (0.62, 0.55, 1.1),
    (0.925, 0.85, 2.7),
    (0.975, 0.62, 0.8),
)


def palette_for_season(season: str) -> Palette:
    """Return the rendering palette for a season name."""
    return SEASON_PALETTES[season]


def _desaturate(color: Color, amount: float) -> Color:
    # Pulls a color toward its own grey (average of its channels), not toward
    # a fixed neutral grey — so a warm color desaturates to a light grey and a
    # dark color desaturates to a dark grey, instead of everything converging
    # on the same midpoint.
    grey = sum(color) / 3
    return _lerp_color(color, (grey, grey, grey), max(0.0, min(1.0, amount)))


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
        accent=_desaturate(palette.accent, amount),
        text=palette.text,
        foliage=_desaturate(palette.foliage, amount) if palette.foliage else None,
    )


def draw_scene(
    surface: pygame.Surface, season: str, desaturation: float = 0.0, elapsed: float = 0.0
) -> None:
    """Draw a full seasonal scene: sky, sun/moon, drifting clouds, hills, ground, and trees.

    `desaturation` in [0, 1] pulls all colors toward grey, expressing hardship
    level without any per-affliction special-casing. `elapsed` (seconds since
    the game started) drives the only continuous motion in the background
    itself — cloud drift — independent of the particle system's weather.
    """
    palette = desaturate_palette(palette_for_season(season), desaturation)
    width, height = surface.get_size()
    ground_height = int(height * GROUND_HEIGHT_RATIO)
    sky_height = height - ground_height

    # Draw the sky one horizontal line at a time, blending further toward
    # sky_bottom the further down the line is — this is what makes the
    # gradient, there's no separate gradient asset or shader.
    for y in range(sky_height):
        t = y / max(1, sky_height - 1)
        color = _lerp_color(palette.sky_top, palette.sky_bottom, t)
        pygame.draw.line(surface, color, (0, y), (width, y))

    _draw_sun(surface, palette.accent, width, sky_height)
    _draw_clouds(surface, _lighten(palette.sky_bottom, 0.45), width, sky_height, elapsed)

    # The flat ground band is the base fill, drawn *before* the hills — hills
    # are the foreground silhouette layered on top, so their crests can rise
    # above the sky/ground line into the sky itself instead of being erased
    # by the ground fill drawn afterward.
    pygame.draw.rect(surface, palette.ground, (0, sky_height, width, ground_height))

    # Hill layers are drawn back-to-front (far, taller, hazier first; near,
    # lower, more saturated on top) so the near layer's silhouette overlaps
    # the far one — the "2-3 layer parallax" the design brief calls for.
    for baseline_ratio, amplitude_ratio, wave_count, phase, shade_amount in HILL_LAYERS:
        hill_color = (
            _lighten(palette.ground, shade_amount)
            if shade_amount >= 0
            else _darken(palette.ground, -shade_amount)
        )
        _draw_hill(
            surface,
            hill_color,
            baseline=sky_height + ground_height * baseline_ratio,
            amplitude=ground_height * amplitude_ratio,
            wave_count=wave_count,
            phase=phase,
            width=width,
            height=height,
        )

    # Trees stand on top of everything else in the scene — the nearest layer,
    # rooted in the ground band.
    _draw_trees(surface, palette, width, height, ground_height, elapsed)


def _draw_clouds(
    surface: pygame.Surface, color: Color, width: int, sky_height: int, elapsed: float
) -> None:
    """Draw a handful of soft clouds, each drifting rightward at its own speed."""
    for y_ratio, speed, scale, start_ratio in CLOUDS:
        cloud_width = round(160 * scale)
        # Wrap around continuously: as a cloud's x passes the right edge, the
        # modulo brings it back in from just off the left edge.
        span = width + cloud_width
        x = (start_ratio * span + elapsed * speed) % span - cloud_width
        y = round(sky_height * y_ratio)
        _draw_cloud(surface, color, x, y, scale)


def _draw_cloud(surface: pygame.Surface, color: Color, x: float, y: float, scale: float) -> None:
    """Draw one cloud as a cluster of overlapping translucent circles."""
    # Each (dx, dy, radius) puff is a fraction of `scale`, offset from the
    # cloud's center — several overlapping soft circles read as one fluffy
    # cloud shape rather than a single flat blob.
    puffs = ((-0.9, 0.18, 0.55), (-0.3, -0.22, 0.72), (0.35, -0.05, 0.65), (0.85, 0.2, 0.5))
    unit = 55 * scale
    cloud_surface_size = round(unit * 5)
    cloud = pygame.Surface((cloud_surface_size, cloud_surface_size), pygame.SRCALPHA)
    center = cloud_surface_size / 2
    for dx, dy, radius_ratio in puffs:
        pygame.draw.circle(
            cloud,
            (*color, 120),
            (round(center + dx * unit), round(center + dy * unit)),
            round(unit * radius_ratio),
        )
    surface.blit(cloud, (x - center, y - center))


def _draw_sun(surface: pygame.Surface, color: Color, width: int, sky_height: int) -> None:
    """Draw a soft glowing disc (sun or moon, depending on season) in the sky."""
    center = (round(width * SUN_POSITION_RATIO[0]), round(sky_height * SUN_POSITION_RATIO[1]))
    radius = round(width * SUN_RADIUS_RATIO)
    glow_layers = 4
    # Draw from the outermost, faintest ring inward to the brightest core —
    # each smaller circle overwrites the center of the previous one, building
    # up a soft radial falloff with no external image or shader.
    for layer in range(glow_layers, 0, -1):
        layer_radius = round(radius * (1 + 0.9 * layer / glow_layers))
        alpha = round(160 * (glow_layers - layer + 1) / glow_layers)
        glow = pygame.Surface((layer_radius * 2, layer_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, alpha), (layer_radius, layer_radius), layer_radius)
        surface.blit(glow, (center[0] - layer_radius, center[1] - layer_radius))
    pygame.draw.circle(surface, color, center, radius)


def _draw_hill(
    surface: pygame.Surface,
    color: Color,
    baseline: float,
    amplitude: float,
    wave_count: float,
    phase: float,
    width: int,
    height: int,
) -> None:
    """Draw one rolling-hill silhouette as a smooth polygon, from `baseline` down to the bottom."""
    steps = 40
    crest_points = []
    for i in range(steps + 1):
        x = width * i / steps
        # A sine wave gives the "rolling" shape: y ranges from `baseline` (a
        # valley, sin at its minimum) up to `baseline - amplitude` (a crest,
        # smaller y draws higher on screen — with a large enough amplitude
        # this crosses above the sky/ground line, which is what makes the
        # hill read as a silhouette against the sky rather than a bump
        # hidden inside the flat ground band).
        y = baseline - amplitude * (0.5 + 0.5 * math.sin(phase + wave_count * math.pi * i / steps))
        crest_points.append((x, y))
    pygame.draw.polygon(
        surface, color, [(0.0, float(height)), *crest_points, (float(width), float(height))]
    )
    # A thin anti-aliased stroke along just the crest line (not the bottom
    # edges) adds definition in low-contrast seasons like winter, where the
    # hill color and the sky/ground behind it are close enough that the fill
    # alone nearly disappears. `aalines` (vs. `lines`) keeps it a soft edge
    # rather than a hard, technical-looking outline.
    pygame.draw.aalines(surface, _darken(color, 0.14), False, crest_points)


def _draw_trees(
    surface: pygame.Surface,
    palette: Palette,
    width: int,
    height: int,
    ground_height: float,
    elapsed: float,
) -> None:
    """Draw the foreground tree line: canopy trees, or bare branches in winter."""
    trunk_color = _darken(palette.ground, 0.38)
    for x_ratio, scale, phase in TREES:
        x = width * x_ratio
        base_y = height - ground_height * 0.06
        trunk_height = ground_height * 0.34 * scale
        # A slow sine sway on the canopy/branch offset, not the trunk itself —
        # real trees flex at the top, not pivot from the root.
        sway = math.sin(elapsed * 0.6 + phase) * 4 * scale
        top = (x + sway, base_y - trunk_height)
        pygame.draw.line(surface, trunk_color, (x, base_y), top, max(2, round(5 * scale)))
        if palette.foliage is None:
            _draw_bare_branches(surface, trunk_color, top, scale, sway)
        else:
            _draw_canopy(surface, palette.foliage, top, scale)


def _draw_canopy(
    surface: pygame.Surface, color: Color, top: tuple[float, float], scale: float
) -> None:
    """Draw a tree's canopy as a cluster of overlapping circles, same technique as clouds."""
    puffs = ((-0.55, 0.1, 0.55), (0.0, -0.35, 0.68), (0.55, 0.1, 0.55), (0.0, 0.3, 0.6))
    unit = 26 * scale
    canopy_size = round(unit * 4.5)
    canopy = pygame.Surface((canopy_size, canopy_size), pygame.SRCALPHA)
    center = canopy_size / 2
    for dx, dy, radius_ratio in puffs:
        pygame.draw.circle(
            canopy,
            color,
            (round(center + dx * unit), round(center + dy * unit)),
            round(unit * radius_ratio),
        )
    # The canopy sits centered on the trunk's top, extending mostly upward.
    surface.blit(canopy, (top[0] - center, top[1] - center * 1.3))


def _draw_bare_branches(
    surface: pygame.Surface, color: Color, top: tuple[float, float], scale: float, sway: float
) -> None:
    """Draw a winter tree's bare branch fork instead of a canopy — no foliage to show."""
    branch_length = 16 * scale
    # Three diverging branches from the trunk's top, each swaying slightly
    # more than the trunk itself since thinner branches flex further.
    for angle_offset in (-0.6, 0.0, 0.6):
        end = (
            top[0] + sway * 0.5 + math.sin(angle_offset) * branch_length,
            top[1] - math.cos(angle_offset) * branch_length,
        )
        pygame.draw.line(surface, color, top, end, max(1, round(2 * scale)))


def _lerp_color(a: Color, b: Color, t: float) -> Color:
    """Blend two colors channel-by-channel; `t=0` gives `a`, `t=1` gives `b`."""
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _lighten(color: Color, amount: float) -> Color:
    """Blend a color toward white by `amount` (0-1) — used for a distant hill layer."""
    return _lerp_color(color, (255, 255, 255), amount)


def _darken(color: Color, amount: float) -> Color:
    """Blend a color toward black by `amount` (0-1) — used for a near hill layer."""
    return _lerp_color(color, (0, 0, 0), amount)
