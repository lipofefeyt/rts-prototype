# RTS Prototype — Project Context for Claude Code

## Project Overview
Building a minimal Warcraft 2-inspired RTS prototype as a learning project.
Primary goal: learn game dev fundamentals. Not aiming to ship.

## Developer Profile
- Strong C++ / Python / systems programming background
- Hobby pace (a few hours/week)
- Setup: Windows + WSL2 + VSCode + Docker
- Claude Code integrated in VSCode/WSL2

## Stack Decision
- **Engine: Pygame** (pure Python, runs natively in WSL2, no editor friction)
- Godot 4 was trialed but abandoned due to editor friction
- All code lives in WSL2, edited in VSCode

## Project Structure
```
rts-prototype/
├── main.py          # game loop, input handling, spawning
├── unit.py          # Unit class
└── assets/
    └── footman.png  # 128x128 sprite (or fallback to blue rect)
```

## Current State (end of Session 1)
- `Unit` class with position, target, speed, selected state
- Straight-line click-to-move (no pathfinding yet)
- Left-click to select a unit (green circle indicator)
- Right-click to move selected unit
- 3 units spawned at startup
- Delta-time based movement (frame-rate independent)

## Current `unit.py`
```python
import pygame

class Unit:
    def __init__(self, x: float, y: float, image: pygame.Surface):
        self.pos = pygame.Vector2(x, y)
        self.target = pygame.Vector2(x, y)
        self.speed = 150.0  # pixels per second
        self.selected = False
        self.image = image
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def move_to(self, pos: pygame.Vector2):
        self.target = pygame.Vector2(pos)

    def update(self, dt: float):
        direction = self.target - self.pos
        if direction.length() > 5:
            self.pos += direction.normalize() * self.speed * dt
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw(self, surface: pygame.Surface):
        surface.blit(self.image, self.rect)
        if self.selected:
            pygame.draw.circle(surface, (0, 255, 0), self.rect.center, 70, 2)

    def contains_point(self, point: tuple) -> bool:
        return self.rect.collidepoint(point)
```

## Current `main.py`
```python
import pygame
from unit import Unit

WIDTH, HEIGHT = 1280, 720
FPS = 60

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RTS Prototype")
    clock = pygame.time.Clock()

    try:
        raw = pygame.image.load("assets/footman.png").convert_alpha()
        sprite = pygame.transform.scale(raw, (128, 128))
    except FileNotFoundError:
        sprite = pygame.Surface((128, 128), pygame.SRCALPHA)
        sprite.fill((70, 130, 180))

    units = [
        Unit(300, 300, sprite),
        Unit(450, 300, sprite),
        Unit(600, 300, sprite),
    ]

    selected_unit = None

    while True:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if selected_unit:
                        selected_unit.selected = False
                        selected_unit = None
                    for unit in units:
                        if unit.contains_point(event.pos):
                            selected_unit = unit
                            unit.selected = True
                            break

                elif event.button == 3:
                    if selected_unit:
                        selected_unit.move_to(event.pos)

        for unit in units:
            unit.update(dt)

        screen.fill((30, 30, 30))
        for unit in units:
            unit.draw(screen)

        pygame.display.flip()

if __name__ == "__main__":
    main()
```

## Milestone Plan

### Phase 1 — Engine footing ✅ (Session 1 done)
- Unit on screen, click-to-move, selection

### Phase 2 — Core loop (Sessions 2–6)
- Box selection (drag rectangle to select multiple units)
- Group movement in formation
- Obstacles (static rects blocking movement)
- A* pathfinding around obstacles
- Basic health + melee combat
- One resource (gold), one building that trains units

### Phase 3 — Minimal AI opponent (Sessions 7–12)
- AI state machine: gather → build → attack
- AI harvests resources, trains units, attacks player
- Tweak aggression, timing, target priority

### Phase 4 — One playable map (Sessions 13–15)
- Proper map with chokepoints, two bases, resource nodes
- Win/lose condition
- Playable skirmish

## Key Design Decisions
- Sprite size: 128x128px
- Viewport: 1280x720
- Movement: delta-time based (frame-rate independent)
- Selection: single unit for now, box selection coming in Session 2
- Pathfinding: A* (to be implemented in Session 2)

## Session 2 Goals
- Box selection (drag to select multiple units)
- Group movement — selected units move in formation without stacking
- Add static obstacles (rectangles)
- A* pathfinding around obstacles

## Godot Lessons Learned (for reference)
- RectangleShape2D uses half-extents (set 16 to get 32px width)
- Assets must use res:// paths, not absolute Windows paths
- .import cache can corrupt and needs manual deletion to fix
- get_rect() doesn't exist on CharacterBody2D
- Ctrl+Shift+A has a recurring editor bug — spawn via code instead
- 128x128 is the right sprite size for modern viewports