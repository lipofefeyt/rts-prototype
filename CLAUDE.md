# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project

Warcraft 2-inspired RTS prototype. Learning project — not aiming to ship. Built with Python 3.12 + pygame 2.6.1, running natively in WSL2.

A Godot 4.3+ / GDScript port is in progress alongside the Python version — see **Godot port** below.

## Running

```bash
source .venv/bin/activate
python main.py        # ESC or close window to quit
```

## Testing

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt   # one-time: adds pytest
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest -q
```

Runs on every push/PR via `.github/workflows/tests.yml`. Three layers, all under `tests/`:
- `test_pathfinding.py`, `test_stats.py`, `test_combat.py`, `test_worker.py`, `test_building.py`
  — pure-logic unit tests, no window needed.
- `test_simulate_frame.py` — black-box tests that drive the real game loop (via
  `main.init_game_state()` / `main.simulate_frame()`, extracted from `run_game()` for this
  purpose) with a fixed `dt`, no window or real input.
- `test_soak.py` — headless AI-vs-AI soak test; runs ~2 simulated minutes at full speed and
  uses `tests/invariants.py` to flag NaN positions, out-of-range HP, negative resources, or a
  unit stuck with a path it's making no progress on. Set `SOAK_FRAMES` to run longer locally.

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
| `floattext.py` | `FloatText`: rising "+N" gold/lumber delivery labels |
| `corpse.py` | `Corpse`: timed decay animation |
| `projectile.py` | `Projectile`: arrow/ballista in-flight objects |
| `sound.py` | Sound effect loading + playback |

### Key constants
- **Viewport:** 1280×720, left `SIDEBAR_W = 220` px = HUD sidebar, right 1060 px = game world
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
`assets/sprites/thumbnails/thumbnails.png` — 180 WC2 UI icons, 46×38 px each, 10 cols × 18 rows.
Full mapping in `assets/sprites/thumbnails/catalog.md`.
Sheet: 5px outer border top/bottom; each row slot = 41px (3px bright frame + 38px content).

```python
col, row = icon_id % 10, icon_id // 10
icon = sheet.subsurface(pygame.Rect(col * 50 + 2, row * 41 + 5, 46, 38))
```

## Godot port

`godot/` holds an in-progress Godot 4.3+/GDScript rewrite of this prototype. The Python version is the
design reference; `GODOT_HANDOFF.md` (repo root) is the authoritative, exhaustive game-design spec used to
drive the port — unit/building stat tables, AI state machine, HUD layout, sprite frame math, combat/formation
rules, all ported exactly from the Python source. Read it before touching anything under `godot/`.

Session-resume notes for the port live alongside the code:
- `godot/SESSION_CONTEXT.md` — phase-by-phase progress, completed autoloads, key design decisions, file tree
- `godot/SYSTEMS_CONTEXT.md`, `godot/SYSTEMS2_CONTEXT.md` — resource gathering, sprites, combat, tech tree detail
- `godot/SIDEBAR_MINIMAP_CONTEXT.md`, `godot/SPRITE_DIRECTION_FIX.md` — narrower implementation notes

As of the last update, `godot/autoloads/` (`GameData`, `StatsDatabase`, `MapManager`) and
`godot/world/WorldTileMap.gd` are done (data layer + grid/pathfinding); unit/combat/worker/HUD/AI phases are
not yet started. Check `godot/SESSION_CONTEXT.md`'s "Completed phases" / "What's next" sections for current status
before assuming what exists.

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
