import pygame


class Unit:
    def __init__(self, x: float, y: float, image: pygame.Surface):
        self.pos = pygame.Vector2(x, y)
        self.path: list[pygame.Vector2] = []
        self.speed = 150.0  # pixels per second
        self.selected = False
        self.image = image
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def move_to(self, path: list[pygame.Vector2]) -> None:
        self.path = list(path)

    def update(self, dt: float) -> None:
        while self.path:
            direction = self.path[0] - self.pos
            if direction.length() <= 4:
                self.path.pop(0)
            else:
                self.pos += direction.normalize() * self.speed * dt
                break
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.image, self.rect)
        if self.selected:
            pygame.draw.circle(surface, (0, 255, 0), self.rect.center, 70, 2)

    def contains_point(self, point: tuple) -> bool:
        return self.rect.collidepoint(point)
