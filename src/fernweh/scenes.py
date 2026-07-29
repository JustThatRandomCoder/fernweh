"""Season palettes and procedural scene backgrounds.

No art assets — every scene is a vertical sky gradient plus a ground band,
using pygame primitives only. Palette choice is keyed purely off season name,
so adding a new season/palette never touches the game loop.
"""

from __future__ import annotations

import math
import random

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
    (0.08, 0.95, 0.9, 4.1, 0.5),
    (0.25, 0.85, 1.3, 0.5, 0.32),
    (0.48, 0.55, 1.8, 2.6, -0.16),
)
# A soft radial darkening toward the screen edges, drawn last over everything
# else — pulls the eye toward the center the way a photographed vignette
# does, and adds depth to what would otherwise be a flat, evenly-lit scene.
VIGNETTE_STRENGTH = 0.35
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
# The path is the journey itself made visible: a dirt track winding through
# the foreground, low in the ground band (near the viewer) so it reads as
# the road underfoot rather than a distant trail. `path_y_ratio` is a pure
# function of x so `game.py` can reuse the exact same curve to walk the
# traveler silhouette along it during a passage, instead of the two drifting
# out of sync if the curve were duplicated.
PATH_BASELINE_RATIO = 0.82
PATH_AMPLITUDE_RATIO = 0.16
PATH_WAVE_COUNT = 1.6
PATH_PHASE = 1.1
PATH_WIDTH_RATIO = 0.05
# Birds only fly in the warmer half of the year — each is a (y_ratio, speed,
# scale, start_ratio) tuple, same shape and wrap-around drift technique as
# CLOUDS above, just rendered as a flapping "M" silhouette instead of a puff
# cluster.
BIRD_SEASONS = ("spring", "summer")
BIRDS = (
    (0.22, 34.0, 1.0, 0.15),
    (0.27, 30.0, 0.8, 0.62),
)
# Fireflies only appear on summer evenings, drifting in small loops near the
# foreground rather than falling like weather particles — each is
# (x_ratio, y_ratio, phase, flicker_speed), fixed positions that only move
# locally, so they read as insects wandering a patch of ground, not rain.
FIREFLY_SEASON = "summer"
FIREFLIES = (
    (0.15, 0.72, 0.0, 2.1),
    (0.30, 0.8, 1.4, 1.7),
    (0.68, 0.76, 2.6, 2.4),
    (0.82, 0.68, 4.1, 1.9),
    (0.5, 0.85, 3.2, 2.6),
)


def path_y_ratio(x_ratio: float) -> float:
    """Return the path's vertical position within the ground band at a given x fraction.

    The result is a fraction of `ground_height` measured from the sky/ground
    line — the same convention `_draw_hill` uses — so callers just multiply
    by `ground_height` and add `sky_height` to get a screen y.
    """
    return PATH_BASELINE_RATIO + PATH_AMPLITUDE_RATIO * math.sin(
        PATH_PHASE + PATH_WAVE_COUNT * math.pi * x_ratio
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
    surface: pygame.Surface,
    season: str,
    desaturation: float = 0.0,
    elapsed: float = 0.0,
    landmark: str | None = None,
) -> None:
    """Draw a full seasonal scene: sky, sun/moon, drifting clouds, hills, ground, and trees.

    `desaturation` in [0, 1] pulls all colors toward grey, expressing hardship
    level without any per-affliction special-casing. `elapsed` (seconds since
    the game started) drives the only continuous motion in the background
    itself — cloud drift — independent of the particle system's weather.
    `landmark`, when given, is one concrete feature the current stage names
    (a bridge, a stream, a building) drawn on top of the generic landscape so
    the picture matches the words — see `draw_landmark`.
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
    if season in BIRD_SEASONS:
        _draw_birds(surface, _darken(palette.sky_bottom, 0.55), width, sky_height, elapsed)

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

    # The path is drawn on top of the ground/hills but underneath the trees,
    # so trunks planted near its edges still occlude it the way real
    # roadside trees would.
    _draw_path(surface, palette, width, sky_height, ground_height)

    # A stage-specific landmark (bridge, stream, building) sits on the ground
    # above the path but below the foreground trees, so trees nearest the
    # viewer still overlap it the way they overlap everything else.
    if landmark is not None:
        draw_landmark(surface, palette, landmark, width, height, ground_height, elapsed)

    # Trees stand on top of everything else in the scene — the nearest layer,
    # rooted in the ground band.
    _draw_trees(surface, palette, width, height, ground_height, elapsed)

    if season == FIREFLY_SEASON:
        _draw_fireflies(surface, width, height, elapsed)

    surface.blit(_vignette_surface(width, height), (0, 0))


class PersonAppearance:
    """One human's look and gait — shared by the player traveler, portraits, and companions.

    Colors are chosen from small curated palettes rather than arbitrary random
    RGB — that keeps every combination readable as "a person" instead of
    occasionally producing an ugly or unreadable color clash. `bob_scale` and
    `stride_scale` vary the walk itself (how bouncy, how long a stride) so
    different people (or the same traveler across different playthroughs)
    don't just look like different outfits on an identical animation.
    """

    def __init__(
        self,
        skin: Color,
        hair: Color,
        tunic: Color,
        trousers: Color,
        bob_scale: float,
        stride_scale: float,
    ) -> None:
        self.skin = skin
        self.hair = hair
        self.tunic = tunic
        self.trousers = trousers
        self.bob_scale = bob_scale
        self.stride_scale = stride_scale


# Curated, not exhaustive — a handful of plausible human skin/hair tones and a
# handful of dyed-cloth colors that read as "traveler's clothes" in a muted
# painterly game, not neon. `random_person_appearance` draws one of each.
SKIN_TONES: tuple[Color, ...] = ((235, 200, 173), (210, 168, 125), (160, 116, 82), (96, 68, 52))
HAIR_COLORS: tuple[Color, ...] = ((40, 32, 26), (92, 60, 34), (176, 142, 92), (58, 58, 62))
TUNIC_COLORS: tuple[Color, ...] = (
    (150, 66, 62),
    (74, 104, 138),
    (94, 128, 82),
    (162, 122, 60),
    (110, 82, 132),
)
TROUSER_COLORS: tuple[Color, ...] = ((66, 58, 50), (52, 58, 68), (86, 72, 54))


def random_person_appearance(rng: random.Random) -> PersonAppearance:
    """Roll a new traveler look and gait from the curated palettes above."""
    return PersonAppearance(
        skin=rng.choice(SKIN_TONES),
        hair=rng.choice(HAIR_COLORS),
        tunic=rng.choice(TUNIC_COLORS),
        trousers=rng.choice(TROUSER_COLORS),
        bob_scale=rng.uniform(0.75, 1.3),
        stride_scale=rng.uniform(0.8, 1.25),
    )


def appearance_for_seed(seed: str) -> PersonAppearance:
    """Deterministic appearance for a seed string (e.g. a companion's id).

    Used as a fallback so a companion always looks the same throughout a
    playthrough even if content didn't explicitly describe their look via
    `person_appearance_from_names` — the same seed always rolls the same
    `random.Random` sequence.
    """
    return random_person_appearance(random.Random(seed))


# Content (`stages.py`) describes a scene character with plain strings
# (role/hair/tunic/skin names, kept in a small fixed vocabulary the pure
# content layer can validate on its own) rather than raw RGB — stages.py
# can't import this pygame-dependent module to look colors up itself, so the
# name *sets* have to be duplicated in both layers by convention (the same
# pattern already used for season names between `state.py` and
# `SEASON_PALETTES`). These dicts are the rendering side of that convention.
NAMED_SKIN_TONES: dict[str, Color] = {
    "light": SKIN_TONES[0],
    "tan": SKIN_TONES[1],
    "deep": SKIN_TONES[2],
    "dark": SKIN_TONES[3],
}
NAMED_HAIR_COLORS: dict[str, Color] = {
    "black": HAIR_COLORS[0],
    "auburn": HAIR_COLORS[1],
    "sandy": HAIR_COLORS[2],
    "grey": HAIR_COLORS[3],
}
NAMED_TUNIC_COLORS: dict[str, Color] = {
    "red": TUNIC_COLORS[0],
    "blue": TUNIC_COLORS[1],
    "green": TUNIC_COLORS[2],
    "gold": TUNIC_COLORS[3],
    "purple": TUNIC_COLORS[4],
}


def person_appearance_from_names(skin: str, hair: str, tunic: str) -> PersonAppearance:
    """Build an explicit, author-controlled appearance from content's named colors.

    Unlike `random_person_appearance`, this is deterministic and used for
    named NPCs the content describes (a portrait's look shouldn't change
    between runs) — trousers/gait stay at neutral defaults since a portrait
    never shows legs and a recruited companion's gait doesn't need to be
    distinctive the way the player traveler's is.
    """
    return PersonAppearance(
        skin=NAMED_SKIN_TONES[skin],
        hair=NAMED_HAIR_COLORS[hair],
        tunic=NAMED_TUNIC_COLORS[tunic],
        trousers=TROUSER_COLORS[0],
        bob_scale=1.0,
        stride_scale=1.0,
    )


def person_appearance_to_dict(appearance: PersonAppearance) -> dict[str, object]:
    """Flatten a `PersonAppearance` to plain JSON-safe types, for `save.py` to persist.

    `save.py` stays pygame-free (it can't import this module), so appearances
    cross that boundary as plain dicts of lists/floats rather than as
    `PersonAppearance` objects — this is the one place that knows how to go
    both directions (see `person_appearance_from_dict` below).
    """
    return {
        "skin": list(appearance.skin),
        "hair": list(appearance.hair),
        "tunic": list(appearance.tunic),
        "trousers": list(appearance.trousers),
        "bob_scale": appearance.bob_scale,
        "stride_scale": appearance.stride_scale,
    }


def person_appearance_from_dict(data: dict[str, object]) -> PersonAppearance:
    """Rebuild a `PersonAppearance` from the dict shape `person_appearance_to_dict` writes."""
    return PersonAppearance(
        skin=tuple(data["skin"]),
        hair=tuple(data["hair"]),
        tunic=tuple(data["tunic"]),
        trousers=tuple(data["trousers"]),
        bob_scale=data["bob_scale"],
        stride_scale=data["stride_scale"],
    )


# The traveler is built from chunky rectangles at this unit size rather than
# thin lines — a small "pixel art" grid of blocks reads as a human figure the
# way a retro sprite does, instead of a wireframe stick figure.
TRAVELER_PIXEL = 3


def draw_traveler(
    surface: pygame.Surface,
    palette: Palette,
    x_ratio: float,
    elapsed: float,
    appearance: PersonAppearance,
    gait_offset: float = 0.0,
    gait_speed: float = 1.0,
) -> None:
    """Draw the traveler as a blocky pixel-art figure, feet planted on the path.

    Called separately from `draw_scene` (rather than folded into it) because
    only a passage between stages shows the traveler in motion — every other
    screen (a stage's question, the ending) has no need for it. `x_ratio` is
    the traveler's horizontal position as a fraction of the screen width; the
    vertical position is derived from `path_y_ratio` so the figure's feet
    always land exactly on the drawn path. `gait_offset`/`gait_speed` let each
    individual passage start the walk cycle at a different point and pace
    (see `Game._start_passage`), so consecutive walks don't play back in
    lockstep even with the same `appearance`.
    """
    width, height = surface.get_size()
    ground_height = height * GROUND_HEIGHT_RATIO
    sky_height = height - ground_height
    x = width * x_ratio
    foot_y = sky_height + ground_height * path_y_ratio(x_ratio)

    phase = elapsed * 9 * gait_speed * appearance.stride_scale + gait_offset
    # Quantizing the continuous sine into eighths before using it to place
    # limbs gives the walk a slight stepped snap between poses — closer to
    # how a low-frame-count sprite animation reads than a perfectly smooth
    # interpolation would.
    stride = round(math.sin(phase) * 8) / 8
    bob = abs(math.cos(phase)) * 3 * appearance.bob_scale

    unit = TRAVELER_PIXEL
    leg_h, torso_h, head_h = 6 * unit, 6 * unit, 4 * unit
    hip_y = foot_y - leg_h - bob
    shoulder_y = hip_y - torso_h
    head_bottom = shoulder_y

    leg_reach = 2.5 * unit * stride
    _pixel_rect(surface, appearance.trousers, x - unit - leg_reach, hip_y, 2 * unit, leg_h)
    _pixel_rect(surface, appearance.trousers, x + leg_reach - unit, hip_y, 2 * unit, leg_h)
    # Feet as small dark blocks at the base of each leg read better than the
    # trouser color simply stopping at the ground.
    shoe_color = _darken(appearance.trousers, 0.4)
    _pixel_rect(
        surface, shoe_color, x - unit - leg_reach - unit * 0.3, foot_y - unit, 2.6 * unit, unit
    )
    _pixel_rect(
        surface, shoe_color, x + leg_reach - unit - unit * 0.3, foot_y - unit, 2.6 * unit, unit
    )

    # A satchel drawn behind the torso, on whichever side is currently the
    # "back" arm, so it reads as slung over one shoulder rather than floating.
    satchel_side = -1 if stride >= 0 else 1
    _pixel_rect(
        surface,
        _lighten(_darken(appearance.tunic, 0.3), 0.1),
        x + satchel_side * 2.6 * unit,
        shoulder_y + unit,
        2 * unit,
        3 * unit,
    )

    _pixel_rect(surface, appearance.tunic, x - 2.5 * unit, shoulder_y, 5 * unit, torso_h)

    arm_reach = 2 * unit * stride
    arm_color = appearance.skin
    _pixel_rect(surface, arm_color, x - 3 * unit - arm_reach * 0.4, shoulder_y, unit, 4.5 * unit)
    _pixel_rect(surface, arm_color, x + 2 * unit + arm_reach * 0.4, shoulder_y, unit, 4.5 * unit)

    _pixel_rect(surface, appearance.skin, x - 2 * unit, head_bottom - head_h, 4 * unit, head_h)
    # Hair as a cap over the top third of the head block plus a fringe row —
    # simple, but enough to break up the skin block into a recognizable head.
    _pixel_rect(surface, appearance.hair, x - 2 * unit, head_bottom - head_h, 4 * unit, unit * 1.4)
    _pixel_rect(surface, appearance.hair, x - 2.2 * unit, head_bottom - head_h, unit * 0.6, head_h)
    _pixel_rect(surface, appearance.hair, x + 1.6 * unit, head_bottom - head_h, unit * 0.6, head_h)


def draw_landmark(
    surface: pygame.Surface,
    palette: Palette,
    landmark: str,
    width: int,
    height: int,
    ground_height: float,
    elapsed: float,
) -> None:
    """Draw one named landmark into the scene, dispatching on the landmark name.

    A registry (`_LANDMARK_DRAWERS`) maps each name from `stages.VALID_LANDMARKS`
    to a small draw routine, so adding a landmark is adding one function and one
    registry entry — `draw_scene` and the game loop never change. An unknown
    name (one validated in content but not yet given a drawer) is silently
    skipped rather than crashing the render.
    """
    drawer = _LANDMARK_DRAWERS.get(landmark)
    if drawer is not None:
        drawer(surface, palette, width, height, ground_height, elapsed)


def draw_bench(
    surface: pygame.Surface,
    palette: Palette,
    center_x: float,
    seat_y: float,
    seat_width: float,
) -> None:
    """Draw a simple wooden bench: a seat plank, a backrest, and two pairs of legs.

    Drawn during a rest passage (see `game.py`) as the thing the traveler and
    their companions sit on. `seat_y` is the top surface of the seat plank —
    the same y a seated figure's hips rest on, so `draw_person_seated` and this
    function stay in lock-step about where "the seat" is. Colors are derived
    from the season palette's ground tone (a woody brown already present in
    every season) rather than a new hard-coded color, so the bench sits
    naturally inside whatever season's scene is on screen.
    """
    # A warm wood tone: the ground darkened toward brown, with a lighter top
    # face so the plank reads as catching the light from above.
    wood = _darken(palette.ground, 0.45)
    wood_top = _lighten(wood, 0.18)
    plank_h = max(6.0, seat_width * 0.06)
    left = center_x - seat_width / 2
    # Back legs first (further from the viewer), then the seat, then the front
    # legs and backrest on top — so nearer parts correctly occlude farther ones.
    leg_w = max(4.0, seat_width * 0.04)
    leg_h = plank_h * 3.2
    for leg_x in (left + leg_w, center_x + seat_width / 2 - 2 * leg_w):
        _pixel_rect(surface, _darken(wood, 0.2), leg_x, seat_y, leg_w, leg_h)
    # The seat plank itself, with a lighter top edge for a hint of depth.
    _pixel_rect(surface, wood, left, seat_y, seat_width, plank_h)
    _pixel_rect(surface, wood_top, left, seat_y, seat_width, plank_h * 0.35)
    # A low backrest: two uprights and a horizontal rail behind the seat. Kept
    # short enough (roughly a seated figure's torso height) that the top rail
    # sits behind the sitters' backs rather than crossing their necks.
    back_h = plank_h * 1.6
    back_top = seat_y - back_h
    for upright_x in (left + leg_w, center_x + seat_width / 2 - 2 * leg_w):
        _pixel_rect(surface, _darken(wood, 0.1), upright_x, back_top, leg_w, back_h)
    _pixel_rect(surface, wood, left, back_top, seat_width, plank_h * 0.8)


def draw_person_seated(
    surface: pygame.Surface,
    palette: Palette,
    center_x: float,
    seat_y: float,
    appearance: PersonAppearance,
    elapsed: float,
    idle_phase: float = 0.0,
) -> None:
    """Draw one person sitting on a bench, built from the same blocky pixels as `draw_traveler`.

    The pose is a seated front view: hips resting on `seat_y`, torso and head
    upright above, arms at the sides, and the shins hanging down off the front
    of the seat to rest feet on the ground below. `idle_phase` offsets a slow
    breathing bob per person (via `elapsed`) so a row of seated figures doesn't
    rise and fall in perfect unison — the resting equivalent of the gait offset
    the walking figures use.
    """
    unit = TRAVELER_PIXEL
    # A gentle, slow breathing rise-and-fall — much smaller and slower than the
    # walk cycle's bob, because a seated figure is at rest, not in motion.
    breathe = math.sin(elapsed * 1.6 + idle_phase) * unit * 0.4

    torso_h, head_h = 6 * unit, 4 * unit
    hip_y = seat_y - breathe
    shoulder_y = hip_y - torso_h
    head_bottom = shoulder_y

    # Shins hang straight down from the front edge of the seat to the ground,
    # feet planted just below — this is the read that says "sitting" rather
    # than "standing", since the thighs are folded onto the seat and hidden.
    shin_h = 5 * unit
    foot_y = seat_y + shin_h
    _pixel_rect(surface, appearance.trousers, center_x - 2.2 * unit, seat_y, 2 * unit, shin_h)
    _pixel_rect(surface, appearance.trousers, center_x + 0.2 * unit, seat_y, 2 * unit, shin_h)
    shoe_color = _darken(appearance.trousers, 0.4)
    _pixel_rect(surface, shoe_color, center_x - 2.5 * unit, foot_y - unit, 2.6 * unit, unit)
    _pixel_rect(surface, shoe_color, center_x - 0.1 * unit, foot_y - unit, 2.6 * unit, unit)

    # Torso, then arms resting close at the sides (no swing — hands in the lap),
    # then the head and hair, mirroring the standing figure's stacking order.
    _pixel_rect(surface, appearance.tunic, center_x - 2.5 * unit, shoulder_y, 5 * unit, torso_h)
    _pixel_rect(surface, appearance.skin, center_x - 3 * unit, shoulder_y, unit, 4.5 * unit)
    _pixel_rect(surface, appearance.skin, center_x + 2 * unit, shoulder_y, unit, 4.5 * unit)

    _pixel_rect(
        surface, appearance.skin, center_x - 2 * unit, head_bottom - head_h, 4 * unit, head_h
    )
    _pixel_rect(
        surface, appearance.hair, center_x - 2 * unit, head_bottom - head_h, 4 * unit, unit * 1.4
    )
    _pixel_rect(
        surface, appearance.hair, center_x - 2.2 * unit, head_bottom - head_h, unit * 0.6, head_h
    )
    _pixel_rect(
        surface, appearance.hair, center_x + 1.6 * unit, head_bottom - head_h, unit * 0.6, head_h
    )


POSE_HEAD_LEAN: dict[str, float] = {
    "standing": 0.0,
    "sitting": 0.35,
    "crouching": 0.55,
}


def draw_portrait(
    surface: pygame.Surface,
    rect: pygame.Rect,
    palette: Palette,
    appearance: PersonAppearance,
    pose: str,
    elapsed: float,
    prop: str | None = None,
) -> None:
    """Draw a close-up bust portrait of the NPC a stage's situation describes.

    Built from the same blocky-rectangle technique as `draw_traveler`, just
    at a larger scale and cropped at the shoulders, visual-novel style,
    instead of a full walking body — a stage's question has room for a
    close-up but not a full figure once the text panel and choice buttons
    are laid out. A slow idle bob and an occasional blink keep it from
    reading as a still image even though nothing about the pose is meant to
    move far; `pose` leans the head slightly for "sitting"/"crouching" so
    the same bust reads as resting rather than standing at attention.
    """
    unit = rect.width / 24
    cx = rect.centerx
    lean = POSE_HEAD_LEAN.get(pose, 0.0) * unit

    # A soft round backdrop behind the bust reads as a close-up vignette,
    # distinguishing the portrait area from the flat panel behind it.
    backdrop_radius = round(rect.width * 0.56)
    backdrop = pygame.Surface((backdrop_radius * 2, backdrop_radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(
        backdrop,
        (*_darken(palette.panel, 0.08), 255),
        (backdrop_radius, backdrop_radius),
        backdrop_radius,
    )
    surface.blit(backdrop, (cx - backdrop_radius, rect.top - backdrop_radius * 0.15))

    # Idle breathing: a slow, small vertical drift, independent of any walk
    # cycle — this portrait never walks, it just isn't perfectly frozen.
    breathe = math.sin(elapsed * 1.3) * unit * 0.18

    shoulder_h = 6 * unit
    shoulder_y = rect.bottom - shoulder_h + breathe
    _pixel_rect(surface, appearance.tunic, cx - 8 * unit, shoulder_y, 16 * unit, shoulder_h)

    neck_y = shoulder_y - 2 * unit
    _pixel_rect(surface, appearance.skin, cx - 2 * unit, neck_y, 4 * unit, 2.2 * unit)

    head_h = 11 * unit
    head_y = neck_y - head_h
    head_x = cx - 5 * unit + lean
    _pixel_rect(surface, appearance.skin, head_x, head_y, 10 * unit, head_h)

    # Hair: a cap over the crown plus two side locks framing the face.
    _pixel_rect(surface, appearance.hair, head_x, head_y, 10 * unit, 3.2 * unit)
    _pixel_rect(surface, appearance.hair, head_x - 0.8 * unit, head_y, unit, head_h * 0.7)
    _pixel_rect(surface, appearance.hair, head_x + 9.8 * unit, head_y, unit, head_h * 0.7)

    # Eyes blink shut for a brief window every few seconds rather than
    # staying open forever — the one detail that most reads as "alive"
    # in a close-up, blocky or not.
    blink = (elapsed * 1.0) % 4.0 > 3.75
    eye_h = 0.4 * unit if not blink else 0.08 * unit
    eye_y = head_y + 5.6 * unit
    eye_color = _darken(appearance.skin, 0.75)
    _pixel_rect(surface, eye_color, head_x + 1.8 * unit, eye_y, 1.6 * unit, eye_h)
    _pixel_rect(surface, eye_color, head_x + 6.6 * unit, eye_y, 1.6 * unit, eye_h)

    mouth_y = head_y + 8.3 * unit
    _pixel_rect(
        surface, _darken(appearance.skin, 0.55), head_x + 3.5 * unit, mouth_y, 3 * unit, 0.5 * unit
    )

    if prop == "well":
        _draw_well_prop(surface, palette, rect)


def _draw_well_prop(surface: pygame.Surface, palette: Palette, rect: pygame.Rect) -> None:
    """Draw a small stone well beside the portrait, hinting at the described setting."""
    unit = rect.width / 24
    base_x = rect.left - unit
    base_y = rect.bottom - 8 * unit
    stone = _lighten(palette.ground, 0.35)
    _pixel_rect(surface, stone, base_x, base_y, 6 * unit, 6 * unit)
    _pixel_rect(surface, _darken(stone, 0.3), base_x + unit, base_y + unit, 4 * unit, 4 * unit)
    roof_color = _darken(palette.ground, 0.45)
    roof_points = [
        (base_x - unit, base_y),
        (base_x + 3 * unit, base_y - 3 * unit),
        (base_x + 7 * unit, base_y),
    ]
    pygame.draw.polygon(surface, roof_color, roof_points)


def _pixel_rect(
    surface: pygame.Surface, color: Color, left: float, top: float, w: float, h: float
) -> None:
    """Draw one blocky sprite rectangle, rounded to whole pixels for crisp edges."""
    pygame.draw.rect(surface, color, pygame.Rect(round(left), round(top), round(w), round(h)))


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


def _draw_birds(
    surface: pygame.Surface, color: Color, width: int, sky_height: int, elapsed: float
) -> None:
    """Draw a couple of distant birds drifting across the sky, wings flapping."""
    for y_ratio, speed, scale, start_ratio in BIRDS:
        span = width + 40
        x = (start_ratio * span + elapsed * speed) % span - 20
        y = round(sky_height * y_ratio)
        _draw_bird(surface, color, x, y, scale, elapsed)


def _draw_bird(
    surface: pygame.Surface, color: Color, x: float, y: float, scale: float, elapsed: float
) -> None:
    """Draw one bird as a flapping 'M' — two strokes whose outer ends bob with a wingbeat."""
    span = 9 * scale
    # The wingtips swing between raised and lowered on a fast sine — the
    # center point stays put, so it reads as a flap rather than a bounce.
    flap = math.sin(elapsed * 9 + x * 0.05) * span * 0.6
    left = (x - span, y - flap)
    right = (x + span, y - flap)
    center = (x, y)
    pygame.draw.lines(surface, color, False, [left, center, right], max(1, round(scale)))


def _draw_fireflies(surface: pygame.Surface, width: int, height: int, elapsed: float) -> None:
    """Draw a handful of softly pulsing fireflies drifting in small loops near the ground."""
    for x_ratio, y_ratio, phase, flicker_speed in FIREFLIES:
        # Local wandering rather than travel: a small circular drift around
        # the spot's own anchor point, independent per firefly via `phase`.
        drift_x = math.cos(elapsed * 0.5 + phase) * 14
        drift_y = math.sin(elapsed * 0.7 + phase) * 8
        x = width * x_ratio + drift_x
        y = height * y_ratio + drift_y
        # Alpha pulses between a dim glow and a bright flash — fireflies
        # blink, they don't glow steadily.
        pulse = 0.5 + 0.5 * math.sin(elapsed * flicker_speed + phase)
        alpha = round(60 + 180 * pulse**3)
        glow = pygame.Surface((12, 12), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 244, 180, alpha), (6, 6), 5)
        pygame.draw.circle(glow, (255, 255, 220, min(255, alpha + 60)), (6, 6), 2)
        surface.blit(glow, (x - 6, y - 6))


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


# Cache the vignette by (width, height): its rings never change frame to
# frame, so rebuilding it from scratch every draw_scene call would burn a
# ring of per-pixel alpha circles 60 times a second for no visual benefit.
_VIGNETTE_CACHE: dict[tuple[int, int], pygame.Surface] = {}


def _vignette_surface(width: int, height: int) -> pygame.Surface:
    """Return a cached black radial-gradient overlay for darkening screen edges."""
    key = (width, height)
    cached = _VIGNETTE_CACHE.get(key)
    if cached is not None:
        return cached
    vignette = pygame.Surface((width, height), pygame.SRCALPHA)
    center = (width / 2, height / 2)
    max_radius = math.hypot(*center)
    # Concentric rings, transparent at the center and darkening outward —
    # each ring is a full-size circle so overlapping alpha builds up
    # smoothly rather than showing banding at ring boundaries.
    rings = 24
    for i in range(rings, 0, -1):
        t = i / rings
        radius = round(max_radius * t)
        alpha = round(255 * VIGNETTE_STRENGTH * t)
        pygame.draw.circle(vignette, (0, 0, 0, alpha), center, radius)
    # The innermost ring/circle above still covers the center at low alpha;
    # cutting a fully transparent hole restores a clear, undarkened middle.
    pygame.draw.circle(vignette, (0, 0, 0, 0), center, round(max_radius * 0.35))
    _VIGNETTE_CACHE[key] = vignette
    return vignette


def _draw_path(
    surface: pygame.Surface, palette: Palette, width: int, sky_height: int, ground_height: float
) -> None:
    """Draw the winding dirt path as a ribbon following `path_y_ratio`.

    Built the same way as a hill silhouette (a strip of sampled points turned
    into a filled polygon), but as a bounded-width ribbon rather than a
    fill-to-the-bottom shape, since the path needs a far *and* near edge.
    """
    steps = 40
    path_color = _lighten(palette.ground, 0.22)
    half_width = ground_height * PATH_WIDTH_RATIO / 2
    top_edge = []
    bottom_edge = []
    for i in range(steps + 1):
        x = width * i / steps
        center_y = sky_height + ground_height * path_y_ratio(i / steps)
        top_edge.append((x, center_y - half_width))
        bottom_edge.append((x, center_y + half_width))
    pygame.draw.polygon(surface, path_color, [*top_edge, *reversed(bottom_edge)])
    # A darker rut line down the center reads as wear from travel, breaking
    # up what would otherwise be a flat band of a single color.
    center_line = [
        (x, sky_height + ground_height * path_y_ratio(i / steps))
        for i, x in ((i, width * i / steps) for i in range(steps + 1))
    ]
    pygame.draw.aalines(surface, _darken(path_color, 0.12), False, center_line)


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


def _draw_bridge(
    surface: pygame.Surface,
    palette: Palette,
    width: int,
    height: int,
    ground_height: float,
    elapsed: float,
) -> None:
    """Draw an old wooden footbridge over a gorge, spanning the scene at path level.

    The deck sags slightly in the middle (an old rope-and-plank bridge, not a
    rigid span) and groans with a small, slow vertical sway keyed off `elapsed`
    — the "groans under its own weight" the situation names. A darker gorge
    shadow drops away beneath the deck to read as the chasm being crossed.
    """
    sky_height = height - ground_height
    x1 = width * 0.2
    x2 = width * 0.8
    span = x2 - x1
    # The deck sits low in the ground band, at roughly the traveler's path
    # level, so a figure crossing during a passage reads as being on it.
    base_y = sky_height + ground_height * 0.6
    sway = math.sin(elapsed * 1.4) * 2.0
    sag = ground_height * 0.07

    def deck_y(x: float) -> float:
        # A parabola that is 0 at both ends and 1 at the center makes the deck
        # dip in the middle; the groan sway is scaled by the same curve so the
        # bridge flexes most where it is least supported.
        t = (x - x1) / span
        dip = 4 * t * (1 - t)
        return base_y + sag * dip + sway * dip

    samples = [(x1 + span * i / 24, deck_y(x1 + span * i / 24)) for i in range(25)]

    # 1. The gorge: a dark chasm dropping from just under the deck to the
    # bottom of the scene, so the bridge reads as spanning a real gap.
    gorge_color = _darken(palette.ground, 0.62)
    gorge = [*samples, (x2, height), (x1, height)]
    pygame.draw.polygon(surface, gorge_color, gorge)

    wood = _darken(palette.ground, 0.5)
    plank = _lighten(wood, 0.28)  # silvered, weathered planks catching the light
    rope = _darken(wood, 0.25)

    # 2. Two suspension ropes sweeping from post to post, one at deck level and
    # one raised as a handrail, both following the same sagging curve.
    handrail = [(x, y - ground_height * 0.16) for x, y in samples]
    pygame.draw.lines(surface, rope, False, handrail, max(2, round(width * 0.004)))
    pygame.draw.lines(surface, rope, False, samples, max(2, round(width * 0.004)))

    # 3. The deck planks: short vertical boards laid across the span, a couple
    # tilted to read as "loose in places". Vertical posts every few planks tie
    # the handrail down to the deck.
    plank_w = span / 24
    for i, (x, y) in enumerate(samples):
        tilt = 2 if i % 5 == 2 else 0  # an occasional plank sitting proud
        _pixel_rect(surface, plank, x - plank_w / 2, y - 3 - tilt, plank_w * 0.9, 6)
        if i % 4 == 0:
            post_top = y - ground_height * 0.16
            _pixel_rect(surface, wood, x - 1, post_top, max(2, round(width * 0.004)), y - post_top)


# Maps each landmark name to its draw routine. Every drawer takes the same
# (surface, palette, width, height, ground_height, elapsed) signature so
# `draw_landmark` can call any of them uniformly. A name here must also be in
# `stages.VALID_LANDMARKS`; names validated in content but not yet given a
# drawer are simply skipped by `draw_landmark`.
def _draw_stream(
    surface: pygame.Surface,
    palette: Palette,
    width: int,
    height: int,
    ground_height: float,
    elapsed: float,
) -> None:
    """Draw a shallow stream crossing the path, with shimmering water and pale stones.

    A cool water ribbon follows the same path curve the traveler walks, so the
    crossing sits exactly where the road does. Slow, drifting highlight lines
    give the surface a live shimmer; a few pale stones near the middle are the
    "something pale catches the light among the stones" the situation names.
    """
    sky_height = height - ground_height
    # A cool water tone: the season's sky pulled toward a muted blue, so it
    # still reads as this season's light on the water rather than a fixed blue.
    water = _lerp_color(palette.sky_bottom, (96, 130, 158), 0.55)
    half = ground_height * 0.1
    steps = 40

    def center_y(i: int) -> float:
        return sky_height + ground_height * path_y_ratio(i / steps)

    # The water body: a wide ribbon centered on the path curve.
    top_edge = [(width * i / steps, center_y(i) - half) for i in range(steps + 1)]
    bottom_edge = [(width * i / steps, center_y(i) + half) for i in range(steps + 1)]
    pygame.draw.polygon(surface, water, [*top_edge, *reversed(bottom_edge)])

    # Shimmer: a few pale highlight lines drifting slowly sideways, each at its
    # own depth within the band, so the surface never looks like flat paint.
    shimmer = _lighten(water, 0.4)
    for lane, speed, phase in ((-0.4, 9.0, 0.0), (0.1, 6.0, 2.0), (0.45, 11.0, 4.0)):
        pts = []
        for i in range(steps + 1):
            x = width * i / steps
            wobble = math.sin(elapsed * 1.5 + phase + i * 0.4) * half * 0.18
            pts.append((x, center_y(i) + lane * half + wobble))
        # The drift is a slow horizontal scroll of where the line brightens,
        # done by only stroking a moving window of the points.
        offset = int((elapsed * speed) % (steps + 1))
        window = pts[offset:] + pts[:offset]
        pygame.draw.aalines(surface, shimmer, False, window[: steps // 2])

    # A cluster of pale, smooth stones near the middle of the crossing.
    stone = _lighten(palette.ground, 0.5)
    for sx, sy in ((0.44, 0.1), (0.52, -0.2), (0.57, 0.25), (0.49, 0.4)):
        cx = width * sx
        cy = sky_height + ground_height * path_y_ratio(sx) + sy * half
        pygame.draw.ellipse(surface, stone, pygame.Rect(cx - 6, cy - 3, 12, 6))


_LANDMARK_DRAWERS: dict[str, object] = {
    "bridge": _draw_bridge,
    "stream": _draw_stream,
}


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
