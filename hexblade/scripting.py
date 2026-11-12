"""Lighting scripts: small Python files that design the keyboard lighting.

A script is a ``.py`` file with::

    NAME = "Můj návrh"
    DESCRIPTION = "Krátký popis"
    PARAMS = {                      # optional, shown as controls in the GUI
        "barva": {"type": "color", "default": "#00c8ff", "label": "Barva"},
        "jas":   {"type": "int", "min": 1, "max": 16, "default": 10, "label": "Jas"},
        "duha":  {"type": "bool", "default": False, "label": "Duha"},
        "styl":  {"type": "choice", "options": ["a", "b"], "default": "a", "label": "Styl"},
    }

    def build(kb, p):
        kb.fill("#000010")
        kb["esc"] = p.barva
        kb.set("wasd", "#ff3000")
        kb.map(lambda k: ...)          # k.id, k.x, k.y, k.cx, k.cy, k.row …
        kb.brightness = p.jas
        # or use an animated effect running in the keyboard itself:
        # kb.effect("ripples", color=p.barva, speed=10)

Scripts produce a design that is written to the keyboard once. The keyboard
stores its settings in flash memory, so nothing is streamed continuously.
"""

from __future__ import annotations

import os
import shutil
import traceback
import types
from dataclasses import dataclass, field
from pathlib import Path

from .layout import HEIGHT_UNITS, KEYS, KEYS_BY_ID, WIDTH_UNITS
from .profile import CONFIG_DIR
from .protocol import BRIGHTNESS_MAX, DIRECTIONS, MODE_IDS, SPEED_MAX

BUNDLED_DIR = Path(__file__).with_name("scripts")
USER_DIR = CONFIG_DIR / "scripts"

# Named key groups usable with kb.set("<group>", colour)
GROUPS: dict[str, list[str]] = {
    "fkeys": [f"f{i}" for i in range(1, 13)],
    "numbers": ["grave", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "minus", "equal"],
    "letters": list("abcdefghijklmnopqrstuvwxyz"),
    "wasd": ["w", "a", "s", "d"],
    "arrows": ["up", "down", "left", "right"],
    "mods": ["lshift", "rshift", "lctrl", "rctrl", "lalt", "ralt", "lwin", "fn", "menu",
             "tab", "caps"],
    "nav": ["insert", "home", "pgup", "delete", "end", "pgdn"],
    "sys": ["prtsc", "scrlk", "pause"],
    "media": ["volup", "voldown", "mute", "calc"],
    "numpad": ["numlock", "kp_div", "kp_mul", "kp_minus", "kp7", "kp8", "kp9", "kp_plus",
               "kp4", "kp5", "kp6", "kp1", "kp2", "kp3", "kp_enter", "kp0", "kp_dot"],
    "punct": ["lbracket", "rbracket", "backslash", "semicolon", "quote", "comma",
              "period", "slash"],
}
GROUPS["alpha"] = GROUPS["letters"] + GROUPS["numbers"] + GROUPS["punct"] + [
    "space", "enter", "backspace", "esc"]
GROUPS["all"] = [k.id for k in KEYS]


@dataclass(frozen=True)
class ScriptKey:
    id: str
    label: str
    x: float      # centre in key units
    y: float
    cx: float     # centre normalised 0–1 across the whole keyboard
    cy: float
    w: float
    h: float
    row: int      # physical row 0 (F-row) … 5 (space row)


_ROWS = sorted({k.y for k in KEYS})
SCRIPT_KEYS = [
    ScriptKey(k.id, k.us, k.x + k.w / 2, k.y + k.h / 2,
              (k.x + k.w / 2) / WIDTH_UNITS, (k.y + k.h / 2) / HEIGHT_UNITS,
              k.w, k.h, _ROWS.index(k.y))
    for k in KEYS
]


class ScriptError(Exception):
    pass


class Canvas:
    """What a script draws into."""

    width = WIDTH_UNITS
    height = HEIGHT_UNITS

    def __init__(self):
        self.keys = list(SCRIPT_KEYS)
        self.colors: dict[str, str] = {k.id: "#000000" for k in self.keys}
        self.brightness = BRIGHTNESS_MAX
        self._effect: dict | None = None

    # --- per-key colours -------------------------------------------------
    def _ids(self, which) -> list[str]:
        if isinstance(which, str):
            if which in GROUPS:
                return GROUPS[which]
            if which in KEYS_BY_ID:
                return [which]
            raise ScriptError(f"neznámá klávesa nebo skupina: {which}")
        out = []
        for w in which:
            out.extend(self._ids(w))
        return out

    def __getitem__(self, key_id: str) -> str:
        return self.colors[key_id]

    def __setitem__(self, key_id: str, color: str) -> None:
        for i in self._ids(key_id):
            self.colors[i] = _norm(color)

    def fill(self, color: str) -> None:
        for i in self.colors:
            self.colors[i] = _norm(color)

    def set(self, which, color: str) -> None:
        self[which] = color

    def map(self, fn) -> None:
        """Set every key to ``fn(key)``; return None to keep the current colour."""
        for k in self.keys:
            c = fn(k)
            if c is not None:
                self.colors[k.id] = _norm(c)

    def key(self, key_id: str) -> ScriptKey:
        return next(k for k in self.keys if k.id == key_id)

    # --- firmware effect --------------------------------------------------
    def effect(self, mode: str, color: str = "#ffffff", rainbow: bool = False,
               brightness: int | None = None, speed: int = 8, direction: int = 0,
               background: str | None = None) -> None:
        """Use one of the keyboard's built-in animated effects instead of per-key colours.

        ``background`` is the idle colour for reactive effects (single_on,
        ripples …); without it the keyboard stays dark between key presses.
        """
        if mode not in MODE_IDS:
            raise ScriptError(f"neznámý efekt: {mode} (možnosti: {', '.join(MODE_IDS)})")
        self._effect = {
            "mode": mode, "color": _norm(color), "rainbow": bool(rainbow),
            "brightness": max(1, min(BRIGHTNESS_MAX, int(brightness or self.brightness))),
            "speed": max(1, min(SPEED_MAX, int(speed))),
            "direction": max(0, min(DIRECTIONS - 1, int(direction))),
            "background": _norm(background) if background else None,
        }

    def to_lighting(self, base: dict) -> dict:
        """Merge the result into a profile ``lighting`` dict (copy)."""
        import copy
        light = copy.deepcopy(base)
        if self._effect:
            e = dict(self._effect)
            mode = e.pop("mode")
            light["mode"] = mode
            light["modes"][mode].update(e)
        else:
            light["mode"] = "custom"
            light["custom_colors"] = dict(self.colors)
            light["custom_brightness"] = max(1, min(BRIGHTNESS_MAX, int(self.brightness)))
        return light


def _norm(color: str) -> str:
    c = str(color).strip()
    if not c.startswith("#"):
        c = "#" + c
    if len(c) != 7:
        raise ScriptError(f"neplatná barva: {color!r} (čekám #rrggbb)")
    int(c[1:], 16)
    return c.lower()


@dataclass
class Script:
    path: Path
    name: str
    description: str = ""
    params: dict = field(default_factory=dict)
    bundled: bool = False
    error: str | None = None
    module: types.ModuleType | None = None

    @property
    def id(self) -> str:
        return self.path.stem

    def defaults(self) -> dict:
        return {k: v.get("default") for k, v in self.params.items()}

    def run(self, values: dict | None = None) -> Canvas:
        if self.module is None:
            raise ScriptError(self.error or "skript nelze načíst")
        vals = self.defaults()
        vals.update({k: v for k, v in (values or {}).items() if k in self.params})
        kb = Canvas()
        try:
            self.module.build(kb, types.SimpleNamespace(**vals))
        except ScriptError:
            raise
        except Exception:
            raise ScriptError(_short_tb())
        return kb


def _short_tb() -> str:
    tb = traceback.format_exc().strip().splitlines()
    # keep only the frames from the script itself
    keep = [l for l in tb if "hexblade/scripting.py" not in l]
    return "\n".join(keep[-6:])


def load_script(path: Path, bundled: bool = False) -> Script:
    s = Script(path=path, name=path.stem, bundled=bundled)
    mod = types.ModuleType(f"hexblade_script_{path.stem}")
    mod.__file__ = str(path)
    try:
        code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
        exec(code, mod.__dict__)
        if not callable(getattr(mod, "build", None)):
            raise ScriptError("skript musí obsahovat funkci build(kb, p)")
        s.module = mod
        s.name = str(getattr(mod, "NAME", path.stem))
        s.description = str(getattr(mod, "DESCRIPTION", ""))
        s.params = dict(getattr(mod, "PARAMS", {}))
    except ScriptError as exc:
        s.error = str(exc)
    except Exception:
        s.error = _short_tb()
    return s


def list_scripts() -> list[Script]:
    """Bundled scripts plus the user's own (a user script overrides a bundled one)."""
    found: dict[str, Script] = {}
    for d, bundled in ((BUNDLED_DIR, True), (USER_DIR, False)):
        if d.is_dir():
            for p in sorted(d.glob("*.py")):
                if p.name.startswith("_"):
                    continue
                found[p.stem] = load_script(p, bundled)
    return sorted(found.values(), key=lambda s: (s.bundled, s.name.lower()))


def find_script(name: str) -> Script:
    for s in list_scripts():
        if name in (s.id, s.name):
            return s
    p = Path(name)
    if p.suffix == ".py" and p.exists():
        return load_script(p)
    raise ScriptError(f"skript „{name}“ nenalezen")


def user_copy(script: Script) -> Path:
    """Copy a bundled script to the user directory so it can be edited."""
    USER_DIR.mkdir(parents=True, exist_ok=True)
    dst = USER_DIR / script.path.name
    if not dst.exists():
        shutil.copy(script.path, dst)
    return dst


def new_script(name: str) -> Path:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    stem = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_") or "skript"
    dst = USER_DIR / f"{stem}.py"
    n = 2
    while dst.exists():
        dst = USER_DIR / f"{stem}_{n}.py"
        n += 1
    tpl = (BUNDLED_DIR / "_sablona.py").read_text(encoding="utf-8")
    dst.write_text(tpl.replace("Nový skript", name), encoding="utf-8")
    return dst


def coerce(param: dict, value):
    """Convert a CLI string to the parameter's type."""
    t = param.get("type", "int")
    if t == "int":
        return int(value)
    if t == "float":
        return float(value)
    if t == "bool":
        return str(value).lower() in ("1", "true", "ano", "yes", "on")
    if t == "color":
        return _norm(value)
    return value
