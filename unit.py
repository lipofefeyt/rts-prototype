import math
import pygame
from stats import UNIT_STATS
from spritesheet import vel_to_dir, DIR_S
from pathfinding import CELL_SIZE

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
        self.rect = pygame.Rect(0, 0, CELL_SIZE, CELL_SIZE)
        self.rect.center = (int(x), int(y))

        self._sheet = sheet
        self._anim_timer = 0.0
        self._last_dir = DIR_S
        self._moving = False
        self._dir_candidate = DIR_S   # proposed direction before hysteresis
        self._dir_frames = 0          # consecutive frames candidate has held
        self.unit_type = unit_type

        s = UNIT_STATS[unit_type]
        self.hp = self.max_hp = s.hp
        self.attack_damage = s.attack_damage
        self.attack_range = s.attack_range
        self.speed = s.speed

        self.armor = 0              # damage reduction per hit; raised by upgrade research
        self.attack_cooldown = 1.0
        self._attack_timer = 0.0
        self._attack_anim_timer = 0.0   # how long to hold the attack-pose frame
        self._repath_timer = 0.0
        self.attack_target = None   # Unit | Building — duck-typed

        # Pre-bake drop shadow for this unit's scale (drawn each frame, not recreated)
        _sw = max(4, int(36 * self._draw_scale))
        _sh = max(2, int(10 * self._draw_scale))
        self._shadow = pygame.Surface((_sw, _sh), pygame.SRCALPHA)
        pygame.draw.ellipse(self._shadow, (0, 0, 0, 60), self._shadow.get_rect())
        self._shadow_oy = int(22 * self._draw_scale)  # px below center → unit's feet
        self._hit_flash = 0.0   # seconds of white-flash remaining after taking damage

    @property
    def cell(self) -> tuple[int, int]:
        """Grid cell (col, row) this unit currently occupies — 1×1 tile footprint."""
        return (int(self.pos.x) // CELL_SIZE, int(self.pos.y) // CELL_SIZE)

    # --- Orders ---

    def move_to(self, path: list[pygame.Vector2]) -> None:
        self.attack_target = None
        self.path = list(path)

    def order_attack(self, target) -> None:
        self.attack_target = target
        self.path = []
        self._repath_timer = 0.0
        self._anim_timer = 0.0

    # --- Per-frame ---

    def update(self, dt: float, enemies: list['Unit'], game_map) -> None:
        self._attack_timer      = max(0.0, self._attack_timer      - dt)
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt)
        self._repath_timer      = max(0.0, self._repath_timer      - dt)
        self._hit_flash         = max(0.0, self._hit_flash         - dt)

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

    _DIR_HOLD = 4   # frames a new direction must be stable before committing

    # Pixels of movement per animation frame advance (one pose switch per half-tile)
    _ANIM_DIST_PER_FRAME: float = 16.0

    def _update_anim(self, vel: pygame.Vector2, dt: float) -> None:
        if self._sheet is None:
            return
        dist = vel.length()
        if dist > 0.01:
            candidate = vel_to_dir(vel)
            if candidate == self._dir_candidate:
                self._dir_frames += 1
            else:
                self._dir_candidate = candidate
                self._dir_frames = 1
            if self._dir_frames >= self._DIR_HOLD:
                self._last_dir = candidate
            self._anim_timer += dist
            self._moving = True
        else:
            self._moving = False
            self._anim_timer = 0.0

    def _deal_attack(self) -> None:
        if self.attack_target:
            self._attack_anim_timer = 0.3
            target_armor = getattr(self.attack_target, "armor", 0)
            dmg = max(1, self.attack_damage - target_armor)
            self.attack_target.hp -= dmg
            if hasattr(self.attack_target, '_hit_flash'):
                self.attack_target._hit_flash = 0.18

    _DIR_VEC = [
        (0, -1), (1, -1), (1, 0), (1, 1),
        (0, 1), (-1, 1), (-1, 0), (-1, -1),
    ]

    def draw(self, surface: pygame.Surface) -> None:
        if getattr(self, 'inside_building', False):
            return   # hidden while physically inside a building

        cx, cy = self.rect.center

        # Drop shadow — drawn first so it appears beneath the sprite
        surface.blit(self._shadow,
                     self._shadow.get_rect(center=(cx, cy + self._shadow_oy)))

        # Sprite (WC2 sheet) or procedural fallback
        if self._sheet is not None:
            if self._attack_anim_timer > 0 and hasattr(self._sheet, 'attack_frame'):
                atk_tick = int((0.3 - self._attack_anim_timer) / 0.1)
                frame = self._sheet.attack_frame(self._last_dir, atk_tick)
            else:
                tick = int(self._anim_timer / self._ANIM_DIST_PER_FRAME) if self._moving else 0
                walk_pose = (1 + tick % 4) if self._moving else 0
                frame = self._sheet.walk_frame(self._last_dir, walk_pose)
            if self._draw_scale != 1.0:
                fw, fh = frame.get_size()
                frame = pygame.transform.scale(
                    frame, (int(fw * self._draw_scale), int(fh * self._draw_scale)))
            surface.blit(frame, frame.get_rect(center=(cx, cy)))
            if self._hit_flash > 0:
                flash = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
                flash.fill((255, 255, 255, int(180 * self._hit_flash / 0.18)))
                surface.blit(flash, flash.get_rect(center=(cx, cy)))
        else:
            if self._draw_scale != 1.0:
                iw, ih = self.image.get_size()
                img = pygame.transform.scale(
                    self.image, (int(iw * self._draw_scale), int(ih * self._draw_scale)))
                surface.blit(img, img.get_rect(center=(cx, cy)))
                if self._hit_flash > 0:
                    flash = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                    flash.fill((255, 255, 255, int(180 * self._hit_flash / 0.18)))
                    surface.blit(flash, flash.get_rect(center=(cx, cy)))
            else:
                surface.blit(self.image, self.rect)
                if self._hit_flash > 0:
                    flash = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                    flash.fill((255, 255, 255, int(180 * self._hit_flash / 0.18)))
                    surface.blit(flash, self.rect)

        if self.selected:
            # WC2-style corner-bracket selection indicator.
            # vis matches the visible character within the 64-px sprite frame (~44 px),
            # not the frame itself, so brackets hug the sprite without spilling onto
            # adjacent buildings.
            vis  = int(44 * self._draw_scale) if self._sheet else int(30 * self._draw_scale)
            pad  = 3
            bx   = cx - vis // 2 - pad
            by   = cy - vis // 2 - pad
            bw   = bh = vis + 2 * pad
            blen = max(5, bw // 4)
            col  = (0, 230, 0)
            for ox, oy, dx, dy in (
                (bx,      by,      1,  1),
                (bx + bw, by,     -1,  1),
                (bx,      by + bh, 1, -1),
                (bx + bw, by + bh,-1, -1),
            ):
                pygame.draw.line(surface, col, (ox, oy), (ox + dx * blen, oy), 2)
                pygame.draw.line(surface, col, (ox, oy), (ox, oy + dy * blen), 2)

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
        # Anchor above the visible sprite character, not rect.top (rect is 1×1 cell).
        y = self.rect.centery - int(30 * self._draw_scale) - 8
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
    PROXIMITY = 20   # pixels from building edge (checked via rect inflation)
    LUMBER_CARRY_CAP = 25
    CHOP_TIME = 5.0

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
        self._lumber_carry_cap = self.LUMBER_CARRY_CAP
        self._chop_timer = 0.0
        self._buildings_ref: list | None = None  # set by order_chop for auto-cycle

    @property
    def inside_building(self) -> bool:
        """True while the worker is physically inside a building (harvesting)."""
        return self._wstate == "harvesting"

    def move_to(self, path: list[pygame.Vector2]) -> None:
        """Cancel any active gather/chop cycle before issuing the move."""
        if self._wstate == "harvesting" and self._mine:
            self._mine.workers_inside = max(0, self._mine.workers_inside - 1)
        self._wstate = "idle"
        self._tree = None
        self._mine = None
        super().move_to(path)

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
                self._mine.workers_inside += 1   # enter mine visually

        elif self._wstate == "harvesting":
            self._harvest_timer -= dt
            if self._harvest_timer <= 0:
                amount = min(self.CARRY_CAP, self._mine.gold)
                self._mine.gold -= amount
                self._carrying = amount
                self._mine.workers_inside = max(0, self._mine.workers_inside - 1)
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
                tree_dir = self._tree.pos - self.pos
                if tree_dir.length_squared() > 0.01:
                    self._last_dir = vel_to_dir(tree_dir)

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
                    amount = min(self._lumber_carry_cap, self._tree.hp)
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

        self._attack_timer      = max(0.0, self._attack_timer      - dt)
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt)
        self._repath_timer      = max(0.0, self._repath_timer      - dt)
        if self._wstate == "chopping" and self._attack_anim_timer == 0.0:
            self._attack_anim_timer = 0.3  # keep axe-swing cycling while chopping

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

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        # Carry indicator: positioned 12px above the health bar anchor
        cx = self.rect.centerx
        cy = self.rect.centery - int(30 * self._draw_scale) - 20
        if self._wstate == "to_hall" and self._carrying > 0:
            # Gold bag — yellow circle with dark outline
            pygame.draw.circle(surface, (255, 215, 0), (cx, cy), 7)
            pygame.draw.circle(surface, (140, 110, 0), (cx, cy), 7, 1)
        elif self._wstate == "to_hall_lumber" and self._lumber_carrying > 0:
            # Lumber bundle — brown rectangle with a lighter highlight stripe
            r = pygame.Rect(cx - 9, cy - 5, 18, 10)
            pygame.draw.rect(surface, (130, 75, 20), r)
            pygame.draw.line(surface, (170, 110, 50), (r.left + 2, r.centery - 2), (r.right - 3, r.centery - 2))
            pygame.draw.line(surface, (170, 110, 50), (r.left + 2, r.centery + 1), (r.right - 3, r.centery + 1))
            pygame.draw.rect(surface, (80, 45, 10), r, 1)
