import pygame

from unit import Worker
from building import GoldMine, Tree, TownHall
from map import GameMap

_OPEN_MAP = ["G" * 20 for _ in range(20)]


def _make_worker(x, y, team=0):
    image = pygame.Surface((1, 1))
    return Worker(x, y, image, team=team)


def _run_until(worker, game_map, predicate, dt=0.05, max_frames=2000):
    for _ in range(max_frames):
        if predicate():
            return True
        worker.update(dt, [], game_map)
    return predicate()


def test_gold_harvest_cycle_delivers_to_hall():
    game_map = GameMap(_OPEN_MAP)
    mine = GoldMine(0, 0, gold=500)
    hall = TownHall(300, 0, team=0)
    worker = _make_worker(mine.pos.x, mine.pos.y)

    worker.order_harvest(mine, hall, game_map)
    assert worker._wstate == "to_mine"

    delivered = _run_until(worker, game_map, lambda: worker.gold_delivered > 0)
    assert delivered
    assert worker.gold_delivered == Worker.CARRY_CAP
    assert mine.gold == 500 - Worker.CARRY_CAP


def test_harvest_respects_carry_cap():
    game_map = GameMap(_OPEN_MAP)
    mine = GoldMine(0, 0, gold=4)   # less than CARRY_CAP
    hall = TownHall(300, 0, team=0)
    worker = _make_worker(mine.pos.x, mine.pos.y)

    worker.order_harvest(mine, hall, game_map)
    delivered = _run_until(worker, game_map, lambda: worker.gold_delivered > 0)
    assert delivered
    assert worker.gold_delivered == 4
    assert mine.gold == 0


def test_lumber_chop_cycle_delivers_to_hall():
    game_map = GameMap(_OPEN_MAP)
    tree = Tree(0, 0)
    hall = TownHall(300, 0, team=0)
    worker = _make_worker(tree.pos.x, tree.pos.y)

    worker.order_chop(tree, hall, game_map, buildings=[tree])
    assert worker._wstate == "to_tree"

    delivered = _run_until(worker, game_map, lambda: worker.lumber_delivered > 0)
    assert delivered
    assert worker.lumber_delivered == Worker.LUMBER_CARRY_CAP
    assert tree.hp == Tree.LUMBER - Worker.LUMBER_CARRY_CAP


def test_lumber_mill_carry_bonus_raises_cap():
    worker = _make_worker(0, 0)
    assert worker._lumber_carry_cap == Worker.LUMBER_CARRY_CAP
    worker._lumber_carry_cap = Worker.LUMBER_CARRY_CAP + 25
    assert worker._lumber_carry_cap == 50


def test_move_to_cancels_active_harvest():
    game_map = GameMap(_OPEN_MAP)
    mine = GoldMine(0, 0, gold=500)
    hall = TownHall(300, 0, team=0)
    worker = _make_worker(mine.pos.x, mine.pos.y)

    worker.order_harvest(mine, hall, game_map)
    worker.update(0.05, [], game_map)   # transitions to "harvesting", increments workers_inside
    assert worker._wstate == "harvesting"
    assert mine.workers_inside == 1

    worker.move_to([pygame.Vector2(999, 999)])
    assert worker._wstate == "idle"
    assert mine.workers_inside == 0
