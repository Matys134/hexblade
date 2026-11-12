"""Šablona lighting skriptu pro Hexblade.

kb      – klávesnice, do které kreslíš:
          kb.fill(barva)            všechny klávesy
          kb["esc"] = barva         jedna klávesa (ID viz `hexblade keys`)
          kb.set("wasd", barva)     skupina: fkeys numbers letters wasd arrows
                                    mods nav sys media numpad punct alpha all
          kb.map(lambda k: barva)   funkce pro každou klávesu; k.id, k.x, k.y
                                    (jednotky kláves), k.cx, k.cy (0–1), k.row
          kb.brightness = 1–16
          kb.effect("ripples", color=…, speed=…)   vestavěný animovaný efekt
          kb.effect("single_on", color=…, background="#001050")
                                    reaktivní efekt s barvou pozadí
p       – hodnoty parametrů z PARAMS (p.barva, p.jas …)

Pomocné funkce: hexblade.fx – mix, dim, add, hsv, rgb, gradient, noise, rng,
smoothstep. Barvy jsou řetězce "#rrggbb".

Tip: LED pod zhruba 30 % jasu (např. dim(barva, 0.3)) skoro nesvítí –
pro „temné“ návrhy je lepší menší počet rozsvícených kláves než moc tmavé barvy.
"""
from hexblade.fx import gradient

NAME = "Nový skript"
DESCRIPTION = "Popis, co skript dělá."
PARAMS = {
    "zleva": {"type": "color", "default": "#001040", "label": "Barva vlevo"},
    "vpravo": {"type": "color", "default": "#3a0060", "label": "Barva vpravo"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 10, "label": "Jas"},
}


def build(kb, p):
    kb.map(lambda k: gradient([p.zleva, p.vpravo], k.cx))
    kb.brightness = p.jas
