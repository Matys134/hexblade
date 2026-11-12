"""Physical layout of the CZC.Gaming Hexblade (ANSI, 104 keys + 4 media keys).

Every key has a position in the firmware's 8 × 18 matrix, which is used both
for per-key lighting and for key remapping. Positions come from the vendor's
KeyboardIDMapping.xml; the four keys above the numpad were found by testing.
"""

from __future__ import annotations

from dataclasses import dataclass

ROWS = 8
COLS = 18


@dataclass(frozen=True)
class Key:
    id: str          # stable identifier used in profiles
    us: str          # US legend
    cz: str          # Czech (QWERTZ) legend
    row: int         # matrix row
    col: int         # matrix column
    x: float         # physical position in key units
    y: float
    w: float = 1.0
    h: float = 1.0

    @property
    def index(self) -> int:
        return self.row * COLS + self.col


def _k(id, us, row, col, x, y, w=1.0, h=1.0, cz=None):
    return Key(id, us, cz if cz is not None else us, row, col, x, y, w, h)


KEYS: list[Key] = [
    # --- function row ---------------------------------------------------
    _k("esc", "Esc", 0, 1, 0, 0),
    _k("f1", "F1", 0, 2, 2, 0), _k("f2", "F2", 0, 3, 3, 0),
    _k("f3", "F3", 0, 4, 4, 0), _k("f4", "F4", 0, 5, 5, 0),
    _k("f5", "F5", 0, 6, 6.5, 0), _k("f6", "F6", 0, 7, 7.5, 0),
    _k("f7", "F7", 0, 8, 8.5, 0), _k("f8", "F8", 0, 9, 9.5, 0),
    _k("f9", "F9", 0, 10, 11, 0), _k("f10", "F10", 0, 11, 12, 0),
    _k("f11", "F11", 0, 12, 13, 0), _k("f12", "F12", 0, 13, 14, 0),
    _k("prtsc", "PrtSc", 6, 4, 15.25, 0),
    _k("scrlk", "ScrLk", 6, 5, 16.25, 0),
    _k("pause", "Pause", 6, 7, 17.25, 0),
    _k("volup", "Vol+", 0, 14, 18.5, 0),
    _k("voldown", "Vol−", 0, 15, 19.5, 0),
    _k("mute", "Mute", 0, 16, 20.5, 0),
    _k("calc", "Calc", 6, 1, 21.5, 0),
    # --- number row -----------------------------------------------------
    _k("grave", "`", 1, 1, 0, 1.25, cz=";"),
    _k("1", "1", 1, 2, 1, 1.25, cz="+ 1"),
    _k("2", "2", 1, 3, 2, 1.25, cz="ě 2"),
    _k("3", "3", 1, 4, 3, 1.25, cz="š 3"),
    _k("4", "4", 1, 5, 4, 1.25, cz="č 4"),
    _k("5", "5", 1, 6, 5, 1.25, cz="ř 5"),
    _k("6", "6", 1, 7, 6, 1.25, cz="ž 6"),
    _k("7", "7", 1, 8, 7, 1.25, cz="ý 7"),
    _k("8", "8", 1, 9, 8, 1.25, cz="á 8"),
    _k("9", "9", 1, 10, 9, 1.25, cz="í 9"),
    _k("0", "0", 1, 11, 10, 1.25, cz="é 0"),
    _k("minus", "-", 1, 12, 11, 1.25, cz="= %"),
    _k("equal", "=", 1, 13, 12, 1.25, cz="´ ˇ"),
    _k("backspace", "Backspace", 5, 13, 13, 1.25, w=2, cz="⌫"),
    _k("insert", "Ins", 6, 8, 15.25, 1.25),
    _k("home", "Home", 6, 9, 16.25, 1.25),
    _k("pgup", "PgUp", 6, 10, 17.25, 1.25),
    _k("numlock", "Num", 1, 14, 18.5, 1.25),
    _k("kp_div", "/", 1, 15, 19.5, 1.25),
    _k("kp_mul", "*", 1, 16, 20.5, 1.25),
    _k("kp_minus", "-", 6, 14, 21.5, 1.25),
    # --- QWERTY row -----------------------------------------------------
    _k("tab", "Tab", 2, 1, 0, 2.25, w=1.5),
    _k("q", "Q", 2, 2, 1.5, 2.25), _k("w", "W", 2, 3, 2.5, 2.25),
    _k("e", "E", 2, 4, 3.5, 2.25), _k("r", "R", 2, 5, 4.5, 2.25),
    _k("t", "T", 2, 6, 5.5, 2.25), _k("y", "Y", 2, 7, 6.5, 2.25, cz="Z"),
    _k("u", "U", 2, 8, 7.5, 2.25), _k("i", "I", 2, 9, 8.5, 2.25),
    _k("o", "O", 2, 10, 9.5, 2.25), _k("p", "P", 2, 11, 10.5, 2.25),
    _k("lbracket", "[", 2, 12, 11.5, 2.25, cz="ú /"),
    _k("rbracket", "]", 2, 13, 12.5, 2.25, cz=") ("),
    _k("backslash", "\\", 3, 13, 13.5, 2.25, w=1.5, cz="¨ '"),
    _k("delete", "Del", 6, 11, 15.25, 2.25),
    _k("end", "End", 6, 12, 16.25, 2.25),
    _k("pgdn", "PgDn", 6, 13, 17.25, 2.25),
    _k("kp7", "7", 2, 14, 18.5, 2.25), _k("kp8", "8", 2, 15, 19.5, 2.25),
    _k("kp9", "9", 2, 16, 20.5, 2.25),
    _k("kp_plus", "+", 6, 15, 21.5, 2.25, h=2),
    # --- home row -------------------------------------------------------
    _k("caps", "Caps", 3, 1, 0, 3.25, w=1.75),
    _k("a", "A", 3, 2, 1.75, 3.25), _k("s", "S", 3, 3, 2.75, 3.25),
    _k("d", "D", 3, 4, 3.75, 3.25), _k("f", "F", 3, 5, 4.75, 3.25),
    _k("g", "G", 3, 6, 5.75, 3.25), _k("h", "H", 3, 7, 6.75, 3.25),
    _k("j", "J", 3, 8, 7.75, 3.25), _k("k", "K", 3, 9, 8.75, 3.25),
    _k("l", "L", 3, 10, 9.75, 3.25),
    _k("semicolon", ";", 3, 11, 10.75, 3.25, cz="ů \""),
    _k("quote", "'", 3, 12, 11.75, 3.25, cz="§ !"),
    _k("enter", "Enter", 4, 13, 12.75, 3.25, w=2.25),
    _k("kp4", "4", 3, 14, 18.5, 3.25), _k("kp5", "5", 3, 15, 19.5, 3.25),
    _k("kp6", "6", 3, 16, 20.5, 3.25),
    # --- bottom alpha row -----------------------------------------------
    _k("lshift", "Shift", 4, 1, 0, 4.25, w=2.25),
    _k("z", "Z", 4, 2, 2.25, 4.25, cz="Y"), _k("x", "X", 4, 3, 3.25, 4.25),
    _k("c", "C", 4, 4, 4.25, 4.25), _k("v", "V", 4, 5, 5.25, 4.25),
    _k("b", "B", 4, 6, 6.25, 4.25), _k("n", "N", 4, 7, 7.25, 4.25),
    _k("m", "M", 4, 8, 8.25, 4.25),
    _k("comma", ",", 4, 9, 9.25, 4.25, cz=", ?"),
    _k("period", ".", 4, 10, 10.25, 4.25, cz=". :"),
    _k("slash", "/", 4, 11, 11.25, 4.25, cz="- _"),
    _k("rshift", "Shift", 4, 12, 12.25, 4.25, w=2.75),
    _k("up", "↑", 5, 11, 16.25, 4.25),
    _k("kp1", "1", 4, 14, 18.5, 4.25), _k("kp2", "2", 4, 15, 19.5, 4.25),
    _k("kp3", "3", 4, 16, 20.5, 4.25),
    _k("kp_enter", "Ent", 5, 16, 21.5, 4.25, h=2),
    # --- modifier row ---------------------------------------------------
    _k("lctrl", "Ctrl", 5, 1, 0, 5.25, w=1.25),
    _k("lwin", "Win", 5, 2, 1.25, 5.25, w=1.25),
    _k("lalt", "Alt", 5, 3, 2.5, 5.25, w=1.25),
    _k("space", "", 5, 4, 3.75, 5.25, w=6.25),
    _k("ralt", "AltGr", 5, 5, 10, 5.25, w=1.25),
    _k("fn", "Fn", 5, 6, 11.25, 5.25, w=1.25),
    _k("menu", "Menu", 5, 7, 12.5, 5.25, w=1.25),
    _k("rctrl", "Ctrl", 5, 8, 13.75, 5.25, w=1.25),
    _k("left", "←", 5, 9, 15.25, 5.25),
    _k("down", "↓", 5, 10, 16.25, 5.25),
    _k("right", "→", 5, 12, 17.25, 5.25),
    _k("kp0", "0", 5, 14, 18.5, 5.25, w=2),
    _k("kp_dot", ".", 5, 15, 20.5, 5.25, cz=","),
]

KEYS_BY_ID: dict[str, Key] = {k.id: k for k in KEYS}
WIDTH_UNITS = max(k.x + k.w for k in KEYS)
HEIGHT_UNITS = max(k.y + k.h for k in KEYS)

# Keys whose function cannot be changed safely (the Fn key is handled by firmware).
NON_REMAPPABLE = {"fn"}
