"""Profiles stored as JSON in ~/.config/hexblade/profiles."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

from .protocol import BRIGHTNESS_MAX, MODES

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "hexblade"
PROFILE_DIR = CONFIG_DIR / "profiles"
STATE_FILE = CONFIG_DIR / "state.json"

# Defaults taken from the vendor's GamingKeyboard.gkdb
_DEFAULT_RAINBOW = {"single_on", "single_off", "glittering", "falling",
                    "outward", "scrolling", "rolling", "rotating", "explode",
                    "launch", "ripples", "flowing", "pulsating", "tilt", "shuttle"}


def default_profile(name: str = "Výchozí") -> dict:
    return {
        "name": name,
        "lighting": {
            "mode": "static",
            "modes": {
                mid: {
                    "color": "#ff0000",
                    "rainbow": mid in _DEFAULT_RAINBOW,
                    "brightness": BRIGHTNESS_MAX,
                    "speed": 12,
                    "direction": 0,
                    "background": None,
                }
                for _, mid, _ in MODES
            },
            "custom_default": "#ffffff",
            "custom_colors": {},
            "custom_brightness": BRIGHTNESS_MAX,
        },
        "keymap": {},
    }


def normalize(profile: dict) -> dict:
    """Fill in missing fields so older/hand-written files still work."""
    base = default_profile(profile.get("name", "Profil"))
    out = copy.deepcopy(base)
    out["name"] = profile.get("name", base["name"])
    light = profile.get("lighting", {})
    for k, v in light.items():
        if k == "modes":
            for mid, s in v.items():
                if mid in out["lighting"]["modes"]:
                    out["lighting"]["modes"][mid].update(s)
        else:
            out["lighting"][k] = v
    out["keymap"] = dict(profile.get("keymap", {}))
    return out


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return s or "profil"


def profile_path(name: str) -> Path:
    return PROFILE_DIR / f"{_slug(name)}.json"


def list_profiles() -> list[str]:
    if not PROFILE_DIR.exists():
        return []
    names = []
    for p in sorted(PROFILE_DIR.glob("*.json")):
        try:
            names.append(json.loads(p.read_text())["name"])
        except (OSError, ValueError, KeyError):
            continue
    return names


def load_profile(name_or_path: str) -> dict:
    p = Path(name_or_path)
    if not (p.suffix == ".json" and p.exists()):
        p = profile_path(name_or_path)
    return normalize(json.loads(p.read_text()))


def save_profile(profile: dict) -> Path:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = profile_path(profile["name"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    tmp.replace(path)
    return path


def delete_profile(name: str) -> None:
    profile_path(name).unlink(missing_ok=True)


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
