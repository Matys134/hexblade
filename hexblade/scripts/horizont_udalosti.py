import math

from hexblade.fx import dim, gradient, mix

NAME = "Horizont událostí"
DESCRIPTION = ("Černá díra uprostřed klávesnice: kolem černého středu žhne akreční disk "
               "(jedna strana jasnější, jako by rotoval) a ven slábne do hluboké fialové tmy.")
PARAMS = {
    "stred": {"type": "choice", "options": ["písmena", "WASD", "numerická část"],
              "default": "písmena", "label": "Kde je díra"},
    "velikost": {"type": "int", "min": 5, "max": 30, "default": 14, "label": "Velikost"},
    "disk": {"type": "color", "default": "#ff6a00", "label": "Akreční disk"},
    "okoli": {"type": "color", "default": "#5000d0", "label": "Okolí"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 13, "label": "Jas"},
}

CENTERS = {"písmena": (7.2, 3.6), "WASD": (3.2, 3.2), "numerická část": (20.0, 3.4)}


def build(kb, p):
    cx, cy = CENTERS[p.stred]
    r = p.velikost / 10            # poloměr černého středu v jednotkách kláves
    hot = mix(p.disk, "#ffd060", 0.5)
    cold = mix(p.disk, "#600000", 0.6)

    def color(k):
        dx, dy = k.x - cx, (k.y - cy) * 1.7
        d = math.hypot(dx, dy)
        if d < r:
            return "#000000"
        doppler = 0.65 + 0.35 * math.cos(math.atan2(dy, dx) - math.pi)  # vlevo jasnější
        ring = (d - r) / (r * 1.6)
        if ring < 1:
            return dim(gradient([hot, p.disk, cold], ring), doppler)
        far = min(1.0, (d - r * 2.6) / 9)
        return dim(p.okoli, (1 - far) * 0.6 + 0.3)

    kb.map(color)
    kb.brightness = p.jas
