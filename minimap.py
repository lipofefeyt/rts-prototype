import pygame
from pathfinding import CELL_SIZE
from map import TILE_COLORS

MINI_W  = 200
MINI_H  = 110   # preserves 40:22 cell ratio
_PANEL_H = 80   # must match main.PANEL_H

_BORDER = (100, 100, 120)
_TEAM_DOT = {0: (80, 150, 255), 1: (255, 80, 80), -1: (220, 200, 50)}


class Minimap:
    def __init__(self, tile_map: list[str]):
        rows = len(tile_map)
        cols = len(tile_map[0]) if tile_map else 40
        self._sx = MINI_W / (cols * CELL_SIZE)
        self._sy = MINI_H / (rows * CELL_SIZE)

        # Bake a slightly darkened terrain surface once
        self._terrain = pygame.Surface((MINI_W, MINI_H))
        cw = MINI_W / cols
        ch = MINI_H / rows
        for r, row in enumerate(tile_map):
            for c, t in enumerate(row):
                base = TILE_COLORS.get(t, TILE_COLORS['G'])
                dark = tuple(max(0, v - 20) for v in base)
                self._terrain.fill(dark,
                    (int(c * cw), int(r * ch), max(1, int(cw) + 1), max(1, int(ch) + 1)))

        self._buf = pygame.Surface((MINI_W, MINI_H))

    def draw(self, surface: pygame.Surface, buildings: list, units: list) -> None:
        self._buf.blit(self._terrain, (0, 0))

        for b in buildings:
            mx = int(b.pos.x * self._sx)
            my = int(b.pos.y * self._sy)
            color = _TEAM_DOT.get(b.team, (200, 200, 200))
            pygame.draw.rect(self._buf, color,
                             (max(0, mx - 3), max(0, my - 3), 6, 6))

        for u in units:
            mx = int(u.pos.x * self._sx)
            my = int(u.pos.y * self._sy)
            color = _TEAM_DOT.get(u.team, (200, 200, 200))
            pygame.draw.circle(self._buf, color, (mx, my), 2)

        pygame.draw.rect(self._buf, _BORDER, (0, 0, MINI_W, MINI_H), 1)

        # Position always anchored to bottom-right of whatever canvas is passed in
        sw, sh = surface.get_size()
        surface.blit(self._buf, (sw - MINI_W - 8, sh - _PANEL_H - MINI_H - 8))
