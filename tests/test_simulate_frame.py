import math

import pygame

import main
from unit import Unit, Worker
from building import GoldMine, TownHall
from map import GameMap
from fog import FogOfWar

_OPEN_MAP = ["G" * 20 for _ in range(20)]


class _NullAI:
    """No-op AI stand-in for tests that only care about unit/worker mechanics."""
    def update(self, dt: float) -> None:
        pass


def _blank_sprite(*_args):
    return pygame.Surface((1, 1))


def _run_frames(n, dt, **kwargs):
    """Drive simulate_frame() for n frames, feeding back the rebound state each time."""
    state = dict(
        units=[], buildings=[], corpses=[], projectiles=[], selected=[],
        selected_building=None, attack_alert=0.0, elapsed=0.0,
    )
    state.update(kwargs)
    game_over = None
    for _ in range(n):
        (state['units'], state['buildings'], state['corpses'], state['projectiles'],
         state['selected'], state['selected_building'], state['attack_alert'],
         state['elapsed'], game_over) = main.simulate_frame(
            dt, state['units'], state['buildings'], state['gold'], state['lumber'],
            state['corpses'], state['projectiles'], state['float_texts'],
            state['upgrades'], state['ai'], state['game_map'], state['fog'],
            state['selected'], state['selected_building'], state['attack_alert'],
            state['elapsed'], state['font'], state['play_sound'], state['sprite'],
            state['sheet'])
        if game_over:
            break
    return state, game_over


def _placeholder_halls():
    """Both teams need a living Town Hall or simulate_frame's victory/defeat
    check ends the match on the very first frame."""
    return [TownHall(2000, 2000, team=0), TownHall(2100, 2000, team=1)]


def test_simulate_frame_moves_unit_to_target():
    game_map = GameMap(_OPEN_MAP)
    image = pygame.Surface((1, 1))
    u = Unit(50, 50, image, team=0, unit_type="footman")
    target = pygame.Vector2(300, 300)
    u.move_to(game_map.find_path(u.pos, target))

    state, _ = _run_frames(
        400, 1 / 60,
        units=[u], buildings=_placeholder_halls(), gold={0: 0, 1: 0}, lumber={0: 0, 1: 0},
        upgrades={0: set(), 1: set()}, ai=_NullAI(), game_map=game_map,
        fog=FogOfWar(game_map.grid_w, game_map.grid_h), font=pygame.font.Font(None, 16),
        play_sound=lambda *_: None, sprite=_blank_sprite, sheet=lambda *_: None,
        float_texts=[],
    )
    moved_unit = state['units'][0]
    assert (moved_unit.pos - target).length() < 8


def test_simulate_frame_worker_delivers_gold_through_full_loop():
    game_map = GameMap(_OPEN_MAP)
    mine = GoldMine(0, 0, gold=500)
    hall = TownHall(300, 0, team=0)
    image = pygame.Surface((1, 1))
    worker = Worker(mine.pos.x, mine.pos.y, image, team=0)
    worker.order_harvest(mine, hall, game_map)

    gold = {0: 500, 1: 500}
    state, _ = _run_frames(
        1000, 1 / 30,
        units=[worker], buildings=[mine, hall, TownHall(2100, 2000, team=1)],
        gold=gold, lumber={0: 200, 1: 200},
        upgrades={0: set(), 1: set()}, ai=_NullAI(), game_map=game_map,
        fog=FogOfWar(game_map.grid_w, game_map.grid_h), font=pygame.font.Font(None, 16),
        play_sound=lambda *_: None, sprite=_blank_sprite, sheet=lambda *_: None,
        float_texts=[],
    )
    # 1000 frames at dt=1/30 is enough time for several harvest/delivery cycles,
    # not just one — check delivery happened in CARRY_CAP-sized increments rather
    # than pinning the exact count.
    assert gold[0] > 500
    assert (gold[0] - 500) % Worker.CARRY_CAP == 0


def test_full_game_state_runs_2000_frames_without_error():
    state = main.init_game_state("normal", map_seed=4874)
    unit_sprites, war2_sheets = state['unit_sprites'], state['war2_sheets']

    def sprite(t, team):
        return unit_sprites.get((t, team), unit_sprites[('footman', team % 2)])

    def sheet(t, team):
        return war2_sheets.get((t, team))

    units, buildings = state['units'], state['buildings']
    gold, lumber = state['gold'], state['lumber']
    corpses, projectiles, float_texts = state['corpses'], state['projectiles'], state['float_texts']
    upgrades, ai = state['upgrades'], state['ai']
    game_map, fog = state['game_map'], state['fog']
    selected, selected_building = state['selected'], state['selected_building']
    font = pygame.font.Font(None, 16)
    attack_alert = elapsed = 0.0
    initial_gold, initial_lumber = gold[1], lumber[1]

    for _ in range(2000):
        (units, buildings, corpses, projectiles, selected, selected_building,
         attack_alert, elapsed, game_over) = main.simulate_frame(
            1 / 60, units, buildings, gold, lumber, corpses, projectiles, float_texts,
            upgrades, ai, game_map, fog, selected, selected_building, attack_alert,
            elapsed, font, lambda *_: None, sprite, sheet)
        for u in units:
            assert math.isfinite(u.pos.x) and math.isfinite(u.pos.y)
        if game_over:
            break

    assert gold[1] >= 0 and lumber[1] >= 0
    # ~33 simulated seconds is enough for the AI's worker to complete several
    # harvest/chop cycles — resources should have moved from their start values.
    assert gold[1] != initial_gold or lumber[1] != initial_lumber
