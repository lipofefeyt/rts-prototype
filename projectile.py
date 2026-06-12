import pygame

SPEED = 420.0   # px/s


class Projectile:
    """Arrow/bolt that homes toward a target and deals damage on contact."""

    def __init__(self, pos: pygame.Vector2, target, damage: int, team: int):
        self.pos = pygame.Vector2(pos)
        self.target = target   # any object with .pos and .is_alive()
        self.damage = damage
        self.team = team

    def update(self, dt: float) -> bool:
        """Move toward target. Returns False when it hits or the target dies."""
        if not self.target.is_alive():
            return False
        direction = self.target.pos - self.pos
        step = SPEED * dt
        if direction.length() <= step:
            if self.target.is_alive():
                self.target.hp -= self.damage
            return False
        self.pos += direction.normalize() * step
        return True

    def draw(self, surface: pygame.Surface) -> None:
        color = (220, 220, 60) if self.team == 0 else (220, 110, 50)
        cx, cy = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(surface, color, (cx, cy), 4)
        pygame.draw.circle(surface, (255, 255, 180) if self.team == 0 else (255, 200, 100),
                           (cx, cy), 2)
