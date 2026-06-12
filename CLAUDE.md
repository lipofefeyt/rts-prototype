# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Warcraft 2-inspired RTS prototype. Learning project — not aiming to ship. Built with Python 3.12 + pygame 2.6.1, running natively in WSL2.

## Running

```bash
source .venv/bin/activate
python main.py        # ESC or close window to quit
```

`assets/footman.png` (128×128) is optional — falls back to a blue rectangle.

## Architecture

Four modules, no framework:

| File | Responsibility |
|------|---------------|
| `main.py` | Game loop, event handling, box selection, formation move dispatch |
| `unit.py` | `Unit`: position, path-following, drawing |
| `map.py` | `GameMap`: obstacle rects → blocked grid cells, calls A* |
| `pathfinding.py` | `astar()` + grid↔world helpers |

**Data flow for a right-click move:**
1. `main.py` computes per-unit formation targets around the click point
2. For each selected unit: `game_map.find_path(unit.pos, target)` → calls `astar()` → returns `list[Vector2]` waypoints
3. `unit.move_to(path)` stores the waypoint list; `unit.update(dt)` advances through it each frame

**Grid:** 32 px cells, 40×22 for a 1280×720 viewport. `GameMap.add_obstacle()` marks all cells a `pygame.Rect` covers as blocked. Diagonal moves are allowed but corner-clipping is prevented in A*.

**Selection:** drag > 4 px triggers box select via `sel_rect.colliderect(unit.rect)`; smaller drag is a single click. `apply_selection()` in `main.py` manages the `selected: list[Unit]` list and flips `unit.selected` flags.

## Milestone plan (from CONTEXT.md)

- **Phase 1 ✅** — Unit on screen, click-to-move, selection
- **Phase 2 (Sessions 2–6)** — Box select, formation move, obstacles, A*, health + combat, gold + building
- **Phase 3 (Sessions 7–12)** — AI state machine (gather → build → attack)
- **Phase 4 (Sessions 13–15)** — Real map, win/lose condition, playable skirmish
