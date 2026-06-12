import math
import pygame
from unit import Unit, Worker, Archer
from map import GameMap, DEFAULT_MAP
from building import Building, TownHall, GoldMine, Barracks, Farm
from ai import AIController
from stats import UNIT_STATS
from corpse import Corpse
from projectile import Projectile
from fog import FogOfWar
from minimap import Minimap, MINI_X, MINI_Y, MINI_W, MINI_H
from sound import pre_init, load_sounds
from pathfinding import CELL_SIZE

WIDTH, HEIGHT = 1280, 720
FPS = 60
FORMATION_SPACING = 90
PANEL_H = 80
PANEL_Y = HEIGHT - PANEL_H

# Bottom panel buttons
TRAIN_BTN        = pygame.Rect(10,  PANEL_Y + 26, 185, 28)
TRAIN_ARCHER_BTN = pygame.Rect(205, PANEL_Y + 26, 185, 28)
RESTART_BTN      = pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 + 50, 160, 40)
_MUTE_BTN        = pygame.Rect(WIDTH - 65, 4, 55, 20)


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


def apply_selection(old: list, new: list) -> list:
    for u in old:
        u.selected = False
    for u in new:
        u.selected = True
    return new


def food_stats(buildings: list, units: list) -> tuple[int, int]:
    cap = sum(b.FOOD for b in buildings if isinstance(b, Farm) and b.team == 0)
    used = sum(1 for u in units if u.team == 0)
    return used, cap


def draw_hud(screen: pygame.Surface, font: pygame.font.Font,
             gold: dict, buildings: list, units: list,
             selected_building, ai_state: str = "",
             muted: bool = False) -> None:
    pygame.draw.rect(screen, (20, 20, 28), (0, 0, WIDTH, 28))
    food_used, food_cap = food_stats(buildings, units)
    screen.blit(font.render(f"Gold: {gold[0]}", True, (255, 215, 0)), (10, 5))
    screen.blit(font.render(f"Food: {food_used}/{food_cap}", True, (200, 230, 200)), (160, 5))

    # Mute toggle indicator
    m_col = (100, 100, 80) if muted else (60, 90, 60)
    pygame.draw.rect(screen, m_col, _MUTE_BTN)
    pygame.draw.rect(screen, (120, 120, 100) if muted else (80, 130, 80), _MUTE_BTN, 1)
    screen.blit(font.render("MUTE" if muted else "SFX", True, (200, 200, 180)),
                (_MUTE_BTN.x + 3, _MUTE_BTN.y + 2))

    if ai_state:
        label = f"Enemy: {ai_state.upper()}"
        color = (255, 80, 80) if ai_state == "attack" else (160, 160, 180)
        surf = font.render(label, True, color)
        screen.blit(surf, (WIDTH - surf.get_width() - 70, 5))

    if selected_building is None:
        return

    pygame.draw.rect(screen, (20, 22, 32), (0, PANEL_Y, WIDTH, PANEL_H))
    pygame.draw.line(screen, (70, 70, 100), (0, PANEL_Y), (WIDTH, PANEL_Y))
    info = f"{selected_building.label}   HP {selected_building.hp}/{selected_building.max_hp}"
    screen.blit(font.render(info, True, (180, 200, 220)), (10, PANEL_Y + 6))

    if isinstance(selected_building, Barracks) and selected_building.team == 0:
        food_used, food_cap = food_stats(buildings, units)
        q_len = len(selected_building.queue)

        for btn, ut in [(TRAIN_BTN, "footman"), (TRAIN_ARCHER_BTN, "archer")]:
            s = UNIT_STATS[ut]
            can = gold[0] >= s.cost and food_used < food_cap and q_len < Barracks.MAX_QUEUE
            pygame.draw.rect(screen, (45, 90, 45) if can else (55, 55, 55), btn)
            pygame.draw.rect(screen, (80, 130, 80) if can else (80, 80, 80), btn, 1)
            label = "Footman" if ut == "footman" else "Archer"
            screen.blit(font.render(f"{label}  {s.cost}g", True, (220, 220, 220)),
                        (btn.x + 6, btn.y + 6))

        # Queue slots
        slot_colors = {"footman": (80, 130, 220), "archer": (60, 200, 150)}
        for i in range(Barracks.MAX_QUEUE):
            sx = TRAIN_ARCHER_BTN.right + 14 + i * 22
            sy = PANEL_Y + 32
            if i < q_len:
                ut_slot = selected_building.queue[i][0]
                color = (80, 220, 80) if i == 0 else slot_colors.get(ut_slot, (80, 130, 220))
                pygame.draw.rect(screen, color, (sx, sy, 16, 16))
            else:
                pygame.draw.rect(screen, (50, 50, 60), (sx, sy, 16, 16), 1)


def draw_game_over(screen: pygame.Surface, font: pygame.font.Font,
                   big_font: pygame.font.Font, result: str, elapsed: float) -> None:
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    title = "VICTORY!" if result == "victory" else "DEFEAT"
    color = (255, 215, 0) if result == "victory" else (255, 60, 60)
    t = big_font.render(title, True, color)
    screen.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 110))

    ts = font.render(f"Elapsed: {int(elapsed)} s", True, (200, 200, 200))
    screen.blit(ts, (WIDTH // 2 - ts.get_width() // 2, HEIGHT // 2 - 20))

    pygame.draw.rect(screen, (45, 90, 45), RESTART_BTN)
    pygame.draw.rect(screen, (80, 140, 80), RESTART_BTN, 2)
    rs = font.render("Restart", True, (220, 220, 220))
    screen.blit(rs, (RESTART_BTN.centerx - rs.get_width() // 2,
                     RESTART_BTN.centery - rs.get_height() // 2))


def _pos_to_grid(pos: pygame.Vector2) -> tuple[int, int]:
    return int(pos.x / CELL_SIZE), int(pos.y / CELL_SIZE)


def run_game(screen: pygame.Surface, clock: pygame.time.Clock,
             font: pygame.font.Font, big_font: pygame.font.Font) -> bool:
    """Play one match. Returns True to restart, False to quit."""

    sounds = load_sounds()
    muted = False

    def _play(name: str) -> None:
        if not muted and name in sounds:
            sounds[name].stop()
            sounds[name].play()

    # --- Sprites ---
    try:
        raw = pygame.image.load("assets/footman.png").convert_alpha()
        player_sprite = pygame.transform.scale(raw, (128, 128))
        enemy_sprite = player_sprite.copy()
    except FileNotFoundError:
        player_sprite = make_sprite((70, 130, 180))
        enemy_sprite  = make_sprite((180, 50,  50))

    player_archer_sprite = make_sprite((50, 185, 165))
    enemy_archer_sprite  = make_sprite((200, 80,  55))
    worker_sprite        = make_sprite((120, 170, 100))
    enemy_worker_sprite  = make_sprite((170, 110, 110))

    # --- Map ---
    game_map = GameMap(WIDTH, HEIGHT)
    fog      = FogOfWar(game_map.grid_w, game_map.grid_h)
    minimap  = Minimap(DEFAULT_MAP)

    # --- Buildings ---
    buildings: list = [
        TownHall(30,  260, team=0),
        Barracks(30,  420, team=0),
        Farm(200, 420, team=0),
        Farm(310, 420, team=0),
        TownHall(1090, 260, team=1),
        Barracks(940,  260, team=1),
        Farm(940,  420, team=1),
        Farm(1090, 420, team=1),
        GoldMine(40,   110),
        GoldMine(1100, 110),
    ]
    player_hall = next(b for b in buildings if isinstance(b, TownHall) and b.team == 0)

    # --- Units ---
    units: list = [
        Unit(280, 330, player_sprite, team=0),
        Unit(380, 330, player_sprite, team=0),
        Worker(180, 360, worker_sprite, team=0),
        Unit(1040, 360, enemy_sprite, team=1),
        Worker(1200, 380, enemy_worker_sprite, team=1),
    ]

    corpses: list[Corpse] = []
    projectiles: list[Projectile] = []

    gold: dict[int, int] = {0: 500, 1: 500}
    selected: list = []
    selected_building = None
    drag_start: pygame.Vector2 | None = None
    drag_current: pygame.Vector2 | None = None
    game_over: str | None = None
    elapsed: float = 0.0

    ai = AIController(
        team=1, buildings=buildings, units=units, gold=gold,
        game_map=game_map, enemy_sprite=enemy_sprite,
        worker_sprite=enemy_worker_sprite,
    )

    while True:
        dt = clock.tick(FPS) / 1000.0

        # ---- Events ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_m:
                    muted = not muted
                    if muted:
                        pygame.mixer.pause()
                    else:
                        pygame.mixer.unpause()

            if game_over is not None:
                if event.type == pygame.MOUSEBUTTONDOWN and RESTART_BTN.collidepoint(event.pos):
                    return True
                continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if _MUTE_BTN.collidepoint(event.pos):
                        muted = not muted
                        if muted:
                            pygame.mixer.pause()
                        else:
                            pygame.mixer.unpause()
                    elif (selected_building is not None
                            and isinstance(selected_building, Barracks)):
                        food_used, food_cap = food_stats(buildings, units)
                        if TRAIN_BTN.collidepoint(event.pos) and food_used < food_cap:
                            selected_building.enqueue(gold, "footman")
                        elif TRAIN_ARCHER_BTN.collidepoint(event.pos) and food_used < food_cap:
                            selected_building.enqueue(gold, "archer")
                        elif event.pos[1] <= PANEL_Y:
                            drag_start = pygame.Vector2(event.pos)
                            drag_current = pygame.Vector2(event.pos)
                    elif event.pos[1] > PANEL_Y and selected_building is not None:
                        pass
                    else:
                        drag_start = pygame.Vector2(event.pos)
                        drag_current = pygame.Vector2(event.pos)

                elif event.button == 3 and selected:
                    enemy_unit = next((u for u in units if u.team == 1
                                       and u.contains_point(event.pos)), None)
                    enemy_bldg = next((b for b in buildings if b.team == 1
                                       and b.contains_point(event.pos)), None)
                    mine = next((b for b in buildings if isinstance(b, GoldMine)
                                  and b.contains_point(event.pos)), None)

                    if enemy_unit:
                        for u in selected:
                            u.order_attack(enemy_unit)
                    elif enemy_bldg:
                        for u in selected:
                            u.order_attack(enemy_bldg)
                    elif mine:
                        movers: list = []
                        for u in selected:
                            if isinstance(u, Worker):
                                u.order_harvest(mine, player_hall, game_map)
                            else:
                                movers.append(u)
                        if movers:
                            tgts = formation_targets(pygame.Vector2(event.pos), len(movers))
                            for u, tgt in zip(movers, tgts):
                                u.move_to(game_map.find_path(u.pos, tgt))
                            _play('move')
                    else:
                        tgts = formation_targets(pygame.Vector2(event.pos), len(selected))
                        for u, tgt in zip(selected, tgts):
                            u.move_to(game_map.find_path(u.pos, tgt))
                        _play('move')

            elif event.type == pygame.MOUSEMOTION and drag_start is not None:
                drag_current = pygame.Vector2(event.pos)

            elif (event.type == pygame.MOUSEBUTTONUP
                  and event.button == 1 and drag_start is not None):
                end = pygame.Vector2(event.pos)
                delta = end - drag_start

                if delta.length() > 4:
                    sel_rect = pygame.Rect(
                        int(min(drag_start.x, end.x)), int(min(drag_start.y, end.y)),
                        int(abs(delta.x)), int(abs(delta.y)),
                    )
                    new_sel = [u for u in units
                               if u.team == 0 and sel_rect.colliderect(u.rect)]
                    selected = apply_selection(selected, new_sel)
                    if selected_building:
                        selected_building.selected = False
                        selected_building = None
                    if selected:
                        _play('select')
                else:
                    bldg = next((b for b in buildings
                                  if b.team == 0 and b.contains_point(event.pos)), None)
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
                        clicked = next((u for u in units
                                         if u.team == 0 and u.contains_point(event.pos)), None)
                        new_sel = [clicked] if clicked else []
                        selected = apply_selection(selected, new_sel)
                        if selected:
                            _play('select')

                drag_start = None
                drag_current = None

        # ---- Update (frozen when game over) ----
        if game_over is None:
            elapsed += dt
            ai.update(dt)

            player_units = [u for u in units if u.team == 0]
            enemy_units  = [u for u in units if u.team == 1]
            for u in player_units:
                u.update(dt, enemy_units, game_map)
            for u in enemy_units:
                u.update(dt, player_units, game_map)

            # Drain archer projectiles
            for u in units:
                if isinstance(u, Archer) and u.projectiles_pending:
                    projectiles.extend(u.projectiles_pending)
                    u.projectiles_pending.clear()

            # Gold harvesting
            for u in units:
                if isinstance(u, Worker):
                    gold[u.team] += u.gold_delivered
                    u.gold_delivered = 0

            # Barracks training
            for b in buildings:
                if isinstance(b, Barracks):
                    for unit_type in b.update(dt):
                        sp = pygame.Vector2(b.rect.right + 40, b.rect.centery)
                        if unit_type == "archer":
                            sprite = player_archer_sprite if b.team == 0 else enemy_archer_sprite
                            new_unit = Archer(sp.x, sp.y, sprite, team=b.team)
                        else:
                            sprite = player_sprite if b.team == 0 else enemy_sprite
                            new_unit = Unit(sp.x, sp.y, sprite, team=b.team)
                        units.append(new_unit)
                        if b.team == 0:
                            _play('train_done')

            # Corpse creation + sound on death
            for u in units:
                if not u.is_alive():
                    corpses.append(Corpse(u.pos, u.team))
                    _play('death')

            units = [u for u in units if u.is_alive()]
            selected = [u for u in selected if u.is_alive()]

            # Corpses decay
            corpses = [c for c in corpses if c.update(dt)]

            # Projectiles
            projectiles = [p for p in projectiles if p.update(dt)]

            buildings = [b for b in buildings if b.is_alive()]
            if selected_building is not None and not selected_building.is_alive():
                selected_building.selected = False
                selected_building = None

            # Fog-of-war visibility update
            fog.update(player_units)

            # Win / lose
            if not any(isinstance(b, TownHall) and b.team == 1 for b in buildings):
                game_over = "victory"
            elif not any(isinstance(b, TownHall) and b.team == 0 for b in buildings):
                game_over = "defeat"

        # ---- Draw ----
        game_map.draw(screen)

        for c in corpses:
            c.draw(screen)

        for b in buildings:
            b.draw(screen)

        # Enemy units hidden if not in visible fog cells
        visible = fog._visible
        for u in units:
            if u.team != 0:
                cell = _pos_to_grid(u.pos)
                if cell not in visible:
                    continue
            u.draw(screen)

        for p in projectiles:
            p.draw(screen)

        # Drag selection box
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

        # Fog overlay (drawn before HUD/minimap so UI remains clear)
        fog.draw(screen)

        # Minimap (above the fog)
        minimap.draw(screen, buildings, units)

        draw_hud(screen, font, gold, buildings, units, selected_building, ai.state, muted)

        if game_over is not None:
            draw_game_over(screen, font, big_font, game_over, elapsed)

        pygame.display.flip()


def main():
    pre_init()   # must come before pygame.init() to set mixer format
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RTS Prototype")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 26)
    big_font = pygame.font.Font(None, 96)

    while run_game(screen, clock, font, big_font):
        pass

    pygame.quit()


if __name__ == "__main__":
    main()
