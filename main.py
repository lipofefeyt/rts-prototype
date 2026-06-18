import math
import pygame
from unit import Unit, Worker, Archer
from map import GameMap, DEFAULT_MAP, generate_map, find_base_area
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
DEFAULT_SEED = 4874   # curated map: centred river, fords at rows 13+48, wide chokepoints
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
GATHER_BTN           = _CMDS[4]   # Worker: gather nearest resource (row 2, col 0)
_QUEUE_SB_Y  = _CMD_SB_Y0 + 2 * _CMD_SB_DY + 6   # = 358  (queue dots below command grid)

# Idle-worker badge — right end of the resource row; click cycles to next idle worker.
_IDLE_W_BTN = pygame.Rect(172, 0, 44, 20)

RESTART_BTN  = pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 + 50, 160, 40)
_MUTE_BTN    = pygame.Rect(4,   HEIGHT - 48, 60, 20)
_FS_BTN      = pygame.Rect(68,  HEIGHT - 48, 60, 20)
_DIFF_BTN    = pygame.Rect(132, HEIGHT - 48, 82, 20)
_TECH_BTN    = pygame.Rect(4,   HEIGHT - 24, 214, 20)
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
_thumbnails_sheet: "pygame.Surface | None" = None

# WC2 icon IDs from pud.h (position = icon_id in the 10-col sheet)
_ICON = {
    # units
    "worker": 0, "footman": 2, "archer": 4, "knight": 8,
    # buildings
    "TownHall": 40, "Farm": 38, "Barracks": 42, "LumberMill": 44, "Blacksmith": 46,
    # actions
    "cancel": 91, "collect": 86, "repair": 85, "move": 83, "return": 89,
    # upgrades
    "weapons_1": 116, "weapons_2": 117,
    "armor_1":   164, "armor_2":   165,
    "ranger":    132,
}


def _get_icon(icon_id: int, size: "tuple[int,int]" = (36, 36)) -> "pygame.Surface | None":
    """Return a scaled Surface for the given WC2 icon ID, or None if sheet not loaded."""
    if _thumbnails_sheet is None:
        return None
    col, row = icon_id % 10, icon_id // 10
    try:
        raw = _thumbnails_sheet.subsurface(pygame.Rect(col * 50 + 2, row * 39, 46, 38))
        if size == (46, 38):
            return raw.copy()
        return pygame.transform.smoothscale(raw, size)
    except (ValueError, pygame.error):
        return None

_BUILD_TOOLTIP = {
    "farm":       ("Farm",         "250g  100w",  "+4 food"),
    "barracks":   ("Barracks",     "500g  200w",  "Trains: Footman, Archer"),
    "lumbermill": ("Lumber Mill",  "600g  150w",  "Worker lumber bonus"),
    "blacksmith": ("Blacksmith",   "800g  150w",  "Unlocks: Knight"),
}


def _make_build_thumbs() -> "dict[str, pygame.Surface]":
    """Create 46×38 thumbnails for build menu buttons using WC2 icons."""
    thumbs: dict = {}
    # Primary: WC2 thumbnail sheet icons (exact pixel art from the game)
    for btype, icon_id in (("farm", 38), ("barracks", 42), ("lumbermill", 44), ("blacksmith", 46)):
        icon = _get_icon(icon_id, (46, 38))
        if icon:
            thumbs[btype] = icon
    # Fallback: scale building sprite sheet thumbnails
    if len(thumbs) < 4:
        from building import _SPRITES as _bsprites
        for btype, stem in (("farm", "farm_team0"), ("barracks", "barracks_team0"),
                            ("lumbermill", "lumbermill_team0"), ("blacksmith", "blacksmith_team0")):
            if btype not in thumbs:
                spr = _bsprites.get(stem)
                if spr:
                    thumbs[btype] = pygame.transform.smoothscale(spr, (46, 38))
    return thumbs


def _worker_gather(worker, buildings: list, game_map, player_hall) -> bool:
    """Send a worker to the nearest available resource (mine first, then tree).
    Returns True if an assignment was made."""
    from building import GoldMine, Tree as _Tree
    mines = [b for b in buildings if isinstance(b, GoldMine) and b.gold > 0]
    trees = [b for b in buildings if isinstance(b, _Tree) and b.hp > 0]
    if mines:
        mine = min(mines, key=lambda m: (m.pos - worker.pos).length())
        worker.order_harvest(mine, player_hall, game_map)
        return True
    if trees:
        tree = min(trees, key=lambda t: (t.pos - worker.pos).length())
        worker.order_chop(tree, player_hall, game_map, buildings)
        return True
    return False


# Unit portrait thumbnails for training buttons — populated by init_ui_thumbs().
_unit_thumbs: dict[str, pygame.Surface] = {}


def init_ui_thumbs(sheets: dict) -> None:
    """Pre-bake unit portrait icons for training buttons.
    Uses WC2 thumbnail sheet icons first; falls back to front-facing walk frame."""
    _unit_thumbs.clear()
    for ut, icon_id in (("worker", 0), ("footman", 2), ("archer", 4), ("knight", 8)):
        icon = _get_icon(icon_id, (46, 38))
        if icon:
            _unit_thumbs[ut] = icon
    # Fallback for any unit not covered above
    for (ut, team), sheet in sheets.items():
        if team != 0 or ut in _unit_thumbs:
            continue
        frame = sheet.walk_frame(4, 0)
        _unit_thumbs[ut] = pygame.transform.smoothscale(frame, (46, 38))


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
        # Icons are 46×38; buttons are 46×46 — blit flush left, 4px from top
        canvas.blit(t, (btn.x, btn.y + 4))
        if locked:
            tc = (80, 75, 85)
            canvas.blit(font.render("LOCK", True, tc), (btn.x + 2, btn.y + 38))
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
    map_w = game_map.grid_w * CELL_SIZE
    map_h = game_map.grid_h * CELL_SIZE
    if rect.left < 0 or rect.top < 0 or rect.right > map_w or rect.bottom > map_h:
        return False
    col0 = rect.left // CELL_SIZE
    row0 = rect.top // CELL_SIZE
    col1 = (rect.right + CELL_SIZE - 1) // CELL_SIZE
    row1 = (rect.bottom + CELL_SIZE - 1) // CELL_SIZE
    for c in range(col0, col1):
        for r in range(row0, row1):
            if (c, r) in game_map.blocked:
                return False
    return not any(rect.colliderect(b.rect) for b in buildings)


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


def draw_tech_tree(canvas: pygame.Surface, font: pygame.font.Font, big_font: pygame.font.Font,
                   buildings: list, team_upgrades: set) -> None:
    """Draw the full-screen tech tree overlay (activated by T key)."""
    # Semi-transparent backdrop
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    canvas.blit(overlay, (0, 0))

    PW, PH = 740, 420
    PX = (WIDTH - PW) // 2
    PY = (HEIGHT - PH) // 2
    panel = pygame.Surface((PW, PH))
    panel.fill((14, 16, 28))
    pygame.draw.rect(panel, (70, 80, 130), panel.get_rect(), 2)

    # Title bar
    pygame.draw.rect(panel, (22, 26, 48), (0, 0, PW, 32))
    t = big_font.render("TECH TREE", True, (190, 210, 255))
    panel.blit(t, (PW // 2 - t.get_width() // 2, 4))
    hint = font.render("[T] or [ESC] close", True, (90, 100, 130))
    panel.blit(hint, (PW - hint.get_width() - 8, 10))

    # Helper: is building built by team 0 and complete?
    def built(label: str) -> bool:
        return any(b.label == label and b.team == 0 and b.is_complete for b in buildings)

    # Helper: draw a single tech node (icon + name + status ring)
    NW, NH = 62, 58
    def draw_node(nx: int, ny: int, icon_id: int, label: str,
                  locked: bool = False, done: bool = False,
                  active: bool = False) -> None:
        if done:
            bg, bd = (22, 46, 22), (55, 120, 55)
        elif locked:
            bg, bd = (22, 20, 30), (50, 48, 68)
        elif active:
            bg, bd = (42, 55, 22), (100, 140, 55)
        else:
            bg, bd = (25, 28, 48), (65, 72, 115)
        pygame.draw.rect(panel, bg, (nx, ny, NW, NH))
        pygame.draw.rect(panel, bd, (nx, ny, NW, NH), 1)
        icon = _get_icon(icon_id, (46, 38))
        if icon:
            if locked:
                icon.set_alpha(80)
            panel.blit(icon, (nx + (NW - 46) // 2, ny + 2))
        lbl = font.render(label, True, (90, 95, 130) if locked else (185, 195, 225))
        panel.blit(lbl, (nx + NW // 2 - lbl.get_width() // 2, ny + 42))

    # Helper: horizontal connector line
    def hline(x0: int, y0: int, x1: int) -> None:
        pygame.draw.line(panel, (65, 75, 110), (x0, y0), (x1, y0), 1)

    def vline(x0: int, y0: int, y1: int) -> None:
        pygame.draw.line(panel, (65, 75, 110), (x0, y0), (x0, y1), 1)

    # --- Row 0: TownHall → Farm ---
    R0Y = 44
    TH_X, TH_Y   = 28,  R0Y
    FARM_X        = 148

    hline(TH_X + NW, TH_Y + NH // 2, FARM_X)
    draw_node(TH_X, TH_Y, 40, "TownHall", done=built("Town Hall"), active=True)
    draw_node(FARM_X, TH_Y, 38, "Farm",
              done=built("Farm"), locked=not built("Town Hall"))

    # --- Row 1: Barracks → LumberMill → Blacksmith ---
    R1Y = R0Y + NH + 36
    BARR_X  = 28
    LMILL_X = 200
    SMITH_X = 380

    vline(TH_X + NW // 2, TH_Y + NH, R1Y)
    hline(TH_X + NW // 2, R1Y, BARR_X + NW // 2)
    hline(BARR_X + NW, R1Y + NH // 2, LMILL_X)
    hline(LMILL_X + NW, R1Y + NH // 2, SMITH_X)

    barr_built = built("Barracks")
    lmill_built = built("Lumber Mill")
    smith_built = built("Blacksmith")
    draw_node(BARR_X,  R1Y, 42, "Barracks",   done=barr_built,  locked=not built("Town Hall"))
    draw_node(LMILL_X, R1Y, 44, "LumberMill", done=lmill_built, locked=not barr_built)
    draw_node(SMITH_X, R1Y, 46, "Blacksmith", done=smith_built, locked=not lmill_built)

    # Upgrade mini-icons beside Blacksmith (right column)
    UX = SMITH_X + NW + 12
    for ui, (rid, icon_id, row_off) in enumerate((
        ("weapons_1", 116, 0), ("weapons_2", 117, 0),
        ("armor_1",   164, 1), ("armor_2",   165, 1),
    )):
        col_off = ui % 2
        ux = UX + col_off * 48
        uy = R1Y + row_off * 38
        done_upg = rid in team_upgrades
        locked_upg = not smith_built
        bg = (22, 46, 22) if done_upg else ((22, 20, 30) if locked_upg else (25, 28, 48))
        bd = (55, 120, 55) if done_upg else ((50, 48, 68) if locked_upg else (65, 72, 115))
        pygame.draw.rect(panel, bg, (ux, uy, 44, 34))
        pygame.draw.rect(panel, bd, (ux, uy, 44, 34), 1)
        ico = _get_icon(icon_id, (44, 30))
        if ico:
            if locked_upg:
                ico.set_alpha(70)
            panel.blit(ico, (ux, uy + 2))

    # Ranger upgrade beside LumberMill
    RNG_X = LMILL_X + NW + 8
    RNG_Y = R1Y + NH // 2 - 17
    rng_done = "ranger" in team_upgrades
    rng_locked = not lmill_built
    pygame.draw.rect(panel, (22, 46, 22) if rng_done else ((22,20,30) if rng_locked else (25,28,48)),
                     (RNG_X, RNG_Y, 44, 34))
    pygame.draw.rect(panel, (55,120,55) if rng_done else ((50,48,68) if rng_locked else (65,72,115)),
                     (RNG_X, RNG_Y, 44, 34), 1)
    rng_ico = _get_icon(132, (44, 30))
    if rng_ico:
        if rng_locked:
            rng_ico.set_alpha(70)
        panel.blit(rng_ico, (RNG_X, RNG_Y + 2))

    # --- Row 2: units trained at Barracks ---
    R2Y = R1Y + NH + 36
    FOOT_X  = 28
    ARCH_X  = 148
    KNIG_X  = 268

    vline(BARR_X + NW // 2, R1Y + NH, R2Y)
    hline(BARR_X + NW // 2, R2Y, KNIG_X + NW // 2)

    draw_node(FOOT_X, R2Y, 2, "Footman", done=False, locked=not barr_built)
    draw_node(ARCH_X, R2Y, 4, "Archer",  done=False, locked=not barr_built)
    draw_node(KNIG_X, R2Y, 8, "Knight",  done=False, locked=not smith_built)

    # Blacksmith required note for Knight
    if not smith_built:
        req = font.render("needs Smith", True, (130, 80, 80))
        panel.blit(req, (KNIG_X + NW // 2 - req.get_width() // 2, R2Y + NH + 2))

    # --- Legend (bottom strip) ---
    LEG_Y = PH - 22
    pygame.draw.line(panel, (45, 50, 80), (12, LEG_Y - 4), (PW - 12, LEG_Y - 4), 1)
    for col, (lbl, bg, bd) in enumerate((
        ("Built",     (22, 46, 22),  (55, 120, 55)),
        ("Available", (25, 28, 48),  (65, 72, 115)),
        ("Locked",    (22, 20, 30),  (50, 48, 68)),
    )):
        lx = 28 + col * 220
        pygame.draw.rect(panel, bg, (lx, LEG_Y, 12, 12))
        pygame.draw.rect(panel, bd, (lx, LEG_Y, 12, 12), 1)
        panel.blit(font.render(lbl, True, (140, 145, 175)), (lx + 16, LEG_Y))

    canvas.blit(panel, (PX, PY))


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

    # ---- Sidebar background ----
    pygame.draw.rect(canvas, (18, 20, 30), (0, 0, SIDEBAR_W, HEIGHT))
    # Header strip (resource row)
    pygame.draw.rect(canvas, (24, 27, 40), (0, 0, SIDEBAR_W, 22))
    # Right border: shadow + highlight lines for a slight panel-edge look
    pygame.draw.line(canvas, (8, 9, 14),   (SIDEBAR_W - 2, 0), (SIDEBAR_W - 2, HEIGHT))
    pygame.draw.line(canvas, (80, 85, 120), (SIDEBAR_W - 1, 0), (SIDEBAR_W - 1, HEIGHT))

    # ---- Resources row (top of sidebar) ----
    food_used, food_cap = food_stats(buildings, units)
    # Small colored icon squares beside each resource value
    _rx = _MINI_SB_X
    pygame.draw.rect(canvas, (220, 180, 0), (_rx, 7, 7, 7))
    canvas.blit(font.render(str(gold[0]),             True, (255, 215, 0)),    (_rx + 10, 4))
    _rx += 66
    pygame.draw.rect(canvas, (80, 160, 50), (_rx, 7, 7, 7))
    canvas.blit(font.render(str(lumber[0]),           True, (120, 200, 80)),   (_rx + 10, 4))
    _rx += 62
    pygame.draw.rect(canvas, (150, 200, 150), (_rx, 7, 7, 7))
    canvas.blit(font.render(f"{food_used}/{food_cap}", True, (200, 230, 200)), (_rx + 10, 4))

    # Idle worker badge — flashes when any team-0 worker is idle
    idle_workers = [u for u in units
                    if hasattr(u, '_wstate') and u._wstate == "idle" and u.team == 0]
    if idle_workers:
        flash = int(pygame.time.get_ticks() / 450) % 2
        badge_col = (255, 160, 0) if flash else (180, 100, 0)
        pygame.draw.rect(canvas, (40, 30, 10), _IDLE_W_BTN)
        pygame.draw.rect(canvas, badge_col, _IDLE_W_BTN, 1)
        canvas.blit(font.render(f"W:{len(idle_workers)}", True, badge_col),
                    (_IDLE_W_BTN.x + 3, _IDLE_W_BTN.y + 2))

    # ---- Section dividers: double-line for a subtle recessed look ----
    for dy in (_SB_DIV1_Y, _SB_DIV2_Y):
        pygame.draw.line(canvas, (10, 11, 18),  (4, dy),     (SIDEBAR_W - 6, dy))
        pygame.draw.line(canvas, (60, 65, 90),  (4, dy + 1), (SIDEBAR_W - 6, dy + 1))

    # Minimap panel border
    mini_rect = pygame.Rect(_MINI_SB_X - 2, _MINI_SB_Y - 2, 204, 114)
    pygame.draw.rect(canvas, (10, 11, 18),  mini_rect, 2)
    pygame.draw.rect(canvas, (55, 60, 85),  mini_rect.inflate(-2, -2), 1)

    # Command area background panel
    _cmd_area = pygame.Rect(2, _SB_DIV2_Y + 2, SIDEBAR_W - 4, 120)
    pygame.draw.rect(canvas, (20, 22, 34), _cmd_area)
    pygame.draw.rect(canvas, (42, 46, 68), _cmd_area, 1)

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
                canvas.blit(thumb, (btn.x, btn.y + 4))
            else:
                canvas.blit(font.render(blabel[:6], True, tc), (btn.x + 2, btn.y + 14))
            if btn.collidepoint(mouse_pos):
                _hovered_build = (btn, btype, can_buy)
        if _hovered_build:
            _draw_build_tooltip(canvas, font, *_hovered_build)

        # Gather button (slot 4) — shown when at least one selected worker is idle
        idle_sel = [u for u in selected if hasattr(u, '_wstate') and u._wstate == "idle"]
        if idle_sel and not build_mode:
            bg = (30, 65, 30)
            bd = (60, 130, 60)
            pygame.draw.rect(canvas, bg, GATHER_BTN)
            pygame.draw.rect(canvas, bd, GATHER_BTN, 1)
            gather_icon = _get_icon(_ICON["collect"], (46, 38))
            if gather_icon:
                canvas.blit(gather_icon, (GATHER_BTN.x, GATHER_BTN.y + 4))
            else:
                canvas.blit(font.render("Gath", True, (140, 220, 140)),
                            (GATHER_BTN.x + 2, GATHER_BTN.y + 14))
            if GATHER_BTN.collidepoint(mouse_pos):
                _draw_info_tooltip(canvas, font, GATHER_BTN, [
                    ("Gather", (200, 240, 200)),
                    ("Send to nearest resource", (140, 180, 140)),
                ])

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
        if isinstance(selected_building, GoldMine):
            gold_left = selected_building.gold
            pct = gold_left / 5000
            bar_w = SIDEBAR_W - 2 * _MINI_SB_X
            col_g = (255, 215, 0) if gold_left > 1000 else (200, 150, 0) if gold_left > 0 else (100, 100, 100)
            canvas.blit(font.render(f"Gold: {gold_left}", True, col_g), (_MINI_SB_X, _SB_INFO_Y0 + 36))
            pygame.draw.rect(canvas, (50, 50, 30), (_MINI_SB_X, _SB_INFO_Y0 + 52, bar_w, 6))
            pygame.draw.rect(canvas, col_g,        (_MINI_SB_X, _SB_INFO_Y0 + 52, int(bar_w * max(0, pct)), 6))
            if selected_building.workers_inside:
                canvas.blit(font.render(f"Miners inside: {selected_building.workers_inside}",
                                        True, (180, 220, 140)), (_MINI_SB_X, _SB_INFO_Y0 + 62))
        else:
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
                    # Upgrade icon from WC2 thumbnail sheet
                    upg_icon = _get_icon(_ICON.get(rid, 0), (46, 28))
                    if upg_icon:
                        alpha = 60 if not prereq_met else (180 if done else 255)
                        upg_icon.set_alpha(alpha)
                        canvas.blit(upg_icon, (btn.x, btn.y + 2))
                    canvas.blit(font.render(sub, True, tc), (btn.x + 2, btn.y + 32))
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
                ranger_icon = _get_icon(_ICON["ranger"], (46, 28))
                if ranger_icon:
                    ranger_icon.set_alpha(60 if done else 255)
                    canvas.blit(ranger_icon, (TRAIN_BTN.x, TRAIN_BTN.y + 2))
                canvas.blit(font.render(sub, True, tc), (TRAIN_BTN.x + 2, TRAIN_BTN.y + 32))
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

    # ---- Tech tree button (full-width at sidebar bottom) ----
    pygame.draw.rect(canvas, (28, 32, 56), _TECH_BTN)
    pygame.draw.rect(canvas, (65, 72, 115), _TECH_BTN, 1)
    tt_lbl = font.render("[T]  Tech Tree", True, (150, 165, 220))
    canvas.blit(tt_lbl, (_TECH_BTN.x + _TECH_BTN.width // 2 - tt_lbl.get_width() // 2,
                         _TECH_BTN.y + 2))

    # ---- AI state badge ----
    if ai_state:
        label = f"Enemy: {ai_state.upper()}"
        color = (255, 80, 80) if ai_state == "attack" else (160, 160, 180)
        canvas.blit(font.render(label, True, color), (_MINI_SB_X, HEIGHT - 72))


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
             difficulty: str = "normal",
             map_seed: "int | None" = None) -> "tuple[bool, str, int | None]":
    """Play one match. Returns (restart, difficulty, next_seed)."""
    import random as _rand

    # Internal render canvas — all game drawing goes here at a fixed 1280×720.
    # At frame end it's scaled to whatever the display surface is.
    canvas = pygame.Surface((WIDTH, HEIGHT))
    fullscreen = False

    def to_game(pos: tuple) -> tuple[int, int]:
        """Translate physical mouse coords → canvas coords."""
        sw, sh = screen.get_size()
        if sw == WIDTH and sh == HEIGHT:
            return (int(pos[0]), int(pos[1]))
        return (int(pos[0] * WIDTH / sw), int(pos[1] * HEIGHT / sh))

    def to_world(pos: tuple) -> tuple[int, int]:
        """Translate physical mouse coords → world (map) coords.
        The game viewport occupies canvas x=[SIDEBAR_W, WIDTH], so subtract the sidebar offset."""
        gp = to_game(pos)
        return (gp[0] - SIDEBAR_W + cam_ix, gp[1] + cam_iy)

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
    global _thumbnails_sheet
    try:
        _thumbnails_sheet = pygame.image.load(
            "assets/sprites/thumbnails/thumbnails.png").convert_alpha()
    except (FileNotFoundError, pygame.error):
        _thumbnails_sheet = None
    init_ui_thumbs(war2_sheets)

    def _sprite(unit_type: str, team: int) -> pygame.Surface:
        return unit_sprites.get((unit_type, team), unit_sprites[('footman', team % 2)])

    def _sheet(unit_type: str, team: int):
        return war2_sheets.get((unit_type, team))

    # --- Map ---
    the_seed  = map_seed if map_seed is not None else _rand.randint(0, 0xFFFF)
    tile_map  = generate_map(64, 64, seed=the_seed)
    minimap   = Minimap(tile_map)   # bake minimap before conversion so forest shows dark-green

    # Convert all non-border 'T' cells → 'G' and build Tree objects for each.
    # Bitmasks are computed before conversion so all 'T' neighbors are still visible.
    _fm_rows = len(tile_map)
    _fm_cols = len(tile_map[0]) if tile_map else 64
    _forest_cells: list[tuple[int, int]] = [
        (_c, _r)
        for _r in range(_fm_rows)
        for _c in range(_fm_cols)
        if tile_map[_r][_c] == 'T'
    ]

    def _tmask(c: int, r: int) -> int:
        mask = 0
        for bit, dc, dr in ((1, 0, -1), (2, 1, 0), (4, 0, 1), (8, -1, 0)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < _fm_rows and 0 <= nc < _fm_cols):
                mask |= bit
            elif tile_map[nr][nc] == 'T':
                mask |= bit
        return mask

    _forest_bitmasks = {(c, r): _tmask(c, r) for c, r in _forest_cells}
    for _r in range(_fm_rows):
        if 'T' not in tile_map[_r]:
            continue
        tile_map[_r] = tile_map[_r].replace('T', 'G')
    _forest_trees = [
        Tree(_c * CELL_SIZE, _r * CELL_SIZE, bitmask=_forest_bitmasks[(_c, _r)])
        for _c, _r in _forest_cells
    ]

    game_map  = GameMap(tile_map)
    fog       = FogOfWar(game_map.grid_w, game_map.grid_h)
    map_px_w  = game_map.grid_w * CELL_SIZE
    map_px_h  = game_map.grid_h * CELL_SIZE

    # Camera
    cam    = pygame.Vector2(0, 0)
    cam_ix = cam_iy = 0   # integer snapshots updated each frame
    SCROLL_SPEED = 500     # world-pixels per second
    SCROLL_EDGE  = 20      # px from canvas edge that triggers scroll

    # World surface — all game objects draw here; we blit a viewport to canvas
    world_surf = pygame.Surface((map_px_w, map_px_h))

    # Move-order click marker: (world_x, world_y, life_remaining_s) or None
    _move_marker: "tuple | None" = None

    # --- Buildings ---
    # Find clear base areas and lay out buildings relative to them
    pc, pr = find_base_area(tile_map, 'left',  min_clear=12)
    ec, er = find_base_area(tile_map, 'right', min_clear=12)

    def _snap(v: int) -> int:
        return (v // CELL_SIZE) * CELL_SIZE

    # Player base layout (all positions grid-snapped)
    px, py = pc * CELL_SIZE, pr * CELL_SIZE
    p_hall_x = _snap(px)
    p_hall_y = _snap(py + 4 * CELL_SIZE)   # 4 rows below base edge so mine has visual gap
    # GoldMine: 3×3 cells, placed above TownHall with 3-row gap so peasant is visible
    p_mine_x  = _snap(p_hall_x)
    p_mine_y  = _snap(p_hall_y - GoldMine.H - 3 * CELL_SIZE)

    # Enemy base layout (mirror: halls open toward river, i.e. toward left)
    ex_right = (ec + 12) * CELL_SIZE   # rightmost column of enemy clear area
    e_hall_x  = _snap(ex_right - TownHall.W - CELL_SIZE)
    e_hall_y  = _snap(er * CELL_SIZE + 4 * CELL_SIZE)
    e_mine_x  = _snap(e_hall_x + TownHall.W // 2)
    e_mine_y  = _snap(e_hall_y - GoldMine.H - 3 * CELL_SIZE)

    _fixed_bldgs: list = [
        TownHall(p_hall_x, p_hall_y, team=0),
        Barracks(p_hall_x, p_hall_y + TownHall.H + 3 * CELL_SIZE, team=0),
        Farm(p_hall_x + TownHall.W + 3 * CELL_SIZE, p_hall_y, team=0),
        Farm(p_hall_x + TownHall.W + 3 * CELL_SIZE, p_hall_y + Farm.H + 2 * CELL_SIZE, team=0),
        TownHall(e_hall_x, e_hall_y, team=1),
        Barracks(e_hall_x, e_hall_y + TownHall.H + 3 * CELL_SIZE, team=1),
        Farm(e_hall_x - Farm.W - 3 * CELL_SIZE, e_hall_y, team=1),
        Farm(e_hall_x - Farm.W - 3 * CELL_SIZE, e_hall_y + Farm.H + 2 * CELL_SIZE, team=1),
        GoldMine(p_mine_x, p_mine_y),
        GoldMine(e_mine_x, e_mine_y),
    ]
    _forest_trees = [t for t in _forest_trees
                     if not any(t.rect.colliderect(b.rect) for b in _fixed_bldgs)]
    buildings: list = _fixed_bldgs + _forest_trees

    for b in buildings:
        game_map.add_obstacle(b.rect)

    player_hall = next(b for b in buildings if isinstance(b, TownHall) and b.team == 0)

    # Start camera centered on the player's TownHall
    cam.x = max(0, min(map_px_w - WIDTH,  player_hall.rect.centerx - WIDTH  // 2))
    cam.y = max(0, min(map_px_h - HEIGHT, player_hall.rect.centery - HEIGHT // 2))

    # --- Units — spawned adjacent to their TownHall ---
    def _spawn_near(hall, dx, dy, utype, team):
        x = _snap(hall.rect.right + dx)
        y = _snap(hall.rect.top   + dy)
        return x, y

    ph = player_hall
    eh = next(b for b in buildings if isinstance(b, TownHall) and b.team == 1)

    # Spawn in the 3-cell gap between TownHall and Farm (not on the farm).
    _p_sx = ph.rect.right + CELL_SIZE
    _e_sx = eh.rect.left  - CELL_SIZE
    units: list = [
        Unit(_p_sx, ph.rect.centery - 16,
             _sprite('footman', 0), team=0, sheet=_sheet('footman', 0)),
        Unit(_p_sx, ph.rect.centery + 16,
             _sprite('footman', 0), team=0, sheet=_sheet('footman', 0)),
        Worker(_p_sx, ph.rect.centery + 48,
               _sprite('worker', 0), team=0, sheet=_sheet('worker', 0)),
        Unit(_e_sx, eh.rect.centery - 16,
             _sprite('footman', 1), team=1, sheet=_sheet('footman', 1)),
        Worker(_e_sx, eh.rect.centery + 32,
               _sprite('worker', 1), team=1, sheet=_sheet('worker', 1)),
    ]

    corpses: list[Corpse] = []
    projectiles: list[Projectile] = []

    gold: dict[int, int] = {0: 500, 1: 500}
    lumber: dict[int, int] = {0: 200, 1: 200}
    upgrades: dict[int, set] = {0: set(), 1: set()}   # completed research IDs per team
    selected: list = []
    selected_building = None
    drag_start: pygame.Vector2 | None = None
    drag_current: pygame.Vector2 | None = None
    game_over: str | None = None
    elapsed: float = 0.0
    build_mode: str | None = None   # "farm" | "barracks" | None
    tech_tree_open: bool = False
    build_ghost: tuple[int, int] = (0, 0)

    ai = AIController(
        team=1, buildings=buildings, units=units, gold=gold, lumber=lumber,
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
                return False, difficulty, None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if tech_tree_open:
                        tech_tree_open = False
                    elif build_mode:
                        build_mode = None
                    elif fullscreen:
                        toggle_fullscreen()
                    else:
                        return False, difficulty, None
                elif event.key == pygame.K_F11:
                    toggle_fullscreen()
                elif event.key == pygame.K_m:
                    _set_mute(not muted)
                elif event.key == pygame.K_t:
                    tech_tree_open = not tech_tree_open
                elif event.key == pygame.K_e:
                    from map import VALID_ERAS
                    idx = VALID_ERAS.index(game_map._era) if game_map._era in VALID_ERAS else 0
                    game_map.set_era(VALID_ERAS[(idx + 1) % len(VALID_ERAS)])

            if game_over is not None:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    gp = to_game(event.pos)
                    if RESTART_BTN.collidepoint(gp):
                        return True, difficulty, the_seed
                continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                gp = to_game(event.pos)    # canvas coords — for sidebar UI
                wp = to_world(event.pos)   # world coords  — for map interactions

                if event.button == 1:
                    # Minimap click → jump camera to that world location
                    if minimap.rect and minimap.rect.collidepoint(gp):
                        mx = gp[0] - minimap.rect.x
                        my = gp[1] - minimap.rect.y
                        cx, cy = minimap.world_to_cam(mx, my,
                                                      WIDTH - SIDEBAR_W, HEIGHT,
                                                      map_px_w, map_px_h)
                        cam.x, cam.y = cx, cy
                        cam_ix, cam_iy = int(cam.x), int(cam.y)
                    elif _IDLE_W_BTN.collidepoint(gp):
                        # Cycle to next idle worker
                        idle = [u for u in units
                                if isinstance(u, Worker) and u.team == 0 and u._wstate == "idle"]
                        if idle:
                            selected = apply_selection(selected, [idle[0]])
                            if selected_building:
                                selected_building.selected = False
                                selected_building = None
                    elif _TECH_BTN.collidepoint(gp):
                        tech_tree_open = not tech_tree_open
                    elif _MUTE_BTN.collidepoint(gp):
                        _set_mute(not muted)
                    elif _FS_BTN.collidepoint(gp):
                        toggle_fullscreen()
                    elif _DIFF_BTN.collidepoint(gp):
                        idx = _DIFF_LEVELS.index(difficulty)
                        difficulty = _DIFF_LEVELS[(idx + 1) % len(_DIFF_LEVELS)]
                        ai._army_threshold = AI_DIFFICULTY[difficulty]["army_threshold"]
                        ai._wave_interval  = AI_DIFFICULTY[difficulty]["wave_interval"]
                    # Building placement must be checked before building-selected branches
                    # so a viewport click always places when build_mode is active.
                    elif build_mode and gp[0] >= SIDEBAR_W:
                        _BCLS = {"farm": Farm, "barracks": Barracks,
                                 "lumbermill": LumberMill, "blacksmith": Blacksmith}
                        bcls = _BCLS[build_mode]
                        sx = (wp[0] // CELL_SIZE) * CELL_SIZE
                        sy = (wp[1] // CELL_SIZE) * CELL_SIZE
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
                    # Building-selected branches come next — these share button slots with
                    # the worker build menu (BUILD_FARM_BTN == TRAIN_BTN == _CMDS[0]).
                    # They MUST be checked before the BUILD_* branches below.
                    elif (selected_building is not None
                            and isinstance(selected_building, TownHall)):
                        food_used, food_cap = food_stats(buildings, units)
                        if TRAIN_BTN.collidepoint(gp) and food_used < food_cap:
                            if selected_building.enqueue(gold, "worker", buildings):
                                _play("train_start")
                        elif gp[0] >= SIDEBAR_W:
                            drag_start = pygame.Vector2(gp)
                            drag_current = pygame.Vector2(gp)
                    elif (selected_building is not None
                            and isinstance(selected_building, Barracks)):
                        food_used, food_cap = food_stats(buildings, units)
                        if TRAIN_BTN.collidepoint(gp) and food_used < food_cap:
                            if selected_building.enqueue(gold, "footman", buildings):
                                _play("train_start")
                        elif TRAIN_ARCHER_BTN.collidepoint(gp) and food_used < food_cap:
                            if selected_building.enqueue(gold, "archer", buildings):
                                _play("train_start")
                        elif (TRAIN_KNIGHT_BTN.collidepoint(gp) and food_used < food_cap
                              and any(isinstance(b, Blacksmith) and b.team == 0
                                      and b.is_complete for b in buildings)):
                            if selected_building.enqueue(gold, "knight", buildings):
                                _play("train_start")
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
                                if selected_building.enqueue_research(
                                        gold, lumber, rid, upgrades[0]):
                                    _play("train_start")
                                break
                        else:
                            if gp[0] >= SIDEBAR_W:
                                drag_start = pygame.Vector2(gp)
                                drag_current = pygame.Vector2(gp)
                    elif (selected_building is not None
                            and isinstance(selected_building, LumberMill)):
                        if TRAIN_BTN.collidepoint(gp):
                            if selected_building.enqueue_research(
                                    gold, lumber, "ranger", upgrades[0]):
                                _play("train_start")
                        elif gp[0] >= SIDEBAR_W:
                            drag_start = pygame.Vector2(gp)
                            drag_current = pygame.Vector2(gp)
                    elif gp[0] < SIDEBAR_W and selected_building is not None:
                        pass
                    # Worker build menu — only reachable when no building is selected.
                    elif BUILD_FARM_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "farm" else "farm"
                        selected = apply_selection(selected, [])
                    elif BUILD_BARRACKS_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "barracks" else "barracks"
                        selected = apply_selection(selected, [])
                    elif BUILD_LUMBERMILL_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "lumbermill" else "lumbermill"
                        selected = apply_selection(selected, [])
                    elif BUILD_BLACKSMITH_BTN.collidepoint(gp):
                        build_mode = None if build_mode == "blacksmith" else "blacksmith"
                        selected = apply_selection(selected, [])
                    elif GATHER_BTN.collidepoint(gp):
                        for u in selected:
                            if isinstance(u, Worker) and u._wstate == "idle":
                                _worker_gather(u, buildings, game_map, player_hall)
                    else:
                        drag_start = pygame.Vector2(gp)
                        drag_current = pygame.Vector2(gp)

                elif event.button == 3:
                    if build_mode:
                        build_mode = None
                    elif selected and gp[0] >= SIDEBAR_W:
                        gv = pygame.Vector2(wp)   # world coords for movement targets
                        enemy_unit = next((u for u in units if u.team == 1
                                           and u.contains_point(wp)), None)
                        enemy_bldg = next((b for b in buildings if b.team == 1
                                           and b.contains_point(wp)), None)
                        mine = next((b for b in buildings if isinstance(b, GoldMine)
                                      and b.contains_point(wp)), None)
                        tree = next((b for b in buildings if isinstance(b, Tree)
                                      and b.contains_point(wp) and b.hp > 0), None)

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
                                other_cells = {u.cell for u in units if u not in selected}
                                tgts = formation_targets(gv, len(movers))
                                for u, tgt in zip(movers, tgts):
                                    u.move_to(game_map.find_path(u.pos, tgt, other_cells))
                                _play('move')
                        elif tree:
                            movers = []
                            for u in selected:
                                if isinstance(u, Worker):
                                    u.order_chop(tree, player_hall, game_map, buildings)
                                else:
                                    movers.append(u)
                            if movers:
                                other_cells = {u.cell for u in units if u not in selected}
                                tgts = formation_targets(gv, len(movers))
                                for u, tgt in zip(movers, tgts):
                                    u.move_to(game_map.find_path(u.pos, tgt, other_cells))
                                _play('move')
                        else:
                            other_cells = {u.cell for u in units if u not in selected}
                            tgts = formation_targets(gv, len(selected))
                            for u, tgt in zip(selected, tgts):
                                u.move_to(game_map.find_path(u.pos, tgt, other_cells))
                            _play('move')
                            _move_marker = (gv.x, gv.y, 0.55)

            elif event.type == pygame.MOUSEMOTION:
                gp_m = to_game(event.pos)
                # Drag on minimap → pan camera
                if (pygame.mouse.get_pressed()[0]
                        and minimap.rect and minimap.rect.collidepoint(gp_m)):
                    mx = gp_m[0] - minimap.rect.x
                    my = gp_m[1] - minimap.rect.y
                    cx, cy = minimap.world_to_cam(mx, my,
                                                  WIDTH - SIDEBAR_W, HEIGHT,
                                                  map_px_w, map_px_h)
                    cam.x, cam.y = cx, cy
                    cam_ix, cam_iy = int(cam.x), int(cam.y)
                if drag_start is not None:
                    drag_current = pygame.Vector2(gp_m)   # canvas coords for drawing
                if build_mode:
                    # store world coords so ghost placement is correct after scrolling
                    build_ghost = (gp_m[0] - SIDEBAR_W + cam_ix, gp_m[1] + cam_iy)

            elif (event.type == pygame.MOUSEBUTTONUP
                  and event.button == 1 and drag_start is not None):
                end = pygame.Vector2(to_game(event.pos))
                delta = end - drag_start

                if delta.length() > 4:
                    # sel_rect in world coords so it can match unit.rect
                    sel_rect = pygame.Rect(
                        int(min(drag_start.x, end.x)) - SIDEBAR_W + cam_ix,
                        int(min(drag_start.y, end.y)) + cam_iy,
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
                    # Single click — convert canvas coords to world coords
                    wp_up = (int(end.x) - SIDEBAR_W + cam_ix, int(end.y) + cam_iy)
                    _tc, _tr = wp_up[0] // CELL_SIZE, wp_up[1] // CELL_SIZE
                    if 0 <= _tr < len(tile_map) and 0 <= _tc < len(tile_map[_tr]):
                        _ttype = tile_map[_tr][_tc]
                        _here = next((b for b in buildings if b.contains_point(wp_up)), None)
                        _extra = f" + {type(_here).__name__}" if _here else ""
                        print(f"[click] tile ({_tc},{_tr}) = '{_ttype}'{_extra}  world ({wp_up[0]},{wp_up[1]})")
                    _bc = [b for b in buildings if b.team in (0, -1) and b.contains_point(wp_up)]
                    bldg = (min(_bc, key=lambda b: (b.pos - pygame.Vector2(wp_up)).length())
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
                                         if u.team == 0 and u.contains_point(wp_up)), None)
                        new_sel = [clicked] if clicked else []
                        selected = apply_selection(selected, new_sel)
                        if selected:
                            _play('select')

                drag_start = None
                drag_current = None

        # ---- Camera edge scroll (game viewport only — ignore sidebar) ----
        _ms = to_game(pygame.mouse.get_pos())
        if SIDEBAR_W < _ms[0] < SIDEBAR_W + SCROLL_EDGE:  cam.x -= SCROLL_SPEED * dt
        elif _ms[0] > WIDTH - SCROLL_EDGE:                 cam.x += SCROLL_SPEED * dt
        if _ms[1] < SCROLL_EDGE:                           cam.y -= SCROLL_SPEED * dt
        elif _ms[1] > HEIGHT - SCROLL_EDGE:                cam.y += SCROLL_SPEED * dt
        cam.x = max(0, min(map_px_w - WIDTH,  cam.x))
        cam.y = max(0, min(map_px_h - HEIGHT, cam.y))
        cam_ix, cam_iy = int(cam.x), int(cam.y)

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

            # Construction progress + lumber mill carry bonus
            for b in buildings:
                b.update_construction(dt)
            for b in buildings:
                if isinstance(b, LumberMill) and b.is_complete:
                    if not getattr(b, '_carry_bonus_applied', False):
                        b._carry_bonus_applied = True
                        cap = Worker.LUMBER_CARRY_CAP + LumberMill.CARRY_BONUS
                        for u in units:
                            if isinstance(u, Worker) and u.team == b.team:
                                u._lumber_carry_cap = cap

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
                        if any(isinstance(bld, LumberMill) and bld.team == b.team and bld.is_complete
                               for bld in buildings):
                            new_unit._lumber_carry_cap = Worker.LUMBER_CARRY_CAP + LumberMill.CARRY_BONUS
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

            # Push apart units that share a cell (1×1 tile separation)
            for i, u1 in enumerate(units):
                for u2 in units[i + 1:]:
                    diff = u1.pos - u2.pos
                    d = diff.length_squared()
                    if 0 < d < CELL_SIZE * CELL_SIZE:
                        sep = diff * ((CELL_SIZE / d ** 0.5 - 1) * 0.5)
                        u1.pos += sep
                        u1.rect.center = (int(u1.pos.x), int(u1.pos.y))
                        u2.pos -= sep
                        u2.rect.center = (int(u2.pos.x), int(u2.pos.y))

            # Corpse + sound on death
            for u in units:
                if not u.is_alive():
                    corpses.append(Corpse(u.pos, u.team, sheet=u._sheet))
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

        # ---- Draw world objects to world_surf ----
        world_surf.fill((0, 0, 0))
        game_map.draw(world_surf)

        for c in corpses:
            c.draw(world_surf)

        _vp = pygame.Rect(cam_ix, cam_iy, WIDTH - SIDEBAR_W, HEIGHT)
        for b in buildings:
            if b.is_alive() and _vp.colliderect(b.rect):
                b.draw(world_surf)

        # Enemy units hidden outside fog visibility
        visible = fog._visible
        for u in units:
            if u.team != 0 and _pos_to_grid(u.pos) not in visible:
                continue
            u.draw(world_surf)

        for p in projectiles:
            p.draw(world_surf)

        # ---- Blit visible portion of world_surf into game viewport (right of sidebar) ----
        canvas.blit(world_surf, (SIDEBAR_W, 0),
                    pygame.Rect(cam_ix, cam_iy, WIDTH - SIDEBAR_W, HEIGHT))

        # Selected-building bracket — drawn over world_surf before fog.
        # GoldMine uses its own yellow rect drawn in building.py, so skip it here.
        if selected_building is not None and selected_building.is_alive() and not isinstance(selected_building, GoldMine):
            r = selected_building.rect
            bx = r.x - cam_ix + SIDEBAR_W
            by = r.y - cam_iy
            bw, bh = r.width, r.height
            blen = max(6, min(bw, bh) // 3)
            for (ox, oy), (dx, dy) in [
                ((bx,      by),      (1,  1)),
                ((bx + bw, by),      (-1,  1)),
                ((bx,      by + bh), (1, -1)),
                ((bx + bw, by + bh), (-1, -1)),
            ]:
                pygame.draw.line(canvas, (0, 230, 0), (ox, oy), (ox + dx * blen, oy), 2)
                pygame.draw.line(canvas, (0, 230, 0), (ox, oy), (ox, oy + dy * blen), 2)

        # Move-order click marker — shrinking ring that fades out
        if _move_marker is not None:
            mx, my, life = _move_marker
            sx = int(mx - cam_ix + SIDEBAR_W)
            sy = int(my - cam_iy)
            ratio = life / 0.55
            radius = max(2, int(4 + ratio * 14))
            alpha  = int(220 * ratio)
            _mm_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(_mm_surf, (0, 255, 60, alpha),
                               (radius + 2, radius + 2), radius, 2)
            canvas.blit(_mm_surf, (sx - radius - 2, sy - radius - 2))
            _move_marker = (mx, my, max(0.0, life - dt))
            if _move_marker[2] == 0.0:
                _move_marker = None

        # Ghost building outline in build mode (screen coords = world - camera)
        if build_mode:
            _GDIMS = {"farm": (Farm.W, Farm.H), "barracks": (Barracks.W, Barracks.H),
                      "lumbermill": (LumberMill.W, LumberMill.H),
                      "blacksmith": (Blacksmith.W, Blacksmith.H)}
            bw, bh = _GDIMS.get(build_mode, (Farm.W, Farm.H))
            sx = (build_ghost[0] // CELL_SIZE) * CELL_SIZE
            sy = (build_ghost[1] // CELL_SIZE) * CELL_SIZE
            ghost_rect_world = pygame.Rect(sx, sy, bw, bh)
            ghost_rect_screen = pygame.Rect(sx - cam_ix + SIDEBAR_W, sy - cam_iy, bw, bh)
            cost_g, cost_l = BUILD_COSTS[build_mode]
            can_place = (placement_valid(ghost_rect_world, buildings, game_map)
                         and gold[0] >= cost_g and lumber[0] >= cost_l)
            fill_col = (0, 200, 0, 70) if can_place else (200, 40, 40, 70)
            line_col  = (0, 255, 0)    if can_place else (255, 60, 60)
            ghost_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            ghost_surf.fill(fill_col)
            canvas.blit(ghost_surf, ghost_rect_screen)
            pygame.draw.rect(canvas, line_col, ghost_rect_screen, 2)

        # Fog overlay — drawn BEFORE the drag box so the selection box is always visible
        fog.draw(canvas, cam_ix, cam_iy, viewport_x=SIDEBAR_W)

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

        draw_hud(canvas, font, gold, lumber, buildings, units, selected, selected_building,
                 ai.state, muted, fullscreen, build_mode=build_mode, difficulty=difficulty,
                 mouse_pos=to_game(pygame.mouse.get_pos()),
                 team_upgrades=upgrades[0])
        # Draw minimap AFTER draw_hud so the sidebar fill doesn't overwrite it
        _mm_bldgs = [b for b in buildings if not isinstance(b, Tree)]
        minimap.draw(canvas, _mm_bldgs, units, dest_xy=(_MINI_SB_X, _MINI_SB_Y),
                     cam=(cam_ix, cam_iy), viewport=(WIDTH - SIDEBAR_W, HEIGHT))

        if tech_tree_open:
            draw_tech_tree(canvas, font, big_font, buildings, upgrades[0])

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
    next_seed  = DEFAULT_SEED
    while True:
        restart, difficulty, next_seed = run_game(
            screen, clock, font, big_font, difficulty=difficulty, map_seed=next_seed)
        if not restart:
            break

    pygame.quit()


if __name__ == "__main__":
    main()
