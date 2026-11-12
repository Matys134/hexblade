from hexblade.fx import dim, mix

NAME = "Temný kokpit"
DESCRIPTION = ("Skoro zhasnutý kokpit stíhačky: tmavě modrý podklad, který k F-řadě "
               "mizí do tmy, žhavé WASD a šipky, tlumené tyrkysové přístroje na "
               "numerické části a rudý Esc.")
PARAMS = {
    "podklad": {"type": "color", "default": "#0020a0", "label": "Podklad"},
    "akcent": {"type": "color", "default": "#ff2a00", "label": "Žhavé klávesy"},
    "pristroje": {"type": "color", "default": "#00b0c0", "label": "Přístroje"},
    "tma": {"type": "int", "min": 0, "max": 100, "default": 15, "label": "Tma podkladu (%)"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 12, "label": "Jas"},
}


def build(kb, p):
    t = p.tma / 100
    # podklad: dole (u mezerníku) nejsvětlejší, nahoru mizí do tmy
    kb.map(lambda k: dim(p.podklad, (1 - t) * (0.45 + 0.55 * k.row / 5)))
    kb.set("fkeys", "#000000")
    kb.set(["prtsc", "scrlk", "pause"], dim(p.podklad, 0.12))
    kb.set("nav", dim(p.podklad, (1 - t) * 0.7))

    kb.set("wasd", p.akcent)
    kb.set("arrows", dim(p.akcent, 0.8))
    kb.set(["lshift", "lctrl", "space"], dim(p.akcent, 0.25))
    kb["esc"] = "#b00000"
    kb.set(["backspace", "delete"], "#400000")

    # přístrojová deska: numpad shora tmavý, dole jasnější
    kb.map(lambda k: dim(p.pristroje, 0.25 + 0.6 * (k.row - 1) / 4)
           if k.id in ("numlock", "kp_div", "kp_mul", "kp_minus", "kp7", "kp8", "kp9",
                       "kp_plus", "kp4", "kp5", "kp6", "kp1", "kp2", "kp3", "kp0",
                       "kp_dot") else None)
    kb["kp_enter"] = p.pristroje
    kb["enter"] = mix(p.pristroje, "#ffffff", 0.15)
    kb.set("media", dim(p.akcent, 0.35))
    kb.brightness = p.jas
