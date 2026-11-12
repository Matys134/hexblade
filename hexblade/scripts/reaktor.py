NAME = "Reaktor"
DESCRIPTION = ("Každý stisk vyšle od klávesy vlnu energie, jako by v klávesnici běžel "
               "reaktor. Efekt „Vlnky“ běží přímo v klávesnici.")
PARAMS = {
    "barva": {"type": "color", "default": "#00ffc0", "label": "Barva energie"},
    "duha": {"type": "bool", "default": False, "label": "Duhové barvy"},
    "rychlost": {"type": "int", "min": 1, "max": 16, "default": 10, "label": "Rychlost vlny"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 16, "label": "Jas"},
}


def build(kb, p):
    kb.effect("ripples", color=p.barva, rainbow=p.duha, speed=p.rychlost, brightness=p.jas)
