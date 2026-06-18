#!/usr/bin/env python3
"""
Annotate a tile atlas PNG with grid lines and tile IDs.

Usage:
    python tools/annotate_atlas.py [era]
    era: forest | winter | wasteland | swamp  (default: forest)

Output:
    assets/sprites/tiles/<era>_atlas_annotated.png

Each tile is drawn 2× its original size so the ID label fits.
The red grid shows tile boundaries; yellow numbers are the tile IDs
used in map.py (id = row * 32 + col, left-to-right, top-to-bottom).
"""
import os
import sys

REPO       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILE_DIR   = os.path.join(REPO, "assets", "sprites", "tiles")
TILE_W     = 32          # source tile size in pixels
ATLAS_COLS = 32          # tiles per row in the atlas
SCALE      = 2           # output magnification


def main() -> None:
    era = sys.argv[1] if len(sys.argv) > 1 else "forest"
    src = os.path.join(TILE_DIR, f"{era}_atlas.png")
    if not os.path.exists(src):
        sys.exit(f"Not found: {src}\nAvailable eras: forest winter wasteland swamp")

    import pygame
    pygame.init()
    # A real display is required for font rendering even in headless mode.
    pygame.display.set_mode((1, 1), pygame.NOFRAME)

    atlas = pygame.image.load(src).convert_alpha()
    aw, ah = atlas.get_width(), atlas.get_height()
    cols   = aw // TILE_W
    rows   = ah // TILE_W

    tile_out = TILE_W * SCALE          # 64 px per tile in the output
    out_w    = cols * tile_out
    out_h    = rows * tile_out

    out = pygame.Surface((out_w, out_h))
    out.fill((20, 20, 20))             # dark background so empty tiles are visible

    # Scale the whole atlas up first (bilinear would be nice, but nearest is fine here)
    scaled = pygame.transform.scale(atlas, (out_w, out_h))
    out.blit(scaled, (0, 0))

    font = pygame.font.Font(None, 15)  # ~12 pt, fits in a 64-px cell

    for r in range(rows):
        for c in range(cols):
            tid  = r * ATLAS_COLS + c
            ox   = c * tile_out
            oy   = r * tile_out

            # Red cell border
            pygame.draw.rect(out, (220, 50, 50), (ox, oy, tile_out, tile_out), 1)

            # Tile-ID label with a black backing so it's legible on any tile colour
            label = font.render(str(tid), True, (255, 230, 50))
            backing = pygame.Surface(label.get_size())
            backing.fill((0, 0, 0))
            out.blit(backing, (ox + 2, oy + 2))
            out.blit(label,   (ox + 2, oy + 2))

    dst = os.path.join(TILE_DIR, f"{era}_atlas_annotated.png")
    pygame.image.save(out, dst)
    print(f"Saved → {dst}  ({cols}×{rows} tiles, output {out_w}×{out_h} px)")
    pygame.quit()


if __name__ == "__main__":
    main()
