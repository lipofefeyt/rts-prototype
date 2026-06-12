#!/usr/bin/env python3
"""
Extract unit sprites from Warcraft II MAINDAT.WAR using war2tools/libwar2.so via ctypes.
Outputs PNG sprite sheets to assets/sprites/.

Usage:
    python tools/extract_war2_sprites.py

Expects the following paths (relative to repo root):
    ../war2tools/build/libwar2/libwar2.so
    ../war2tools/build/libpud/libpud.so
    ../war2tools/data/maindat.war

Output layout:
    assets/sprites/<unit>_<team>_walk.png    — horizontal strip, all walk frames
    assets/sprites/<unit>_<team>_all.png     — ALL frames (walk + attack + death)
    assets/sprites/manifest.json             — frame sizes and counts per sprite sheet
"""

import ctypes
import os
import json
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAR2DIR  = os.path.join(REPO, "..", "war2tools")
MAINDAT  = os.path.join(WAR2DIR, "data", "maindat.war")
LIBWAR2  = os.path.join(WAR2DIR, "build", "libwar2", "libwar2.so")
LIBPUD   = os.path.join(WAR2DIR, "build", "libpud", "libpud.so")
OUT_DIR  = os.path.join(REPO, "assets", "sprites")

# Units to extract: (name, Pud_Unit id, walk_frames_per_dir, directions)
UNITS = [
    # Human
    ("footman",     0x00, 5, 8),
    ("peasant",     0x02, 5, 8),
    ("knight",      0x06, 5, 8),
    ("archer",      0x08, 5, 8),
    # Orc
    ("grunt",       0x01, 5, 8),
    ("peon",        0x03, 5, 8),
    ("ogre",        0x07, 5, 8),
    ("axethrower",  0x09, 5, 8),
]

# Player colors: (name, Pud_Player id)
# Red = team 0 (human blue in WC2), Blue = team 1 (orc red in WC2)
# We map Red→team0 and Blue→team1 to match our game's colour scheme
PLAYERS = [
    ("team0", 0),   # PUD_PLAYER_RED   (human blue in WC2)
    ("team1", 1),   # PUD_PLAYER_BLUE  (orc red  in WC2)
]

PUD_ERA_FOREST = 0   # tileset doesn't matter for unit sprites

# ---------------------------------------------------------------------------
# ctypes bindings
# ---------------------------------------------------------------------------

class PudColor(ctypes.Structure):
    _fields_ = [("r", ctypes.c_uint8), ("g", ctypes.c_uint8),
                ("b", ctypes.c_uint8), ("a", ctypes.c_uint8)]

SpriteCB = ctypes.CFUNCTYPE(
    None,                          # void return
    ctypes.c_void_p,               # user data
    ctypes.POINTER(PudColor),      # sprite pixels
    ctypes.c_int,                  # x (origin, often 0)
    ctypes.c_int,                  # y
    ctypes.c_uint,                 # w
    ctypes.c_uint,                 # h
    ctypes.c_void_p,               # War2_Sprites_Descriptor* (opaque)
    ctypes.c_uint16,               # sprite_id (frame index)
)


def load_libs():
    for path in (LIBPUD, LIBWAR2):
        if not os.path.exists(path):
            sys.exit(f"Library not found: {path}\n"
                     "Build war2tools first:  cd ../war2tools && mkdir -p build && cd build && cmake .. && cmake --build .")
    if not os.path.exists(MAINDAT):
        sys.exit(f"MAINDAT.WAR not found at {MAINDAT}")

    libpud  = ctypes.CDLL(LIBPUD,  mode=ctypes.RTLD_GLOBAL)   # libwar2 depends on it
    libwar2 = ctypes.CDLL(LIBWAR2, mode=ctypes.RTLD_GLOBAL)

    libwar2.war2_init.restype    = ctypes.c_int
    libwar2.war2_open.restype    = ctypes.c_void_p
    libwar2.war2_open.argtypes   = [ctypes.c_char_p]
    libwar2.war2_close.argtypes  = [ctypes.c_void_p]
    libwar2.war2_shutdown.argtypes = []
    libwar2.war2_sprites_decode.restype  = ctypes.c_uint
    libwar2.war2_sprites_decode.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        SpriteCB, ctypes.c_void_p,
    ]
    return libwar2

# ---------------------------------------------------------------------------
# Per-unit extraction
# ---------------------------------------------------------------------------

def extract_unit(libwar2, w2_handle, unit_name: str, unit_id: int,
                 player_name: str, player_id: int) -> dict:
    """Returns list of frames: [{w, h, rgba_bytes}, ...]"""
    frames: list[dict] = []

    def on_sprite(_data, pixels, _x, _y, w, h, _sd, frame_id):
        rgba = bytes(pixels[i].r << 0 | pixels[i].g << 8 |   # trick: build list directly
                     0 for i in range(0))                      # placeholder — see below
        # Build raw RGBA bytes from the PudColor array
        n = w * h
        buf = bytearray(4 * n)
        for i in range(n):
            p = pixels[i]
            buf[4*i]   = p.r
            buf[4*i+1] = p.g
            buf[4*i+2] = p.b
            buf[4*i+3] = p.a
        frames.append({"id": int(frame_id), "w": int(w), "h": int(h), "rgba": bytes(buf)})

    cb = SpriteCB(on_sprite)
    libwar2.war2_sprites_decode(w2_handle, unit_id, player_id, PUD_ERA_FOREST, cb, None)
    return frames

# ---------------------------------------------------------------------------
# PNG writing (using pygame — already in the venv)
# ---------------------------------------------------------------------------

def save_strip(frames: list[dict], out_path: str) -> dict:
    """
    Saves all frames as a horizontal PNG strip.
    Returns manifest info: {frames, frame_w, frame_h, strip_w, strip_h}.
    """
    import pygame

    if not frames:
        return {}

    # Normalise to the max dimensions found across all frames
    max_w = max(f["w"] for f in frames)
    max_h = max(f["h"] for f in frames)
    n = len(frames)

    strip = pygame.Surface((max_w * n, max_h), pygame.SRCALPHA)
    strip.fill((0, 0, 0, 0))

    for i, frame in enumerate(sorted(frames, key=lambda f: f["id"])):
        w, h = frame["w"], frame["h"]
        surf = pygame.image.frombuffer(frame["rgba"], (w, h), "RGBA")
        # Centre smaller frames in the cell
        ox = i * max_w + (max_w - w) // 2
        oy = (max_h - h) // 2
        strip.blit(surf, (ox, oy))

    pygame.image.save(strip, out_path)
    return {"frames": n, "frame_w": max_w, "frame_h": max_h,
            "strip_w": max_w * n, "strip_h": max_h}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import pygame
    pygame.init()

    os.makedirs(OUT_DIR, exist_ok=True)
    libwar2 = load_libs()

    if not libwar2.war2_init():
        sys.exit("war2_init() failed")

    w2 = libwar2.war2_open(MAINDAT.encode())
    if not w2:
        sys.exit(f"war2_open failed for {MAINDAT}")

    manifest = {}

    for unit_name, unit_id, walk_per_dir, directions in UNITS:
        for player_name, player_id in PLAYERS:
            label = f"{unit_name}_{player_name}"
            print(f"Extracting {label} ...", flush=True)

            frames = extract_unit(libwar2, w2, unit_name, unit_id, player_name, player_id)
            if not frames:
                print(f"  ⚠ no frames returned — skipping")
                continue

            # All frames
            all_path = os.path.join(OUT_DIR, f"{label}_all.png")
            info = save_strip(frames, all_path)
            print(f"  {len(frames)} frames → {all_path}")

            # Walk-only subset: first walk_per_dir * directions frames
            walk_count = walk_per_dir * directions
            walk_frames = [f for f in frames if f["id"] < walk_count]
            if walk_frames:
                walk_path = os.path.join(OUT_DIR, f"{label}_walk.png")
                walk_info = save_strip(walk_frames, walk_path)
                info["walk"] = walk_info
                print(f"  walk subset ({walk_count} frames) → {walk_path}")

            manifest[label] = info

    libwar2.war2_close(w2)
    libwar2.war2_shutdown()

    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written to {manifest_path}")
    pygame.quit()


if __name__ == "__main__":
    main()
