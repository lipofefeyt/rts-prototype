from dataclasses import dataclass


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
}
