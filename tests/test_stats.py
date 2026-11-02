from stats import UNIT_STATS, UPGRADES


def test_all_unit_stats_have_positive_core_fields():
    for name, s in UNIT_STATS.items():
        assert s.hp > 0, name
        assert s.attack_damage > 0, name
        assert s.attack_range > 0, name
        assert s.speed > 0, name
        assert s.cost > 0, name
        assert s.train_time > 0, name


def test_knight_requires_blacksmith():
    assert "Blacksmith" in UNIT_STATS["knight"].requires


def test_base_tier1_units_have_no_requirements():
    assert UNIT_STATS["footman"].requires == ()
    assert UNIT_STATS["archer"].requires == ()
    assert UNIT_STATS["worker"].requires == ()


def test_upgrade_prereq_chain_weapons():
    assert UPGRADES["weapons_1"].requires is None
    assert UPGRADES["weapons_2"].requires == "weapons_1"


def test_upgrade_prereq_chain_armor():
    assert UPGRADES["armor_1"].requires is None
    assert UPGRADES["armor_2"].requires == "armor_1"


def test_upgrade_effects_reference_known_unit_types():
    for rid, spec in UPGRADES.items():
        for unit_type, stat_name, delta in spec.effects:
            assert unit_type in UNIT_STATS, f"{rid} affects unknown unit {unit_type}"
            assert delta != 0, rid


def test_ranger_training_is_archer_only():
    spec = UPGRADES["ranger"]
    affected_types = {ut for ut, _, _ in spec.effects}
    assert affected_types == {"archer"}
