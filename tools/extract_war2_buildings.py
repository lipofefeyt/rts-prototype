#!/usr/bin/env python3
"""
Extract building sprites and terrain tiles from Warcraft II MAINDAT.WAR.

Usage:
    python tools/extract_war2_buildings.py

Output:
    assets/sprites/buildings/<label>.png        — completed building (last frame)
    assets/sprites/buildings/<label>_all.png    — all frames as a strip (debug)
    assets/sprites/tiles/forest_atlas.png       — full tileset atlas (32×32 tiles)
    assets/sprites/buildings/manifest.json
"""

import ctypes
import os
import json
import sys

REPO     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAR2DIR  = os.path.join(REPO, "..", "war2tools")
MAINDAT  = os.path.join(WAR2DIR, "data", "maindat.war")
LIBWAR2  = os.path.join(WAR2DIR, "build", "libwar2", "libwar2.so")
LIBPUD   = os.path.join(WAR2DIR, "build", "libpud", "libpud.so")
BLDG_DIR = os.path.join(REPO, "assets", "sprites", "buildings")
TILE_DIR = os.path.join(REPO, "assets", "sprites", "tiles")

PUD_ERA_FOREST    = 0
PUD_ERA_WINTER    = 1
PUD_ERA_WASTELAND = 2
PUD_ERA_SWAMP     = 3
_ERA_IDS = {"forest": 0, "winter": 1, "wasteland": 2, "swamp": 3}


class PudColor(ctypes.Structure):
    _fields_ = [("r", ctypes.c_uint8), ("g", ctypes.c_uint8),
                ("b", ctypes.c_uint8), ("a", ctypes.c_uint8)]


SpriteCB = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,            # user data
    ctypes.POINTER(PudColor),   # pixels
    ctypes.c_int,               # x
    ctypes.c_int,               # y
    ctypes.c_uint,              # w
    ctypes.c_uint,              # h
    ctypes.c_void_p,            # War2_Sprites_Descriptor* (opaque)
    ctypes.c_uint16,            # frame index
)

TilesetCB = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,            # user data
    ctypes.POINTER(PudColor),   # pixels
    ctypes.c_uint,              # w
    ctypes.c_uint,              # h
    ctypes.c_void_p,            # War2_Tileset_Descriptor* (opaque)
    ctypes.c_uint16,            # tile_id
)

# (output label, Pud_Unit id, player_id for color)
# Human and orc buildings have separate unit IDs.
# Gold Mine has no meaningful player color; use 0.
BUILDINGS = [
    ("townhall_team0",    0x4a, 0),   # Human Town Hall
    ("townhall_team1",    0x4b, 1),   # Orc Great Hall
    ("barracks_team0",    0x3c, 0),   # Human Barracks
    ("barracks_team1",    0x3d, 1),   # Orc Barracks
    ("farm_team0",        0x3a, 0),   # Human Farm
    ("farm_team1",        0x3b, 1),   # Orc Pig Farm
    ("lumbermill_team0",  0x4c, 0),   # Elven Lumber Mill
    ("lumbermill_team1",  0x4d, 1),   # Troll Lumber Mill
    ("blacksmith_team0",  0x52, 0),   # Human Blacksmith
    ("blacksmith_team1",  0x53, 1),   # Orc Blacksmith
    ("goldmine",          0x5c, 0),   # Gold Mine
]


def load_libs():
    for path in (LIBPUD, LIBWAR2):
        if not os.path.exists(path):
            sys.exit(f"Library not found: {path}\n"
                     "Build war2tools first: cd ../war2tools && mkdir -p build && "
                     "cd build && cmake .. && cmake --build .")
    if not os.path.exists(MAINDAT):
        sys.exit(f"MAINDAT.WAR not found: {MAINDAT}")

    libpud  = ctypes.CDLL(LIBPUD,  mode=ctypes.RTLD_GLOBAL)
    libwar2 = ctypes.CDLL(LIBWAR2, mode=ctypes.RTLD_GLOBAL)

    libwar2.war2_init.restype             = ctypes.c_int
    libwar2.war2_open.restype             = ctypes.c_void_p
    libwar2.war2_open.argtypes            = [ctypes.c_char_p]
    libwar2.war2_close.argtypes           = [ctypes.c_void_p]
    libwar2.war2_shutdown.argtypes        = []
    libwar2.war2_sprites_decode.restype   = ctypes.c_uint
    libwar2.war2_sprites_decode.argtypes  = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        SpriteCB, ctypes.c_void_p,
    ]
    libwar2.war2_tileset_decode.restype   = ctypes.c_uint
    libwar2.war2_tileset_decode.argtypes  = [
        ctypes.c_void_p, ctypes.c_int, TilesetCB, ctypes.c_void_p,
    ]
    return libwar2


def _extract_frames(libwar2, w2, unit_id, player_id):
    frames = []

    def on_sprite(_data, pixels, _x, _y, w, h, _sd, frame_id):
        n = w * h
        buf = bytearray(4 * n)
        for i in range(n):
            p = pixels[i]
            buf[4 * i]     = p.r
            buf[4 * i + 1] = p.g
            buf[4 * i + 2] = p.b
            buf[4 * i + 3] = p.a
        frames.append({"id": int(frame_id), "w": int(w), "h": int(h), "rgba": bytes(buf)})

    cb = SpriteCB(on_sprite)
    libwar2.war2_sprites_decode(w2, player_id, PUD_ERA_FOREST, unit_id, cb, None)
    return sorted(frames, key=lambda f: f["id"])


def _save_strip(frames, out_path):
    """Save all frames as a horizontal PNG strip. Returns manifest dict."""
    import pygame
    if not frames:
        return {}
    max_w = max(f["w"] for f in frames)
    max_h = max(f["h"] for f in frames)
    n     = len(frames)
    strip = pygame.Surface((max_w * n, max_h), pygame.SRCALPHA)
    strip.fill((0, 0, 0, 0))
    for i, frame in enumerate(frames):
        w, h = frame["w"], frame["h"]
        surf = pygame.image.frombuffer(frame["rgba"], (w, h), "RGBA")
        ox = i * max_w + (max_w - w) // 2
        oy = (max_h - h) // 2
        strip.blit(surf, (ox, oy))
    pygame.image.save(strip, out_path)
    return {"frames": n, "frame_w": max_w, "frame_h": max_h,
            "strip_w": max_w * n, "strip_h": max_h}


def _save_frame(frame, out_path):
    """Save a single frame as PNG. Returns (w, h)."""
    import pygame
    w, h = frame["w"], frame["h"]
    surf = pygame.image.frombuffer(frame["rgba"], (w, h), "RGBA")
    pygame.image.save(surf, out_path)
    return w, h


def main():
    import pygame
    pygame.init()
    os.makedirs(BLDG_DIR, exist_ok=True)
    os.makedirs(TILE_DIR, exist_ok=True)

    libwar2 = load_libs()

    if not libwar2.war2_init():
        sys.exit("war2_init() failed")

    w2 = libwar2.war2_open(MAINDAT.encode())
    if not w2:
        sys.exit(f"war2_open failed for {MAINDAT}")

    manifest = {}

    # ── Buildings ────────────────────────────────────────────────────────────
    for label, unit_id, player_id in BUILDINGS:
        print(f"Extracting {label} (0x{unit_id:02x}, player={player_id}) ...", flush=True)

        frames = _extract_frames(libwar2, w2, unit_id, player_id)
        if not frames:
            print("  ⚠  no frames returned — skipping")
            continue

        sizes = sorted(set((f["w"], f["h"]) for f in frames))
        print(f"  {len(frames)} frames, sizes: {sizes}")

        # Full strip for visual inspection
        all_path  = os.path.join(BLDG_DIR, f"{label}_all.png")
        info      = _save_strip(frames, all_path)

        # Frame 0 is the completed building; subsequent frames are construction stages.
        done_frame = frames[0]
        done_path  = os.path.join(BLDG_DIR, f"{label}.png")
        dw, dh     = _save_frame(done_frame, done_path)
        info["done"] = {"frame_w": dw, "frame_h": dh, "frame_id": done_frame["id"]}

        manifest[label] = info
        print(f"  ✓  completed frame saved → {done_path}  ({dw}×{dh})")

    # ── Tilesets (all 4 eras) ─────────────────────────────────────────────────
    import pygame as _pg
    for era_name, era_id in _ERA_IDS.items():
        print(f"\nExtracting {era_name} tileset ...", flush=True)
        tiles: list[dict] = []

        def on_tile(_data, pixels, w, h, _ts, tile_id, _t=tiles):
            n = w * h
            buf = bytearray(4 * n)
            for i in range(n):
                p = pixels[i]
                buf[4*i]=p.r; buf[4*i+1]=p.g; buf[4*i+2]=p.b; buf[4*i+3]=p.a
            _t.append({"id": int(tile_id), "w": int(w), "h": int(h), "rgba": bytes(buf)})

        tile_cb = TilesetCB(on_tile)
        count   = libwar2.war2_tileset_decode(w2, era_id, tile_cb, None)
        print(f"  {count} tiles decoded ({len(tiles)} received)")

        if tiles:
            tile_w = tiles[0]["w"]
            tile_h = tiles[0]["h"]
            cols   = 32
            rows   = (len(tiles) + cols - 1) // cols
            atlas  = _pg.Surface((tile_w * cols, tile_h * rows), _pg.SRCALPHA)
            atlas.fill((0, 0, 0, 0))
            for tile in tiles:
                tid = tile["id"]
                surf = _pg.image.frombuffer(tile["rgba"], (tile["w"], tile["h"]), "RGBA")
                atlas.blit(surf, ((tid % cols) * tile_w, (tid // cols) * tile_h))
            atlas_path = os.path.join(TILE_DIR, f"{era_name}_atlas.png")
            _pg.image.save(atlas, atlas_path)
            manifest[f"{era_name}_tileset"] = {
                "tiles": len(tiles), "tile_w": tile_w, "tile_h": tile_h, "cols": cols, "rows": rows,
            }
            print(f"  ✓  atlas → {atlas_path}  ({cols}×{rows} grid of {tile_w}×{tile_h})")

    libwar2.war2_close(w2)
    libwar2.war2_shutdown()

    manifest_path = os.path.join(BLDG_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest → {manifest_path}")
    pygame.quit()


if __name__ == "__main__":
    main()
