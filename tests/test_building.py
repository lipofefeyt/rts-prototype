from building import Farm, Barracks, Blacksmith, TownHall
from main import food_stats


def test_construction_starts_at_one_hp_and_incomplete():
    f = Farm(0, 0, team=0)
    f.start_construction()
    assert f.hp == 1
    assert not f.is_complete


def test_construction_progress_matches_formula():
    f = Farm(0, 0, team=0)
    f.start_construction()
    f.update_construction(Farm.build_time / 2)
    expected = max(1, int(f.max_hp * 0.5))
    assert f.hp == expected
    assert not f.is_complete


def test_construction_completes_at_build_time():
    f = Farm(0, 0, team=0)
    f.start_construction()
    f.update_construction(Farm.build_time)
    assert f.is_complete
    assert f.hp == f.max_hp


def test_construction_clamps_at_build_time():
    f = Farm(0, 0, team=0)
    f.start_construction()
    f.update_construction(Farm.build_time * 10)   # way overshoot
    assert f.is_complete
    assert f.hp == f.max_hp


def test_food_cap_only_counts_complete_player_farms():
    incomplete = Farm(0, 0, team=0)
    incomplete.start_construction()
    complete = Farm(100, 0, team=0)
    enemy = Farm(200, 0, team=1)
    enemy.start_construction()
    enemy.update_construction(Farm.build_time)

    used, cap = food_stats([incomplete, complete, enemy], [])
    assert cap == Farm.FOOD   # only `complete` counts: incomplete isn't done, enemy is team 1


def test_barracks_enqueue_respects_queue_cap():
    b = Barracks(0, 0, team=0)
    gold = {0: 10_000}
    for _ in range(Barracks.MAX_QUEUE):
        assert b.enqueue(gold, "footman")
    assert not b.enqueue(gold, "footman")   # queue full


def test_barracks_enqueue_fails_without_gold():
    b = Barracks(0, 0, team=0)
    gold = {0: 1}
    assert not b.enqueue(gold, "footman")
    assert gold[0] == 1   # nothing deducted on failure


def test_knight_requires_blacksmith_present():
    b = Barracks(0, 0, team=0)
    gold = {0: 10_000}
    no_blacksmith = [b]
    assert not b.enqueue(gold, "knight", no_blacksmith)

    blacksmith = Blacksmith(0, 0, team=0)
    blacksmith.start_construction()
    blacksmith.update_construction(Blacksmith.build_time)
    assert b.enqueue(gold, "knight", [b, blacksmith])


def test_research_requires_prereq_completed():
    bs = Blacksmith(0, 0, team=0)
    bs.start_construction()
    bs.update_construction(Blacksmith.build_time)
    gold = {0: 10_000}
    lumber = {0: 10_000}

    # weapons_2 requires weapons_1 to be in `done` first.
    assert not bs.enqueue_research(gold, lumber, "weapons_2", done=set())
    assert bs.enqueue_research(gold, lumber, "weapons_1", done=set())


def test_research_queue_is_single_slot():
    bs = Blacksmith(0, 0, team=0)
    bs.start_construction()
    bs.update_construction(Blacksmith.build_time)
    gold = {0: 10_000}
    lumber = {0: 10_000}

    assert bs.enqueue_research(gold, lumber, "weapons_1", done=set())
    assert not bs.enqueue_research(gold, lumber, "armor_1", done=set())
