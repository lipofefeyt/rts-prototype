import math
import pygame
from building import TownHall, Barracks, Farm, GoldMine, Blacksmith
from unit import Unit, Worker
from stats import UNIT_STATS
from pathfinding import CELL_SIZE

# Difficulty presets (issue #17)
DIFFICULTY = {
    "easy":   {"army_threshold": 2, "wave_interval": 90.0},
    "normal": {"army_threshold": 4, "wave_interval": 45.0},
    "hard":   {"army_threshold": 7, "wave_interval": 22.0},
}

WORKER_REPLACE_COST   = UNIT_STATS["worker"].cost
FARM_GOLD_COST        = 250
BARRACKS_GOLD_COST    = 500
BLACKSMITH_GOLD_COST  = 800
BUILD_CHECK_INTERVAL  = 8.0  # seconds between AI build evaluations


class AIController:
    """
    Three-state machine:  GATHER → (army full?) → ATTACK → GATHER
    Harvesting and training run passively every tick regardless of state.
    """

    def __init__(self, team: int, buildings: list, units: list, gold: dict,
                 game_map, enemy_sprite: pygame.Surface, worker_sprite: pygame.Surface,
                 sheets: dict | None = None, difficulty: str = "normal"):
        self.team = team
        self.buildings = buildings   # shared reference — appends are visible in main
        self.units = units
        self.gold = gold
        self.game_map = game_map
        self.enemy_sprite = enemy_sprite
        self.worker_sprite = worker_sprite
        self.sheets = sheets or {}
        d = DIFFICULTY.get(difficulty, DIFFICULTY["normal"])
        self._army_threshold = d["army_threshold"]
        self._wave_interval   = d["wave_interval"]
        self.state = "gather"
        self._wave_timer  = 0.0
        self._build_timer = 0.0

    # --- Main tick ---

    def update(self, dt: float) -> None:
        self._wave_timer  = max(0.0, self._wave_timer  - dt)
        self._build_timer = max(0.0, self._build_timer - dt)
        self._tick_workers()
        self._tick_training()
        self._tick_siege()

        if self._build_timer == 0.0:
            self._tick_build()
            self._build_timer = BUILD_CHECK_INTERVAL

        if self.state == "gather":
            if len(self._army()) >= self._army_threshold and self._wave_timer == 0.0:
                self.state = "attack"

        elif self.state == "attack":
            self._do_attack()
            self._wave_timer = self._wave_interval
            self.state = "gather"

    # --- Passive management (runs every frame) ---

    def _tick_workers(self) -> None:
        mine = self._nearest_mine()
        hall = self._hall()
        if not mine or not hall:
            return

        workers = self._workers()
        for w in workers:
            if w._wstate == "idle":
                w.order_harvest(mine, hall, self.game_map)

        # Replace a lost worker if the AI can afford it
        if not workers and self.gold[self.team] >= WORKER_REPLACE_COST:
            sp = pygame.Vector2(hall.rect.right + 40, hall.rect.centery)
            sheet = self.sheets.get(('worker', self.team))
            self.units.append(Worker(sp.x, sp.y, self.worker_sprite, team=self.team, sheet=sheet))
            self.gold[self.team] -= WORKER_REPLACE_COST

    def _tick_training(self) -> None:
        barracks = self._barracks()
        if not barracks or not barracks.is_complete:
            return
        food_cap = sum(b.FOOD for b in self.buildings
                       if isinstance(b, Farm) and b.team == self.team and b.is_complete)
        food_used = sum(1 for u in self.units if u.team == self.team)
        if food_used >= food_cap or len(barracks.queue) >= Barracks.MAX_QUEUE:
            return
        # Rotate unit types: footman / footman / archer; knight replaces footman when Blacksmith ready
        army_size = len(self._army())
        if army_size % 3 == 2:
            unit_type = "archer"
        elif self._blacksmith_ready():
            unit_type = "knight"
        else:
            unit_type = "footman"
        if self.gold[self.team] < UNIT_STATS[unit_type].cost:
            unit_type = "footman"
        if self.gold[self.team] >= UNIT_STATS[unit_type].cost:
            barracks.enqueue(self.gold, unit_type)

    # --- Attack ---

    def _do_attack(self) -> None:
        """March the whole army toward the player base. Auto-aggro handles en-route combat."""
        player_hall = next(
            (b for b in self.buildings if isinstance(b, TownHall) and b.team != self.team), None
        )
        army = self._army()
        if not player_hall or not army:
            return
        cols = max(1, math.ceil(math.sqrt(len(army))))
        total_w = (cols - 1) * 100
        total_h = (math.ceil(len(army) / cols) - 1) * 100
        for i, u in enumerate(army):
            c = i % cols
            r = i // cols
            tgt = pygame.Vector2(
                player_hall.pos.x - total_w / 2 + c * 100,
                player_hall.pos.y - total_h / 2 + r * 100,
            )
            u.move_to(self.game_map.find_path(u.pos, tgt))

    def _tick_siege(self) -> None:
        """Units that arrive at the player base with no remaining enemies switch to attacking the TownHall."""
        player_hall = next(
            (b for b in self.buildings if isinstance(b, TownHall) and b.team != self.team), None
        )
        if not player_hall:
            return
        for u in self._army():
            if u.attack_target is None and not u.path:
                if (player_hall.pos - u.pos).length() < 300:
                    u.order_attack(player_hall)

    # --- Building ---

    def _tick_build(self) -> None:
        """Place a Farm when food-capped; rebuild Barracks/Blacksmith when missing."""
        food_cap  = sum(b.FOOD for b in self.buildings
                        if isinstance(b, Farm) and b.team == self.team and b.is_complete)
        food_used = sum(1 for u in self.units if u.team == self.team)

        if food_used >= food_cap and self.gold[self.team] >= FARM_GOLD_COST:
            rect = self._find_placement(Farm)
            if rect:
                f = Farm(rect.x, rect.y, team=self.team)
                f.start_construction()
                self.buildings.append(f)
                self.game_map.add_obstacle(f.rect)
                self.gold[self.team] -= FARM_GOLD_COST

        if not self._barracks() and self.gold[self.team] >= BARRACKS_GOLD_COST:
            rect = self._find_placement(Barracks)
            if rect:
                b = Barracks(rect.x, rect.y, team=self.team)
                b.start_construction()
                self.buildings.append(b)
                self.game_map.add_obstacle(b.rect)
                self.gold[self.team] -= BARRACKS_GOLD_COST

        if (self._barracks() and not self._blacksmith()
                and self.gold[self.team] >= BLACKSMITH_GOLD_COST):
            rect = self._find_placement(Blacksmith)
            if rect:
                bs = Blacksmith(rect.x, rect.y, team=self.team)
                bs.start_construction()
                self.buildings.append(bs)
                self.game_map.add_obstacle(bs.rect)
                self.gold[self.team] -= BLACKSMITH_GOLD_COST

    def _find_placement(self, building_class) -> "pygame.Rect | None":
        """Spiral outward from TownHall looking for the first valid grid-snapped spot."""
        hall = self._hall()
        if not hall:
            return None
        gw = self.game_map.grid_w * CELL_SIZE
        gh = self.game_map.grid_h * CELL_SIZE
        for dist in range(CELL_SIZE, 360, CELL_SIZE):
            for deg in range(0, 360, 20):
                angle = math.radians(deg)
                sx = int((hall.pos.x + math.cos(angle) * dist) // CELL_SIZE) * CELL_SIZE
                sy = int((hall.pos.y + math.sin(angle) * dist) // CELL_SIZE) * CELL_SIZE
                rect = pygame.Rect(sx, sy, building_class.W, building_class.H)
                if self._placement_valid(rect, gw, gh):
                    return rect
        return None

    def _placement_valid(self, rect: pygame.Rect, gw: int, gh: int) -> bool:
        if rect.left < 0 or rect.top < 0 or rect.right > gw or rect.bottom > gh - 80:
            return False
        col0 = rect.left  // CELL_SIZE
        row0 = rect.top   // CELL_SIZE
        col1 = (rect.right  + CELL_SIZE - 1) // CELL_SIZE
        row1 = (rect.bottom + CELL_SIZE - 1) // CELL_SIZE
        for c in range(col0, col1):
            for r in range(row0, row1):
                if (c, r) in self.game_map.blocked:
                    return False
        pad = rect.inflate(8, 8)
        return not any(pad.colliderect(b.rect) for b in self.buildings)

    # --- Helpers ---

    def _workers(self) -> list:
        return [u for u in self.units if u.team == self.team and isinstance(u, Worker)]

    def _army(self) -> list:
        return [u for u in self.units if u.team == self.team and not isinstance(u, Worker)]

    def _hall(self):
        return next((b for b in self.buildings if isinstance(b, TownHall) and b.team == self.team), None)

    def _barracks(self):
        return next((b for b in self.buildings if isinstance(b, Barracks) and b.team == self.team), None)

    def _blacksmith(self):
        return next((b for b in self.buildings if isinstance(b, Blacksmith) and b.team == self.team), None)

    def _blacksmith_ready(self) -> bool:
        b = self._blacksmith()
        return b is not None and b.is_complete

    def _nearest_mine(self):
        hall = self._hall()
        mines = [b for b in self.buildings if isinstance(b, GoldMine) and b.gold > 0]
        if not hall or not mines:
            return None
        return min(mines, key=lambda m: (m.pos - hall.pos).length())
