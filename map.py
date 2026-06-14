import os
import pygame
from pathfinding import CELL_SIZE, world_to_grid, grid_to_world_center, astar

# Fallback colours used when the atlas PNG is absent (solid fills).
# All three eras share the same tile IDs — only the palette differs.
_ERA_TILE_COLORS: dict[str, dict[str, tuple]] = {
    "forest":    {'G': (52, 88, 40),    'D': (108, 78, 50),  'W': (28, 52, 92),  'T': (24, 60, 8)},
    "winter":    {'G': (200, 205, 220), 'D': (140, 160, 200),'W': (28, 52, 92),  'T': (160, 165, 185)},
    "wasteland": {'G': (120, 55, 10),   'D': (75, 40, 10),   'W': (15, 30, 42),  'T': (110, 48, 4)},
    "swamp":     {'G': (52, 88, 40),    'D': (108, 78, 50),  'W': (20, 45, 30),  'T': (24, 60, 8)},
}
TILE_COLORS = _ERA_TILE_COLORS["forest"]  # active era colours (reassigned by GameMap)
TILE_BLOCKED = {'W', 'T'}

# Tile IDs — identical across all WC2 eras (the atlas just uses different palettes).
_TILE_VARIANTS: dict[str, list[int]] = {
    'G': [80, 81, 82, 84, 85, 86, 87, 88, 89, 90, 91, 92],
    'W': [16, 17, 18, 19, 32, 33, 34, 35],
    'D': [48, 49, 50, 52, 53, 54, 55, 56],
    'T': [96, 97, 98, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
}
_ATLAS_COLS  = 32
_TILE_DIR    = os.path.join(os.path.dirname(__file__), "assets", "sprites", "tiles")
VALID_ERAS   = ("forest", "winter", "wasteland", "swamp")


def _load_tile_variants(era: str = "forest") -> dict[str, list[pygame.Surface]]:
    """Extract variant tile surfaces from the atlas for the given era. Returns {} if absent."""
    atlas_path = os.path.join(_TILE_DIR, f"{era}_atlas.png")
    if not os.path.exists(atlas_path):
        return {}
    try:
        atlas = pygame.image.load(atlas_path).convert()
    except Exception as e:
        print(f"map: warning: {era} atlas: {e}")
        return {}
    aw, ah = atlas.get_width(), atlas.get_height()
    result: dict[str, list[pygame.Surface]] = {}
    for char, ids in _TILE_VARIANTS.items():
        surfs: list[pygame.Surface] = []
        for tid in ids:
            col, row = tid % _ATLAS_COLS, tid // _ATLAS_COLS
            x, y = col * CELL_SIZE, row * CELL_SIZE
            if x + CELL_SIZE <= aw and y + CELL_SIZE <= ah:
                surfs.append(atlas.subsurface(pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)).copy())
        if surfs:
            result[char] = surfs
    if result:
        print(f"map: {era} tile variants: { {k: len(v) for k, v in result.items()} }")
    return result

# 40 cols × 22 rows at 32 px/cell = 1280×704.
# River runs through cols 16-21.  Two dirt fords at rows 3-4 (upper) and 13-14 (lower).
# Tree borders on rows 0-1 and 20-21 only (safe: no buildings in those rows).
DEFAULT_MAP = [
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",  #  0 top tree border
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",  #  1 top tree border
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  2
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  #  3 upper ford
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  #  4 upper ford
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  5
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  6
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  7
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  8
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  9
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 10
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 11
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 12
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  # 13 lower ford
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  # 14 lower ford
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 15
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 16
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 17
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 18
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 19
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",  # 20 bottom tree border
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",  # 21 bottom tree border
]


class GameMap:
    def __init__(self, width: int, height: int, tile_map: list[str] = DEFAULT_MAP,
                 era: str = "forest"):
        self.grid_w = width // CELL_SIZE
        self.grid_h = height // CELL_SIZE
        self.tiles = tile_map
        self.blocked: set[tuple[int, int]] = set()

        for r, row in enumerate(tile_map):
            for c, t in enumerate(row):
                if t in TILE_BLOCKED:
                    self.blocked.add((c, r))

        self._era = era
        self._surface = pygame.Surface((self.grid_w * CELL_SIZE, self.grid_h * CELL_SIZE))
        self._bake_surface(era)

    def _bake_surface(self, era: str) -> None:
        """(Re)render the pre-baked tile surface for the given era atlas."""
        global TILE_COLORS
        self._era = era
        TILE_COLORS = _ERA_TILE_COLORS.get(era, _ERA_TILE_COLORS["forest"])
        tile_variants = _load_tile_variants(era)
        self._surface.fill((0, 0, 0))
        for r, row in enumerate(self.tiles):
            for c, t in enumerate(row):
                x, y = c * CELL_SIZE, r * CELL_SIZE
                variants = tile_variants.get(t)
                if variants:
                    idx = (c * 7 + r * 13) % len(variants)
                    self._surface.blit(variants[idx], (x, y))
                else:
                    color = TILE_COLORS.get(t, TILE_COLORS['G'])
                    pygame.draw.rect(self._surface, color, (x, y, CELL_SIZE, CELL_SIZE))

    def set_era(self, era: str) -> None:
        """Switch the map tileset palette to a different WC2 era. Blocked cells unchanged."""
        if era not in VALID_ERAS:
            return
        self._bake_surface(era)

    def add_obstacle(self, rect: pygame.Rect) -> None:
        """Programmatic obstacle on top of tile data (kept for compatibility)."""
        col0 = rect.left // CELL_SIZE
        row0 = rect.top // CELL_SIZE
        col1 = (rect.right + CELL_SIZE - 1) // CELL_SIZE
        row1 = (rect.bottom + CELL_SIZE - 1) // CELL_SIZE
        for c in range(col0, col1):
            for r in range(row0, row1):
                if 0 <= c < self.grid_w and 0 <= r < self.grid_h:
                    self.blocked.add((c, r))

    def remove_obstacle(self, rect: pygame.Rect) -> None:
        """Remove building/tree obstacle cells. Permanent terrain is unaffected."""
        col0 = rect.left // CELL_SIZE
        row0 = rect.top // CELL_SIZE
        col1 = (rect.right + CELL_SIZE - 1) // CELL_SIZE
        row1 = (rect.bottom + CELL_SIZE - 1) // CELL_SIZE
        for c in range(col0, col1):
            for r in range(row0, row1):
                if not self.is_terrain_blocked(c, r):
                    self.blocked.discard((c, r))

    def is_terrain_blocked(self, grid_col: int, grid_row: int) -> bool:
        """True for impassable terrain tiles (water). Does NOT include building obstacles."""
        if not (0 <= grid_row < len(self.tiles) and 0 <= grid_col < len(self.tiles[grid_row])):
            return False
        return self.tiles[grid_row][grid_col] in TILE_BLOCKED

    def _nearest_accessible(self, cell: tuple[int, int]) -> "tuple[int,int] | None":
        """BFS outward from cell to find the nearest non-blocked grid cell."""
        from collections import deque
        visited = {cell}
        queue: deque = deque([cell])
        while queue:
            c = queue.popleft()
            for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nb = (c[0] + dc, c[1] + dr)
                if nb in visited:
                    continue
                if not (0 <= nb[0] < self.grid_w and 0 <= nb[1] < self.grid_h):
                    continue
                visited.add(nb)
                if nb not in self.blocked:
                    return nb
                queue.append(nb)
        return None

    def find_path(self, start_pos: pygame.Vector2, goal_pos: pygame.Vector2) -> list[pygame.Vector2]:
        start = world_to_grid(start_pos, self.grid_w, self.grid_h)
        goal  = world_to_grid(goal_pos,  self.grid_w, self.grid_h)

        # Redirect to nearest walkable cell when goal is inside a building / terrain
        if goal in self.blocked:
            near = self._nearest_accessible(goal)
            if near is None:
                return []
            goal     = near
            goal_pos = grid_to_world_center(*goal)

        if start == goal:
            return [pygame.Vector2(goal_pos)]
        cells = astar(self.blocked, start, goal, self.grid_w, self.grid_h)
        if not cells:
            return []
        path = [grid_to_world_center(c, r) for c, r in cells]
        path[-1] = pygame.Vector2(goal_pos)
        return path

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._surface, (0, 0))
