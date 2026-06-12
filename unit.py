import pygame

MELEE_RANGE = 100.0    # center-to-center px to land a hit
AGGRO_RANGE = 220.0    # idle units auto-attack enemies that walk this close
REPATH_INTERVAL = 0.5  # seconds between A* re-calculations while chasing


class Unit:
    def __init__(self, x: float, y: float, image: pygame.Surface, team: int = 0):
        self.pos = pygame.Vector2(x, y)
        self.path: list[pygame.Vector2] = []
        self.speed = 150.0
        self.selected = False
        self.team = team
        self.image = image
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

        self.hp = 60
        self.max_hp = 60
        self.attack_damage = 10
        self.attack_range = MELEE_RANGE
        self.attack_cooldown = 1.0  # seconds between hits
        self._attack_timer = 0.0
        self._repath_timer = 0.0
        self.attack_target: 'Unit | None' = None

    # --- Orders ---

    def move_to(self, path: list[pygame.Vector2]) -> None:
        self.attack_target = None
        self.path = list(path)

    def order_attack(self, target: 'Unit') -> None:
        self.attack_target = target
        self.path = []
        self._repath_timer = 0.0

    # --- Per-frame ---

    def update(self, dt: float, enemies: list['Unit'], game_map) -> None:
        self._attack_timer = max(0.0, self._attack_timer - dt)
        self._repath_timer = max(0.0, self._repath_timer - dt)

        # Drop dead target
        if self.attack_target is not None and not self.attack_target.is_alive():
            self.attack_target = None

        # Auto-aggro: idle units react to nearby enemies
        if self.attack_target is None and not self.path:
            nearest, nearest_dist = None, AGGRO_RANGE
            for e in enemies:
                d = (e.pos - self.pos).length()
                if d < nearest_dist:
                    nearest_dist, nearest = d, e
            if nearest:
                self.attack_target = nearest

        # Combat + chasing
        if self.attack_target is not None:
            dist = (self.attack_target.pos - self.pos).length()
            if dist <= self.attack_range:
                self.path = []  # stop; we're in range
                if self._attack_timer == 0.0:
                    self.attack_target.hp -= self.attack_damage
                    self._attack_timer = self.attack_cooldown
            else:
                # Chase: re-path periodically so we track a moving target
                if self._repath_timer == 0.0:
                    self.path = game_map.find_path(self.pos, self.attack_target.pos)
                    self._repath_timer = REPATH_INTERVAL

        # Movement along waypoints
        while self.path:
            direction = self.path[0] - self.pos
            if direction.length() <= 4:
                self.path.pop(0)
            else:
                self.pos += direction.normalize() * self.speed * dt
                break

        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.image, self.rect)
        if self.selected:
            pygame.draw.circle(surface, (0, 255, 0), self.rect.center, 70, 2)
        self._draw_health_bar(surface)

    # --- Queries ---

    def is_alive(self) -> bool:
        return self.hp > 0

    def contains_point(self, point: tuple) -> bool:
        return self.rect.collidepoint(point)

    # --- Internal ---

    def _draw_health_bar(self, surface: pygame.Surface) -> None:
        if self.hp >= self.max_hp and not self.selected:
            return
        bar_w, bar_h = 80, 6
        x = self.rect.centerx - bar_w // 2
        y = self.rect.top - 10
        ratio = max(0.0, self.hp / self.max_hp)
        color = (0, 200, 0) if ratio > 0.5 else (220, 180, 0) if ratio > 0.25 else (200, 30, 30)
        pygame.draw.rect(surface, (50, 50, 50), (x, y, bar_w, bar_h))
        pygame.draw.rect(surface, color, (x, y, int(bar_w * ratio), bar_h))
