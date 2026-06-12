import math
import os
import json
import pygame

_SPRITE_DIR = os.path.join(os.path.dirname(__file__), "assets", "sprites")

WALK_FRAMES_PER_DIR = 5
NUM_DIRECTIONS = 8
ANIM_FPS = 8.0   # walk animation rate

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
        """direction 0-7 (N…NW clockwise), tick increments each animated frame."""
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
}


def load_war2_sprites() -> dict[tuple, SpriteSheet]:
    """
    Load WC2 walk sprite sheets from assets/sprites/.
    Returns {} when PNGs are absent — run tools/extract_war2_sprites.py first.
    Falls back gracefully; units use procedural sprites when sheet is None.
    """
    manifest_path = os.path.join(_SPRITE_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path) as f:
        manifest = json.load(f)

    sheets: dict[tuple, SpriteSheet] = {}
    for key, stem in _SHEET_NAMES.items():
        path = os.path.join(_SPRITE_DIR, f"{stem}_walk.png")
        if not os.path.exists(path):
            continue
        walk_info = manifest.get(stem, {}).get("walk", {})
        fw = walk_info.get("frame_w", 58)
        fh = walk_info.get("frame_h", 58)
        try:
            sheets[key] = SpriteSheet(path, fw, fh)
        except Exception as e:
            print(f"spritesheet: warning: could not load {path}: {e}")
    if sheets:
        print(f"spritesheet: loaded {len(sheets)} WC2 walk strips")
    return sheets
