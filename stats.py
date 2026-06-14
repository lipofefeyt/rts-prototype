from dataclasses import dataclass, field


@dataclass(frozen=True)
class UnitStats:
    hp: int
    attack_damage: int
    attack_range: float
    speed: float
    cost: int
    train_time: float


UNIT_STATS: dict[str, UnitStats] = {
    "footman": UnitStats(hp=60,  attack_damage=10, attack_range=100.0, speed=150.0, cost=135, train_time=8.0),
    "archer":  UnitStats(hp=40,  attack_damage=15, attack_range=256.0, speed=130.0, cost=150, train_time=10.0),
    "worker":  UnitStats(hp=40,  attack_damage=5,  attack_range=80.0,  speed=160.0, cost=75,  train_time=6.0),
    "knight":  UnitStats(hp=150, attack_damage=20, attack_range=96.0,  speed=130.0, cost=800, train_time=25.0),
}


@dataclass(frozen=True)
class UpgradeSpec:
    name: str
    building: str               # label of building where research happens
    gold: int
    wood: int
    time: float                 # seconds
    effects: tuple              # ((unit_type, stat_name, delta), ...)
    requires: "str | None"      # upgrade_id that must complete first


# All melee units benefit from weapons/armor upgrades.
# Ranger Training is archer-exclusive (range + damage).
UPGRADES: dict[str, UpgradeSpec] = {
    "weapons_1": UpgradeSpec(
        "Improved Weapons I",  "Blacksmith", 150, 0, 12,
        (("footman", "attack_damage", 2), ("knight", "attack_damage", 2)),
        None,
    ),
    "weapons_2": UpgradeSpec(
        "Improved Weapons II", "Blacksmith", 250, 0, 16,
        (("footman", "attack_damage", 2), ("knight", "attack_damage", 2)),
        "weapons_1",
    ),
    "armor_1": UpgradeSpec(
        "Improved Armor I",    "Blacksmith", 150, 0, 12,
        (("footman", "armor", 2), ("knight", "armor", 2)),
        None,
    ),
    "armor_2": UpgradeSpec(
        "Improved Armor II",   "Blacksmith", 250, 0, 16,
        (("footman", "armor", 2), ("knight", "armor", 2)),
        "armor_1",
    ),
    "ranger": UpgradeSpec(
        "Ranger Training",     "LumberMill", 200, 0, 14,
        (("archer", "attack_range", 64), ("archer", "attack_damage", 3)),
        None,
    ),
}
