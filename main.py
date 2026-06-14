import math
import pygame
from unit import Unit, Worker, Archer
from map import GameMap, DEFAULT_MAP
from building import Building, TownHall, GoldMine, Barracks, Farm, Tree, Blacksmith, LumberMill, load_building_sprites
from ai import AIController, DIFFICULTY as AI_DIFFICULTY
from stats import UNIT_STATS, UPGRADES
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
SIDEBAR_W = 220   # left panel width; sidebar overlays x=0..219 of the game canvas

# Sidebar layout — all coords relative to canvas (0, 0)
_MINI_SB_X  = 10
_MINI_SB_Y  = 26   # minimap top (below resource row)
# Minimap is MINI_W=200 × MINI_H=110 (defined in minimap.py)

_SB_DIV1_Y  = _MINI_SB_Y + 110 + 4    # = 140  (divider after minimap)
_SB_INFO_Y0 = _SB_DIV1_Y + 4          # = 144  (portrait / info top)
_PORTRAIT_W = 60
_PORTRAIT_H = 60
_SB_INFO_TX = _MINI_SB_X + _PORTRAIT_W + 4  # = 74  (text x beside portrait)

_SB_DIV2_Y  = _SB_INFO_Y0 + 98        # = 242  (divider after info)
_CMD_SB_Y0  = _SB_DIV2_Y + 6          # = 248  (command button grid top)
_CMD_SB_DX  = 52
_CMD_SB_DY  = 52
_CMD_W = _CMD_H = 46

_CMDS = [pygame.Rect(4 + (i % 4) * _CMD_SB_DX,
                     _CMD_SB_Y0 + (i // 4) * _CMD_SB_DY,
                     _CMD_W, _CMD_H)
         for i in range(8)]

# Slot aliases — same Rect objects reused by context
TRAIN_BTN            = _CMDS[0]   # TownHall: Worker  / Barracks: Footman / LumberMill: Ranger
TRAIN_ARCHER_BTN     = _CMDS[1]   # Barracks: Archer
TRAIN_KNIGHT_BTN     = _CMDS[2]   # Barracks: Knight
RESEARCH_BTN_4       = _CMDS[3]   # Blacksmith: Armor II
BUILD_FARM_BTN       = _CMDS[0]   # Worker build menu
BUILD_BARRACKS_BTN   = _CMDS[1]
BUILD_LUMBERMILL_BTN = _CMDS[2]
BUILD_BLACKSMITH_BTN = _CMDS[3]
_QUEUE_SB_Y  = _CMD_SB_Y0 + 2 * _CMD_SB_DY + 6   # = 358  (queue dots below command grid)

RESTART_BTN  = pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 + 50, 160, 40)
_MUTE_BTN    = pygame.Rect(4,   HEIGHT - 28, 60, 20)
_FS_BTN      = pygame.Rect(68,  HEIGHT - 28, 60, 20)
_DIFF_BTN    = pygame.Rect(132, HEIGHT - 28, 82, 20)
_DIFF_LEVELS = ("easy", "normal", "hard")
_DIFF_COLORS = {"easy": (40,120,40), "normal": (40,70,120), "hard": (120,40,40)}

# Building placement costs: (gold, lumber)
BUILD_COSTS = {
    "farm":       (250, 100),
    "barracks":   (500, 200),
    "lumbermill": (600, 150),
    "blacksmith": (800, 150),
}

_build_thumbs: "dict | None" = None

_BUILD_TOOLTIP = {
    "farm":       ("Farm",         "250g  100w",  "+4 food"),
    "barracks":   ("Barracks",     "500g  200w",  "Trains: Footman, Archer"),
    "lumbermill": ("Lumber Mill",  "600g  150w",  "Worker lumber bonus"),
    "blacksmith": ("Blacksmith",   "800g  150w",  "Unlocks: Knight"),
}


def _make_build_thumbs() -> "dict[str, pygame.Surface]":
    """Create 36×36 thumbnails for build menu buttons.
    Uses WC2 building sprites when available; falls back to procedural art."""
    from building import _SPRITES as _bsprites
    thumbs: dict = {}
    S = 36

    for btype, stem in (("farm", "farm_team0"), ("barracks", "barracks_team0")):
        spr = _bsprites.get(stem)
        if spr:
            thumbs[btype] = pygame.transform.smoothscale(spr, (S, S))

    if "farm" not in thumbs:
        s = pygame.Surface((S, S), pygame.SRCALPHA)
        s.fill((34, 80, 34))
        pygame.draw.polygon(s, (140, 60, 40), [(6, 17), (18, 3), (30, 17)])
        pygame.draw.rect(s, (180, 80, 50), (7, 17, 22, 15))
        pygame.draw.rect(s, (100, 40, 20), (14, 22, 8, 10))
        thumbs["farm"] = s

    if "barracks" not in thumbs:
        s = pygame.Surface((S, S), pygame.SRCALPHA)
        s.fill((25, 40, 80))
        for bx in (2, 8, 14, 20, 26):
            pygame.draw.rect(s, (60, 90, 150), (bx, 5, 4, 7))
        pygame.draw.rect(s, (60, 90, 150), (2, 11, 32, 20))
        pygame.draw.rect(s, (15, 25, 55), (12, 19, 12, 12))
        thumbs["barracks"] = s

    # LumberMill — procedural only (no WC2 sprite extracted yet)
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    s.fill((70, 45, 20))
    pygame.draw.polygon(s, (90, 55, 25), [(1, 12), (18, 1), (35, 12)])
    pygame.draw.rect(s, (120, 80, 40), (2, 11, 32, 22))
    pygame.draw.line(s, (210, 210, 210), (5, 14), (30, 30), 3)
    pygame.draw.line(s, (210, 210, 210), (30, 14), (5, 30), 3)
    thumbs["lumbermill"] = s

    # Blacksmith — procedural only (no WC2 sprite extracted yet)
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    s.fill((45, 40, 38))
    pygame.draw.polygon(s, (60, 55, 50), [(1, 12), (18, 1), (35, 12)])
    pygame.draw.rect(s, (80, 75, 70), (2, 11, 32, 22))
    pygame.draw.rect(s, (160, 155, 150), (9, 20, 18, 8))
    pygame.draw.rect(s, (160, 155, 150), (12, 17, 12, 5))
    pygame.draw.circle(s, (220, 100, 20), (27, 26), 4)
    thumbs["blacksmith"] = s

    return thumbs


# Unit portrait thumbnails for training buttons — populated by init_ui_thumbs().
_unit_thumbs: dict[str, pygame.Surface] = {}


def init_ui_thumbs(sheets: dict) -> None:
    """Pre-bake 36×36 front-facing portraits for each trainable unit type.
    Call once after load_war2_sprites() so draw_hud can use them without per-frame scaling."""
    _unit_thumbs.clear()
    S = 36
    for (ut, team), sheet in sheets.items():
        if team != 0:
            continue
        frame = sheet.walk_frame(4, 0)  # DIR_S, tick 0 = front-facing portrait
        _unit_thumbs[ut] = pygame.transform.smoothscale(frame, (S, S))


def _draw_build_tooltip(canvas: pygame.Surface, font: pygame.font.Font,
                        btn: pygame.Rect, btype: str, can_buy: bool) -> None:
    info = _BUILD_TOOLTIP.get(btype)
    if info is None:
        return
    name, cost, detail = info
    cost_col = (255, 215, 80) if can_buy else (160, 100, 100)
    _draw_info_tooltip(canvas, font, btn, [
        (name,   (230, 230, 230)),
        (cost,   cost_col),
        (detail, (160, 200, 160)),
    ])


_BUILDING_UNLOCKS: dict[str, str] = {
    "Town Hall":    "Trains: Worker",
    "Barracks":     "Trains: Footman, Archer (+Knight with Blacksmith)",
    "Lumber Mill":  "Worker +25 lumber carry  |  Research: Ranger Training",
    "Blacksmith":   "Unlocks: Knight  |  Research: Weapons & Armor upgrades",
    "Farm":         "Provides +4 food",
}


def _draw_train_btn(canvas: pygame.Surface, font: pygame.font.Font,
                    btn: pygame.Rect, ut: str, label: str,
                    cost_g: int, can_afford: bool, mouse_pos: tuple,
                    locked: bool = False, lock_reason: str = "") -> None:
    """Draw a training button with WC2-style unit portrait thumbnail."""
    if locked:
        bg, bd = (32, 30, 32), (60, 55, 60)
    else:
        bg = (40, 75, 40) if can_afford else (50, 50, 55)
        bd = (70, 130, 70) if can_afford else (75, 75, 80)
    pygame.draw.rect(canvas, bg, btn)
    pygame.draw.rect(canvas, bd, btn, 1)

    thumb = _unit_thumbs.get(ut)
    if thumb:
        t = thumb.copy()
        t.set_alpha(60 if locked else (160 if not can_afford else 255))
        canvas.blit(t, (btn.x + 5, btn.y + 5))
        if locked:
            tc = (80, 75, 85)
            canvas.blit(font.render("[lock]", True, tc), (btn.x + 3, btn.y + 34))
    else:
        tc = (80, 75, 85) if locked else ((220, 220, 220) if can_afford else (130, 130, 130))
        canvas.blit(font.render(label[:6], True, tc), (btn.x + 2, btn.y + 6))
        canvas.blit(font.render(f"{cost_g}g", True, tc), (btn.x + 4, btn.y + 24))

    if btn.collidepoint(mouse_pos):
        if locked:
            _draw_info_tooltip(canvas, font, btn, [
                (label, (200, 190, 220)),
                (lock_reason, (200, 120, 120)),
            ])
        else:
            col_g = (220, 200, 80) if can_afford else (160, 100, 80)
            _draw_info_tooltip(canvas, font, btn, [
                (label, (220, 220, 230)),
                (f"{cost_g} gold", col_g),
            ])


def _draw_info_tooltip(canvas: pygame.Surface, font: pygame.font.Font,
                       btn: pygame.Rect, lines: "list[tuple[str, tuple]]") -> None:
    """Draw a small tooltip above (or below if near top) btn.
    lines: list of (text, color) pairs."""
    pad = 6
    lh = font.get_height()
    surfs = [font.render(t, True, c) for t, c in lines]
    tw = max(s.get_width() for s in surfs) + pad * 2
    th = lh * len(surfs) + pad * 2
    tx = max(0, min(btn.x, WIDTH - tw))
    ty = btn.y - th - 4
    if ty < 30:
        ty = btn.bottom + 4
    pygame.draw.rect(canvas, (18, 18, 28), (tx, ty, tw, th))
    pygame.draw.rect(canvas, (80, 80, 120), (tx, ty, tw, th), 1)
    for i, surf in enumerate(surfs):
        canvas.blit(surf, (tx + pad, ty + pad + i * lh))


def placement_valid(rect: pygame.Rect, buildings: list, game_map) -> bool:
    """True when rect fits on passable terrain without overlapping existing buildings."""
    if rect.left < SIDEBAR_W or rect.top < 0 or rect.right > WIDTH or rect.bottom > HEIGHT:
        return False
    col0 = rect.left // CELL_SIZE
    row0 = rect.top // CELL_SIZE
    col1 = (rect.right + CELL_SIZE - 1) // CELL_SIZE
    row1 = (rect.bottom + CELL_SIZE - 1) // CELL_SIZE
    for c in range(col0, col1):
        for r in range(row0, row1):
            if (c, r) in game_map.blocked:
                return False
    pad = rect.inflate(8, 8)
    return not any(pad.colliderect(b.rect) for b in buildings)


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
    cap = sum(b.FOOD for b in buildings if isinstance(b, Farm) and b.team == 0 and b.is_complete)
    used = sum(1 for u in units if u.team == 0)
    return used, cap


_PORTRAIT_BG: dict[str, tuple] = {
    "worker":  (80,  55,  30),
    "footman": (35,  65, 110),
    "archer":  (35,  85,  50),
    "knight":  (70,  50, 105),
}
_WORKER_STATUS: dict[str, str] = {
    "idle":           "Idle",
    "to_mine":        "Going to mine",
    "harvesting":     "Mining",
    "to_hall":        "Returning gold",
    "to_tree":        "Going to tree",
    "chopping":       "Chopping",
    "to_hall_lumber": "Returning lumber",
}


def _draw_unit_info_panel(canvas: pygame.Surface, font: pygame.font.Font,
                          selected: list) -> None:
    """Sidebar info section: single-unit portrait + stats, or multi-select summary."""
    if len(selected) == 1:
        u = selected[0]
        pr = pygame.Rect(_MINI_SB_X, _SB_INFO_Y0, _PORTRAIT_W, _PORTRAIT_H)
        pc = _PORTRAIT_BG.get(u.unit_type, (55, 55, 75))
        pygame.draw.rect(canvas, pc, pr)
        pygame.draw.rect(canvas, tuple(min(255, c + 70) for c in pc), pr, 2)
        if u._sheet is not None:
            # direction 4 = DIR_S, tick 0 → front-facing (direction-major idx=20)
            pf = pygame.transform.scale(u._sheet.walk_frame(4, 0), (pr.width, pr.height))
            canvas.blit(pf, pr)
        else:
            ab = font.render(u.unit_type[0].upper(), True, (220, 220, 220))
            canvas.blit(ab, ab.get_rect(center=pr.center))

        tx, ty = _SB_INFO_TX, _SB_INFO_Y0
        canvas.blit(font.render(u.unit_type.capitalize(), True, (210, 215, 240)), (tx, ty))
        ratio = max(0.0, u.hp / u.max_hp)
        bc = (0, 200, 0) if ratio > 0.5 else (220, 180, 0) if ratio > 0.25 else (200, 30, 30)
        bx, by, bw, bh = tx, ty + 18, 130, 7
        pygame.draw.rect(canvas, (50, 50, 50), (bx, by, bw, bh))
        pygame.draw.rect(canvas, bc, (bx, by, int(bw * ratio), bh))
        canvas.blit(font.render(f"{u.hp}/{u.max_hp}", True, (175, 200, 175)), (tx, ty + 28))
        canvas.blit(font.render(f"Atk {u.attack_damage}  Rng {int(u.attack_range)}",
                                True, (155, 170, 190)), (tx, ty + 44))
        canvas.blit(font.render(f"Spd {int(u.speed)}" + (f"  Arm {u.armor}" if u.armor else ""),
                                True, (155, 170, 190)), (tx, ty + 58))
        if isinstance(u, Worker):
            status = _WORKER_STATUS.get(u._wstate, u._wstate)
            canvas.blit(font.render(status, True, (140, 190, 145)),
                        (_MINI_SB_X, _SB_INFO_Y0 + _PORTRAIT_H + 4))
    else:
        from collections import Counter
        total_hp  = sum(u.hp     for u in selected)
        total_max = sum(u.max_hp for u in selected)
        canvas.blit(font.render(f"{len(selected)} units", True, (200, 210, 235)),
                    (_MINI_SB_X, _SB_INFO_Y0))
        ratio = total_hp / total_max if total_max else 0
        bc = (0, 200, 0) if ratio > 0.5 else (220, 180, 0) if ratio > 0.25 else (200, 30, 30)
        bw = SIDEBAR_W - 2 * _MINI_SB_X
        pygame.draw.rect(canvas, (50, 50, 50), (_MINI_SB_X, _SB_INFO_Y0 + 22, bw, 8))
        pygame.draw.rect(canvas, bc,           (_MINI_SB_X, _SB_INFO_Y0 + 22, int(bw * ratio), 8))
        canvas.blit(font.render(f"HP {total_hp}/{total_max}", True, (175, 200, 175)),
                    (_MINI_SB_X, _SB_INFO_Y0 + 34))
        counts = Counter(u.unit_type for u in selected)
        for row, (ut, n) in enumerate(sorted(counts.items())[:4]):
            canvas.blit(font.render(f"{ut.capitalize()}×{n}", True, (155, 170, 190)),
                        (_MINI_SB_X, _SB_INFO_Y0 + 52 + row * 16))


def draw_hud(canvas: pygame.Surface, font: pygame.font.Font,
             gold: dict, lumber: dict, buildings: list, units: list,
             selected: list, selected_building, ai_state: str = "",
             muted: bool = False, fullscreen: bool = False,
             build_mode: str | None = None,
             difficulty: str = "normal",
             mouse_pos: tuple = (0, 0),
             team_upgrades: "set | None" = None) -> None:
    global _build_thumbs
    if team_upgrades is None:
        team_upgrades = set()

    # ---- Sidebar background + right border ----
    pygame.draw.rect(canvas, (18, 20, 28), (0, 0, SIDEBAR_W, HEIGHT))
    pygame.draw.line(canvas, (70, 70, 100), (SIDEBAR_W - 1, 0), (SIDEBAR_W - 1, HEIGHT))

    # ---- Resources row (top of sidebar) ----
    food_used, food_cap = food_stats(buildings, units)
    canvas.blit(font.render(f"G:{gold[0]}",           True, (255, 215, 0)),    (_MINI_SB_X, 4))
    canvas.blit(font.render(f"L:{lumber[0]}",         True, (120, 200, 80)),   (_MINI_SB_X + 78, 4))
    canvas.blit(font.render(f"F:{food_used}/{food_cap}", True, (200, 230, 200)), (_MINI_SB_X + 148, 4))

    # ---- Section dividers ----
    pygame.draw.line(canvas, (55, 55, 80), (4, _SB_DIV1_Y), (SIDEBAR_W - 6, _SB_DIV1_Y))
    pygame.draw.line(canvas, (55, 55, 80), (4, _SB_DIV2_Y), (SIDEBAR_W - 6, _SB_DIV2_Y))

    # ---- Command buttons — context-sensitive ----
    worker_selected = any(isinstance(u, Worker) for u in selected) if selected else False
    if worker_selected or build_mode:
        if _build_thumbs is None:
            _build_thumbs = _make_build_thumbs()
        _hovered_build: "tuple | None" = None
        for btn, btype, blabel in [
            (BUILD_FARM_BTN,       "farm",       "Farm"),
            (BUILD_BARRACKS_BTN,   "barracks",   "Barracks"),
            (BUILD_LUMBERMILL_BTN, "lumbermill", "LMill"),
            (BUILD_BLACKSMITH_BTN, "blacksmith", "Smith"),
        ]:
            cost_g, cost_l = BUILD_COSTS[btype]
            active  = build_mode == btype
            can_buy = gold[0] >= cost_g and lumber[0] >= cost_l
            bg     = (50, 80, 140) if active else ((35, 65, 35) if can_buy else (40, 40, 40))
            border = (120, 160, 255) if active else ((70, 120, 70) if can_buy else (70, 70, 70))
            tc     = (220, 220, 220) if (can_buy or active) else (110, 110, 110)
            pygame.draw.rect(canvas, bg, btn)
            pygame.draw.rect(canvas, border, btn, 1)
            thumb = _build_thumbs.get(btype)
            if thumb:
                big = pygame.transform.scale(thumb, (36, 36))
                canvas.blit(big, (btn.x + 5, btn.y + 5))
            else:
                canvas.blit(font.render(blabel[:6], True, tc), (btn.x + 2, btn.y + 14))
            if btn.collidepoint(mouse_pos):
                _hovered_build = (btn, btype, can_buy)
        if _hovered_build:
            _draw_build_tooltip(canvas, font, *_hovered_build)

    # ---- Info section: build-mode prompt, unit info, or building info ----
    if build_mode:
        _BNAMES = {"farm": "Farm", "barracks": "Barracks",
                   "lumbermill": "Lumber Mill", "blacksmith": "Blacksmith"}
        bname = _BNAMES.get(build_mode, build_mode)
        canvas.blit(font.render("Placing:", True, (180, 220, 180)), (_MINI_SB_X, _SB_INFO_Y0))
        canvas.blit(font.render(bname, True, (220, 255, 220)), (_MINI_SB_X, _SB_INFO_Y0 + 18))
        canvas.blit(font.render("RMB / ESC cancel", True, (150, 180, 150)),
                    (_MINI_SB_X, _SB_INFO_Y0 + 36))
    elif selected_building is None:
        if selected:
            _draw_unit_info_panel(canvas, font, selected)
    else:
        bld_status = "" if selected_building.is_complete else "  [...]"
        canvas.blit(font.render(selected_building.label, True, (180, 200, 220)),
                    (_MINI_SB_X, _SB_INFO_Y0))
        canvas.blit(font.render(f"HP {selected_building.hp}/{selected_building.max_hp}{bld_status}",
                                True, (155, 175, 195)), (_MINI_SB_X, _SB_INFO_Y0 + 18))
        unlocks_text = _BUILDING_UNLOCKS.get(selected_building.label)
        if unlocks_text:
            for i, line in enumerate(unlocks_text.split("  |  ")[:2]):
                canvas.blit(font.render(line, True, (120, 175, 120)),
                            (_MINI_SB_X, _SB_INFO_Y0 + 36 + i * 16))

        # Building-specific command buttons
        if isinstance(selected_building, TownHall) and selected_building.team == 0:
            food_used, food_cap = food_stats(buildings, units)
            s = UNIT_STATS["worker"]
            q_len = len(selected_building.queue)
            can_w = gold[0] >= s.cost and food_used < food_cap and q_len < TownHall.MAX_QUEUE
            _draw_train_btn(canvas, font, TRAIN_BTN, "worker", "Worker",
                            s.cost, can_w, mouse_pos)
            slot_colors_th = {"worker": (100, 200, 100)}
            for i in range(TownHall.MAX_QUEUE):
                sx = 4 + i * 16
                if i < q_len:
                    ut_slot = selected_building.queue[i][0]
                    color = (80, 220, 80) if i == 0 else slot_colors_th.get(ut_slot, (100, 200, 100))
                    pygame.draw.rect(canvas, color, (sx, _QUEUE_SB_Y, 13, 13))
                else:
                    pygame.draw.rect(canvas, (50, 50, 60), (sx, _QUEUE_SB_Y, 13, 13), 1)

        elif isinstance(selected_building, Barracks) and selected_building.team == 0:
            if selected_building.is_complete:
                food_used, food_cap = food_stats(buildings, units)
                q_len = len(selected_building.queue)
                for btn, ut, ulabel in [(TRAIN_BTN, "footman", "Footman"),
                                         (TRAIN_ARCHER_BTN, "archer", "Archer")]:
                    s = UNIT_STATS[ut]
                    can = gold[0] >= s.cost and food_used < food_cap and q_len < Barracks.MAX_QUEUE
                    _draw_train_btn(canvas, font, btn, ut, ulabel, s.cost, can, mouse_pos)
                s = UNIT_STATS["knight"]
                has_smith = any(isinstance(b, Blacksmith) and b.team == 0 and b.is_complete
                                for b in buildings)
                can_k = has_smith and gold[0] >= s.cost and food_used < food_cap and q_len < Barracks.MAX_QUEUE
                _draw_train_btn(canvas, font, TRAIN_KNIGHT_BTN, "knight", "Knight",
                                s.cost, can_k, mouse_pos,
                                locked=not has_smith, lock_reason="Requires: Blacksmith")
                slot_colors = {"footman": (80, 130, 220), "archer": (60, 200, 150), "knight": (220, 180, 80)}
                for i in range(Barracks.MAX_QUEUE):
                    sx = 4 + i * 16
                    if i < q_len:
                        ut_slot = selected_building.queue[i][0]
                        color = (80, 220, 80) if i == 0 else slot_colors.get(ut_slot, (80, 130, 220))
                        pygame.draw.rect(canvas, color, (sx, _QUEUE_SB_Y, 13, 13))
                    else:
                        pygame.draw.rect(canvas, (50, 50, 60), (sx, _QUEUE_SB_Y, 13, 13), 1)

        elif isinstance(selected_building, Blacksmith) and selected_building.team == 0:
            if selected_building.is_complete:
                busy_rid = selected_building.research_queue[0][0] if selected_building.research_queue else None
                _SMITH_ABBR = {"weapons_1": ("Wpn I",  (200,190,100)),
                               "armor_1":   ("Arm I",   (100,170,200)),
                               "weapons_2": ("Wpn II",  (220,210,120)),
                               "armor_2":   ("Arm II",  (120,190,220))}
                for btn, rid in [
                    (TRAIN_BTN,        "weapons_1"),
                    (TRAIN_ARCHER_BTN, "armor_1"),
                    (TRAIN_KNIGHT_BTN, "weapons_2"),
                    (RESEARCH_BTN_4,   "armor_2"),
                ]:
                    spec = UPGRADES[rid]
                    done = rid in team_upgrades
                    busy = busy_rid == rid
                    prereq_met = spec.requires is None or spec.requires in team_upgrades
                    can_afford = gold[0] >= spec.gold
                    abbr, acol = _SMITH_ABBR[rid]
                    if done:
                        bg, bd, tc = (28, 50, 28), (50, 90, 50), (80, 160, 80)
                        sub = "DONE"
                    elif busy:
                        remaining = selected_building.research_queue[0][1]
                        ratio = 1.0 - remaining / spec.time
                        bg, bd, tc = (50, 70, 30), (90, 130, 60), acol
                        sub = f"{int(remaining)}s"
                    elif not prereq_met:
                        bg, bd, tc = (32, 30, 32), (60, 55, 60), (80, 75, 80)
                        sub = "[lock]"
                    elif not can_afford:
                        bg, bd, tc = (45, 40, 30), (75, 65, 45), (130, 120, 90)
                        sub = f"{spec.gold}g"
                    else:
                        bg, bd, tc = (60, 55, 25), (110, 100, 50), acol
                        sub = f"{spec.gold}g"
                    pygame.draw.rect(canvas, bg, btn)
                    pygame.draw.rect(canvas, bd, btn, 1)
                    if busy:
                        progress_w = int(btn.width * ratio)
                        pygame.draw.rect(canvas, (80, 120, 40), (btn.x, btn.y, progress_w, btn.height))
                        pygame.draw.rect(canvas, bd, btn, 1)
                    canvas.blit(font.render(abbr, True, tc), (btn.x + 2, btn.y + 6))
                    canvas.blit(font.render(sub,  True, tc), (btn.x + 2, btn.y + 24))
                    if btn.collidepoint(mouse_pos) and not done:
                        req_line = f"Req: {UPGRADES[spec.requires].name}" if spec.requires else "No prereqs"
                        _draw_info_tooltip(canvas, font, btn, [
                            (spec.name, (220, 215, 170)),
                            (f"{spec.gold}g  {spec.time:.0f}s", (200, 215, 80) if can_afford else (160, 100, 80)),
                            (req_line, (140, 160, 140)),
                        ])

        elif isinstance(selected_building, LumberMill) and selected_building.team == 0:
            if selected_building.is_complete:
                rid = "ranger"
                spec = UPGRADES[rid]
                done = rid in team_upgrades
                busy = bool(selected_building.research_queue)
                can_afford = gold[0] >= spec.gold
                if done:
                    bg, bd, tc = (28, 50, 28), (50, 90, 50), (80, 160, 80)
                    sub = "DONE"
                elif busy:
                    remaining = selected_building.research_queue[0][1]
                    ratio = 1.0 - remaining / spec.time
                    bg, bd, tc = (30, 55, 55), (55, 100, 100), (150, 220, 220)
                    sub = f"{int(remaining)}s"
                elif not can_afford:
                    bg, bd, tc = (35, 45, 45), (60, 75, 75), (100, 140, 140)
                    sub = f"{spec.gold}g"
                else:
                    bg, bd, tc = (25, 65, 65), (50, 115, 115), (160, 230, 230)
                    sub = f"{spec.gold}g"
                pygame.draw.rect(canvas, bg, TRAIN_BTN)
                pygame.draw.rect(canvas, bd, TRAIN_BTN, 1)
                if busy:
                    pygame.draw.rect(canvas, (40, 100, 100),
                                     (TRAIN_BTN.x, TRAIN_BTN.y, int(TRAIN_BTN.width * ratio), TRAIN_BTN.height))
                    pygame.draw.rect(canvas, bd, TRAIN_BTN, 1)
                canvas.blit(font.render("Ranger", True, tc), (TRAIN_BTN.x + 2, TRAIN_BTN.y + 6))
                canvas.blit(font.render(sub, True, tc), (TRAIN_BTN.x + 2, TRAIN_BTN.y + 24))
                if TRAIN_BTN.collidepoint(mouse_pos) and not done:
                    _draw_info_tooltip(canvas, font, TRAIN_BTN, [
                        (spec.name, (160, 230, 230)),
                        (f"{spec.gold}g  {spec.time:.0f}s", (200, 215, 80) if can_afford else (160, 100, 80)),
                        ("Archer range +64, damage +3", (140, 200, 170)),
                    ])

    # ---- System buttons (sidebar bottom) ----
    m_col = (80, 50, 50) if muted else (40, 80, 40)
    pygame.draw.rect(canvas, m_col, _MUTE_BTN)
    pygame.draw.rect(canvas, (120, 80, 80) if muted else (70, 130, 70), _MUTE_BTN, 1)
    canvas.blit(font.render("MUT" if muted else "SFX", True, (200, 200, 180)),
                (_MUTE_BTN.x + 4, _MUTE_BTN.y + 2))

    fs_col = (50, 70, 90) if fullscreen else (40, 60, 80)
    pygame.draw.rect(canvas, fs_col, _FS_BTN)
    pygame.draw.rect(canvas, (80, 110, 140), _FS_BTN, 1)
    canvas.blit(font.render("WIN" if fullscreen else "F11", True, (180, 210, 240)),
                (_FS_BTN.x + 4, _FS_BTN.y + 2))

    diff_bg = _DIFF_COLORS.get(difficulty, (60, 60, 60))
    pygame.draw.rect(canvas, diff_bg, _DIFF_BTN)
    pygame.draw.rect(canvas, tuple(min(255, c + 50) for c in diff_bg), _DIFF_BTN, 1)
    canvas.blit(font.render(difficulty.upper(), True, (220, 220, 220)),
                (_DIFF_BTN.x + 4, _DIFF_BTN.y + 2))

    # ---- AI state badge ----
    if ai_state:
        label = f"Enemy: {ai_state.upper()}"
        color = (255, 80, 80) if ai_state == "attack" else (160, 160, 180)
        canvas.blit(font.render(label, True, color), (_MINI_SB_X, HEIGHT - 52))


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
             font: pygame.font.Font, big_font: pygame.font.Font,
             difficulty: str = "normal") -> tuple[bool, str]:
    """Play one match. Returns (restart, difficulty)."""

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

    # --- Sprites ---
    load_building_sprites()
    unit_sprites = load_unit_sprites()
    war2_sheets  = load_war2_sprites()
    init_ui_thumbs(war2_sheets)

    def _sprite(unit_type: str, team: int) -> pygame.Surface:
        return unit_sprites.get((unit_type, team), unit_sprites[('footman', team % 2)])

    def _sheet(unit_type: str, team: int):
        return war2_sheets.get((unit_type, team))

    # --- Map ---
    game_map = GameMap(WIDTH, HEIGHT)
    fog      = FogOfWar(game_map.grid_w, game_map.grid_h)
    minimap  = Minimap(DEFAULT_MAP)

    # --- Buildings ---
    # Trees: 4×3 clusters at each corner (cols 6-9, rows 0-2 player; cols 30-33, rows 0-2 enemy)
    _trees = [Tree(c * 32, r * 32)
              for c in range(6, 10) for r in range(0, 3)] + \
             [Tree(c * 32, r * 32)
              for c in range(30, 34) for r in range(0, 3)]

    # Building positions are grid-snapped (multiples of 32px) so obstacle cells
    # align cleanly and leave 1-cell gaps for unit navigation.
    buildings: list = [
        TownHall(288,  256, team=0),   # 128×96 → cols 9-12, rows 8-10  (past sidebar)
        Barracks(288,  384, team=0),   # 96×96  → cols 9-11, rows 12-14
        Farm(448,  384, team=0),       # 64×64  → cols 14-15, rows 12-13
        Farm(384,  192, team=0),       # 64×64  → cols 12-13, rows  6-7  (above TownHall)
        TownHall(1088, 256, team=1),   # 128×96 → cols 34-37, rows 8-10
        Barracks(1152, 384, team=1),   # 96×96  → cols 36-38, rows 12-14
        Farm(992,  384, team=1),       # 64×64  → cols 31-32, rows 12-13
        Farm(1088, 384, team=1),       # 64×64  → cols 34-35, rows 12-13
        GoldMine(288,   96),           # 96×96  → cols 9-11, rows 3-5
        GoldMine(1152,  96),           # 96×96  → cols 36-38, rows 3-5
    ] + _trees

    for b in buildings:
        game_map.add_obstacle(b.rect)

    player_hall = next(b for b in buildings if isinstance(b, TownHall) and b.team == 0)

    # --- Units ---
    units: list = [
        Unit(536, 330,  _sprite('footman', 0), team=0, sheet=_sheet('footman', 0)),
        Unit(636, 330,  _sprite('footman', 0), team=0, sheet=_sheet('footman', 0)),
        Worker(436, 360, _sprite('worker',  0), team=0, sheet=_sheet('worker',  0)),
        Unit(1040, 360,  _sprite('footman', 1), team=1, sheet=_sheet('footman', 1)),
        Worker(1200, 380, _sprite('worker',  1), team=1, sheet=_sheet('worker',  1)),
    ]

    corpses: list[Corpse] = []
    projectiles: list[Projectile] = []

    gold: dict[int, int] = {0: 500, 1: 500}
    lumber: dict[int, int] = {0: 0, 1: 0}
    upgrades: dict[int, set] = {0: set(), 1: set()}   # completed research IDs per team
    selected: list = []
    selected_building = None
    drag_start: pygame.Vector2 | None = None
    drag_current: pygame.Vector2 | None = None
    game_over: str | None = None
    elapsed: float = 0.0
    build_mode: str | None = None   # "farm" | "barracks" | None
    build_ghost: tuple[int, int] = (0, 0)

    ai = AIController(
        team=1, buildings=buildings, units=units, gold=gold,
        game_map=game_map,
        enemy_sprite=_sprite('footman', 1),
        worker_sprite=_sprite('worker',  1),
        sheets=war2_sheets,
        difficulty=difficulty,
    )

    while True:
        dt = clock.tick(FPS) / 1000.0

        # ---- Events ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, difficulty
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if build_mode:
                        build_mode = None
                    elif fullscreen:
                        toggle_fullscreen()
                    else:
                        return False, difficulty
                elif event.key == pygame.K_F11:
                    toggle_fullscreen()
                elif event.key == pygame.K_m:
                    _set_mute(not muted)

            if game_over is not None:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    gp = to_game(event.pos)
                    if RESTART_BTN.collidepoint(gp):
                        return True, difficulty
                continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                gp = to_game(event.pos)

                if event.button == 1:
                    if _MUTE_BTN.collidepoint(gp):
                        _set_mute(not muted)
                    elif _FS_BTN.collidepoint(gp):
                        toggle_fullscreen()
                    elif _DIFF_BTN.collidepoint(gp):
                        idx = _DIFF_LEVELS.index(difficulty)
                        difficulty = _DIFF_LEVELS[(idx + 1) % len(_DIFF_LEVELS)]
                        ai._army_threshold = AI_DIFFICULTY[difficulty]["army_threshold"]
                        ai._wave_interval  = AI_DIFFICULTY[difficulty]["wave_interval"]
                    elif BUILD_FARM_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "farm" else "farm"
                        selected = apply_selection(selected, [])
                        if selected_building:
                            selected_building.selected = False
                            selected_building = None
                    elif BUILD_BARRACKS_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "barracks" else "barracks"
                        selected = apply_selection(selected, [])
                        if selected_building:
                            selected_building.selected = False
                            selected_building = None
                    elif BUILD_LUMBERMILL_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "lumbermill" else "lumbermill"
                        selected = apply_selection(selected, [])
                        if selected_building:
                            selected_building.selected = False
                            selected_building = None
                    elif BUILD_BLACKSMITH_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "blacksmith" else "blacksmith"
                        selected = apply_selection(selected, [])
                        if selected_building:
                            selected_building.selected = False
                            selected_building = None
                    elif build_mode and gp[0] >= SIDEBAR_W:
                        _BCLS = {"farm": Farm, "barracks": Barracks,
                                 "lumbermill": LumberMill, "blacksmith": Blacksmith}
                        bcls = _BCLS[build_mode]
                        sx = (gp[0] // CELL_SIZE) * CELL_SIZE
                        sy = (gp[1] // CELL_SIZE) * CELL_SIZE
                        ghost_rect = pygame.Rect(sx, sy, bcls.W, bcls.H)
                        cost_g, cost_l = BUILD_COSTS[build_mode]
                        if (placement_valid(ghost_rect, buildings, game_map)
                                and gold[0] >= cost_g and lumber[0] >= cost_l):
                            new_b = bcls(sx, sy, team=0)
                            new_b.start_construction()
                            buildings.append(new_b)
                            game_map.add_obstacle(new_b.rect)
                            gold[0] -= cost_g
                            lumber[0] -= cost_l
                            # keep build_mode active so player can chain-place
                    elif (selected_building is not None
                            and isinstance(selected_building, TownHall)):
                        food_used, food_cap = food_stats(buildings, units)
                        if TRAIN_BTN.collidepoint(gp) and food_used < food_cap:
                            selected_building.enqueue(gold, "worker")
                        elif gp[0] >= SIDEBAR_W:
                            drag_start = pygame.Vector2(gp)
                            drag_current = pygame.Vector2(gp)
                    elif (selected_building is not None
                            and isinstance(selected_building, Barracks)):
                        food_used, food_cap = food_stats(buildings, units)
                        if TRAIN_BTN.collidepoint(gp) and food_used < food_cap:
                            selected_building.enqueue(gold, "footman")
                        elif TRAIN_ARCHER_BTN.collidepoint(gp) and food_used < food_cap:
                            selected_building.enqueue(gold, "archer")
                        elif (TRAIN_KNIGHT_BTN.collidepoint(gp) and food_used < food_cap
                              and any(isinstance(b, Blacksmith) and b.team == 0
                                      and b.is_complete for b in buildings)):
                            selected_building.enqueue(gold, "knight")
                        elif gp[0] >= SIDEBAR_W:
                            drag_start = pygame.Vector2(gp)
                            drag_current = pygame.Vector2(gp)
                    elif (selected_building is not None
                            and isinstance(selected_building, Blacksmith)):
                        for btn, rid in [
                            (TRAIN_BTN,        "weapons_1"),
                            (TRAIN_ARCHER_BTN,  "armor_1"),
                            (TRAIN_KNIGHT_BTN,  "weapons_2"),
                            (RESEARCH_BTN_4,    "armor_2"),
                        ]:
                            if btn.collidepoint(gp):
                                selected_building.enqueue_research(
                                    gold, lumber, rid, upgrades[0])
                                break
                        else:
                            if gp[0] >= SIDEBAR_W:
                                drag_start = pygame.Vector2(gp)
                                drag_current = pygame.Vector2(gp)
                    elif (selected_building is not None
                            and isinstance(selected_building, LumberMill)):
                        if TRAIN_BTN.collidepoint(gp):
                            selected_building.enqueue_research(
                                gold, lumber, "ranger", upgrades[0])
                        elif gp[0] >= SIDEBAR_W:
                            drag_start = pygame.Vector2(gp)
                            drag_current = pygame.Vector2(gp)
                    elif gp[0] < SIDEBAR_W and selected_building is not None:
                        pass
                    else:
                        drag_start = pygame.Vector2(gp)
                        drag_current = pygame.Vector2(gp)

                elif event.button == 3:
                    if build_mode:
                        build_mode = None
                    elif selected and gp[0] >= SIDEBAR_W:
                        gv = pygame.Vector2(gp)
                        enemy_unit = next((u for u in units if u.team == 1
                                           and u.contains_point(gp)), None)
                        enemy_bldg = next((b for b in buildings if b.team == 1
                                           and b.contains_point(gp)), None)
                        mine = next((b for b in buildings if isinstance(b, GoldMine)
                                      and b.contains_point(gp)), None)
                        tree = next((b for b in buildings if isinstance(b, Tree)
                                      and b.contains_point(gp) and b.hp > 0), None)

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
                        elif tree:
                            movers = []
                            for u in selected:
                                if isinstance(u, Worker):
                                    u.order_chop(tree, player_hall, game_map, buildings)
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

            elif event.type == pygame.MOUSEMOTION:
                gp_m = to_game(event.pos)
                if drag_start is not None:
                    drag_current = pygame.Vector2(gp_m)
                if build_mode:
                    build_ghost = gp_m

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
                    _bc = [b for b in buildings if b.team == 0 and b.contains_point(gp)]
                    bldg = (min(_bc, key=lambda b: (b.pos - pygame.Vector2(gp)).length())
                            if _bc else None)
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

            # Unit separation — push overlapping units apart
            _SEP_DIST = 28.0
            _SEP_STR  = 80.0
            all_units = player_units + enemy_units
            for i in range(len(all_units)):
                u = all_units[i]
                for j in range(i + 1, len(all_units)):
                    v = all_units[j]
                    diff = u.pos - v.pos
                    dist = diff.length()
                    if 0 < dist < _SEP_DIST:
                        push = diff.normalize() * (_SEP_DIST - dist) / _SEP_DIST * _SEP_STR * dt
                        u.pos += push
                        v.pos -= push
                        u.rect.center = (int(u.pos.x), int(u.pos.y))
                        v.rect.center = (int(v.pos.x), int(v.pos.y))

            # Drain archer projectiles
            for u in units:
                if isinstance(u, Archer) and u.projectiles_pending:
                    projectiles.extend(u.projectiles_pending)
                    u.projectiles_pending.clear()

            # Gold + lumber harvesting
            for u in units:
                if isinstance(u, Worker):
                    gold[u.team] += u.gold_delivered
                    u.gold_delivered = 0
                    lumber[u.team] += u.lumber_delivered
                    u.lumber_delivered = 0

            # Construction progress
            for b in buildings:
                b.update_construction(dt)

            def _apply_upgrades(unit: Unit, team: int) -> None:
                """Apply all completed research effects to a newly created unit."""
                for rid in upgrades.get(team, set()):
                    spec = UPGRADES[rid]
                    for ut, stat, delta in spec.effects:
                        if unit.unit_type == ut:
                            setattr(unit, stat, getattr(unit, stat) + delta)
                            if stat == "max_hp":
                                unit.hp = unit.max_hp

            # Research queues (Blacksmith + LumberMill)
            for b in buildings:
                if not isinstance(b, (Blacksmith, LumberMill)):
                    continue
                for rid in b.update(dt):
                    spec = UPGRADES[rid]
                    upgrades[b.team].add(rid)
                    # Apply to all existing units of the affected types
                    for u in units:
                        if u.team != b.team:
                            continue
                        for ut, stat, delta in spec.effects:
                            if u.unit_type == ut:
                                setattr(u, stat, getattr(u, stat) + delta)
                                if stat == "max_hp":
                                    u.hp = min(u.hp + delta, u.max_hp)
                    if b.team == 0:
                        _play('train_done')

            # Training queues (Barracks + TownHall)
            for b in buildings:
                if not isinstance(b, (Barracks, TownHall)):
                    continue
                for unit_type in b.update(dt):
                    sp = pygame.Vector2(b.rect.right + 40, b.rect.centery)
                    new_unit: Unit
                    if unit_type == "worker":
                        new_unit = Worker(sp.x, sp.y, _sprite('worker', b.team), team=b.team,
                                          sheet=_sheet('worker', b.team))
                    elif unit_type == "archer":
                        new_unit = Archer(sp.x, sp.y, _sprite('archer', b.team), team=b.team,
                                          sheet=_sheet('archer', b.team))
                    elif unit_type == "knight":
                        new_unit = Unit(sp.x, sp.y, _sprite('knight', b.team), team=b.team,
                                        unit_type="knight", sheet=_sheet('knight', b.team))
                    else:
                        new_unit = Unit(sp.x, sp.y, _sprite('footman', b.team), team=b.team,
                                        sheet=_sheet('footman', b.team))
                    _apply_upgrades(new_unit, b.team)
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

            for b in buildings:
                if isinstance(b, Tree) and not b.is_alive():
                    game_map.remove_obstacle(b.rect)
            buildings = [b for b in buildings if b.is_alive()]
            if selected_building is not None and not selected_building.is_alive():
                selected_building.selected = False
                selected_building = None

            player_bldgs = [b for b in buildings if b.team == 0]
            fog.update(player_units + player_bldgs)

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

        # Ghost building outline in build mode (drawn above units, below fog)
        if build_mode:
            _GDIMS = {"farm": (Farm.W, Farm.H), "barracks": (Barracks.W, Barracks.H),
                      "lumbermill": (LumberMill.W, LumberMill.H),
                      "blacksmith": (Blacksmith.W, Blacksmith.H)}
            bw, bh = _GDIMS.get(build_mode, (Farm.W, Farm.H))
            sx = (build_ghost[0] // CELL_SIZE) * CELL_SIZE
            sy = (build_ghost[1] // CELL_SIZE) * CELL_SIZE
            ghost_rect = pygame.Rect(sx, sy, bw, bh)
            cost_g, cost_l = BUILD_COSTS[build_mode]
            can_place = (placement_valid(ghost_rect, buildings, game_map)
                         and gold[0] >= cost_g and lumber[0] >= cost_l)
            fill_col = (0, 200, 0, 70) if can_place else (200, 40, 40, 70)
            line_col  = (0, 255, 0)    if can_place else (255, 60, 60)
            ghost_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            ghost_surf.fill(fill_col)
            canvas.blit(ghost_surf, ghost_rect)
            pygame.draw.rect(canvas, line_col, ghost_rect, 2)

        # Fog overlay — drawn BEFORE the drag box so the selection box is always visible
        fog.draw(canvas)

        # Drag selection box (drawn on top of fog so it's always readable)
        if drag_start is not None and drag_current is not None:
            delta = drag_current - drag_start
            if delta.length() > 4:
                rx = int(min(drag_start.x, drag_current.x))
                ry = int(min(drag_start.y, drag_current.y))
                rw = int(abs(delta.x))
                rh = int(abs(delta.y))
                if rw > 0 and rh > 0:
                    sel_surf = pygame.Surface((rw, rh), pygame.SRCALPHA)
                    sel_surf.fill((0, 255, 0, 40))
                    canvas.blit(sel_surf, (rx, ry))
                    pygame.draw.rect(canvas, (0, 255, 0), (rx, ry, rw, rh), 1)

        minimap.draw(canvas, buildings, units, dest_xy=(_MINI_SB_X, _MINI_SB_Y))
        draw_hud(canvas, font, gold, lumber, buildings, units, selected, selected_building,
                 ai.state, muted, fullscreen, build_mode=build_mode, difficulty=difficulty,
                 mouse_pos=to_game(pygame.mouse.get_pos()),
                 team_upgrades=upgrades[0])

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

    difficulty = "normal"
    while True:
        restart, difficulty = run_game(screen, clock, font, big_font, difficulty=difficulty)
        if not restart:
            break

    pygame.quit()


if __name__ == "__main__":
    main()
