import os
import pygame
from stats import UNIT_STATS, UPGRADES

_BAR_W, _BAR_H = 80, 6

# Populated by load_building_sprites() called from main after display is up.
_SPRITES: dict[str, pygame.Surface] = {}
# goldmine_all frames: index 0 = unlit, index 1 = lit (workers inside)
_GOLDMINE_FRAMES: list[pygame.Surface] = []
# Tree tile variants extracted from the forest atlas (32×32 each)
_TREE_TILES: list[pygame.Surface] = []
# Optional user-provided tree PNG (wins over atlas tiles and procedural sprite)
_TREE_PNG: "pygame.Surface | None" = None
# Full complete-tileset sheet for bitmask-based autotile selection
_TREE_COMPLETE_SHEET: "pygame.Surface | None" = None

_SPRITE_DIR        = os.path.join(os.path.dirname(__file__), "assets", "sprites", "buildings")
_TILE_DIR          = os.path.join(os.path.dirname(__file__), "assets", "sprites", "tiles")
_COMPLETE_TILE_DIR = os.path.join(os.path.dirname(__file__), "assets", "sprites", "tiles_complete")
_TILE_SIZE  = 32

# Interior tree tile (row, col) coordinates in the 19-col complete tileset.
# These are all fully-surrounded variants — right for a standalone Tree building.
_COMPLETE_TREE_INTERIOR: tuple[tuple[int, int], ...] = (
    (5, 13), (5, 16), (5, 17), (5, 18),
    (6,  0), (6,  4), (6,  5), (6,  6),
    (6, 11), (6, 13), (6, 14),
    (7,  0), (7,  4), (7,  5), (7,  6), (7,  7), (7,  8),
)
_COMPLETE_TILE_COLS = 19  # forest/winter/wasteland sheet width

# Autotile bitmask → (row, col) coordinates in the 19-col complete tileset.
# N=1 E=2 S=4 W=8; missing bitmasks fall back to 15 (interior).
_TREE_BITMASK_COORDS: dict[int, list[tuple[int, int]]] = {
    1:  [(6,  9)],
    3:  [(5,  7), (6, 16)],
    4:  [(6,  7)],
    5:  [(6,  8)],
    6:  [(5,  9), (7,  3)],
    7:  [(5,  8)],
    9:  [(6, 15)],
    11: [(5, 15), (6, 10), (6, 17)],
    12: [(5, 12), (6, 18)],
    13: [(5, 14)],
    14: [(5, 11), (7,  1)],
    15: [(5, 13), (5, 16), (5, 17), (5, 18),
         (6,  0), (6,  4), (6,  5), (6,  6),
         (6, 11), (6, 13), (6, 14),
         (7,  0), (7,  4), (7,  5), (7,  6), (7,  7), (7,  8)],
}


def load_building_sprites() -> None:
    """Load WC2 building PNGs into the module cache. Call once after pygame display init."""
    global _GOLDMINE_FRAMES, _TREE_TILES, _TREE_PNG, _TREE_COMPLETE_SHEET
    stems = ("townhall_team0", "townhall_team1",
             "barracks_team0", "barracks_team1",
             "farm_team0", "farm_team1",
             "lumbermill_team0", "lumbermill_team1",
             "blacksmith_team0", "blacksmith_team1")
    for stem in stems:
        path = os.path.join(_SPRITE_DIR, f"{stem}.png")
        if os.path.exists(path):
            try:
                _SPRITES[stem] = pygame.image.load(path).convert_alpha()
            except Exception as e:
                print(f"building: warning: {path}: {e}")

    # Load goldmine_all.png as two separate frames (unlit=0, lit=1)
    gm_path = os.path.join(_SPRITE_DIR, "goldmine_all.png")
    if os.path.exists(gm_path):
        try:
            strip = pygame.image.load(gm_path).convert_alpha()
            fw = strip.get_width() // 2
            fh = strip.get_height()
            _GOLDMINE_FRAMES.clear()
            _GOLDMINE_FRAMES.extend([
                strip.subsurface(pygame.Rect(0,  0, fw, fh)).copy(),
                strip.subsurface(pygame.Rect(fw, 0, fw, fh)).copy(),
            ])
        except Exception as e:
            print(f"building: warning: goldmine_all.png: {e}")

    # Load interior tree tiles from the complete tileset (same source as the terrain autotiler).
    complete_path = os.path.join(_COMPLETE_TILE_DIR, "forest.png")
    if os.path.exists(complete_path):
        try:
            sheet = pygame.image.load(complete_path).convert()
            _TREE_COMPLETE_SHEET = sheet
            sw, sh = sheet.get_width(), sheet.get_height()
            _TREE_TILES.clear()
            for tr, tc in _COMPLETE_TREE_INTERIOR:
                x, y = tc * _TILE_SIZE, tr * _TILE_SIZE
                if x + _TILE_SIZE <= sw and y + _TILE_SIZE <= sh:
                    _TREE_TILES.append(
                        sheet.subsurface(pygame.Rect(x, y, _TILE_SIZE, _TILE_SIZE)).copy())
        except Exception as e:
            print(f"building: warning: complete tree tiles: {e}")

    # Optional user-provided tree PNG (any size; scaled to 32×32).
    # Place assets/sprites/buildings/tree.png to override the atlas tiles.
    # Tip: crop a section of assets/sprites/tiles/forest_atlas.png as the source.
    tree_path = os.path.join(_SPRITE_DIR, "tree.png")
    if os.path.exists(tree_path):
        try:
            raw = pygame.image.load(tree_path).convert_alpha()
            _TREE_PNG = pygame.transform.scale(raw, (Tree.W, Tree.H))
        except Exception as e:
            print(f"building: warning: tree.png: {e}")

    total = len(_SPRITES) + (2 if _GOLDMINE_FRAMES else 0) + len(_TREE_TILES) + (1 if _TREE_PNG else 0)
    if total:
        print(f"building: loaded {len(_SPRITES)} building sprites, "
              f"{len(_GOLDMINE_FRAMES)} goldmine frames, {len(_TREE_TILES)} tree tiles"
              f"{', tree.png' if _TREE_PNG else ''}")


class Building:
    label: str = "Building"
    build_time: float = 0.0   # subclasses set > 0 for construction delay

    def __init__(self, rect: pygame.Rect, team: int, hp: int, color: tuple):
        self.rect = rect
        self.pos = pygame.Vector2(rect.centerx, rect.centery)
        self.team = team
        self.hp = self.max_hp = hp
        self.color = color
        self.selected = False
        # Build timer starts at build_time → buildings are complete by default.
        # Call start_construction() right after __init__ to begin a countdown.
        self._build_timer: float = self.build_time

    @property
    def is_complete(self) -> bool:
        return self._build_timer >= self.build_time

    def start_construction(self) -> None:
        """Begin a construction countdown. HP starts at 1 and grows proportionally."""
        if self.build_time > 0:
            self._build_timer = 0.0
            self.hp = 1

    def update_construction(self, dt: float) -> None:
        if self.is_complete:
            return
        self._build_timer = min(self.build_time, self._build_timer + dt)
        self.hp = max(1, int(self.max_hp * self._build_timer / self.build_time))

    def is_alive(self) -> bool:
        return self.hp > 0

    def contains_point(self, point: tuple) -> bool:
        return self.rect.collidepoint(point)

    def _blit_sprite(self, surface: pygame.Surface, stem: str) -> bool:
        """Blit a named sprite centered on self.rect. Returns True if drawn."""
        spr = _SPRITES.get(stem)
        if spr is None:
            return False
        surface.blit(spr, spr.get_rect(center=self.rect.center))
        return True

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, tuple(min(255, c + 50) for c in self.color), self.rect, 2)
        self._draw_health_bar(surface)
        self._draw_construction_bar(surface)

    def _draw_health_bar(self, surface: pygame.Surface) -> None:
        if self.hp >= self.max_hp and not self.selected:
            return
        x = self.rect.centerx - _BAR_W // 2
        y = self.rect.top - 10
        ratio = max(0.0, self.hp / self.max_hp)
        color = (0, 200, 0) if ratio > 0.5 else (220, 180, 0) if ratio > 0.25 else (200, 30, 30)
        pygame.draw.rect(surface, (50, 50, 50), (x, y, _BAR_W, _BAR_H))
        pygame.draw.rect(surface, color, (x, y, int(_BAR_W * ratio), _BAR_H))

    def _draw_construction_bar(self, surface: pygame.Surface) -> None:
        if self.is_complete:
            return
        ratio = self._build_timer / self.build_time if self.build_time > 0 else 1.0
        x = self.rect.centerx - _BAR_W // 2
        y = self.rect.top - 18
        pygame.draw.rect(surface, (30, 30, 60), (x, y, _BAR_W, _BAR_H))
        pygame.draw.rect(surface, (80, 140, 220), (x, y, int(_BAR_W * ratio), _BAR_H))


class TownHall(Building):
    label = "Town Hall"
    W, H = 128, 96
    MAX_QUEUE = 3

    def __init__(self, x: int, y: int, team: int):
        color = (50, 80, 140) if team == 0 else (140, 50, 50)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 1200, color)
        self.queue: list[tuple[str, float]] = []

    def enqueue(self, gold: dict, unit_type: str = "worker", all_buildings: list | None = None) -> bool:
        if len(self.queue) >= self.MAX_QUEUE:
            return False
        s = UNIT_STATS[unit_type]
        if all_buildings and s.requires:
            labels = {b.label for b in all_buildings if b.team == self.team and b.is_complete}
            if not all(r in labels for r in s.requires):
                return False
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
        stem = f"townhall_team{self.team}"
        if not self._blit_sprite(surface, stem):
            pygame.draw.rect(surface, self.color, self.rect)
        self._draw_health_bar(surface)
        self._draw_construction_bar(surface)
        if self.queue:
            ut, remaining = self.queue[0]
            total = UNIT_STATS[ut].train_time
            ratio = 1.0 - remaining / total
            x = self.rect.centerx - 40
            y = self.rect.top - 28
            pygame.draw.rect(surface, (40, 40, 40), (x, y, 80, 5))
            pygame.draw.rect(surface, (100, 200, 100), (x, y, int(80 * ratio), 5))


class GoldMine(Building):
    label = "Gold Mine"
    W, H = 96, 96   # 3×3 grid tiles; sprite is 96×89 so it fits naturally

    def __init__(self, x: int, y: int, gold: int = 5000):
        super().__init__(pygame.Rect(x, y, self.W, self.H), -1, 9999, (190, 160, 0))
        self.gold = gold
        self.workers_inside: int = 0   # incremented while a Worker is harvesting

    def draw(self, surface: pygame.Surface) -> None:
        frames = _GOLDMINE_FRAMES
        if frames:
            # frame 0 = unlit (idle or exhausted), frame 1 = lit (workers inside)
            if self.gold <= 0:
                spr = frames[0].copy()
                spr.fill((80, 80, 80, 0), special_flags=pygame.BLEND_RGB_SUB)
            else:
                spr = frames[1] if self.workers_inside > 0 else frames[0]
            surface.blit(spr, spr.get_rect(center=self.rect.center))
        else:
            color = (120, 100, 60) if self.gold <= 0 else self.color
            pygame.draw.rect(surface, color, self.rect)
            pygame.draw.rect(surface, (240, 210, 40), self.rect, 3)
        if self.selected:
            pygame.draw.rect(surface, (255, 220, 0), self.rect, 2)


class Barracks(Building):
    label = "Barracks"
    W, H = 96, 96
    MAX_QUEUE = 5
    build_time = 30.0

    # Progress-bar color per unit type
    _BAR_COLORS = {"footman": (80, 180, 255), "archer": (80, 220, 160), "knight": (220, 180, 80)}

    def __init__(self, x: int, y: int, team: int):
        color = (40, 70, 120) if team == 0 else (120, 40, 40)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 800, color)
        self.queue: list[tuple[str, float]] = []  # (unit_type, seconds_remaining)

    def enqueue(self, gold: dict, unit_type: str = "footman", all_buildings: list | None = None) -> bool:
        if len(self.queue) >= self.MAX_QUEUE:
            return False
        s = UNIT_STATS[unit_type]
        if all_buildings and s.requires:
            labels = {b.label for b in all_buildings if b.team == self.team and b.is_complete}
            if not all(r in labels for r in s.requires):
                return False
        if gold.get(self.team, 0) < s.cost:
            return False
        gold[self.team] -= s.cost
        self.queue.append((unit_type, s.train_time))
        return True

    def update(self, dt: float) -> list[str]:
        """Tick training queue; returns list of unit_type strings ready to spawn."""
        if not self.is_complete or not self.queue:
            return []
        ut, remaining = self.queue[0]
        self.queue[0] = (ut, remaining - dt)
        spawned: list[str] = []
        while self.queue and self.queue[0][1] <= 0:
            spawned.append(self.queue.pop(0)[0])
        return spawned

    def draw(self, surface: pygame.Surface) -> None:
        stem = f"barracks_team{self.team}"
        if not self._blit_sprite(surface, stem):
            pygame.draw.rect(surface, self.color, self.rect)
        self._draw_health_bar(surface)
        self._draw_construction_bar(surface)
        if self.is_complete and self.queue:
            ut, remaining = self.queue[0]
            total = UNIT_STATS[ut].train_time
            ratio = 1.0 - remaining / total
            x = self.rect.centerx - 40
            y = self.rect.top - 20
            pygame.draw.rect(surface, (40, 40, 40), (x, y, 80, 5))
            bar_color = self._BAR_COLORS.get(ut, (80, 180, 255))
            pygame.draw.rect(surface, bar_color, (x, y, int(80 * ratio), 5))


class Tree(Building):
    label = "Tree"
    W, H = 32, 32
    LUMBER = 100

    _SPRITE: "pygame.Surface | None" = None

    def __init__(self, x: int, y: int, bitmask: int = 15):
        super().__init__(pygame.Rect(x, y, self.W, self.H), -1, self.LUMBER, (34, 85, 34))
        self._bitmask = bitmask
        self._cached_sprite: "pygame.Surface | None" = None

    @classmethod
    def _make_sprite(cls) -> pygame.Surface:
        if cls._SPRITE is not None:
            return cls._SPRITE
        s = pygame.Surface((cls.W, cls.H), pygame.SRCALPHA)
        # Trunk
        pygame.draw.rect(s, (72, 44, 18), (13, 19, 6, 13))
        # Shadow beneath canopy
        pygame.draw.circle(s, (12, 50, 12), (16, 22), 10)
        # Dark outer canopy
        pygame.draw.circle(s, (22, 80, 22), (16, 16), 13)
        # Mid canopy
        pygame.draw.circle(s, (38, 118, 38), (16, 14), 11)
        # Left sub-cluster
        pygame.draw.circle(s, (32, 105, 32), (10, 18), 7)
        # Right sub-cluster
        pygame.draw.circle(s, (32, 105, 32), (22, 17), 6)
        # Top highlight
        pygame.draw.circle(s, (70, 165, 55), (14, 9), 6)
        # Bright specular tip
        pygame.draw.circle(s, (95, 195, 70), (13, 7), 3)
        cls._SPRITE = s
        return s

    def _pick_sprite(self) -> "pygame.Surface | None":
        if _TREE_PNG is not None:
            return _TREE_PNG
        if _TREE_COMPLETE_SHEET is not None:
            coords = _TREE_BITMASK_COORDS.get(self._bitmask) or _TREE_BITMASK_COORDS.get(15, [])
            if coords:
                h = (self.rect.x // _TILE_SIZE * 7 + self.rect.y // _TILE_SIZE * 13) % len(coords)
                tr, tc = coords[h]
                x, y = tc * _TILE_SIZE, tr * _TILE_SIZE
                sw, sh = _TREE_COMPLETE_SHEET.get_size()
                if x + _TILE_SIZE <= sw and y + _TILE_SIZE <= sh:
                    return _TREE_COMPLETE_SHEET.subsurface(
                        pygame.Rect(x, y, _TILE_SIZE, _TILE_SIZE)).copy()
        if _TREE_TILES:
            idx = (self.rect.x // _TILE_SIZE * 7 + self.rect.y // _TILE_SIZE * 13) % len(_TREE_TILES)
            return _TREE_TILES[idx]
        return None

    def draw(self, surface: pygame.Surface) -> None:
        if self._cached_sprite is None:
            self._cached_sprite = self._pick_sprite()
        spr = self._cached_sprite
        if spr is not None:
            if self.hp < self.max_hp:
                spr = spr.copy()
                spr.set_alpha(180)
            surface.blit(spr, self.rect)
        else:
            surface.blit(self._make_sprite(), self.rect)
        pygame.draw.rect(surface, (180, 220, 60), self.rect, 1)
        if self.hp < self.max_hp:
            ratio = self.hp / self.max_hp
            bx, by = self.rect.x + 2, self.rect.y - 6
            pygame.draw.rect(surface, (50, 50, 50), (bx, by, 28, 4))
            pygame.draw.rect(surface, (60, 160, 60), (bx, by, int(28 * ratio), 4))


class Farm(Building):
    label = "Farm"
    W, H = 64, 64
    FOOD = 4
    build_time = 15.0

    def __init__(self, x: int, y: int, team: int):
        color = (60, 120, 50) if team == 0 else (120, 80, 50)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 400, color)

    def draw(self, surface: pygame.Surface) -> None:
        stem = f"farm_team{self.team}"
        if not self._blit_sprite(surface, stem):
            pygame.draw.rect(surface, self.color, self.rect)
        self._draw_health_bar(surface)
        self._draw_construction_bar(surface)


class Blacksmith(Building):
    label = "Blacksmith"
    W, H = 96, 96
    build_time = 30.0
    _RESEARCH_IDS = ("weapons_1", "weapons_2", "armor_1", "armor_2")

    def __init__(self, x: int, y: int, team: int):
        color = (70, 65, 60) if team == 0 else (80, 55, 45)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 700, color)
        self.research_queue: list[tuple[str, float]] = []

    def enqueue_research(self, gold: dict, lumber: dict,
                         research_id: str, done: set) -> bool:
        """Start a research if affordable, not done, prereq met, and queue empty."""
        if self.research_queue or research_id in done:
            return False
        spec = UPGRADES.get(research_id)
        if spec is None or spec.building != self.label:
            return False
        if spec.requires and spec.requires not in done:
            return False
        if gold.get(self.team, 0) < spec.gold or lumber.get(self.team, 0) < spec.wood:
            return False
        gold[self.team] -= spec.gold
        lumber[self.team] -= spec.wood
        self.research_queue.append((research_id, spec.time))
        return True

    def update(self, dt: float) -> list[str]:
        """Tick research queue; returns list of completed research_ids."""
        if not self.is_complete or not self.research_queue:
            return []
        rid, remaining = self.research_queue[0]
        self.research_queue[0] = (rid, remaining - dt)
        done: list[str] = []
        while self.research_queue and self.research_queue[0][1] <= 0:
            done.append(self.research_queue.pop(0)[0])
        return done

    def draw(self, surface: pygame.Surface) -> None:
        stem = f"blacksmith_team{self.team}"
        if not self._blit_sprite(surface, stem):
            pygame.draw.rect(surface, self.color, self.rect)
            cx, cy = self.rect.centerx, self.rect.centery
            pygame.draw.rect(surface, (140, 130, 120), (cx - 18, cy - 8, 36, 14))
            pygame.draw.rect(surface, (140, 130, 120), (cx - 10, cy + 6,  20, 8))
        self._draw_health_bar(surface)
        self._draw_construction_bar(surface)
        if self.is_complete and self.research_queue:
            rid, remaining = self.research_queue[0]
            total = UPGRADES[rid].time
            ratio = 1.0 - remaining / total
            x = self.rect.centerx - 40
            y = self.rect.top - 20
            pygame.draw.rect(surface, (40, 40, 40), (x, y, 80, 5))
            pygame.draw.rect(surface, (200, 180, 80), (x, y, int(80 * ratio), 5))


class LumberMill(Building):
    label = "Lumber Mill"
    W, H = 96, 96
    CARRY_BONUS = 25
    build_time = 25.0
    _RESEARCH_IDS = ("ranger",)

    def __init__(self, x: int, y: int, team: int):
        color = (90, 65, 35) if team == 0 else (100, 60, 30)
        super().__init__(pygame.Rect(x, y, self.W, self.H), team, 600, color)
        self.research_queue: list[tuple[str, float]] = []

    def enqueue_research(self, gold: dict, lumber: dict,
                         research_id: str, done: set) -> bool:
        if self.research_queue or research_id in done:
            return False
        spec = UPGRADES.get(research_id)
        if spec is None or spec.building != self.label:
            return False
        if spec.requires and spec.requires not in done:
            return False
        if gold.get(self.team, 0) < spec.gold or lumber.get(self.team, 0) < spec.wood:
            return False
        gold[self.team] -= spec.gold
        lumber[self.team] -= spec.wood
        self.research_queue.append((research_id, spec.time))
        return True

    def update(self, dt: float) -> list[str]:
        if not self.is_complete or not self.research_queue:
            return []
        rid, remaining = self.research_queue[0]
        self.research_queue[0] = (rid, remaining - dt)
        done: list[str] = []
        while self.research_queue and self.research_queue[0][1] <= 0:
            done.append(self.research_queue.pop(0)[0])
        return done

    def draw(self, surface: pygame.Surface) -> None:
        stem = f"lumbermill_team{self.team}"
        if not self._blit_sprite(surface, stem):
            pygame.draw.rect(surface, self.color, self.rect)
            cx, cy = self.rect.centerx, self.rect.centery
            pygame.draw.line(surface, (200, 180, 140), (cx - 16, cy - 12), (cx + 16, cy + 12), 4)
            pygame.draw.line(surface, (200, 180, 140), (cx + 16, cy - 12), (cx - 16, cy + 12), 4)
        self._draw_health_bar(surface)
        self._draw_construction_bar(surface)
        if self.is_complete and self.research_queue:
            rid, remaining = self.research_queue[0]
            total = UPGRADES[rid].time
            ratio = 1.0 - remaining / total
            x = self.rect.centerx - 40
            y = self.rect.top - 20
            pygame.draw.rect(surface, (40, 40, 40), (x, y, 80, 5))
            pygame.draw.rect(surface, (100, 200, 100), (x, y, int(80 * ratio), 5))
