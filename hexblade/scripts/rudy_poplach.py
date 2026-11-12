from hexblade.fx import dim

NAME = "Rudý poplach"
DESCRIPTION = ("Lodní poplach: celá klávesnice pomalu pulzuje temně rudou "
               "(efekt Dýchání), nebo staticky jako nouzové osvětlení s rudou zemí.")
PARAMS = {
    "styl": {"type": "choice", "options": ["pulzující", "nouzové světlo"],
             "default": "pulzující", "label": "Styl"},
    "barva": {"type": "color", "default": "#ff0000", "label": "Barva"},
    "rychlost": {"type": "int", "min": 1, "max": 16, "default": 5, "label": "Rychlost pulzu"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 9, "label": "Jas"},
}


def build(kb, p):
    if p.styl == "pulzující":
        kb.effect("breath", color=p.barva, speed=p.rychlost, brightness=p.jas)
        return
    kb.map(lambda k: dim(p.barva, 0.3 + 0.7 * (k.row / 5) ** 2))
    kb.set(["esc", "fkeys"], dim(p.barva, 0.5))
    kb.brightness = p.jas
