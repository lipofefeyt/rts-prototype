import pygame
from pathfinding import CELL_SIZE, world_to_grid, grid_to_world_center, astar


class GameMap:
    def __init__(self, width: int, height: int):
        self.grid_w = width // CELL_SIZE
        self.grid_h = height // CELL_SIZE
        self.obstacles: list[pygame.Rect] = []
        self.blocked: set[tuple[int, int]] = set()

    def add_obstacle(self, rect: pygame.Rect) -> None:
        self.obstacles.append(rect)
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
            return [pygame.Vector2(goal_pos)]  # fallback: straight-line

        path = [grid_to_world_center(c, r) for c, r in cells]
        path[-1] = pygame.Vector2(goal_pos)  # snap last waypoint to exact click
        return path

    def draw(self, surface: pygame.Surface) -> None:
        for obs in self.obstacles:
            pygame.draw.rect(surface, (100, 60, 20), obs)
            pygame.draw.rect(surface, (150, 100, 50), obs, 2)
