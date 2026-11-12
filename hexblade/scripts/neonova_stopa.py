NAME = "Neonová stopa"
DESCRIPTION = ("Klávesnice je potmě a rozsvítí se jen klávesa, kterou stiskneš, a pak "
               "pomalu dohasíná. Běží přímo v klávesnici (efekt „Rozsvícení po stisku“).")
PARAMS = {
    "barva": {"type": "color", "default": "#00c8ff", "label": "Barva"},
    "duha": {"type": "bool", "default": False, "label": "Duhové barvy"},
    "rychlost": {"type": "int", "min": 1, "max": 16, "default": 6, "label": "Rychlost dohasínání"},
    "jas": {"type": "int", "min": 1, "max": 16, "default": 16, "label": "Jas"},
}


def build(kb, p):
    kb.effect("single_on", color=p.barva, rainbow=p.duha, speed=p.rychlost, brightness=p.jas)
