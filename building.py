import pygame
from stats import UNIT_STATS

_BAR_W, _BAR_H = 80, 6


class Building:
    label: str = "Building"

    def __init__(self, rect: pygame.Rect, team: int, hp: int, color: tuple):
        self.rect = rect
        self.pos = pygame.Vector2(rect.centerx, rect.centery)
        self.team = team
        self.hp = self.max_hp = hp
        self.color = color
        self.selected = False

    def is_alive(self) -> bool:
        return self.hp > 0

    def contains_point(self, point: tuple) -> bool:
        return self.rect.collidepoint(point)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.color, self.rect)
        border = (255, 220, 0) if self.selected else tuple(min(255, c + 50) for c in self.color)
        pygame.draw.rect(surface, border, self.rect, 2)
        self._draw_health_bar(surface)

    def _draw_health_bar(self, surface: pygame.Surface) -> None:
        if self.hp >= self.max_hp and not self.selected:
            return
        x = self.rect.centerx - _BAR_W // 2
        y = self.rect.top - 10
        ratio = max(0.0, self.hp / self.max_hp)
        color = (0, 200, 0) if ratio > 0.5 else (220, 180, 0) if ratio > 0.25 else (200, 30, 30)
        pygame.draw.rect(surface, (50, 50, 50), (x, y, _BAR_W, _BAR_H))
        pygame.draw.rect(surface, color, (x, y, int(_BAR_W * ratio), _BAR_H))


class TownHall(Building):
    label = "Town Hall"
    W, H = 160, 128

    def __init__(self, x: int, y: int, team: int):
        color = (50, 80, 140) if team == 0 else (140, 50, 50)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 1200, color)


class GoldMine(Building):
    label = "Gold Mine"
    W, H = 96, 96

    def __init__(self, x: int, y: int, gold: int = 5000):
        super().__init__(pygame.Rect(x, y, self.W, self.H), -1, 9999, (190, 160, 0))
        self.gold = gold

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, (240, 210, 40), self.rect, 3)


class Barracks(Building):
    label = "Barracks"
    W, H = 128, 128
    MAX_QUEUE = 5

    # Progress-bar color per unit type
    _BAR_COLORS = {"footman": (80, 180, 255), "archer": (80, 220, 160)}

    def __init__(self, x: int, y: int, team: int):
        color = (40, 70, 120) if team == 0 else (120, 40, 40)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 800, color)
        self.queue: list[tuple[str, float]] = []  # (unit_type, seconds_remaining)

    def enqueue(self, gold: dict, unit_type: str = "footman") -> bool:
        if len(self.queue) >= self.MAX_QUEUE:
            return False
        s = UNIT_STATS[unit_type]
        if gold.get(self.team, 0) < s.cost:
            return False
        gold[self.team] -= s.cost
        self.queue.append((unit_type, s.train_time))
        return True

    def update(self, dt: float) -> list[str]:
        """Tick training queue; returns list of unit_type strings ready to spawn."""
        if not self.queue:
            return []
        ut, remaining = self.queue[0]
        self.queue[0] = (ut, remaining - dt)
        spawned: list[str] = []
        while self.queue and self.queue[0][1] <= 0:
            spawned.append(self.queue.pop(0)[0])
        return spawned

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        if self.queue:
            ut, remaining = self.queue[0]
            total = UNIT_STATS[ut].train_time
            ratio = 1.0 - remaining / total
            x = self.rect.centerx - 40
            y = self.rect.top - 20
            pygame.draw.rect(surface, (40, 40, 40), (x, y, 80, 5))
            bar_color = self._BAR_COLORS.get(ut, (80, 180, 255))
            pygame.draw.rect(surface, bar_color, (x, y, int(80 * ratio), 5))


class Farm(Building):
    label = "Farm"
    W, H = 96, 96
    FOOD = 4

    def __init__(self, x: int, y: int, team: int):
        color = (60, 120, 50) if team == 0 else (120, 80, 50)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 400, color)
