import pygame
from pathfinding import CELL_SIZE
from map import TILE_COLORS, TILE_BLOCKED

# Minimap must fit within the sidebar slot between the resource row and the info panel.
MINI_MAX_W = 200   # max width  (sidebar is 220px, 10px margins each side)
MINI_MAX_H = 110   # max height (slot reserved in sidebar layout)

_BORDER   = (100, 100, 120)
_VIEW_BOX = (220, 220, 255)
_TEAM_DOT = {0: (80, 150, 255), 1: (255, 80, 80), -1: (220, 200, 50)}


class Minimap:
    def __init__(self, tile_map: list[str]):
        rows = len(tile_map)
        cols = len(tile_map[0]) if tile_map else 40

        # Scale so neither dimension exceeds its max, preserving aspect ratio
        scale = min(MINI_MAX_W / cols, MINI_MAX_H / rows)
        self.width  = max(1, int(cols * scale))
        self.height = max(1, int(rows * scale))

        self._sx = self.width  / (cols * CELL_SIZE)
        self._sy = self.height / (rows * CELL_SIZE)

        # rect is set by draw() on first call once dest_xy is known
        self.rect: pygame.Rect | None = None

        # Bake a slightly darkened terrain surface once
        self._terrain = pygame.Surface((self.width, self.height))
        cw = self.width  / cols
        ch = self.height / rows
        for r, row in enumerate(tile_map):
            for c, t in enumerate(row):
                base = TILE_COLORS.get(t, TILE_COLORS['G'])
                dark = tuple(max(0, v - 20) for v in base)
                self._terrain.fill(dark,
                    (int(c * cw), int(r * ch),
                     max(1, int(cw) + 1), max(1, int(ch) + 1)))

        self._buf = pygame.Surface((self.width, self.height))

    def world_to_cam(self, mx: int, my: int,
                     viewport_w: int, viewport_h: int,
                     map_px_w: int, map_px_h: int) -> tuple[float, float]:
        """Convert a minimap pixel click to the camera (cam.x, cam.y) that centres on it."""
        world_x = mx / self._sx
        world_y = my / self._sy
        cam_x = max(0.0, min(float(map_px_w - viewport_w), world_x - viewport_w / 2))
        cam_y = max(0.0, min(float(map_px_h - viewport_h), world_y - viewport_h / 2))
        return cam_x, cam_y

    def draw(self, surface: pygame.Surface, buildings: list, units: list,
             dest_xy: "tuple | None" = None,
             cam: "tuple[int,int]" = (0, 0),
             viewport: "tuple[int,int]" = (1060, 720)) -> None:
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

        # Viewport rectangle
        vx = int(cam[0] * self._sx)
        vy = int(cam[1] * self._sy)
        vw = max(1, int(viewport[0] * self._sx))
        vh = max(1, int(viewport[1] * self._sy))
        pygame.draw.rect(self._buf, _VIEW_BOX, (vx, vy, vw, vh), 1)

        pygame.draw.rect(self._buf, _BORDER, (0, 0, self.width, self.height), 1)

        if dest_xy is not None:
            self.rect = pygame.Rect(dest_xy[0], dest_xy[1], self.width, self.height)
            surface.blit(self._buf, dest_xy)
        else:
            sw, sh = surface.get_size()
            dx = sw - self.width - 8
            dy = sh - 80 - self.height - 8
            self.rect = pygame.Rect(dx, dy, self.width, self.height)
            surface.blit(self._buf, (dx, dy))
