import pygame

from unit import Unit
from stats import UNIT_STATS


def _make_unit(unit_type="footman", team=0):
    image = pygame.Surface((1, 1))
    return Unit(0, 0, image, team=team, unit_type=unit_type)


def test_damage_formula_no_armor():
    attacker = _make_unit("footman")
    target = _make_unit("footman", team=1)
    attacker.order_attack(target)
    start_hp = target.hp
    attacker._deal_attack()
    assert target.hp == start_hp - UNIT_STATS["footman"].attack_damage


def test_damage_formula_with_armor_reduces_damage():
    attacker = _make_unit("footman")
    target = _make_unit("footman", team=1)
    target.armor = 4
    attacker.order_attack(target)
    start_hp = target.hp
    attacker._deal_attack()
    dealt = start_hp - target.hp
    assert dealt == UNIT_STATS["footman"].attack_damage - 4


def test_damage_never_drops_below_one():
    attacker = _make_unit("footman")
    target = _make_unit("footman", team=1)
    target.armor = 999   # far exceeds attack_damage
    attacker.order_attack(target)
    start_hp = target.hp
    attacker._deal_attack()
    assert start_hp - target.hp == 1


def test_hit_flash_set_on_damage():
    attacker = _make_unit("footman")
    target = _make_unit("footman", team=1)
    attacker.order_attack(target)
    assert target._hit_flash == 0.0
    attacker._deal_attack()
    assert target._hit_flash > 0.0


def test_unit_dies_at_zero_hp():
    u = _make_unit("footman")
    assert u.is_alive()
    u.hp = 1
    u.hp -= 5
    assert not u.is_alive()


def test_weapon_upgrade_increases_damage_dealt():
    attacker = _make_unit("footman")
    target = _make_unit("footman", team=1)
    attacker.attack_damage += 2   # simulate Improved Weapons I applied
    attacker.order_attack(target)
    start_hp = target.hp
    attacker._deal_attack()
    assert start_hp - target.hp == UNIT_STATS["footman"].attack_damage + 2
