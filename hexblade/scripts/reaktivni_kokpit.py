from hexblade.fx import dim

NAME = "Reaktivní kokpit"
DESCRIPTION = ("Temně modrý podklad kokpitu, ze kterého při psaní jemně vybíhají "
               "tyrkysové vlny (nebo se rozsvítí jen stisknutá klávesa). Využívá "
               "barvu pozadí reaktivních efektů – skrytou funkci firmwaru, kterou "
               "původní software neumí.")
PARAMS = {
    "efekt": {"type": "choice", "options": ["stopa", "vlny"], "default": "stopa",
              "label": "Reakce na stisk"},
    "podklad": {"type": "color", "default": "#0020a0", "label": "Podklad"},
    "sila_podkladu": {"type": "int", "min": 30, "max": 100, "default": 70,
                      "label": "Síla podkladu (%)"},
    "reakce": {"type": "color", "default": "#00c8ff", "label": "Barva reakce"},
    "rychlost": {"type": "int", "min": 1, "max": 16, "default": 6, "label": "Rychlost"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 12, "label": "Jas"},
}


def build(kb, p):
    mode = "ripples" if p.efekt == "vlny" else "single_on"
    kb.effect(mode, color=p.reakce, background=dim(p.podklad, p.sila_podkladu / 100),
              speed=p.rychlost, brightness=p.jas)
