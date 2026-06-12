# RTS Prototype — Design Reference

Warcraft 2-inspired. Two mirrored factions: **Humans** (blue, team 0) vs **Orcs** (red, team 1).

---

## Tech Tree

```
Town Hall ──────────────────── Farm
     │                          (no prereqs, just gold)
     └─── Barracks ──────────── Lumber Mill ─── Blacksmith
               │                                     │
               │                                     └── (upgrade: weapons/armor)
               ├── Footman / Grunt     (Tier 1)
               ├── Archer  / Troll     (Tier 1)
               └── Knight  / Ogre      (Tier 2, requires Blacksmith)
```

---

## Buildings

| Building | Faction | Prereqs | HP | Cost | Food Cap |
|----------|---------|---------|-----|------|----------|
| Town Hall | Human | — | 1200 | start | — |
| Great Hall | Orc | — | 1200 | start | — |
| Farm | Human | Town Hall | 400 | 80g | +4 |
| Pig Farm | Orc | Great Hall | 400 | 80g | +4 |
| Barracks | Human | Town Hall | 800 | 150g | — |
| Barracks | Orc | Great Hall | 800 | 150g | — |
| Lumber Mill | Human | Barracks | 600 | 200g | — |
| Mill | Orc | Barracks | 600 | 200g | — |
| Blacksmith | Human | Barracks + Lumber Mill | 700 | 250g | — |
| Foundry | Orc | Barracks + Mill | 700 | 250g | — |
| Guard Tower | Human | Lumber Mill | 300 | 130g | — |
| Watch Tower | Orc | Mill | 300 | 130g | — |

> **Currently implemented:** Town Hall, Farm, Barracks, Gold Mine (neutral).

---

## Units

| Unit | Faction | Train at | Prereqs | HP | Dmg | Range | Speed | Cost | Time |
|------|---------|----------|---------|-----|-----|-------|-------|------|------|
| Worker | Human | Town Hall | — | 40 | 5 | 80 | 160 | 75g | 6 s |
| Peon | Orc | Great Hall | — | 40 | 5 | 80 | 160 | 75g | 6 s |
| Footman | Human | Barracks | — | 60 | 10 | 100 (melee) | 150 | 135g | 8 s |
| Grunt | Orc | Barracks | — | 70 | 12 | 100 (melee) | 145 | 135g | 8 s |
| Archer | Human | Barracks | — | 40 | 15 | 256 (ranged) | 130 | 150g | 10 s |
| Troll Axethrower | Orc | Barracks | — | 40 | 12 | 256 (ranged) | 130 | 150g | 10 s |
| Knight | Human | Barracks | Blacksmith | 90 | 20 | 110 (melee) | 120 | 220g | 14 s |
| Ogre | Orc | Barracks | Foundry | 100 | 18 | 110 (melee) | 110 | 220g | 14 s |

> **Currently implemented:** Worker, Footman (Unit), Archer.

---

## Upgrades (Blacksmith / Foundry)

| Upgrade | Effect | Cost | Time |
|---------|--------|------|------|
| Improved Weapons Lv1 | +2 melee damage all units | 150g | 12 s |
| Improved Weapons Lv2 | +2 melee damage (requires Lv1) | 250g | 16 s |
| Improved Armor Lv1 | +2 effective HP (damage reduction) | 150g | 12 s |
| Improved Armor Lv2 | +2 effective HP (requires Lv1) | 250g | 16 s |
| Ranger Training (Lumber Mill) | Archer range 256 → 320, +3 dmg | 200g | 14 s |

---

## How to enforce prereqs in code

`stats.py` already has `UNIT_STATS`. Add a `requires` field:

```python
@dataclass(frozen=True)
class UnitStats:
    ...
    requires: tuple[str, ...] = ()   # building labels that must exist

UNIT_STATS = {
    "footman": UnitStats(..., requires=()),
    "archer":  UnitStats(..., requires=()),
    "knight":  UnitStats(..., requires=("Blacksmith",)),
}
```

Check in `draw_hud` / `Barracks.enqueue`:

```python
def _prereqs_met(unit_type: str, buildings: list) -> bool:
    labels = {b.label for b in buildings if b.team == team and b.is_alive()}
    return all(r in labels for r in UNIT_STATS[unit_type].requires)
```

---

## Design principles

- **Food cap governs pace** — each extra Farm lets you field 4 more units.
- **Gold is the only resource** (wood dropped for simplicity; add a `Lumber` resource later if wanted).
- **Symmetry first** — mirror Human/Orc stats ±10% so balance is easy to tune.
- **One new Tier 2 unit at a time** — Knight is the natural next implementation target.
