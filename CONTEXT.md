# RTS Prototype — Project Context

## Project Overview
Warcraft 2-inspired RTS prototype, built as a learning project. Not aiming to ship.
Primary goal: game dev fundamentals, asset pipelines, AI state machines.

## Developer Profile
- Strong C++ / Python / systems programming background
- Hobby pace (a few hours/week)
- Setup: Windows + WSL2 + VSCode, Claude Code integrated
- New to pygame at project start

## Stack
- **Engine:** Pygame 2.6.1, Python 3.12, running natively in WSL2
- Godot 4 was trialed and abandoned (editor friction in WSL2)

## Current State (Session ~9)

### Gameplay
- Two-base skirmish: Human (blue/team 0) vs Orc AI (red/team 1)
- Procedural map (seed 4874 locked): grass, dirt, water, forests, two gold mines
- Four tilesets (Forest, Winter, Wasteland, Swamp) — Forest active by default
- Fog of war per team
- Win/lose: destroy enemy Town Hall

### Units implemented
| Unit | Tier | Notes |
|------|------|-------|
| Worker / Peasant | — | Harvests gold + lumber, carries back to hall |
| Footman | 1 | Melee |
| Archer | 1 | Ranged |
| Knight | 2 | Requires Blacksmith |

### Buildings implemented
| Building | Notes |
|----------|-------|
| Town Hall / Great Hall | Trains workers |
| Barracks | Trains footmen, archers, knights |
| Farm / Pig Farm | +4 food cap each |
| Lumber Mill | Required for Blacksmith |
| Blacksmith | Enables Knight training |
| Gold Mine | Depletes; worker harvests 100g/trip |
| Trees | Harvested for lumber (10 lumber/chop) |

### AI
- State machine: gather → attack → gather
- Harvests gold and lumber
- Trains mixed army (footman/archer/knight rotation)
- Builds Farms when food-capped, rebuilds Barracks/Blacksmith when missing
- Difficulty presets: easy / normal / hard

### Sprites
- WC2 sprites extracted from MAINDAT.WAR via war2tools/libwar2 (ctypes bridge)
- Unit strips: pose-major layout, 5 stored dirs, SW/W/NW mirrored
- Team colour via per-team palette swap at extraction time
- Building sprites: human and orc variants, summer + seasonal tilesets
- Thumbnails: 190 WC2 UI icons in `assets/sprites/thumbnails/thumbnails.png`
  (catalog at `assets/sprites/thumbnails/catalog.md`)

### HUD
- Left sidebar (WC2-style): resource display, minimap, unit panel, build menu
- Single-unit panel: portrait placeholder + HP/stats
- Build menu: thumbnail icons for each building, hover cost tooltip
- Minimap: clickable to pan camera

## Milestone Plan

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Unit on screen, click-to-move, selection |
| 2 | ✅ | Box select, formation, A*, health, combat, gold |
| 3 | ✅ | AI state machine: gather → build → attack |
| 4 | ✅ | Skirmish map, fog of war, win/lose |
| 5 | ✅ | Lumber, building placement, food cap, minimap |
| 6 | ✅ | Tech tree: Blacksmith, Knight, upgrade prereqs |
| 7 | ✅ | WC2 sprite pipeline, 8-dir walk, team colour, four tilesets |
| 8 | 🔄 | Animation polish: worker carry walk sprites, gameplay feel |
| 9 | ⬜ | Tech tree UI panel (visual upgrade screen with thumbnail icons) |
| 10 | ⬜ | Orc faction units (Grunt, Peon, Troll, Ogre with correct sprites) |

## Known gaps / next sessions

- **Worker carry walk sprites** — WC2 carry animations exist in MAINDAT.WAR but are not mapped
  in war2tools `sprites.c`. Fix requires adding PUD_UNIT constants for carry workers and
  finding the correct archive entry numbers.
- **Tech tree UI panel** — visual panel showing upgrade tree, costs, research buttons
  with WC2 thumbnail icons.
- **Orc faction** — Grunt/Peon/Troll/Ogre sprites extracted but unit types not fully wired.
- **Carry indicator** — currently a colored dot/rect above the worker; replace once carry
  walk sprites land.

## Key Design Decisions
- Viewport: 1280×720, HUD sidebar 160 px wide on the left
- Grid: 32 px cells
- Movement: delta-time based, frame-rate independent
- Selection: box drag (>4 px) or click; `apply_selection()` in main.py
- Pathfinding: A* with diagonal moves, corner-clipping prevention
- Formation: spiral offsets around click point, one A* call per unit
