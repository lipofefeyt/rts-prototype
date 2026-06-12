import pygame
from pathfinding import CELL_SIZE, world_to_grid, grid_to_world_center, astar

TILE_COLORS = {
    'G': (52, 88, 40),    # grass
    'D': (108, 78, 50),   # dirt / ford crossing
    'W': (28, 52, 92),    # water — impassable
}
TILE_BLOCKED = {'W'}

# 40 cols × 22 rows at 32 px/cell = 1280×704 (top bar covers the last row visually)
# River runs through cols 16-21.  Two dirt fords at rows 3-4 (upper) and 13-14 (lower).
DEFAULT_MAP = [
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  0
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  1
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  #  2
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  #  3  upper ford
    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  #  4  upper ford
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
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 20
    "GGGGGGGGGGGGGGGGWWWWWWGGGGGGGGGGGGGGGGGG",  # 21
]


class GameMap:
    def __init__(self, width: int, height: int, tile_map: list[str] = DEFAULT_MAP):
        self.grid_w = width // CELL_SIZE
        self.grid_h = height // CELL_SIZE
        self.tiles = tile_map
        self.blocked: set[tuple[int, int]] = set()

        for r, row in enumerate(tile_map):
            for c, t in enumerate(row):
                if t in TILE_BLOCKED:
                    self.blocked.add((c, r))

        # Pre-bake tile surface so draw() is a single blit per frame
        self._surface = pygame.Surface((self.grid_w * CELL_SIZE, self.grid_h * CELL_SIZE))
        for r, row in enumerate(tile_map):
            for c, t in enumerate(row):
                color = TILE_COLORS.get(t, TILE_COLORS['G'])
                pygame.draw.rect(self._surface, color,
                                 (c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE))

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

    def find_path(self, start_pos: pygame.Vector2, goal_pos: pygame.Vector2) -> list[pygame.Vector2]:
        start = world_to_grid(start_pos, self.grid_w, self.grid_h)
        goal = world_to_grid(goal_pos, self.grid_w, self.grid_h)
        if start == goal:
            return [pygame.Vector2(goal_pos)]
        cells = astar(self.blocked, start, goal, self.grid_w, self.grid_h)
        if not cells:
            return [pygame.Vector2(goal_pos)]
        path = [grid_to_world_center(c, r) for c, r in cells]
        path[-1] = pygame.Vector2(goal_pos)
        return path

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._surface, (0, 0))
