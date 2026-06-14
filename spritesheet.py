import math
import os
import json
import pygame

_SPRITE_DIR = os.path.join(os.path.dirname(__file__), "assets", "sprites")

# WC2 walk strip layout: direction-major, 8 directions × 5 poses each = 40 frames.
# Frame index = direction * 5 + pose  (direction 0=N … 7=NW, clockwise)
# Frames 0-4=N, 5-9=NE, 10-14=E, 15-19=SE, 20-24=S, 25-29=SW, 30-34=W, 35-39=NW
WALK_FRAMES_PER_DIR = 5   # 5 walk poses per direction
NUM_STRIP_DIRS      = 8   # 8 directions stored in the strip
NUM_DIRECTIONS      = 8
ANIM_FPS            = 8.0

DIR_N, DIR_NE, DIR_E, DIR_SE, DIR_S, DIR_SW, DIR_W, DIR_NW = range(8)


def vel_to_dir(vel: pygame.Vector2) -> int:
    """Map a movement velocity to a WC2 direction index (0=N, clockwise)."""
    if vel.length_squared() < 0.01:
        return DIR_S
    # atan2(y, x): 0=East, 90=South in pygame's y-down system
    angle = math.degrees(math.atan2(vel.y, vel.x))
    angle = (angle + 360) % 360
    # Shift so North (270°) maps to sector 0, then divide into 45° buckets
    return int(((angle - 247.5) % 360) / 45) % 8


class SpriteSheet:
    """Horizontal PNG strip — all frames the same size."""

    def __init__(self, path: str, frame_w: int, frame_h: int) -> None:
        sheet = pygame.image.load(path).convert_alpha()
        total = sheet.get_width() // frame_w
        self.frame_w = frame_w
        self.frame_h = frame_h
        self._frames = [
            sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h)).copy()
            for i in range(total)
        ]

    def walk_frame(self, direction: int, tick: int) -> pygame.Surface:
        """direction 0-7 (N=0 … NW=7, clockwise), tick increments each animated frame.
        Direction-major layout: idx = direction * 5 + (tick % 5).
        """
        idx = direction * WALK_FRAMES_PER_DIR + (tick % WALK_FRAMES_PER_DIR)
        return self._frames[min(idx, len(self._frames) - 1)]


# (unit_type, team) → sprite sheet filename stem
# team 0 = human player (Red player colour), team 1 = orc AI (Blue player colour)
_SHEET_NAMES: dict[tuple, str] = {
    ('footman', 0): 'footman_team0',
    ('footman', 1): 'grunt_team1',
    ('archer',  0): 'archer_team0',
    ('archer',  1): 'axethrower_team1',
    ('worker',  0): 'peasant_team0',
    ('worker',  1): 'peon_team1',
    ('knight',  0): 'knight_team0',
    ('knight',  1): 'ogre_team1',
}


# Player-colour pixel values as extracted by libwar2 per team.
# Human (team0) units carry pure red insignia; orc (team1) units carry pure blue.
_PLAYER_COLOUR_SRC: dict[int, list[tuple[int,int,int]]] = {
    0: [(164, 0, 0), (124, 0, 0)],    # 2 shades of red
    1: [(0, 60, 192), (0, 36, 148)],  # 2 shades of blue
}

# Default team colours — matchmaking palette (WC2-accurate defaults).
TEAM_COLOURS: dict[int, tuple[int,int,int]] = {
    0: (164, 0, 0),    # red
    1: (0, 60, 192),   # blue
}


def recolour_surface(surf: pygame.Surface,
                     src_shades: list[tuple[int,int,int]],
                     dst_colour: tuple[int,int,int]) -> pygame.Surface:
    """Return a copy of surf with player-colour shades replaced by dst_colour equivalents.

    Each src shade is mapped to a proportionally-bright shade of dst_colour,
    preserving the light/dark ramp used for the insignia.
    The reference brightness is the max channel of src_shades[0] (the bright shade).
    """
    out = surf.copy()
    bright_src = max(src_shades[0])
    if bright_src == 0:
        return out

    pa = pygame.PixelArray(out)
    for src in src_shades:
        ratio = max(src) / bright_src
        dst = tuple(int(c * ratio) for c in dst_colour)
        # Build mapped colour in the surface's pixel format
        src_mapped = out.map_rgb(*src)
        dst_mapped = out.map_rgb(*dst)
        pa.replace(src_mapped, dst_mapped)
    del pa
    return out


def load_war2_sprites(colours: "dict[int,tuple] | None" = None) -> dict[tuple, SpriteSheet]:
    """Load WC2 walk sprite sheets from assets/sprites/.

    `colours` optionally overrides per-team player colours, e.g. {0: (0,200,0)} for green team 0.
    Recolouring is applied at load time so draw() pays zero cost per frame.
    Returns {} when PNGs are absent — run tools/extract_war2_sprites.py first.
    """
    manifest_path = os.path.join(_SPRITE_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path) as f:
        manifest = json.load(f)

    effective_colours = {**TEAM_COLOURS, **(colours or {})}

    sheets: dict[tuple, SpriteSheet] = {}
    for key, stem in _SHEET_NAMES.items():
        path = os.path.join(_SPRITE_DIR, f"{stem}_walk.png")
        if not os.path.exists(path):
            continue
        walk_info = manifest.get(stem, {}).get("walk", {})
        fw = walk_info.get("frame_w", 58)
        fh = walk_info.get("frame_h", 58)
        try:
            team = key[1]
            src_shades = _PLAYER_COLOUR_SRC.get(team, [])
            dst = effective_colours.get(team)
            sheet = SpriteSheet(path, fw, fh)
            if src_shades and dst and dst != TEAM_COLOURS.get(team):
                sheet._frames = [recolour_surface(f, src_shades, dst) for f in sheet._frames]
            sheets[key] = sheet
        except Exception as e:
            print(f"spritesheet: warning: could not load {path}: {e}")
    if sheets:
        print(f"spritesheet: loaded {len(sheets)} WC2 walk strips")
    return sheets
