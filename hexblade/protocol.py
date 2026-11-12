"""Encoding of Hexblade configuration blocks.

See docs/PROTOCOL.md for the full description.
"""

from __future__ import annotations

from .layout import COLS, KEYS, ROWS

# Block command bytes (second byte of the 04 xx header)
CMD_KEYMAP = 0x11
CMD_LIGHTING = 0x13
CMD_MACROS = 0x15

LIGHTING_SIZE = 0x480
KEYMAP_SIZE = 0x280

MODE_CUSTOM = 0x80  # per-key colours ("UserDefine" / OwnerDrawMode)

# (number, internal id, Czech label) – order and numbering come from the
# firmware; the English names are the vendor's.
MODES: list[tuple[int, str, str]] = [
    (1, "static", "Statická"),
    (2, "single_on", "Rozsvícení po stisku"),
    (3, "single_off", "Zhasnutí po stisku"),
    (4, "glittering", "Třpytky"),
    (5, "falling", "Padající"),
    (6, "colourful", "Barevná"),
    (7, "breath", "Dýchání"),
    (8, "spectrum", "Spektrum"),
    (9, "outward", "Ze středu ven"),
    (10, "scrolling", "Posouvání"),
    (11, "rolling", "Rolování"),
    (12, "rotating", "Rotace"),
    (13, "explode", "Exploze"),
    (14, "launch", "Výstřel"),
    (15, "ripples", "Vlnky"),
    (16, "flowing", "Tekoucí"),
    (17, "pulsating", "Pulzování"),
    (18, "tilt", "Náklon"),
    (19, "shuttle", "Kyvadlo"),
]
MODE_IDS = {mid: num for num, mid, _ in MODES}
MODE_NAMES = {num: mid for num, mid, _ in MODES}
MODE_LABELS = {mid: label for _, mid, label in MODES}

BRIGHTNESS_MAX = 16
SPEED_MAX = 16
DIRECTIONS = 4


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def mode_record(number: int, color: str = "#000000", rainbow: bool = False,
                brightness: int = BRIGHTNESS_MAX, speed: int = 12,
                direction: int = 0, background: str | None = None) -> bytes:
    """One 16-byte lighting mode record.

    ``background`` (bytes 4–7) is a second colour that the vendor tool never
    sends; reactive effects use it as the idle background colour.
    """
    r, g, b = _hex_to_rgb(color)
    rec = bytearray(16)
    rec[0] = number
    rec[1], rec[2], rec[3] = r, g, b
    if background:
        rec[4], rec[5], rec[6] = _hex_to_rgb(background)
        rec[7] = 1
    rec[8] = 1 if rainbow else 0
    rec[9] = _clamp(brightness, 1, BRIGHTNESS_MAX)
    rec[10] = _clamp(speed, 1, SPEED_MAX)
    rec[11] = _clamp(direction, 0, DIRECTIONS - 1)
    rec[14], rec[15] = 0xAA, 0x55
    return bytes(rec)


def encode_lighting(lighting: dict) -> bytes:
    """Build the 0x480-byte lighting block.

    Layout: 32 × 16-byte mode slots (19 effects + custom), 8 × 18 × 4 bytes of
    per-key colours ``[0x80, R, G, B]``, then the record of the active mode.
    """
    block = bytearray(LIGHTING_SIZE)
    modes = lighting.get("modes", {})
    active = lighting.get("mode", "static")

    for num, mid, _ in MODES:
        s = modes.get(mid, {})
        rec = mode_record(num, s.get("color", "#ff0000"), s.get("rainbow", False),
                          s.get("brightness", BRIGHTNESS_MAX), s.get("speed", 12),
                          s.get("direction", 0), s.get("background"))
        block[(num - 1) * 16 : num * 16] = rec

    custom_brightness = lighting.get("custom_brightness", BRIGHTNESS_MAX)
    custom_rec = bytearray(16)
    custom_rec[0] = MODE_CUSTOM
    custom_rec[9] = _clamp(custom_brightness, 1, BRIGHTNESS_MAX)
    custom_rec[14], custom_rec[15] = 0xAA, 0x55
    block[19 * 16 : 20 * 16] = custom_rec

    if active == "off":
        colors: dict = {}
        default = "#000000"
    else:
        colors = lighting.get("custom_colors", {})
        default = lighting.get("custom_default", "#ffffff")
    key_by_index = {k.index: k for k in KEYS}
    for idx in range(ROWS * COLS):
        key = key_by_index.get(idx)
        color = colors.get(key.id, default) if key else "#000000"
        r, g, b = _hex_to_rgb(color)
        off = 0x200 + idx * 4
        block[off : off + 4] = bytes([0x80, r, g, b])

    if active in ("custom", "off"):
        active_rec = bytes(custom_rec)
    else:
        num = MODE_IDS[active]
        active_rec = bytes(block[(num - 1) * 16 : num * 16])
    block[0x440:0x450] = active_rec
    return bytes(block)


# ---------------------------------------------------------------------------
# Key remapping
# ---------------------------------------------------------------------------

MOD_BITS = {"lctrl": 0x01, "lshift": 0x02, "lalt": 0x04, "lwin": 0x08,
            "rctrl": 0x10, "rshift": 0x20, "ralt": 0x40, "rwin": 0x80}
MOD_LABELS = {"lctrl": "Ctrl", "lshift": "Shift", "lalt": "Alt", "lwin": "Win",
              "rctrl": "Pravý Ctrl", "rshift": "Pravý Shift", "ralt": "AltGr",
              "rwin": "Pravý Win"}

# HID keyboard usages offered as remap targets: (usage, label)
KEY_USAGES: list[tuple[int, str]] = (
    [(0x04 + i, chr(ord("A") + i)) for i in range(26)]
    + [(0x1E + i, str((i + 1) % 10)) for i in range(10)]
    + [(0x28, "Enter"), (0x29, "Esc"), (0x2A, "Backspace"), (0x2B, "Tab"),
       (0x2C, "Mezerník"), (0x2D, "- (US)"), (0x2E, "= (US)"), (0x2F, "[ (US)"),
       (0x30, "] (US)"), (0x31, "\\ (US)"), (0x33, "; (US)"), (0x34, "' (US)"),
       (0x35, "` (US)"), (0x36, ", (US)"), (0x37, ". (US)"), (0x38, "/ (US)"),
       (0x39, "Caps Lock")]
    + [(0x3A + i, f"F{i + 1}") for i in range(12)]
    + [(0x68 + i, f"F{i + 13}") for i in range(12)]
    + [(0x46, "Print Screen"), (0x47, "Scroll Lock"), (0x48, "Pause"),
       (0x49, "Insert"), (0x4A, "Home"), (0x4B, "Page Up"), (0x4C, "Delete"),
       (0x4D, "End"), (0x4E, "Page Down"), (0x4F, "Šipka vpravo"),
       (0x50, "Šipka vlevo"), (0x51, "Šipka dolů"), (0x52, "Šipka nahoru"),
       (0x53, "Num Lock"), (0x54, "Num /"), (0x55, "Num *"), (0x56, "Num -"),
       (0x57, "Num +"), (0x58, "Num Enter")]
    + [(0x59 + i, f"Num {i + 1}") for i in range(9)]
    + [(0x62, "Num 0"), (0x63, "Num ,"), (0x64, "ISO \\ |"), (0x65, "Menu"),
       (0xE0, "Levý Ctrl"), (0xE1, "Levý Shift"), (0xE2, "Levý Alt"),
       (0xE3, "Levý Win"), (0xE4, "Pravý Ctrl"), (0xE5, "Pravý Shift"),
       (0xE6, "AltGr"), (0xE7, "Pravý Win")]
)
KEY_USAGE_LABELS = dict(KEY_USAGES)

# HID consumer usages: (usage, label)
MEDIA_USAGES: list[tuple[int, str]] = [
    (0xCD, "Přehrát / pozastavit"), (0xB7, "Zastavit"), (0xB5, "Další skladba"),
    (0xB6, "Předchozí skladba"), (0xE2, "Ztlumit"), (0xE9, "Hlasitost +"),
    (0xEA, "Hlasitost −"), (0x192, "Kalkulačka"), (0x18A, "E-mail"),
    (0x194, "Tento počítač"), (0x183, "Přehrávač médií"),
    (0x223, "Prohlížeč – domů"), (0x221, "Hledat"), (0x224, "Prohlížeč – zpět"),
    (0x225, "Prohlížeč – vpřed"), (0x227, "Prohlížeč – obnovit"),
    (0x22A, "Oblíbené"),
]
MEDIA_USAGE_LABELS = dict(MEDIA_USAGES)

MOUSE_ACTIONS: list[tuple[str, str, bytes]] = [
    ("left", "Levé tlačítko", bytes([0x01, 0x01, 0x01, 0x00])),
    ("right", "Pravé tlačítko", bytes([0x01, 0x01, 0x02, 0x00])),
    ("middle", "Prostřední tlačítko", bytes([0x01, 0x01, 0x04, 0x00])),
    ("back", "Zpět (tlačítko 4)", bytes([0x01, 0x01, 0x08, 0x00])),
    ("forward", "Vpřed (tlačítko 5)", bytes([0x01, 0x01, 0x10, 0x00])),
    ("wheel_up", "Kolečko nahoru", bytes([0x01, 0x03, 0x01, 0x00])),
    ("wheel_down", "Kolečko dolů", bytes([0x01, 0x03, 0xFF, 0x00])),
]
MOUSE_BY_ID = {mid: (label, code) for mid, label, code in MOUSE_ACTIONS}


def encode_action(action: dict | None) -> bytes:
    """4-byte firmware code for one key. ``None``/default → 00 00 00 00."""
    if not action or action.get("type", "default") == "default":
        return bytes(4)
    kind = action["type"]
    if kind == "key":
        usage = int(action["usage"])
        mods = 0
        for m in action.get("mods", []):
            mods |= MOD_BITS[m]
        if 0xE0 <= usage <= 0xE7:
            # modifiers are sent as a bit only (vendor tool zeroes the usage)
            return bytes([0x02, mods | (1 << (usage - 0xE0)), 0x00, 0x00])
        return bytes([0x02, mods, usage, 0x00])
    if kind == "media":
        usage = int(action["usage"])
        return bytes([0x03, usage & 0xFF, usage >> 8, 0x00])
    if kind == "mouse":
        return MOUSE_BY_ID[action["button"]][1]
    if kind == "disabled":
        return bytes([0x02, 0x00, 0x00, 0x00])
    raise ValueError(f"neznámý typ akce: {kind}")


def describe_action(action: dict | None) -> str:
    if not action or action.get("type", "default") == "default":
        return "Výchozí"
    kind = action["type"]
    if kind == "key":
        parts = [MOD_LABELS[m] for m in action.get("mods", [])]
        parts.append(KEY_USAGE_LABELS.get(int(action["usage"]),
                                          f"0x{int(action['usage']):02x}"))
        return " + ".join(parts)
    if kind == "media":
        return MEDIA_USAGE_LABELS.get(int(action["usage"]), "Multimédia")
    if kind == "mouse":
        return "Myš: " + MOUSE_BY_ID[action["button"]][0]
    if kind == "disabled":
        return "Vypnuto"
    return kind


def encode_keymap(keymap: dict) -> bytes:
    """Build the 0x280-byte keymap block (8 × 18 × 4 bytes, padding, AA 55)."""
    block = bytearray(KEYMAP_SIZE)
    for key in KEYS:
        code = encode_action(keymap.get(key.id))
        block[key.index * 4 : key.index * 4 + 4] = code
    block[0x27E], block[0x27F] = 0xAA, 0x55  # signature, without it the map is ignored
    return bytes(block)
