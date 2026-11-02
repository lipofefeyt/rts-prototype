import pygame

GOLD_COLOUR   = (255, 220, 40)
LUMBER_COLOUR = (120, 200, 80)
_DURATION = 1.5   # seconds
_RISE_PX  = 30    # world-pixels risen over full lifetime


class FloatText:
    """A "+N" label that rises and fades over the game world."""

    def __init__(self, text: str, colour: tuple, pos: pygame.Vector2,
                 font: pygame.font.Font) -> None:
        self._pos  = pygame.Vector2(pos)
        self._age  = 0.0
        raw = font.render(text, True, colour)
        # Pre-bake at each alpha step would be wasteful; store surface + colour key instead.
        self._surf = raw.convert_alpha()

    def update(self, dt: float) -> bool:
        self._age += dt
        return self._age < _DURATION

    def draw(self, surface: pygame.Surface) -> None:
        t     = self._age / _DURATION
        alpha = int(255 * max(0.0, 1.0 - t * t))
        y_off = int(_RISE_PX * t)
        self._surf.set_alpha(alpha)
        surface.blit(self._surf,
                     self._surf.get_rect(center=(int(self._pos.x),
                                                 int(self._pos.y) - y_off)))
