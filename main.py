import math
import pygame
from unit import Unit
from map import GameMap

WIDTH, HEIGHT = 1280, 720
FPS = 60
FORMATION_SPACING = 90


def make_sprite(color: tuple) -> pygame.Surface:
    s = pygame.Surface((128, 128), pygame.SRCALPHA)
    s.fill(color)
    return s


def formation_targets(center: pygame.Vector2, count: int) -> list[pygame.Vector2]:
    if count == 0:
        return []
    cols = max(1, math.ceil(math.sqrt(count)))
    rows = math.ceil(count / cols)
    total_w = (cols - 1) * FORMATION_SPACING
    total_h = (rows - 1) * FORMATION_SPACING
    result = []
    for i in range(count):
        c = i % cols
        r = i // cols
        x = center.x - total_w / 2 + c * FORMATION_SPACING
        y = center.y - total_h / 2 + r * FORMATION_SPACING
        result.append(pygame.Vector2(x, y))
    return result


def apply_selection(old: list[Unit], new: list[Unit]) -> list[Unit]:
    for u in old:
        u.selected = False
    for u in new:
        u.selected = True
    return new


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RTS Prototype")
    clock = pygame.time.Clock()

    try:
        raw = pygame.image.load("assets/footman.png").convert_alpha()
        player_sprite = pygame.transform.scale(raw, (128, 128))
        enemy_sprite = player_sprite.copy()
    except FileNotFoundError:
        player_sprite = make_sprite((70, 130, 180))   # steel blue
        enemy_sprite = make_sprite((180, 50, 50))      # red

    game_map = GameMap(WIDTH, HEIGHT)
    game_map.add_obstacle(pygame.Rect(500, 200, 128, 256))
    game_map.add_obstacle(pygame.Rect(800, 400, 200, 64))

    units: list[Unit] = [
        Unit(200, 300, player_sprite, team=0),
        Unit(320, 300, player_sprite, team=0),
        Unit(440, 300, player_sprite, team=0),
        Unit(1000, 200, enemy_sprite, team=1),
        Unit(1100, 300, enemy_sprite, team=1),
        Unit(1000, 400, enemy_sprite, team=1),
    ]
    selected: list[Unit] = []

    drag_start: pygame.Vector2 | None = None
    drag_current: pygame.Vector2 | None = None

    while True:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    drag_start = pygame.Vector2(event.pos)
                    drag_current = pygame.Vector2(event.pos)

                elif event.button == 3 and selected:
                    # Right-click on enemy → attack order; otherwise move
                    enemy_clicked = next(
                        (u for u in units if u.team == 1 and u.contains_point(event.pos)), None
                    )
                    if enemy_clicked:
                        for unit in selected:
                            unit.order_attack(enemy_clicked)
                    else:
                        targets = formation_targets(pygame.Vector2(event.pos), len(selected))
                        for unit, tgt in zip(selected, targets):
                            unit.move_to(game_map.find_path(unit.pos, tgt))

            elif event.type == pygame.MOUSEMOTION and drag_start is not None:
                drag_current = pygame.Vector2(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and drag_start is not None:
                end = pygame.Vector2(event.pos)
                delta = end - drag_start

                if delta.length() > 4:
                    sel_rect = pygame.Rect(
                        int(min(drag_start.x, end.x)),
                        int(min(drag_start.y, end.y)),
                        int(abs(delta.x)),
                        int(abs(delta.y)),
                    )
                    new_sel = [u for u in units if u.team == 0 and sel_rect.colliderect(u.rect)]
                else:
                    clicked = next((u for u in units if u.team == 0 and u.contains_point(event.pos)), None)
                    new_sel = [clicked] if clicked else []

                selected = apply_selection(selected, new_sel)
                drag_start = None
                drag_current = None

        # Update — each unit sees only the opposing team as enemies
        player_units = [u for u in units if u.team == 0]
        enemy_units = [u for u in units if u.team == 1]
        for u in player_units:
            u.update(dt, enemy_units, game_map)
        for u in enemy_units:
            u.update(dt, player_units, game_map)

        # Reap dead units
        units = [u for u in units if u.is_alive()]
        selected = [u for u in selected if u.is_alive()]

        # --- Draw ---
        screen.fill((30, 30, 30))
        game_map.draw(screen)
        for unit in units:
            unit.draw(screen)

        # Box selection overlay
        if drag_start is not None and drag_current is not None:
            delta = drag_current - drag_start
            if delta.length() > 4:
                rx = int(min(drag_start.x, drag_current.x))
                ry = int(min(drag_start.y, drag_current.y))
                rw, rh = int(abs(delta.x)), int(abs(delta.y))
                overlay = pygame.Surface((max(1, rw), max(1, rh)), pygame.SRCALPHA)
                overlay.fill((0, 255, 0, 40))
                screen.blit(overlay, (rx, ry))
                pygame.draw.rect(screen, (0, 255, 0), (rx, ry, rw, rh), 1)

        pygame.display.flip()


if __name__ == "__main__":
    main()
