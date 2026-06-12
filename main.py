import math
import pygame
from unit import Unit, Worker
from map import GameMap
from building import Building, TownHall, GoldMine, Barracks, Farm
from ai import AIController

WIDTH, HEIGHT = 1280, 720
FPS = 60
FORMATION_SPACING = 90
PANEL_H = 80
PANEL_Y = HEIGHT - PANEL_H
TRAIN_BTN = pygame.Rect(10, PANEL_Y + 22, 195, 36)


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


def food_stats(buildings: list[Building], units: list[Unit]) -> tuple[int, int]:
    cap = sum(b.FOOD for b in buildings if isinstance(b, Farm) and b.team == 0)
    used = sum(1 for u in units if u.team == 0)
    return used, cap


def draw_hud(screen: pygame.Surface, font: pygame.font.Font,
             gold: dict, buildings: list[Building], units: list[Unit],
             selected_building: Building | None, ai_state: str = "") -> None:
    # Top bar
    pygame.draw.rect(screen, (20, 20, 28), (0, 0, WIDTH, 28))
    food_used, food_cap = food_stats(buildings, units)
    screen.blit(font.render(f"Gold: {gold[0]}", True, (255, 215, 0)), (10, 5))
    screen.blit(font.render(f"Food: {food_used}/{food_cap}", True, (200, 230, 200)), (160, 5))
    if ai_state:
        label = f"Enemy: {ai_state.upper()}"
        color = (255, 80, 80) if ai_state == "attack" else (160, 160, 180)
        surf = font.render(label, True, color)
        screen.blit(surf, (WIDTH - surf.get_width() - 10, 5))

    if selected_building is None:
        return

    # Bottom panel
    pygame.draw.rect(screen, (20, 22, 32), (0, PANEL_Y, WIDTH, PANEL_H))
    pygame.draw.line(screen, (70, 70, 100), (0, PANEL_Y), (WIDTH, PANEL_Y))
    info = f"{selected_building.label}   HP {selected_building.hp}/{selected_building.max_hp}"
    screen.blit(font.render(info, True, (180, 200, 220)), (10, PANEL_Y + 4))

    if isinstance(selected_building, Barracks) and selected_building.team == 0:
        food_used, food_cap = food_stats(buildings, units)
        can_afford = gold[0] >= Barracks.TRAIN_COST
        can_food = food_used < food_cap
        can_queue = len(selected_building.queue) < Barracks.MAX_QUEUE
        enabled = can_afford and can_food and can_queue
        btn_col = (45, 90, 45) if enabled else (55, 55, 55)
        pygame.draw.rect(screen, btn_col, TRAIN_BTN)
        pygame.draw.rect(screen, (80, 130, 80) if enabled else (80, 80, 80), TRAIN_BTN, 1)
        screen.blit(font.render(f"Train Footman  {Barracks.TRAIN_COST}g", True, (220, 220, 220)), (TRAIN_BTN.x + 6, TRAIN_BTN.y + 9))

        # Queue slot indicators
        for i in range(Barracks.MAX_QUEUE):
            sx = TRAIN_BTN.right + 14 + i * 22
            sy = PANEL_Y + 30
            if i < len(selected_building.queue):
                col = (80, 220, 80) if i == 0 else (80, 130, 220)
                pygame.draw.rect(screen, col, (sx, sy, 16, 16))
            else:
                pygame.draw.rect(screen, (50, 50, 60), (sx, sy, 16, 16), 1)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RTS Prototype")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 26)

    try:
        raw = pygame.image.load("assets/footman.png").convert_alpha()
        player_sprite = pygame.transform.scale(raw, (128, 128))
        enemy_sprite = player_sprite.copy()
    except FileNotFoundError:
        player_sprite = make_sprite((70, 130, 180))
        enemy_sprite = make_sprite((180, 50, 50))

    worker_sprite = make_sprite((120, 170, 100))        # always defined
    enemy_worker_sprite = make_sprite((170, 110, 110))

    game_map = GameMap(WIDTH, HEIGHT)
    game_map.add_obstacle(pygame.Rect(500, 200, 128, 256))
    game_map.add_obstacle(pygame.Rect(800, 400, 200, 64))

    # --- World setup ---
    buildings: list[Building] = [
        # Player base (left)
        TownHall(30, 260, team=0),
        Barracks(30, 420, team=0),
        Farm(200, 420, team=0),
        Farm(310, 420, team=0),
        # Enemy base (right)
        TownHall(1090, 260, team=1),
        Barracks(940, 260, team=1),
        Farm(940, 420, team=1),
        Farm(1090, 420, team=1),
        # Neutral gold mines
        GoldMine(40, 110),     # player-side
        GoldMine(1100, 110),   # enemy-side
    ]

    player_hall = next(b for b in buildings if isinstance(b, TownHall) and b.team == 0)

    units: list[Unit] = [
        Unit(280, 330, player_sprite, team=0),
        Unit(380, 330, player_sprite, team=0),
        Worker(180, 360, worker_sprite, team=0),
        # Enemy starting force
        Unit(1040, 360, enemy_sprite, team=1),
        Worker(1200, 380, enemy_worker_sprite, team=1),
    ]

    gold: dict[int, int] = {0: 500, 1: 500}

    ai = AIController(
        team=1,
        buildings=buildings,
        units=units,
        gold=gold,
        game_map=game_map,
        enemy_sprite=enemy_sprite,
        worker_sprite=enemy_worker_sprite,
    )
    selected: list[Unit] = []
    selected_building: Building | None = None

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
                    # Panel button takes priority over drag
                    if (selected_building is not None
                            and isinstance(selected_building, Barracks)
                            and TRAIN_BTN.collidepoint(event.pos)):
                        food_used, food_cap = food_stats(buildings, units)
                        if food_used < food_cap:
                            selected_building.enqueue(gold)
                    elif event.pos[1] > PANEL_Y and selected_building is not None:
                        pass  # clicked inside panel but not on a button — ignore
                    else:
                        drag_start = pygame.Vector2(event.pos)
                        drag_current = pygame.Vector2(event.pos)

                elif event.button == 3 and selected:
                    enemy_hit = next((u for u in units if u.team == 1 and u.contains_point(event.pos)), None)
                    mine_hit = next((b for b in buildings if isinstance(b, GoldMine) and b.contains_point(event.pos)), None)

                    if enemy_hit:
                        for u in selected:
                            u.order_attack(enemy_hit)
                    elif mine_hit:
                        movers: list[Unit] = []
                        for u in selected:
                            if isinstance(u, Worker):
                                u.order_harvest(mine_hit, player_hall, game_map)
                            else:
                                movers.append(u)
                        if movers:
                            targets = formation_targets(pygame.Vector2(event.pos), len(movers))
                            for u, tgt in zip(movers, targets):
                                u.move_to(game_map.find_path(u.pos, tgt))
                    else:
                        targets = formation_targets(pygame.Vector2(event.pos), len(selected))
                        for u, tgt in zip(selected, targets):
                            u.move_to(game_map.find_path(u.pos, tgt))

            elif event.type == pygame.MOUSEMOTION and drag_start is not None:
                drag_current = pygame.Vector2(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and drag_start is not None:
                end = pygame.Vector2(event.pos)
                delta = end - drag_start

                if delta.length() > 4:
                    # Box select — units only
                    sel_rect = pygame.Rect(
                        int(min(drag_start.x, end.x)), int(min(drag_start.y, end.y)),
                        int(abs(delta.x)), int(abs(delta.y)),
                    )
                    selected = apply_selection(selected, [u for u in units if u.team == 0 and sel_rect.colliderect(u.rect)])
                    if selected_building:
                        selected_building.selected = False
                        selected_building = None
                else:
                    # Single click — buildings first, then units
                    bldg = next((b for b in buildings if b.team == 0 and b.contains_point(event.pos)), None)
                    if bldg:
                        if selected_building:
                            selected_building.selected = False
                        bldg.selected = True
                        selected_building = bldg
                        selected = apply_selection(selected, [])
                    else:
                        if selected_building:
                            selected_building.selected = False
                            selected_building = None
                        clicked = next((u for u in units if u.team == 0 and u.contains_point(event.pos)), None)
                        selected = apply_selection(selected, [clicked] if clicked else [])

                drag_start = None
                drag_current = None

        # --- Update ---
        ai.update(dt)

        player_units = [u for u in units if u.team == 0]
        enemy_units = [u for u in units if u.team == 1]
        for u in player_units:
            u.update(dt, enemy_units, game_map)
        for u in enemy_units:
            u.update(dt, player_units, game_map)

        # Collect worker gold deliveries (all teams)
        for u in units:
            if isinstance(u, Worker):
                gold[u.team] += u.gold_delivered
                u.gold_delivered = 0

        # Spawn trained units from Barracks
        for b in buildings:
            if isinstance(b, Barracks):
                n = b.update(dt)
                for _ in range(n):
                    sp = pygame.Vector2(b.rect.right + 40, b.rect.centery)
                    sprite = player_sprite if b.team == 0 else enemy_sprite
                    units.append(Unit(sp.x, sp.y, sprite, team=b.team))

        # Reap dead units
        units = [u for u in units if u.is_alive()]
        selected = [u for u in selected if u.is_alive()]

        # --- Draw ---
        screen.fill((30, 30, 30))
        game_map.draw(screen)

        for b in buildings:
            b.draw(screen)
        for u in units:
            u.draw(screen)

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

        draw_hud(screen, font, gold, buildings, units, selected_building, ai.state)
        pygame.display.flip()


if __name__ == "__main__":
    main()
