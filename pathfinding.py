import heapq
import pygame

CELL_SIZE = 32


def world_to_grid(pos: pygame.Vector2, grid_w: int, grid_h: int) -> tuple[int, int]:
    col = max(0, min(int(pos.x / CELL_SIZE), grid_w - 1))
    row = max(0, min(int(pos.y / CELL_SIZE), grid_h - 1))
    return col, row


def grid_to_world_center(col: int, row: int) -> pygame.Vector2:
    return pygame.Vector2(col * CELL_SIZE + CELL_SIZE // 2, row * CELL_SIZE + CELL_SIZE // 2)


def astar(
    blocked: set[tuple[int, int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    grid_w: int,
    grid_h: int,
) -> list[tuple[int, int]]:
    """Returns grid cells from start (exclusive) to goal (inclusive), or [] if unreachable."""
    if goal in blocked:
        return []

    open_heap: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g: dict[tuple[int, int], float] = {start: 0.0}

    def h(c: tuple[int, int]) -> float:
        return abs(c[0] - goal[0]) + abs(c[1] - goal[1])

    while open_heap:
        _, cur = heapq.heappop(open_heap)

        if cur == goal:
            path: list[tuple[int, int]] = []
            while cur in came_from:
                path.append(cur)
                cur = came_from[cur]
            path.reverse()
            return path

        for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            nb = (cur[0] + dc, cur[1] + dr)
            if not (0 <= nb[0] < grid_w and 0 <= nb[1] < grid_h):
                continue
            if nb in blocked:
                continue
            # Prevent clipping through diagonal corners
            if dc and dr and ((cur[0] + dc, cur[1]) in blocked or (cur[0], cur[1] + dr) in blocked):
                continue
            cost = 1.414 if dc and dr else 1.0
            tentative_g = g[cur] + cost
            if tentative_g < g.get(nb, float("inf")):
                came_from[nb] = cur
                g[nb] = tentative_g
                heapq.heappush(open_heap, (tentative_g + h(nb), nb))

    return []
