"""
Procedural unit sprites drawn with pygame primitives.
Each function returns a 64×64 SRCALPHA Surface.
Replace these with actual sprite-sheet loading when you have assets.
"""
import math
import pygame


def _s() -> pygame.Surface:
    return pygame.Surface((64, 64), pygame.SRCALPHA)


def _dim(c: tuple, f: float) -> tuple:
    return tuple(min(255, max(0, int(v * f))) for v in c)


# ---------------------------------------------------------------------------
# Footman / Grunt  (melee, armoured)
# ---------------------------------------------------------------------------
def make_footman(team: int) -> pygame.Surface:
    s = _s()
    arm  = (70, 100, 180) if team == 0 else (180, 60, 60)
    dark = _dim(arm, 0.55)
    met  = (160, 168, 178)
    metd = _dim(met, 0.72)
    skin = (210, 168, 130)

    # Greaves / boots
    pygame.draw.rect(s, dark, (22, 45, 9, 15))
    pygame.draw.rect(s, dark, (33, 45, 9, 15))
    pygame.draw.rect(s, met,  (22, 56, 9,  4))
    pygame.draw.rect(s, met,  (33, 56, 9,  4))

    # Torso + chest plate
    pygame.draw.rect(s, arm,  (19, 24, 26, 22))
    pygame.draw.rect(s, met,  (22, 27, 20, 12), border_radius=2)
    pygame.draw.line(s, metd, (32, 27), (32, 39), 1)

    # Shield (left)
    pts = [(7,22),(17,20),(17,44),(12,48),(7,44)]
    pygame.draw.polygon(s, metd, pts)
    pygame.draw.polygon(s, met,  pts, 1)
    pygame.draw.circle(s, (180, 50, 50), (12, 34), 4)
    pygame.draw.circle(s, (220, 90, 90), (12, 34), 2)

    # Sword (right)
    pygame.draw.line(s, met,            (51,  9), (51, 24), 3)
    pygame.draw.line(s, (150, 110, 45), (45, 24), (58, 24), 3)
    pygame.draw.rect(s, (105,  70, 28), (49, 25, 5, 11))
    pygame.draw.rect(s, met,            (49, 35, 5,  3))

    # Head + helm
    pygame.draw.circle(s, skin, (32, 14), 9)
    pygame.draw.rect(s, metd,   (23,  6, 18, 10))
    pygame.draw.rect(s, met,    (23,  6, 18, 10), 1)
    pygame.draw.rect(s, metd,   (27, 13, 10,  6))   # visor

    return s


# ---------------------------------------------------------------------------
# Archer / Troll axethrower  (ranged, lighter build)
# ---------------------------------------------------------------------------
def make_archer(team: int) -> pygame.Surface:
    s = _s()
    lth  = (50, 185, 165) if team == 0 else (200, 80, 55)
    dark = _dim(lth, 0.60)
    wood = (120, 80, 40)
    skin = (210, 168, 130)

    # Legs
    pygame.draw.rect(s, dark, (23, 45, 8, 15))
    pygame.draw.rect(s, dark, (33, 45, 8, 15))

    # Leather tunic
    pygame.draw.rect(s, lth,  (21, 25, 22, 21))
    pygame.draw.rect(s, dark, (21, 25, 22, 21), 1)

    # Quiver (back / left side)
    pygame.draw.rect(s, _dim(wood, 0.8), (9, 22, 8, 20), border_radius=2)
    for xi in (11, 14):
        pygame.draw.line(s, (190, 150, 60), (xi, 22), (xi, 15), 1)

    # Bow: two staves meeting at a tip (D-shape)
    pygame.draw.line(s, wood, (50, 11), (57, 32), 2)
    pygame.draw.line(s, wood, (57, 32), (50, 53), 2)
    pygame.draw.line(s, (200, 190, 160), (50, 11), (50, 53), 1)   # string

    # Arrow (nocked)
    pygame.draw.line(s, wood, (30, 32), (57, 32), 2)
    pygame.draw.polygon(s, (170, 168, 165), [(57, 30), (57, 34), (62, 32)])

    # Head + hood
    pygame.draw.circle(s, skin, (32, 14), 8)
    pygame.draw.arc(s, dark, pygame.Rect(22, 4, 20, 20), 0, math.pi, 5)
    pygame.draw.rect(s, dark, (22, 11, 20, 6))

    return s


# ---------------------------------------------------------------------------
# Worker / Peon  (civilian, carries a pickaxe)
# ---------------------------------------------------------------------------
def make_worker(team: int) -> pygame.Surface:
    s = _s()
    tun  = (120, 170, 100) if team == 0 else (170, 110, 110)
    dark = _dim(tun, 0.60)
    brn  = (105, 72, 42)
    skin = (210, 168, 130)
    met  = (158, 162, 168)

    # Legs
    pygame.draw.rect(s, brn,  (23, 45, 8, 15))
    pygame.draw.rect(s, brn,  (33, 45, 8, 15))

    # Belt
    pygame.draw.rect(s, brn,  (20, 44, 24, 4))

    # Tunic
    pygame.draw.rect(s, tun,  (20, 25, 24, 22))
    pygame.draw.rect(s, dark, (20, 25, 24, 22), 1)

    # Pickaxe: handle + head
    pygame.draw.line(s, brn, (40, 36), (58, 22), 2)
    pygame.draw.polygon(s, met,  [(54, 18), (62, 13), (64, 21), (57, 23)])
    pygame.draw.polygon(s, dark, [(57, 23), (62, 26), (60, 31), (54, 26)])

    # Head (no helm)
    pygame.draw.circle(s, skin, (32, 14), 9)
    pygame.draw.arc(s, brn, pygame.Rect(22, 4, 20, 18), 0, math.pi, 4)

    return s


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_unit_sprites() -> dict:
    """Returns {(unit_type, team): Surface} for all known unit types."""
    return {
        ('footman', 0): make_footman(0),
        ('footman', 1): make_footman(1),
        ('archer',  0): make_archer(0),
        ('archer',  1): make_archer(1),
        ('worker',  0): make_worker(0),
        ('worker',  1): make_worker(1),
    }
