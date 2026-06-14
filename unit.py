import math
import pygame
from stats import UNIT_STATS
from spritesheet import vel_to_dir, ANIM_FPS, DIR_N

AGGRO_RANGE = 220.0    # idle units auto-attack enemies this close
REPATH_INTERVAL = 0.5  # seconds between A* recalcs while chasing


class Unit:
    _draw_scale: float = 1.0   # subclasses override to render at a different visual size

    def __init__(self, x: float, y: float, image: pygame.Surface,
                 team: int = 0, unit_type: str = "footman", sheet=None):
        self.pos = pygame.Vector2(x, y)
        self.path: list[pygame.Vector2] = []
        self.selected = False
        self.team = team
        self.image = image
        self.rect = pygame.Rect(0, 0, 64, 64)
        self.rect.center = (int(x), int(y))

        self._sheet = sheet
        self._anim_timer = 0.0
        self._last_dir = DIR_N
        self._moving = False
        self.unit_type = unit_type

        s = UNIT_STATS[unit_type]
        self.hp = self.max_hp = s.hp
        self.attack_damage = s.attack_damage
        self.attack_range = s.attack_range
        self.speed = s.speed

        self.armor = 0              # damage reduction per hit; raised by upgrade research
        self.attack_cooldown = 1.0
        self._attack_timer = 0.0
        self._repath_timer = 0.0
        self.attack_target = None   # Unit | Building — duck-typed

        # Pre-bake drop shadow for this unit's scale (drawn each frame, not recreated)
        _sw = max(4, int(36 * self._draw_scale))
        _sh = max(2, int(10 * self._draw_scale))
        self._shadow = pygame.Surface((_sw, _sh), pygame.SRCALPHA)
        pygame.draw.ellipse(self._shadow, (0, 0, 0, 60), self._shadow.get_rect())
        self._shadow_oy = int(22 * self._draw_scale)  # px below center → unit's feet

    # --- Orders ---

    def move_to(self, path: list[pygame.Vector2]) -> None:
        self.attack_target = None
        self.path = list(path)
        self._anim_timer = 0.0

    def order_attack(self, target) -> None:
        self.attack_target = target
        self.path = []
        self._repath_timer = 0.0
        self._anim_timer = 0.0

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
        move_vel = pygame.Vector2(0, 0)
        while self.path:
            direction = self.path[0] - self.pos
            if direction.length() <= 4:
                self.path.pop(0)
            else:
                move_vel = direction.normalize()
                self.pos += move_vel * self.speed * dt
                break

        # Animate facing the destination (last waypoint), not the current waypoint.
        # This keeps direction stable: A* first-step detours no longer cause spin.
        if self.path and move_vel.length_squared() > 0.01:
            dest = self.path[-1] - self.pos
            anim_vel = dest.normalize() if dest.length_squared() > 0.01 else move_vel
        else:
            anim_vel = pygame.Vector2(0, 0)

        self._update_anim(anim_vel, dt)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def _update_anim(self, vel: pygame.Vector2, dt: float) -> None:
        if self._sheet is None:
            return
        if vel.length_squared() > 0.01:
            self._last_dir = vel_to_dir(vel)
            self._anim_timer += dt
            self._moving = True
        else:
            self._moving = False
            self._anim_timer = 0.0

    def _deal_attack(self) -> None:
        if self.attack_target:
            target_armor = getattr(self.attack_target, "armor", 0)
            dmg = max(1, self.attack_damage - target_armor)
            self.attack_target.hp -= dmg

    _DIR_VEC = [
        (0, -1), (1, -1), (1, 0), (1, 1),
        (0, 1), (-1, 1), (-1, 0), (-1, -1),
    ]

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = self.rect.center

        # Drop shadow — drawn first so it appears beneath the sprite
        surface.blit(self._shadow,
                     self._shadow.get_rect(center=(cx, cy + self._shadow_oy)))

        # Sprite (WC2 sheet) or procedural fallback
        if self._sheet is not None:
            tick = int(self._anim_timer * ANIM_FPS) if self._moving else 0
            frame = self._sheet.walk_frame(self._last_dir, tick)
            if self._draw_scale != 1.0:
                fw, fh = frame.get_size()
                frame = pygame.transform.scale(
                    frame, (int(fw * self._draw_scale), int(fh * self._draw_scale)))
            surface.blit(frame, frame.get_rect(center=(cx, cy)))
        else:
            if self._draw_scale != 1.0:
                iw, ih = self.image.get_size()
                img = pygame.transform.scale(
                    self.image, (int(iw * self._draw_scale), int(ih * self._draw_scale)))
                surface.blit(img, img.get_rect(center=(cx, cy)))
            else:
                surface.blit(self.image, self.rect)

        if self.selected:
            # WC2-style corner-bracket selection indicator
            vis  = int(58 * self._draw_scale) if self._sheet else int(56 * self._draw_scale)
            pad  = 5
            bx   = cx - vis // 2 - pad
            by   = cy - vis // 2 - pad
            bw   = bh = vis + 2 * pad
            blen = max(6, bw // 4)
            col  = (0, 230, 0)
            for ox, oy, dx, dy in (
                (bx,      by,      1,  1),
                (bx + bw, by,     -1,  1),
                (bx,      by + bh, 1, -1),
                (bx + bw, by + bh,-1, -1),
            ):
                pygame.draw.line(surface, col, (ox, oy), (ox + dx * blen, oy), 2)
                pygame.draw.line(surface, col, (ox, oy), (ox, oy + dy * blen), 2)

            # Direction pointer — reaches the bracket edge
            if self._sheet is not None:
                dvx, dvy = self._DIR_VEC[self._last_dir]
                n   = math.sqrt(dvx * dvx + dvy * dvy)
                tip = vis // 2 + pad - 1
                pygame.draw.line(surface, (255, 220, 0),
                                 (cx, cy),
                                 (cx + int(dvx / n * tip), cy + int(dvy / n * tip)), 2)

            # Waypoint dots
            for i, wp in enumerate(self.path):
                pygame.draw.circle(surface,
                                   (255, 110, 0) if i == 0 else (180, 65, 0),
                                   (int(wp.x), int(wp.y)), 3)

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
        bar_w = int(48 * self._draw_scale) + 4   # ~52 footman, ~46 archer, ~38 worker
        bar_h = 4
        x = self.rect.centerx - bar_w // 2
        y = self.rect.top - 8
        ratio = max(0.0, self.hp / self.max_hp)
        color = (0, 200, 0) if ratio > 0.5 else (220, 180, 0) if ratio > 0.25 else (200, 30, 30)
        pygame.draw.rect(surface, (0, 0, 0), (x - 1, y - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(surface, (35, 35, 35), (x, y, bar_w, bar_h))
        if ratio > 0:
            pygame.draw.rect(surface, color, (x, y, max(1, int(bar_w * ratio)), bar_h))


class Archer(Unit):
    """Ranged unit: fires a homing Projectile instead of dealing instant damage."""

    _draw_scale: float = 0.88   # lighter build than footman — visually distinguishable

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
    """Harvests gold from a GoldMine and returns it to a TownHall drop-off.
    Also chops Trees for lumber via order_chop()."""

    _draw_scale: float = 0.72  # workers are visually smaller than combat units
    CARRY_CAP = 10
    HARVEST_TIME = 3.0
    PROXIMITY = 80   # pixels from building edge (checked via rect inflation)
    LUMBER_CARRY_CAP = 25
    CHOP_TIME = 3.0

    def __init__(self, x: float, y: float, image: pygame.Surface, team: int = 0, sheet=None):
        super().__init__(x, y, image, team, unit_type="worker", sheet=sheet)
        self.gold_delivered = 0
        self.lumber_delivered = 0
        self._mine = None
        self._dropoff = None
        self._carrying = 0
        self._wstate = "idle"
        self._harvest_timer = 0.0
        self._tree = None
        self._lumber_carrying = 0
        self._chop_timer = 0.0
        self._buildings_ref: list | None = None  # set by order_chop for auto-cycle

    def order_harvest(self, mine, dropoff, game_map) -> None:
        self._mine = mine
        self._dropoff = dropoff
        self._wstate = "to_mine"
        self.attack_target = None
        self.path = game_map.find_path(self.pos, mine.pos)

    def order_chop(self, tree, dropoff, game_map, buildings=None) -> None:
        self._tree = tree
        self._dropoff = dropoff
        self._buildings_ref = buildings
        self._wstate = "to_tree"
        self.attack_target = None
        self._anim_timer = 0.0
        self.path = game_map.find_path(self.pos, tree.pos)

    def _find_next_tree(self):
        """Return nearest alive Tree from _buildings_ref, or None."""
        if self._buildings_ref is None:
            return None
        from building import Tree as _Tree
        candidates = [b for b in self._buildings_ref
                      if isinstance(b, _Tree) and b.hp > 0]
        if not candidates:
            return None
        return min(candidates, key=lambda t: (t.pos - self.pos).length())

    def _near(self, building) -> bool:
        """True when self.pos is within PROXIMITY px of building's rect edge."""
        pad = building.rect.inflate(self.PROXIMITY * 2, self.PROXIMITY * 2)
        return pad.collidepoint(int(self.pos.x), int(self.pos.y))

    def update(self, dt: float, enemies: list, game_map) -> None:  # noqa: C901
        if self._wstate == "to_mine" and self._mine:
            if self._mine.gold <= 0:
                self._wstate = "idle"
            elif self._near(self._mine):
                self.path = []
                self._wstate = "harvesting"
                self._harvest_timer = self.HARVEST_TIME

        elif self._wstate == "harvesting":
            self._harvest_timer -= dt
            if self._harvest_timer <= 0:
                amount = min(self.CARRY_CAP, self._mine.gold)
                self._mine.gold -= amount
                self._carrying = amount
                self._wstate = "to_hall"
                if self._dropoff:
                    self.path = game_map.find_path(self.pos, self._dropoff.pos)

        elif self._wstate == "to_hall" and self._dropoff:
            if self._near(self._dropoff):
                self.path = []
                self.gold_delivered += self._carrying
                self._carrying = 0
                if self._mine and self._mine.gold > 0:
                    self._wstate = "to_mine"
                    self.path = game_map.find_path(self.pos, self._mine.pos)
                else:
                    self._wstate = "idle"

        elif self._wstate == "to_tree" and self._tree:
            if self._tree.hp <= 0:
                self._wstate = "idle"
            elif self._near(self._tree):
                self.path = []
                self._wstate = "chopping"
                self._chop_timer = self.CHOP_TIME

        elif self._wstate == "chopping":
            if self._tree and self._tree.hp <= 0:
                if self._lumber_carrying > 0 and self._dropoff:
                    self._wstate = "to_hall_lumber"
                    self.path = game_map.find_path(self.pos, self._dropoff.pos)
                else:
                    self._wstate = "idle"
            else:
                self._chop_timer -= dt
                if self._chop_timer <= 0 and self._tree:
                    amount = min(self.LUMBER_CARRY_CAP, self._tree.hp)
                    self._tree.hp -= amount
                    self._lumber_carrying += amount
                    self._wstate = "to_hall_lumber"
                    if self._dropoff:
                        self.path = game_map.find_path(self.pos, self._dropoff.pos)

        elif self._wstate == "to_hall_lumber" and self._dropoff:
            if self._near(self._dropoff):
                self.path = []
                self.lumber_delivered += self._lumber_carrying
                self._lumber_carrying = 0
                if self._tree and self._tree.hp > 0:
                    self._wstate = "to_tree"
                    self.path = game_map.find_path(self.pos, self._tree.pos)
                else:
                    # Tree exhausted — cycle to the nearest alive tree if we have a reference
                    next_tree = self._find_next_tree()
                    if next_tree is not None:
                        self._tree = next_tree
                        self._wstate = "to_tree"
                        self.path = game_map.find_path(self.pos, next_tree.pos)
                    else:
                        self._wstate = "idle"

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

        move_vel = pygame.Vector2(0, 0)
        while self.path:
            direction = self.path[0] - self.pos
            if direction.length() <= 4:
                self.path.pop(0)
            else:
                move_vel = direction.normalize()
                self.pos += move_vel * self.speed * dt
                break

        if self.path and move_vel.length_squared() > 0.01:
            dest = self.path[-1] - self.pos
            anim_vel = dest.normalize() if dest.length_squared() > 0.01 else move_vel
        else:
            anim_vel = pygame.Vector2(0, 0)
        self._update_anim(anim_vel, dt)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
