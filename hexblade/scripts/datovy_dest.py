from hexblade.fx import dim, mix, rng

NAME = "Datový déšť"
DESCRIPTION = ("Zamrzlý okamžik padajících dat: sloupce kláves se světlou „hlavou“ a "
               "slábnoucí stopou na černém pozadí.")
PARAMS = {
    "barva": {"type": "color", "default": "#00ff50", "label": "Barva"},
    "proudy": {"type": "int", "min": 10, "max": 100, "default": 55, "label": "Hustota proudů (%)"},
    "seminko": {"type": "int", "min": 1, "max": 999, "default": 7, "label": "Semínko"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 12, "label": "Jas"},
}


def build(kb, p):
    r = rng(p.seminko)
    columns = {}
    for k in sorted(kb.keys, key=lambda k: k.x):
        col = round(k.x)
        if col not in columns:
            on = r.random() < p.proudy / 100
            columns[col] = (r.randint(0, 6), r.randint(2, 5)) if on else None
    head_col = mix(p.barva, "#ffffff", 0.6)

    def color(k):
        c = columns.get(round(k.x))
        if not c:
            return "#000000"
        head, length = c
        dist = head - k.row
        if dist == 0:
            return head_col
        if 0 < dist <= length:
            return dim(p.barva, 0.3 + 0.6 * (1 - dist / (length + 1)))
        return "#000000"

    kb.map(color)
    kb.brightness = p.jas
