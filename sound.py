import math
import struct
import pygame

_RATE = 44100


def pre_init() -> None:
    """Call before pygame.init() to lock in the correct mixer format."""
    pygame.mixer.pre_init(frequency=_RATE, size=-16, channels=2, buffer=512)


def _tone(freq: float, ms: int, vol: float = 0.25, decay: float = 2.0) -> pygame.mixer.Sound:
    n = int(_RATE * ms / 1000)
    buf = bytearray(4 * n)
    for i in range(n):
        env = (1.0 - i / n) ** decay
        v = int(vol * env * 32767 * math.sin(2 * math.pi * freq * i / _RATE))
        struct.pack_into('<hh', buf, 4 * i, v, v)
    return pygame.mixer.Sound(buffer=buf)


def _sweep(f0: float, f1: float, ms: int, vol: float = 0.25) -> pygame.mixer.Sound:
    n = int(_RATE * ms / 1000)
    buf = bytearray(4 * n)
    for i in range(n):
        t = i / n
        freq = f0 + (f1 - f0) * t
        env = 1.0 - t
        v = int(vol * env * 32767 * math.sin(2 * math.pi * freq * i / _RATE))
        struct.pack_into('<hh', buf, 4 * i, v, v)
    return pygame.mixer.Sound(buffer=buf)


def load_sounds() -> dict[str, pygame.mixer.Sound]:
    """Generate all in-memory sounds. Returns empty dict if mixer unavailable."""
    try:
        return {
            'select':     _tone(880,  70, 0.18, 2.5),
            'move':       _tone(660,  90, 0.15, 2.5),
            'death':      _sweep(330, 110, 320, 0.22),
            'train_done': _tone(1100, 130, 0.20, 2.0),
        }
    except Exception:
        return {}
