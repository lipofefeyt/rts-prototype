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

> **Currently implemented:** Town Hall, Farm, Barracks, Lumber Mill, Blacksmith, Gold Mine, Trees.

---

## Units

| Unit | Faction | Train at | Prereqs | HP | Dmg | Range | Speed | Cost | Time | Status |
|------|---------|----------|---------|-----|-----|-------|-------|------|------|--------|
| Worker | Human | Town Hall | — | 40 | 5 | 80 | 90 | 75g | 6 s | ✅ |
| Peon | Orc | Great Hall | — | 40 | 5 | 80 | 90 | 75g | 6 s | sprites only |
| Footman | Human | Barracks | — | 60 | 10 | 100 (melee) | 85 | 135g | 8 s | ✅ |
| Grunt | Orc | Barracks | — | 70 | 12 | 100 (melee) | 85 | 135g | 8 s | sprites only |
| Archer | Human | Barracks | — | 40 | 15 | 256 (ranged) | 75 | 150g | 10 s | ✅ |
| Troll Axethrower | Orc | Barracks | — | 40 | 12 | 256 (ranged) | 75 | 150g | 10 s | sprites only |
| Knight | Human | Barracks | Blacksmith | 150 | 20 | 96 (melee) | 80 | 800g | 25 s | ✅ |
| Ogre | Orc | Barracks | Foundry | 100 | 18 | 110 (melee) | 80 | 220g | 14 s | — |

> Speed values reflect current `stats.py` (~45% reduction from WC2 originals for feel).

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

## Prereq enforcement (implemented)

`UnitStats.requires` is a tuple of building labels. `Barracks.enqueue` and the player build menu
both check that all required buildings exist for the training team before allowing the action.

---

## Design principles

- **Food cap governs pace** — each Farm adds 4 food; train queue blocks when food_used ≥ food_cap.
- **Two resources** — gold (mine harvest, 100g/trip) and lumber (tree harvest, 10 lumber/chop).
- **Symmetry first** — Human/Orc mirror stats; balance tuned by tweaking `stats.py`.
- **Sprite pipeline first** — real WC2 art extracted from MAINDAT.WAR; carry walk sprites are the remaining gap.
