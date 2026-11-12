"""Ukázkový skript: přechod mezi dvěma barvami.

Zkopíruj si ho tlačítkem „Upravit kopii kódu“ nebo začni tlačítkem
„Nový skript…“ – šablona popisuje vše, co skript může používat.
"""
from hexblade.fx import gradient

NAME = "Přechod barev"
DESCRIPTION = "Ukázka: plynulý přechod mezi dvěma barvami zleva doprava nebo shora dolů."
PARAMS = {
    "prvni": {"type": "color", "default": "#00a0ff", "label": "První barva"},
    "druha": {"type": "color", "default": "#ff00a0", "label": "Druhá barva"},
    "smer": {"type": "choice", "options": ["zleva doprava", "shora dolů"],
             "default": "zleva doprava", "label": "Směr"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 16, "label": "Jas"},
}


def build(kb, p):
    if p.smer == "zleva doprava":
        kb.map(lambda k: gradient([p.prvni, p.druha], k.cx))
    else:
        kb.map(lambda k: gradient([p.prvni, p.druha], k.row / 5))
    kb.brightness = p.jas
