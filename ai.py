import math
import pygame
from building import TownHall, Barracks, Farm, GoldMine
from unit import Unit, Worker
from stats import UNIT_STATS

# Difficulty knobs (issue #6)
ARMY_THRESHOLD = 4    # combat units needed before launching a wave
WAVE_INTERVAL = 45.0  # seconds between waves
WORKER_REPLACE_COST = UNIT_STATS["worker"].cost


class AIController:
    """
    Three-state machine:  GATHER → (army full?) → ATTACK → GATHER
    Harvesting and training run passively every tick regardless of state.
    """

    def __init__(self, team: int, buildings: list, units: list, gold: dict,
                 game_map, enemy_sprite: pygame.Surface, worker_sprite: pygame.Surface,
                 sheets: dict | None = None):
        self.team = team
        self.buildings = buildings   # shared reference — appends are visible in main
        self.units = units
        self.gold = gold
        self.game_map = game_map
        self.enemy_sprite = enemy_sprite
        self.worker_sprite = worker_sprite
        self.sheets = sheets or {}
        self.state = "gather"
        self._wave_timer = 0.0

    # --- Main tick ---

    def update(self, dt: float) -> None:
        self._wave_timer = max(0.0, self._wave_timer - dt)
        self._tick_workers()
        self._tick_training()
        self._tick_siege()   # idle units at player base finish the job

        if self.state == "gather":
            if len(self._army()) >= ARMY_THRESHOLD and self._wave_timer == 0.0:
                self.state = "attack"

        elif self.state == "attack":
            self._do_attack()
            self._wave_timer = WAVE_INTERVAL
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
        if not barracks:
            return
        food_cap = sum(b.FOOD for b in self.buildings if isinstance(b, Farm) and b.team == self.team)
        food_used = sum(1 for u in self.units if u.team == self.team)
        if food_used >= food_cap or len(barracks.queue) >= Barracks.MAX_QUEUE:
            return
        # Train Archers every third unit for variety
        army_size = len(self._army())
        unit_type = "archer" if army_size % 3 == 2 else "footman"
        if self.gold[self.team] < UNIT_STATS[unit_type].cost:
            unit_type = "footman"  # fall back to cheaper option
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

    # --- Helpers ---

    def _workers(self) -> list:
        return [u for u in self.units if u.team == self.team and isinstance(u, Worker)]

    def _army(self) -> list:
        return [u for u in self.units if u.team == self.team and not isinstance(u, Worker)]

    def _hall(self):
        return next((b for b in self.buildings if isinstance(b, TownHall) and b.team == self.team), None)

    def _barracks(self):
        return next((b for b in self.buildings if isinstance(b, Barracks) and b.team == self.team), None)

    def _nearest_mine(self):
        hall = self._hall()
        mines = [b for b in self.buildings if isinstance(b, GoldMine)]
        if not hall or not mines:
            return None
        return min(mines, key=lambda m: (m.pos - hall.pos).length())
