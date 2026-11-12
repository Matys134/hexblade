from hexblade.fx import dim, mix, noise, rng, smoothstep

NAME = "Hvězdné pole"
DESCRIPTION = ("Hluboký vesmír: černá klávesnice s náhodně rozesetými hvězdami různé "
               "jasnosti a volitelnou slabou mlhovinou. Jiné „semínko“ = jiná obloha.")
PARAMS = {
    "hustota": {"type": "int", "min": 5, "max": 60, "default": 22, "label": "Hustota hvězd (%)"},
    "mlhovina": {"type": "int", "min": 0, "max": 100, "default": 70, "label": "Mlhovina (%)"},
    "barva_mlhoviny": {"type": "color", "default": "#4a00ff", "label": "Barva mlhoviny"},
    "seminko": {"type": "int", "min": 1, "max": 999, "default": 42, "label": "Semínko"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 14, "label": "Jas"},
}

STAR_COLORS = ["#ffffff", "#c0e0ff", "#80b0ff", "#ffe0b0", "#d0a0ff"]


def build(kb, p):
    r = rng(p.seminko)

    def color(k):
        n = noise(k.x / 4.5, k.y / 2.5, p.seminko)
        cloud = smoothstep(0.35, 0.75, n)
        neb = dim(p.barva_mlhoviny, (0.3 + 0.6 * cloud) * p.mlhovina / 100) if cloud > 0.05 else "#000000"
        if r.random() < p.hustota / 100:
            star = dim(r.choice(STAR_COLORS), 0.4 + 0.6 * r.random() ** 2)
            return mix(neb, star, 0.85)
        return neb

    kb.map(color)
    kb.brightness = p.jas
