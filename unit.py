import pygame
from stats import UNIT_STATS
from spritesheet import vel_to_dir, ANIM_FPS, DIR_S

AGGRO_RANGE = 220.0    # idle units auto-attack enemies this close
REPATH_INTERVAL = 0.5  # seconds between A* recalcs while chasing


class Unit:
    def __init__(self, x: float, y: float, image: pygame.Surface,
                 team: int = 0, unit_type: str = "footman", sheet=None):
        self.pos = pygame.Vector2(x, y)
        self.path: list[pygame.Vector2] = []
        self.selected = False
        self.team = team
        self.image = image
        # Fixed 64×64 hit-box regardless of sprite sheet frame dimensions
        self.rect = pygame.Rect(0, 0, 64, 64)
        self.rect.center = (int(x), int(y))

        self._sheet = sheet
        self._anim_timer = 0.0
        self._last_dir = DIR_S
        self._moving = False
        self._dir_cooldown = 0  # frames remaining before direction can change again

        s = UNIT_STATS[unit_type]
        self.hp = self.max_hp = s.hp
        self.attack_damage = s.attack_damage
        self.attack_range = s.attack_range
        self.speed = s.speed

        self.attack_cooldown = 1.0
        self._attack_timer = 0.0
        self._repath_timer = 0.0
        self.attack_target = None   # Unit | Building — duck-typed

    # --- Orders ---

    def move_to(self, path: list[pygame.Vector2]) -> None:
        self.attack_target = None
        self.path = list(path)

    def order_attack(self, target) -> None:
        self.attack_target = target
        self.path = []
        self._repath_timer = 0.0

    # --- Per-frame ---

    def update(self, dt: float, enemies: list['Unit'], game_map) -> None:
        self._attack_timer = max(0.0, self._attack_timer - dt)
        self._repath_timer = max(0.0, self._repath_timer - dt)

        if self.attack_target is not None and not self.attack_target.is_alive():
            self.attack_target = None

        # Auto-aggro
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
                self.path = []
                if self._attack_timer == 0.0:
                    self._deal_attack()
                    self._attack_timer = self.attack_cooldown
            else:
                if self._repath_timer == 0.0:
                    self.path = game_map.find_path(self.pos, self.attack_target.pos)
                    self._repath_timer = REPATH_INTERVAL

        # Waypoint movement
        old_pos = pygame.Vector2(self.pos)
        while self.path:
            direction = self.path[0] - self.pos
            if direction.length() <= 4:
                self.path.pop(0)
            else:
                self.pos += direction.normalize() * self.speed * dt
                break
        self._update_anim(self.pos - old_pos, dt)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    _DIR_COOLDOWN = 6   # frames to hold a direction before accepting another change

    def _update_anim(self, vel: pygame.Vector2, dt: float) -> None:
        if self._sheet is None:
            return
        if vel.length_squared() > 0.01:
            new_dir = vel_to_dir(vel)
            if self._dir_cooldown > 0:
                self._dir_cooldown -= 1
            elif new_dir != self._last_dir:
                self._last_dir = new_dir
                self._dir_cooldown = self._DIR_COOLDOWN
            self._anim_timer += dt
            self._moving = True
        else:
            self._moving = False
            self._anim_timer = 0.0

    def _deal_attack(self) -> None:
        if self.attack_target:
            self.attack_target.hp -= self.attack_damage

    def draw(self, surface: pygame.Surface) -> None:
        if self._sheet is not None:
            tick = int(self._anim_timer * ANIM_FPS) if self._moving else 0
            frame = self._sheet.walk_frame(self._last_dir, tick)
            surface.blit(frame, frame.get_rect(center=self.rect.center))
        else:
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


class Archer(Unit):
    """Ranged unit: fires a homing Projectile instead of dealing instant damage."""

    def __init__(self, x: float, y: float, image: pygame.Surface, team: int = 0, sheet=None):
        super().__init__(x, y, image, team, unit_type="archer", sheet=sheet)
        self.projectiles_pending: list = []   # drained by main each frame

    def _deal_attack(self) -> None:
        from projectile import Projectile
        if self.attack_target:
            self.projectiles_pending.append(
                Projectile(pygame.Vector2(self.pos), self.attack_target,
                           self.attack_damage, self.team)
            )


class Worker(Unit):
    """Harvests gold from a GoldMine and returns it to a TownHall drop-off."""

    CARRY_CAP = 10
    HARVEST_TIME = 3.0
    PROXIMITY = 90

    def __init__(self, x: float, y: float, image: pygame.Surface, team: int = 0, sheet=None):
        super().__init__(x, y, image, team, unit_type="worker", sheet=sheet)
        self.gold_delivered = 0
        self._mine = None
        self._dropoff = None
        self._carrying = 0
        self._wstate = "idle"
        self._harvest_timer = 0.0

    def order_harvest(self, mine, dropoff, game_map) -> None:
        self._mine = mine
        self._dropoff = dropoff
        self._wstate = "to_mine"
        self.attack_target = None
        self.path = game_map.find_path(self.pos, mine.pos)

    def update(self, dt: float, enemies: list, game_map) -> None:
        if self._wstate == "to_mine" and self._mine:
            if not self.path and (self._mine.pos - self.pos).length() < self.PROXIMITY:
                self._wstate = "harvesting"
                self._harvest_timer = self.HARVEST_TIME

        elif self._wstate == "harvesting":
            self._harvest_timer -= dt
            if self._harvest_timer <= 0:
                self._carrying = self.CARRY_CAP
                self._wstate = "to_hall"
                if self._dropoff:
                    self.path = game_map.find_path(self.pos, self._dropoff.pos)

        elif self._wstate == "to_hall" and self._dropoff:
            if not self.path and (self._dropoff.pos - self.pos).length() < self.PROXIMITY:
                self.gold_delivered += self._carrying
                self._carrying = 0
                self._wstate = "to_mine"
                if self._mine:
                    self.path = game_map.find_path(self.pos, self._mine.pos)

        self._attack_timer = max(0.0, self._attack_timer - dt)
        self._repath_timer = max(0.0, self._repath_timer - dt)

        if self.attack_target is not None:
            if not self.attack_target.is_alive():
                self.attack_target = None
            else:
                dist = (self.attack_target.pos - self.pos).length()
                if dist <= self.attack_range:
                    self.path = []
                    if self._attack_timer == 0.0:
                        self.attack_target.hp -= self.attack_damage
                        self._attack_timer = self.attack_cooldown

        old_pos = pygame.Vector2(self.pos)
        while self.path:
            direction = self.path[0] - self.pos
            if direction.length() <= 4:
                self.path.pop(0)
            else:
                self.pos += direction.normalize() * self.speed * dt
                break
        self._update_anim(self.pos - old_pos, dt)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
