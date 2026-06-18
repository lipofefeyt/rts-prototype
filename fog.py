import pygame
from pathfinding import CELL_SIZE

SIGHT_CELLS = 8    # grid-cell radius of unit vision


class FogOfWar:
    """
    Two-tier fog: unexplored (opaque black) and explored-but-dark (semi-transparent).
    Updated once per frame from friendly unit positions.
    """

    def __init__(self, grid_w: int, grid_h: int):
        self.grid_w = grid_w
        self.grid_h = grid_h
        self._explored: set[tuple[int, int]] = set()
        self._visible: set[tuple[int, int]] = set()
        self._surface = pygame.Surface(
            (grid_w * CELL_SIZE, grid_h * CELL_SIZE), pygame.SRCALPHA
        )
        # Pre-compute the circle offsets once
        self._offsets: list[tuple[int, int]] = [
            (dc, dr)
            for dc in range(-SIGHT_CELLS, SIGHT_CELLS + 1)
            for dr in range(-SIGHT_CELLS, SIGHT_CELLS + 1)
            if dc * dc + dr * dr <= SIGHT_CELLS * SIGHT_CELLS
        ]

    def update(self, observers: list) -> None:
        """observers: any mix of friendly units + buildings that have a .pos attribute."""
        visible: set[tuple[int, int]] = set()
        for u in observers:
            cx = int(u.pos.x / CELL_SIZE)
            cy = int(u.pos.y / CELL_SIZE)
            for dc, dr in self._offsets:
                c, r = cx + dc, cy + dr
                if 0 <= c < self.grid_w and 0 <= r < self.grid_h:
                    visible.add((c, r))

        self._explored |= visible
        self._visible = visible

        cell = CELL_SIZE
        self._surface.fill((0, 0, 0, 255))
        for c, r in self._explored:
            alpha = 0 if (c, r) in visible else 140
            self._surface.fill((0, 0, 0, alpha), (c * cell, r * cell, cell, cell))

    def is_visible(self, grid_cell: tuple[int, int]) -> bool:
        return grid_cell in self._visible

    def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0,
             viewport_x: int = 0) -> None:
        surface.blit(self._surface, (viewport_x - cam_x, -cam_y))
