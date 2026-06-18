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
# 'W_edge': shallow-water/shore tiles; the brown land strip is on the SOUTH side.
#           Rotate 90/180/270 to get W/N/E edge variants.
# 'W_deep': solid deep-water tiles for river interior (no land neighbours).
_TILE_VARIANTS: dict[str, list[int]] = {
    'G':      [80, 81, 82, 84, 85, 86, 87, 88, 89, 90, 91, 92],
    'W_edge': [16, 17, 18, 19, 32, 33, 34, 35],
    'W_deep': [256, 257, 272, 273, 288, 289, 290, 304, 305, 320, 321, 322,
               336, 337, 352, 353, 368, 369, 384, 385, 400, 401, 402],
    'D':      [48, 49, 50, 52, 53, 54, 55, 56],
    'T':      [112, 113, 114],
}
# Legacy alias so external code that reads TILE_VARIANTS['W'] still works.
_TILE_VARIANTS['W'] = _TILE_VARIANTS['W_edge']
_ATLAS_COLS  = 32
_TILE_DIR    = os.path.join(os.path.dirname(__file__), "assets", "sprites", "tiles")
_COMPLETE_TILE_DIR = os.path.join(os.path.dirname(__file__), "assets", "sprites", "tiles_complete")
VALID_ERAS   = ("forest", "winter", "wasteland", "swamp")

# Column count of each era's complete tileset sheet (rows are always 20).
_ERA_TILE_COLS: dict[str, int] = {
    "forest": 19, "winter": 19, "wasteland": 19, "swamp": 20,
}

# Tree autotile bitmask → list of (row, col) tile coordinates in the complete sheet.
# Bitmask bits: N=1  E=2  S=4  W=8  (1 = that cardinal neighbour is also a tree).
# Multiple coords per bitmask are visual variants picked deterministically from position.
# Fallback for unknown bitmasks (0, 2, 8, 10) uses interior tiles (bitmask 15).
_TREE_BITMASK_COORDS: dict[int, list[tuple[int, int]]] = {
    1:  [(6,  9)],                                              # N only
    3:  [(5,  7), (6, 16)],                                     # N+E  (terrain S+W)
    4:  [(6,  7)],                                              # S only
    5:  [(6,  8)],                                              # N+S  vertical strip
    6:  [(5,  9), (7,  3)],                                     # E+S  (terrain N+W)
    7:  [(5,  8)],                                              # N+E+S (terrain W)
    9:  [(6, 15)],                                              # N+W  (terrain S+E)
    11: [(5, 15), (6, 10), (6, 17)],                           # N+E+W (terrain S)
    12: [(5, 12), (6, 18)],                                     # S+W  (terrain N+E)
    13: [(5, 14)],                                              # N+S+W (terrain E)
    14: [(5, 11), (7,  1)],                                     # E+S+W (terrain N)
    15: [(5, 13), (5, 16), (5, 17), (5, 18),                   # fully interior
         (6,  0), (6,  4), (6,  5), (6,  6),
         (6, 11), (6, 13), (6, 14),
         (7,  0), (7,  4), (7,  5), (7,  6), (7,  7), (7,  8)],
}


def _load_complete_tree_tiles(era: str) -> "dict[int, list[pygame.Surface]]":
    """Load bitmask→surface lists from tiles_complete/<era>.png. Returns {} if absent."""
    path = os.path.join(_COMPLETE_TILE_DIR, f"{era}.png")
    if not os.path.exists(path):
        return {}
    try:
        sheet = pygame.image.load(path).convert()
    except Exception as e:
        print(f"map: warning: complete tileset {era}: {e}")
        return {}

    cols  = _ERA_TILE_COLS.get(era, 19)
    sw, sh = sheet.get_width(), sheet.get_height()

    def _tile(r: int, c: int) -> "pygame.Surface | None":
        x, y = c * CELL_SIZE, r * CELL_SIZE
        if x + CELL_SIZE <= sw and y + CELL_SIZE <= sh:
            return sheet.subsurface(pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)).copy()
        return None

    interior = [s for r, c in _TREE_BITMASK_COORDS[15] if (s := _tile(r, c))]
    result: dict[int, list[pygame.Surface]] = {}
    for bitmask, coords in _TREE_BITMASK_COORDS.items():
        surfs = [s for r, c in coords if (s := _tile(r, c))]
        result[bitmask] = surfs if surfs else interior  # fall back to interior
    # Missing bitmasks (0, 2, 8, 10) → interior
    for missing in (0, 2, 8, 10):
        if missing not in result:
            result[missing] = interior

    if result:
        print(f"map: complete tree tiles for {era} ({len(result)} bitmasks, "
              f"sheet {cols}×{sh // CELL_SIZE})")
    return result


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
# River enters from col 17 at top, dips left to col 15 in the middle, returns to col 17
# at the bottom — a gentle S-curve.  Two diagonal ford crossings at rows 4-5 and 15-16.
# Tree borders (T) are 1-2 cells thick at the edges; buildings are in cols 9-15 (player)
# and 31-38 (enemy), so the river stays safely in cols 15-24 throughout.
DEFAULT_MAP = [
    "T" * 40,                                    #  0  top border
    "T" * 40,                                    #  1  top border
    "TT" + "G"*15 + "W"*8 + "G"*13 + "TT",     #  2  river cols 17-24  (wider near top)
    "TT" + "G"*15 + "W"*8 + "G"*14 + "T",      #  3  river cols 17-24  (1T right: enemy mine col 38 safe)
    "T"  + "G"*13 + "D"*13 + "G"*12 + "T",     #  4  upper ford cols 14-26
    "G"*13 + "D"*14 + "G"*13,                   #  5  upper ford cols 13-26  (no border: open crossing)
    "TT" + "G"*14 + "W"*8 + "G"*14 + "TT",     #  6  river cols 16-23  (post-ford shift left)
    "TT" + "G"*13 + "W"*8 + "G"*15 + "TT",     #  7  river cols 15-22
    "T"  + "G"*14 + "W"*7 + "G"*17 + "T",      #  8  river cols 15-21  (narrows, stable zone)
    "T"  + "G"*14 + "W"*7 + "G"*17 + "T",      #  9  river cols 15-21
    "T"  + "G"*14 + "W"*7 + "G"*17 + "T",      # 10  river cols 15-21  (footman spawns col 13-14 = G)
    "T"  + "G"*14 + "W"*7 + "G"*17 + "T",      # 11  river cols 15-21  (enemy worker spawn col 37 = G)
    "TT" + "G"*14 + "W"*6 + "G"*17 + "T",      # 12  river cols 16-21  (farm1 col 15 = G; 1T right)
    "TT" + "G"*14 + "W"*6 + "G"*17 + "T",      # 13  river cols 16-21
    "T"  + "G"*14 + "W"*7 + "G"*17 + "T",      # 14  river cols 15-21
    "T"  + "G"*12 + "D"*14 + "G"*12 + "T",     # 15  lower ford cols 13-26
    "T"  + "G"*13 + "D"*13 + "G"*12 + "T",     # 16  lower ford cols 14-26  (diagonal offset)
    "TT" + "G"*13 + "W"*8 + "G"*15 + "TT",     # 17  river cols 15-22  (post-ford widens)
    "TT" + "G"*14 + "W"*8 + "G"*14 + "TT",     # 18  river cols 16-23  (shifting right)
    "TT" + "G"*15 + "W"*8 + "G"*13 + "TT",     # 19  river cols 17-24  (symmetric to top)
    "T" * 40,                                    # 20  bottom border
    "T" * 40,                                    # 21  bottom border
]


class GameMap:
    def __init__(self, tile_map: list[str] = DEFAULT_MAP, era: str = "forest"):
        self.grid_h = len(tile_map)
        self.grid_w = max(len(row) for row in tile_map) if tile_map else 40
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
        tree_tiles    = _load_complete_tree_tiles(era)
        self._surface.fill((0, 0, 0))
        for r, row in enumerate(self.tiles):
            for c, t in enumerate(row):
                x, y = c * CELL_SIZE, r * CELL_SIZE
                if t == 'W':
                    self._blit_water(c, r, x, y, tile_variants)
                elif t == 'T':
                    self._blit_tree(c, r, x, y, tree_tiles)
                else:
                    variants = tile_variants.get(t)
                    if variants:
                        idx = (c * 7 + r * 13) % len(variants)
                        self._surface.blit(variants[idx], (x, y))
                    else:
                        color = TILE_COLORS.get(t, TILE_COLORS['G'])
                        pygame.draw.rect(self._surface, color, (x, y, CELL_SIZE, CELL_SIZE))

    def _blit_tree(self, c: int, r: int, x: int, y: int,
                   tree_tiles: "dict[int, list[pygame.Surface]]") -> None:
        """Autotile a tree cell based on its four cardinal neighbours."""
        if not tree_tiles:
            pygame.draw.rect(self._surface, TILE_COLORS.get('T', (24, 60, 8)),
                             (x, y, CELL_SIZE, CELL_SIZE))
            return

        def is_tree(dr: int, dc: int) -> bool:
            nr, nc = r + dr, c + dc
            # Off-map → treat as tree so the forest border looks interior
            if not (0 <= nr < self.grid_h and 0 <= nc < self.grid_w):
                return True
            return self.tiles[nr][nc] == 'T'

        bitmask = (
            (1 if is_tree(-1,  0) else 0) |   # N
            (2 if is_tree( 0,  1) else 0) |   # E
            (4 if is_tree( 1,  0) else 0) |   # S
            (8 if is_tree( 0, -1) else 0)     # W
        )

        variants = tree_tiles.get(bitmask) or tree_tiles.get(15, [])
        if variants:
            idx = (c * 7 + r * 13) % len(variants)
            self._surface.blit(variants[idx], (x, y))
        else:
            pygame.draw.rect(self._surface, TILE_COLORS.get('T', (24, 60, 8)),
                             (x, y, CELL_SIZE, CELL_SIZE))

    def _blit_water(self, c: int, r: int, x: int, y: int,
                    tile_variants: dict) -> None:
        """Autotile a single water cell: deep interior, rotated edge when adjacent to land."""
        edge = tile_variants.get('W_edge', [])
        deep = tile_variants.get('W_deep', edge)  # fallback to edge if deep absent

        def is_land(r2: int, c2: int) -> bool:
            if not (0 <= r2 < len(self.tiles) and 0 <= c2 < len(self.tiles[r2])):
                return True  # off-map edge counts as land
            return self.tiles[r2][c2] != 'W'

        land_n = is_land(r - 1, c)
        land_s = is_land(r + 1, c)
        land_e = is_land(r, c + 1)
        land_w = is_land(r, c - 1)

        vi = c * 7 + r * 13  # deterministic variant seed

        if not (land_n or land_s or land_e or land_w):
            # Interior — use deep water
            pool = deep or edge
            if pool:
                self._surface.blit(pool[vi % len(pool)], (x, y))
            else:
                pygame.draw.rect(self._surface, TILE_COLORS['W'], (x, y, CELL_SIZE, CELL_SIZE))
            return

        if not edge:
            pygame.draw.rect(self._surface, TILE_COLORS['W'], (x, y, CELL_SIZE, CELL_SIZE))
            return

        # Edge tile: land strip is on the SOUTH side (rotation = 0).
        # pygame.transform.rotate is CCW: bottom→right at 90°, bottom→left at 270°.
        # Priority: W and E edges first (river is vertical).
        if land_w and not land_e:
            rotation = 270   # bottom → left  → land strip faces west
        elif land_e and not land_w:
            rotation = 90    # bottom → right → land strip faces east
        elif land_n and not land_s:
            rotation = 180   # bottom → top  → land strip faces north
        else:
            rotation = 0     # land to south (or multiple — default)

        tile = edge[vi % len(edge)]
        if rotation:
            tile = pygame.transform.rotate(tile, rotation)
        self._surface.blit(tile, (x, y))

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

    def find_path(self, start_pos: pygame.Vector2, goal_pos: pygame.Vector2,
                  extra_blocked: "set | None" = None) -> list[pygame.Vector2]:
        start = world_to_grid(start_pos, self.grid_w, self.grid_h)
        goal  = world_to_grid(goal_pos,  self.grid_w, self.grid_h)

        blocked = self.blocked if not extra_blocked else (self.blocked | extra_blocked)

        # Redirect to nearest walkable cell when goal is inside a building / terrain
        if goal in blocked:
            near = self._nearest_accessible(goal)
            if near is None:
                return []
            goal     = near
            goal_pos = grid_to_world_center(*goal)

        if start == goal:
            return [pygame.Vector2(goal_pos)]
        cells = astar(blocked, start, goal, self.grid_w, self.grid_h)
        if not cells:
            return []
        path = [grid_to_world_center(c, r) for c, r in cells]
        path[-1] = pygame.Vector2(goal_pos)
        return path

    def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0) -> None:
        surface.blit(self._surface, (-cam_x, -cam_y))


# ---------------------------------------------------------------------------
# Procedural map generation
# ---------------------------------------------------------------------------

import random as _rng_module


def generate_map(cols: int = 64, rows: int = 64,
                 seed: "int | None" = None) -> list[str]:
    """
    Generate a WC2-style map with a vertical S-curve river, two dirt fords,
    tree patches at corners and mid-edges, and guaranteed clear base areas
    on the left (player) and right (enemy) sides.
    """
    rng = _rng_module.Random(seed)
    grid = [['G'] * cols for _ in range(rows)]

    # ── Tree border (2 cells thick) ──────────────────────────────────────
    for r in range(rows):
        for c in range(cols):
            if r < 2 or r >= rows - 2 or c < 2 or c >= cols - 2:
                grid[r][c] = 'T'

    # ── River: vertical S-curve ───────────────────────────────────────────
    river_center = cols // 2 + rng.randint(-cols // 10, cols // 10)
    river_hw = rng.randint(3, 5)   # half-width

    ford_y1 = rng.randint(rows // 5, rows // 3)
    ford_y2 = rng.randint(2 * rows // 3, 4 * rows // 5)
    ford_rows: set[int] = set(range(ford_y1 - 1, ford_y1 + 3)) | \
                          set(range(ford_y2 - 1, ford_y2 + 3))

    col = river_center
    for r in range(2, rows - 2):
        col += rng.choice([-1, -1, 0, 0, 0, 1, 1])
        col = max(river_hw + cols // 5, min(cols - river_hw - cols // 5, col))
        tile = 'D' if r in ford_rows else 'W'
        for dc in range(-river_hw, river_hw + 1):
            c = col + dc
            if 2 <= c < cols - 2:
                grid[r][c] = tile

    # ── Base zones ────────────────────────────────────────────────────────
    # Player: left quarter; Enemy: right quarter; both in vertical middle half
    player_c = range(2, cols // 4)
    enemy_c  = range(3 * cols // 4, cols - 2)
    base_r   = range(rows // 4, 3 * rows // 4)

    def _is_base(r: int, c: int) -> bool:
        return (r in base_r) and (c in player_c or c in enemy_c)

    # ── Tree density fill ─────────────────────────────────────────────────
    # Three zones determine density:
    #   • Top strip (rows 2 .. rows//4)         : 78%  → dense forest flanking bases
    #   • Bottom strip (3*rows//4 .. rows-2)    : 78%
    #   • No-man's-land (base rows, between bases): 50% → medium forest with openings
    #   • Base wing cells                       :  0%  → cleared below by _is_base
    def _density(r: int, c: int) -> float:
        if r < rows // 4 or r >= 3 * rows // 4:
            return 0.78
        if cols // 4 <= c < 3 * cols // 4:
            return 0.50
        return 0.0  # player/enemy side of base band — kept open

    for r in range(2, rows - 2):
        for c in range(2, cols - 2):
            if _is_base(r, c) or grid[r][c] in ('W', 'D'):
                continue
            d = _density(r, c)
            if d > 0 and rng.random() < d:
                grid[r][c] = 'T'

    # ── Force clear base zones (override any trees placed above) ──────────
    for r in range(rows):
        for c in range(cols):
            if _is_base(r, c):
                grid[r][c] = 'G'

    return [''.join(row) for row in grid]


def find_base_area(tile_map: list[str], side: str = 'left',
                   min_clear: int = 10) -> tuple[int, int]:
    """
    Return the (col, row) grid position of the most passable min_clear×min_clear
    area on the requested side of the map.
    """
    rows = len(tile_map)
    cols = max(len(r) for r in tile_map) if tile_map else 0

    if side == 'left':
        c_range = range(2, cols // 3 - min_clear + 1)
    else:
        c_range = range(2 * cols // 3, cols - min_clear - 2)
    r_range = range(rows // 4, 3 * rows // 4 - min_clear + 1)

    best_score = -1
    best = (2, rows // 4) if side == 'left' else (2 * cols // 3, rows // 4)

    for r0 in r_range:
        for c0 in c_range:
            score = sum(
                1
                for dr in range(min_clear) for dc in range(min_clear)
                if (r0 + dr < rows and c0 + dc < cols
                    and tile_map[r0 + dr][c0 + dc] == 'G')
            )
            if score > best_score:
                best_score = score
                best = (c0, r0)

    return best
