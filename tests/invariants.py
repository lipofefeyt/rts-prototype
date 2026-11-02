"""Per-frame sanity checks for the headless soak test.

Flags the kind of bug that a short unit test won't catch: NaN positions,
HP drifting out of range, resources going negative, or a unit stuck with
a path it's not making progress on (a pathfinding/AI deadlock).
"""
import math

_STUCK_EPS = 2.0   # px of movement below which a unit is considered "not moving"


class InvariantChecker:
    def __init__(self, stuck_after: float = 10.0):
        self.stuck_after = stuck_after
        self._last_pos: dict[int, tuple[float, float]] = {}
        self._stuck_time: dict[int, float] = {}

    def check(self, frame: int, dt: float, units: list, buildings: list,
              gold: dict, lumber: dict) -> None:
        alive_ids = set()
        for u in units:
            key = id(u)
            alive_ids.add(key)
            x, y = u.pos.x, u.pos.y
            if not (math.isfinite(x) and math.isfinite(y)):
                raise AssertionError(
                    f"frame {frame}: {u.unit_type} (team {u.team}) has a "
                    f"non-finite position ({x}, {y})")
            if not (0 < u.hp <= u.max_hp):
                raise AssertionError(
                    f"frame {frame}: {u.unit_type} (team {u.team}) hp out of "
                    f"range: {u.hp}/{u.max_hp}")

            wants_to_move = bool(u.path)
            last = self._last_pos.get(key)
            moved = last is None or math.hypot(last[0] - x, last[1] - y) > _STUCK_EPS
            # Only accrue stuck-time while the unit actually has somewhere it's
            # trying to go — legitimate pauses (chopping/harvesting/attacking,
            # where path is empty by design) must not carry over into the next
            # movement phase and trigger a false deadlock on its first frame.
            if not wants_to_move or moved:
                self._stuck_time[key] = 0.0
            else:
                self._stuck_time[key] = self._stuck_time.get(key, 0.0) + dt
            if wants_to_move and self._stuck_time[key] > self.stuck_after:
                raise AssertionError(
                    f"frame {frame}: {u.unit_type} (team {u.team}) stuck at "
                    f"({x:.0f}, {y:.0f}) for {self._stuck_time[key]:.1f}s "
                    f"with a non-empty path — likely pathfinding/AI deadlock")
            self._last_pos[key] = (x, y)

        for b in buildings:
            if not (0 < b.hp <= b.max_hp):
                raise AssertionError(
                    f"frame {frame}: {b.label} (team {b.team}) hp out of "
                    f"range: {b.hp}/{b.max_hp}")

        for team, g in gold.items():
            if g < 0:
                raise AssertionError(f"frame {frame}: team {team} gold went negative: {g}")
        for team, l in lumber.items():
            if l < 0:
                raise AssertionError(f"frame {frame}: team {team} lumber went negative: {l}")

        # Bound memory: drop trackers for units that died this frame.
        for key in list(self._last_pos):
            if key not in alive_ids:
                del self._last_pos[key]
                self._stuck_time.pop(key, None)
