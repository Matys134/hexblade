"""Colour helpers for lighting scripts.

Colours are plain ``"#rrggbb"`` strings everywhere, so scripts can mix
helpers freely::

    from hexblade.fx import mix, hsv, dim, gradient
"""

from __future__ import annotations

import colorsys
import math
import random as _random

BLACK = "#000000"
WHITE = "#ffffff"


def _rgb(c: str) -> tuple[float, float, float]:
    c = c.lstrip("#")
    return int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255


def rgb(r: float, g: float, b: float) -> str:
    """Colour from components 0–255 (floats are fine, values are clamped)."""
    cl = lambda v: max(0, min(255, round(v)))
    return "#%02x%02x%02x" % (cl(r), cl(g), cl(b))


def hsv(h: float, s: float = 1.0, v: float = 1.0) -> str:
    """Colour from hue 0–1 (wraps around), saturation and value 0–1."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return rgb(r * 255, g * 255, b * 255)


def mix(a: str, b: str, t: float) -> str:
    """Linear blend: t=0 → a, t=1 → b."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return rgb((ra + (rb - ra) * t) * 255, (ga + (gb - ga) * t) * 255, (ba + (bb - ba) * t) * 255)


def dim(c: str, f: float) -> str:
    """Scale brightness of a colour (0 = black, 1 = unchanged)."""
    r, g, b = _rgb(c)
    return rgb(r * f * 255, g * f * 255, b * f * 255)


def add(a: str, b: str) -> str:
    """Additive blend (light + light), clamped."""
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return rgb((ra + rb) * 255, (ga + gb) * 255, (ba + bb) * 255)


def gradient(stops: list[str], t: float) -> str:
    """Pick a colour on a multi-stop gradient, t in 0–1."""
    if len(stops) == 1:
        return stops[0]
    t = max(0.0, min(1.0, t)) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    return mix(stops[i], stops[i + 1], t - i)


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0) if e1 != e0 else 0.0))
    return t * t * (3 - 2 * t)


def noise(x: float, y: float, seed: int = 0) -> float:
    """Smooth 2D value noise in 0–1."""
    def h(ix, iy):
        n = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 0xFFFF

    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    top = h(x0, y0) + (h(x0 + 1, y0) - h(x0, y0)) * sx
    bot = h(x0, y0 + 1) + (h(x0 + 1, y0 + 1) - h(x0, y0 + 1)) * sx
    return top + (bot - top) * sy


def rng(seed: int) -> _random.Random:
    """Deterministic random generator (same seed → same design)."""
    return _random.Random(seed)
