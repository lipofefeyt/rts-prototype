from pathfinding import astar


def test_straight_line_no_obstacles():
    path = astar(set(), (0, 0), (5, 0), grid_w=10, grid_h=10)
    assert path[-1] == (5, 0)
    assert len(path) == 5   # start excluded, goal included


def test_path_around_obstacle():
    # Solid wall across row 1, cols 0-4, forces a detour.
    blocked = {(c, 1) for c in range(5)}
    path = astar(blocked, (0, 0), (0, 2), grid_w=10, grid_h=10)
    assert path
    assert path[-1] == (0, 2)
    assert not any(cell in blocked for cell in path)


def test_unreachable_goal_returns_empty():
    # Goal itself is blocked -> no path.
    path = astar({(5, 5)}, (0, 0), (5, 5), grid_w=10, grid_h=10)
    assert path == []


def test_fully_enclosed_goal_returns_empty():
    cx, cy = 5, 5
    ring = {(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if not (dx == 0 and dy == 0)}
    path = astar(ring, (0, 0), (cx, cy), grid_w=10, grid_h=10)
    assert path == []


def test_no_diagonal_corner_clipping():
    # Both orthogonal neighbors of the diagonal step are blocked, so the
    # 1-step diagonal shortcut from (1,1) to (2,2) must be disallowed —
    # the solver has to detour around, producing a longer path.
    blocked = {(2, 1), (1, 2)}
    path = astar(blocked, (1, 1), (2, 2), grid_w=6, grid_h=6)
    assert path
    assert path[-1] == (2, 2)
    assert len(path) > 1   # direct diagonal step would have been length 1
    assert not any(cell in blocked for cell in path)


def test_same_start_and_goal():
    path = astar(set(), (3, 3), (3, 3), grid_w=10, grid_h=10)
    assert path == []
