# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project

Warcraft 2-inspired RTS prototype. Learning project — not aiming to ship. Built with Python 3.12 + pygame 2.6.1, running natively in WSL2.

## Running

```bash
source .venv/bin/activate
python main.py        # ESC or close window to quit
```

## Architecture

| File | Responsibility |
|------|---------------|
| `main.py` | Game loop, event handling, box selection, formation move, HUD, build menu, tech-tree UI |
| `unit.py` | `Unit` (move, combat, draw), `Worker` (harvest gold/lumber, carry, build) |
| `building.py` | All building classes: `TownHall`, `Barracks`, `Farm`, `GoldMine`, `Tree`, `Blacksmith`, `LumberMill` |
| `map.py` | `GameMap`: obstacle grid, A* calls, map generation (`generate_map`) |
| `pathfinding.py` | `astar()` + grid↔world helpers; `CELL_SIZE = 32` |
| `ai.py` | `AIController`: gather→attack state machine, build placement, worker dispatching |
| `stats.py` | `UnitStats`, `UNIT_STATS` dict, `UPGRADES` dict |
| `spritesheet.py` | `SpriteSheet`: frame extraction, walk/attack/death frame helpers |
| `sprites.py` | libwar2 ctypes bridge — extracts PNG strips from MAINDAT.WAR |
| `fog.py` | `FogOfWar`: per-team visibility grid, reveal/shroud |
| `minimap.py` | `Minimap`: draws terrain + units + buildings at small scale |
| `corpse.py` | `Corpse`: timed decay animation |
| `projectile.py` | `Projectile`: arrow/ballista in-flight objects |
| `sound.py` | Sound effect loading + playback |

### Key constants
- **Viewport:** 1280×720, left 160 px = HUD sidebar, right 1120 px = game world
- **Grid:** `CELL_SIZE = 32 px`, map varies by seed
- **Map seed:** locked to `4874` for the current skirmish map

### Sprite layout (WC2 unit strips)
- Strips are **pose-major**: `frame_idx = pose * 5 + strip_dir`
- 5 stored directions: N, NE, E, SE, S (indices 0–4); SW/W/NW are mirrors of SE/E/NE
- `vel_to_dir(v)` maps velocity → 8-way direction 0–7; `strip_dir()` maps to 0–4 + flip flag
- Walk poses 0–4, attack poses 5–7 (Footman/Archer) or 5–9 (Worker, 5 attack poses), death fills the rest

### Data flow for a right-click move
1. `main.py` computes per-unit formation targets around the click point
2. For each unit: `game_map.find_path(unit.pos, target)` → `astar()` → `list[Vector2]`
3. `unit.move_to(path)` stores waypoints; `unit.update(dt)` advances through them each frame

### Worker state machine
```
idle → to_mine → harvesting → to_hall → idle          (gold loop)
idle → to_tree → chopping   → to_hall_lumber → idle   (lumber loop)
```
`_attack_anim_timer` drives the axe-swing (0.3 s per swing, re-triggered while in `chopping`).
`_last_dir` is set to face the tree when entering `chopping`.

### Tech tree (implemented)
```
TownHall ── Farm
    └── Barracks ── LumberMill ── Blacksmith
              ├── Footman / Archer  (Tier 1)
              └── Knight            (Tier 2, requires Blacksmith)
```

### Asset extraction tools
```
tools/extract_war2_sprites.py    # unit walk/attack strips from MAINDAT.WAR via libwar2
tools/extract_war2_buildings.py  # building sprite sheets
```
Source data: `~/workspace/war2tools/data/maindat.war`. Output: `assets/sprites/`.

### Thumbnail icons
`assets/sprites/thumbnails/thumbnails.png` — 190 WC2 UI icons, 46×38 px each, 10 cols × 19 rows.
Full mapping in `assets/sprites/thumbnails/catalog.md`.

```python
col, row = icon_id % 10, icon_id // 10
icon = sheet.subsurface(pygame.Rect(col * 50 + 2, row * 39, 46, 38))
```

## Milestone summary

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Unit on screen, click-to-move, selection |
| 2 | ✅ | Box select, formation, A*, health, combat, gold |
| 3 | ✅ | AI state machine: gather → build → attack |
| 4 | ✅ | Skirmish map, fog of war, win/lose |
| 5 | ✅ | Lumber, building placement, food cap, minimap |
| 6 | ✅ | Tech tree: Blacksmith, Knight, upgrade prereqs |
| 7 | ✅ | WC2 sprite pipeline, 8-dir walk, team colour, four tilesets |
| 8 | 🔄 | Animation polish: worker carry visuals, gameplay feel |
