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
from minimap import Minimap
from sound import pre_init, load_sounds
from sprites import load_unit_sprites
from spritesheet import load_war2_sprites
from pathfinding import CELL_SIZE

# Logical (canvas) resolution — game coordinates always live here
WIDTH, HEIGHT = 1280, 720
FPS = 60
FORMATION_SPACING = 90
PANEL_H = 80
PANEL_Y = HEIGHT - PANEL_H

# Bottom panel buttons (in canvas space)
TRAIN_BTN        = pygame.Rect(10,  PANEL_Y + 26, 185, 28)
TRAIN_ARCHER_BTN = pygame.Rect(205, PANEL_Y + 26, 185, 28)
RESTART_BTN      = pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 + 50, 160, 40)
_MUTE_BTN        = pygame.Rect(WIDTH - 70, 4, 60, 20)
_FS_BTN          = pygame.Rect(WIDTH - 136, 4, 60, 20)   # fullscreen toggle button


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


def draw_hud(canvas: pygame.Surface, font: pygame.font.Font,
             gold: dict, buildings: list, units: list,
             selected_building, ai_state: str = "",
             muted: bool = False, fullscreen: bool = False) -> None:
    pygame.draw.rect(canvas, (20, 20, 28), (0, 0, WIDTH, 28))
    food_used, food_cap = food_stats(buildings, units)
    canvas.blit(font.render(f"Gold: {gold[0]}", True, (255, 215, 0)), (10, 5))
    canvas.blit(font.render(f"Food: {food_used}/{food_cap}", True, (200, 230, 200)), (160, 5))

    if ai_state:
        label = f"Enemy: {ai_state.upper()}"
        color = (255, 80, 80) if ai_state == "attack" else (160, 160, 180)
        surf = font.render(label, True, color)
        canvas.blit(surf, (_FS_BTN.x - surf.get_width() - 10, 5))

    # SFX / mute button
    m_col = (80, 50, 50) if muted else (40, 80, 40)
    pygame.draw.rect(canvas, m_col, _MUTE_BTN)
    pygame.draw.rect(canvas, (120, 80, 80) if muted else (70, 130, 70), _MUTE_BTN, 1)
    canvas.blit(font.render("MUTE" if muted else "SFX", True, (200, 200, 180)),
                (_MUTE_BTN.x + 4, _MUTE_BTN.y + 2))

    # Fullscreen toggle button
    fs_col = (50, 70, 90) if fullscreen else (40, 60, 80)
    pygame.draw.rect(canvas, fs_col, _FS_BTN)
    pygame.draw.rect(canvas, (80, 110, 140), _FS_BTN, 1)
    canvas.blit(font.render("WIN" if fullscreen else "F11", True, (180, 210, 240)),
                (_FS_BTN.x + 6, _FS_BTN.y + 2))

    if selected_building is None:
        return

    pygame.draw.rect(canvas, (20, 22, 32), (0, PANEL_Y, WIDTH, PANEL_H))
    pygame.draw.line(canvas, (70, 70, 100), (0, PANEL_Y), (WIDTH, PANEL_Y))
    info = f"{selected_building.label}   HP {selected_building.hp}/{selected_building.max_hp}"
    canvas.blit(font.render(info, True, (180, 200, 220)), (10, PANEL_Y + 6))

    if isinstance(selected_building, Barracks) and selected_building.team == 0:
        food_used, food_cap = food_stats(buildings, units)
        q_len = len(selected_building.queue)

        for btn, ut in [(TRAIN_BTN, "footman"), (TRAIN_ARCHER_BTN, "archer")]:
            s = UNIT_STATS[ut]
            can = gold[0] >= s.cost and food_used < food_cap and q_len < Barracks.MAX_QUEUE
            pygame.draw.rect(canvas, (45, 90, 45) if can else (55, 55, 55), btn)
            pygame.draw.rect(canvas, (80, 130, 80) if can else (80, 80, 80), btn, 1)
            label = "Footman" if ut == "footman" else "Archer"
            canvas.blit(font.render(f"{label}  {s.cost}g", True, (220, 220, 220)),
                        (btn.x + 6, btn.y + 6))

        slot_colors = {"footman": (80, 130, 220), "archer": (60, 200, 150)}
        for i in range(Barracks.MAX_QUEUE):
            sx = TRAIN_ARCHER_BTN.right + 14 + i * 22
            sy = PANEL_Y + 32
            if i < q_len:
                ut_slot = selected_building.queue[i][0]
                color = (80, 220, 80) if i == 0 else slot_colors.get(ut_slot, (80, 130, 220))
                pygame.draw.rect(canvas, color, (sx, sy, 16, 16))
            else:
                pygame.draw.rect(canvas, (50, 50, 60), (sx, sy, 16, 16), 1)


def draw_game_over(canvas: pygame.Surface, font: pygame.font.Font,
                   big_font: pygame.font.Font, result: str, elapsed: float) -> None:
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    canvas.blit(overlay, (0, 0))

    title = "VICTORY!" if result == "victory" else "DEFEAT"
    color = (255, 215, 0) if result == "victory" else (255, 60, 60)
    t = big_font.render(title, True, color)
    canvas.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 110))

    ts = font.render(f"Elapsed: {int(elapsed)} s", True, (200, 200, 200))
    canvas.blit(ts, (WIDTH // 2 - ts.get_width() // 2, HEIGHT // 2 - 20))

    pygame.draw.rect(canvas, (45, 90, 45), RESTART_BTN)
    pygame.draw.rect(canvas, (80, 140, 80), RESTART_BTN, 2)
    rs = font.render("Restart", True, (220, 220, 220))
    canvas.blit(rs, (RESTART_BTN.centerx - rs.get_width() // 2,
                     RESTART_BTN.centery - rs.get_height() // 2))


def _pos_to_grid(pos: pygame.Vector2) -> tuple[int, int]:
    return int(pos.x / CELL_SIZE), int(pos.y / CELL_SIZE)


def run_game(screen: pygame.Surface, clock: pygame.time.Clock,
             font: pygame.font.Font, big_font: pygame.font.Font) -> bool:
    """Play one match. Returns True to restart, False to quit."""

    # Internal render canvas — all game drawing goes here at a fixed 1280×720.
    # At frame end it's scaled to whatever the display surface is.
    canvas = pygame.Surface((WIDTH, HEIGHT))
    fullscreen = False

    def to_game(pos: tuple) -> tuple[int, int]:
        """Translate physical mouse coords → canvas (game) coords."""
        sw, sh = screen.get_size()
        if sw == WIDTH and sh == HEIGHT:
            return (int(pos[0]), int(pos[1]))
        return (int(pos[0] * WIDTH / sw), int(pos[1] * HEIGHT / sh))

    def toggle_fullscreen() -> None:
        nonlocal screen, fullscreen
        fullscreen = not fullscreen
        if fullscreen:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((WIDTH, HEIGHT))

    # --- Sounds ---
    sounds = load_sounds()
    muted = False

    def _play(name: str) -> None:
        if not muted and name in sounds:
            try:
                sounds[name].stop()
                sounds[name].play()
            except pygame.error:
                pass

    def _set_mute(m: bool) -> None:
        nonlocal muted
        muted = m
        try:
            if muted:
                pygame.mixer.pause()
            else:
                pygame.mixer.unpause()
        except pygame.error:
            pass

    # --- Unit sprites ---
    unit_sprites = load_unit_sprites()
    war2_sheets  = load_war2_sprites()

    def _sprite(unit_type: str, team: int) -> pygame.Surface:
        return unit_sprites.get((unit_type, team), unit_sprites[('footman', team % 2)])

    def _sheet(unit_type: str, team: int):
        return war2_sheets.get((unit_type, team))

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
        Unit(280, 330,  _sprite('footman', 0), team=0, sheet=_sheet('footman', 0)),
        Unit(380, 330,  _sprite('footman', 0), team=0, sheet=_sheet('footman', 0)),
        Worker(180, 360, _sprite('worker',  0), team=0, sheet=_sheet('worker',  0)),
        Unit(1040, 360,  _sprite('footman', 1), team=1, sheet=_sheet('footman', 1)),
        Worker(1200, 380, _sprite('worker',  1), team=1, sheet=_sheet('worker',  1)),
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
        game_map=game_map,
        enemy_sprite=_sprite('footman', 1),
        worker_sprite=_sprite('worker',  1),
        sheets=war2_sheets,
    )

    while True:
        dt = clock.tick(FPS) / 1000.0

        # ---- Events ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if fullscreen:
                        toggle_fullscreen()
                    else:
                        return False
                elif event.key == pygame.K_F11:
                    toggle_fullscreen()
                elif event.key == pygame.K_m:
                    _set_mute(not muted)

            if game_over is not None:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    gp = to_game(event.pos)
                    if RESTART_BTN.collidepoint(gp):
                        return True
                continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                gp = to_game(event.pos)

                if event.button == 1:
                    if _MUTE_BTN.collidepoint(gp):
                        _set_mute(not muted)
                    elif _FS_BTN.collidepoint(gp):
                        toggle_fullscreen()
                    elif (selected_building is not None
                            and isinstance(selected_building, Barracks)):
                        food_used, food_cap = food_stats(buildings, units)
                        if TRAIN_BTN.collidepoint(gp) and food_used < food_cap:
                            selected_building.enqueue(gold, "footman")
                        elif TRAIN_ARCHER_BTN.collidepoint(gp) and food_used < food_cap:
                            selected_building.enqueue(gold, "archer")
                        elif gp[1] <= PANEL_Y:
                            drag_start = pygame.Vector2(gp)
                            drag_current = pygame.Vector2(gp)
                    elif gp[1] > PANEL_Y and selected_building is not None:
                        pass
                    else:
                        drag_start = pygame.Vector2(gp)
                        drag_current = pygame.Vector2(gp)

                elif event.button == 3 and selected:
                    gv = pygame.Vector2(gp)
                    enemy_unit = next((u for u in units if u.team == 1
                                       and u.contains_point(gp)), None)
                    enemy_bldg = next((b for b in buildings if b.team == 1
                                       and b.contains_point(gp)), None)
                    mine = next((b for b in buildings if isinstance(b, GoldMine)
                                  and b.contains_point(gp)), None)

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
                            tgts = formation_targets(gv, len(movers))
                            for u, tgt in zip(movers, tgts):
                                u.move_to(game_map.find_path(u.pos, tgt))
                            _play('move')
                    else:
                        tgts = formation_targets(gv, len(selected))
                        for u, tgt in zip(selected, tgts):
                            u.move_to(game_map.find_path(u.pos, tgt))
                        _play('move')

            elif event.type == pygame.MOUSEMOTION and drag_start is not None:
                drag_current = pygame.Vector2(to_game(event.pos))

            elif (event.type == pygame.MOUSEBUTTONUP
                  and event.button == 1 and drag_start is not None):
                end = pygame.Vector2(to_game(event.pos))
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
                    gp = (int(end.x), int(end.y))
                    bldg = next((b for b in buildings
                                  if b.team == 0 and b.contains_point(gp)), None)
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
                                         if u.team == 0 and u.contains_point(gp)), None)
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
                        new_unit: Unit
                        if unit_type == "archer":
                            new_unit = Archer(sp.x, sp.y, _sprite('archer', b.team), team=b.team,
                                              sheet=_sheet('archer', b.team))
                        else:
                            new_unit = Unit(sp.x, sp.y, _sprite('footman', b.team), team=b.team,
                                            sheet=_sheet('footman', b.team))
                        units.append(new_unit)
                        if b.team == 0:
                            _play('train_done')

            # Corpse + sound on death
            for u in units:
                if not u.is_alive():
                    corpses.append(Corpse(u.pos, u.team))
                    _play('death')

            units = [u for u in units if u.is_alive()]
            selected = [u for u in selected if u.is_alive()]

            corpses = [c for c in corpses if c.update(dt)]
            projectiles = [p for p in projectiles if p.update(dt)]

            buildings = [b for b in buildings if b.is_alive()]
            if selected_building is not None and not selected_building.is_alive():
                selected_building.selected = False
                selected_building = None

            fog.update(player_units)

            if not any(isinstance(b, TownHall) and b.team == 1 for b in buildings):
                game_over = "victory"
            elif not any(isinstance(b, TownHall) and b.team == 0 for b in buildings):
                game_over = "defeat"

        # ---- Draw to canvas ----
        game_map.draw(canvas)

        for c in corpses:
            c.draw(canvas)

        for b in buildings:
            b.draw(canvas)

        # Enemy units hidden outside fog visibility
        visible = fog._visible
        for u in units:
            if u.team != 0 and _pos_to_grid(u.pos) not in visible:
                continue
            u.draw(canvas)

        for p in projectiles:
            p.draw(canvas)

        # Fog overlay — drawn BEFORE the drag box so the selection box is always visible
        fog.draw(canvas)

        # Drag selection box (drawn on top of fog so it's always readable)
        if drag_start is not None and drag_current is not None:
            delta = drag_current - drag_start
            if delta.length() > 4:
                rx = int(min(drag_start.x, drag_current.x))
                ry = int(min(drag_start.y, drag_current.y))
                rw, rh = int(abs(delta.x)), int(abs(delta.y))
                sel_surf = pygame.Surface((max(1, rw), max(1, rh)), pygame.SRCALPHA)
                sel_surf.fill((0, 255, 0, 40))
                canvas.blit(sel_surf, (rx, ry))
                pygame.draw.rect(canvas, (0, 255, 0), (rx, ry, rw, rh), 1)

        minimap.draw(canvas, buildings, units)
        draw_hud(canvas, font, gold, buildings, units, selected_building,
                 ai.state, muted, fullscreen)

        if game_over is not None:
            draw_game_over(canvas, font, big_font, game_over, elapsed)

        # ---- Blit canvas to display (scaling when fullscreen) ----
        if screen.get_size() == (WIDTH, HEIGHT):
            screen.blit(canvas, (0, 0))
        else:
            pygame.transform.scale(canvas, screen.get_size(), screen)

        pygame.display.flip()


def main():
    pre_init()   # set mixer params before pygame.init()
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
