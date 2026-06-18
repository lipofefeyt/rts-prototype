import pygame

_STAGES = [
    ((75, 58, 58), 22),   # fresh  — brownish-red blob
    ((55, 45, 45), 15),   # bones  — medium dark
    ((40, 33, 33),  8),   # dust   — small dark smudge
]
STAGE_DURATION = 3.0


class Corpse:
    def __init__(self, pos: pygame.Vector2, team: int, sheet=None):
        self.pos = pygame.Vector2(pos)
        self.team = team
        self._stage = 0
        self._timer = 0.0
        self._sheet = sheet

    def update(self, dt: float) -> bool:
        """Advance decay timer. Returns False when the corpse should be removed."""
        self._timer += dt
        if self._timer >= STAGE_DURATION:
            self._timer -= STAGE_DURATION
            self._stage += 1
        return self._stage < len(_STAGES)

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.pos.x), int(self.pos.y)

        if self._sheet is not None and hasattr(self._sheet, 'death_frame'):
            elapsed = self._stage * STAGE_DURATION + self._timer
            frame = self._sheet.death_frame(elapsed)
            if self._stage == len(_STAGES) - 1:
                alpha = max(0, int(255 * (1.0 - self._timer / STAGE_DURATION)))
                frame = frame.copy()
                frame.set_alpha(alpha)
            surface.blit(frame, frame.get_rect(center=(cx, cy)))
            return

        # Fallback: colored circle with cross mark
        color, radius = _STAGES[self._stage]
        pygame.draw.circle(surface, color, (cx, cy), radius)
        dark = tuple(max(0, c - 18) for c in color)
        pygame.draw.line(surface, dark, (cx - radius + 3, cy - radius + 3),
                         (cx + radius - 3, cy + radius - 3), 1)
        pygame.draw.line(surface, dark, (cx + radius - 3, cy - radius + 3),
                         (cx - radius + 3, cy + radius - 3), 1)
