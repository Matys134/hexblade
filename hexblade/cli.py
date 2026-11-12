"""Command line interface: ``hexblade <příkaz>``."""

from __future__ import annotations

import argparse
import sys

from . import profile as prof
from .device import Device, DeviceError, find_devices
from .layout import KEYS
from .protocol import (BRIGHTNESS_MAX, CMD_KEYMAP, CMD_LIGHTING, DIRECTIONS,
                       MODES, SPEED_MAX, encode_keymap, encode_lighting)


def _color(value: str) -> str:
    v = value.lstrip("#")
    if len(v) != 6 or any(c not in "0123456789abcdefABCDEF" for c in v):
        raise argparse.ArgumentTypeError("barva musí být ve tvaru RRGGBB")
    return "#" + v.lower()


def apply_profile(p: dict, keymap: bool = False, device_path: str | None = None) -> None:
    with Device(device_path) as dev:
        dev.write_block(CMD_LIGHTING, encode_lighting(p["lighting"]))
        if keymap:
            dev.write_block(CMD_KEYMAP, encode_keymap(p["keymap"]))


def cmd_info(args) -> int:
    devs = find_devices()
    if not devs:
        print("Klávesnice nenalezena.")
        return 1
    for d in devs:
        print(f"{d.name}  {d.path}  (rozhraní {d.interface})")
    return 0


def cmd_modes(args) -> int:
    for num, mid, label in MODES:
        print(f"{num:2d}  {mid:12s} {label}")
    print("    custom       Vlastní barvy kláves")
    print("    off          Vypnuto")
    return 0


def cmd_keys(args) -> int:
    for k in KEYS:
        print(f"{k.id:10s} {k.cz:10s} matice {k.row},{k.col}")
    return 0


def cmd_light(args) -> int:
    state = prof.load_state()
    try:
        p = prof.load_profile(state["profile"]) if state.get("profile") else prof.default_profile()
    except (OSError, ValueError):
        p = prof.default_profile()
    light = p["lighting"]
    light["mode"] = args.mode
    if args.mode in light["modes"]:
        s = light["modes"][args.mode]
        if args.color:
            s["color"] = args.color
        if args.rainbow is not None:
            s["rainbow"] = args.rainbow
        if args.brightness is not None:
            s["brightness"] = args.brightness
        if args.speed is not None:
            s["speed"] = args.speed
        if args.direction is not None:
            s["direction"] = args.direction
    elif args.mode == "custom":
        if args.color:
            light["custom_default"] = args.color
        if args.brightness is not None:
            light["custom_brightness"] = args.brightness
    apply_profile(p, device_path=args.device)
    print("Hotovo.")
    return 0


def cmd_apply(args) -> int:
    p = prof.load_profile(args.profile)
    apply_profile(p, keymap=args.keymap, device_path=args.device)
    print(f"Profil „{p['name']}“ nahrán" + (" včetně mapování kláves." if args.keymap else "."))
    return 0


def cmd_profiles(args) -> int:
    for n in prof.list_profiles():
        print(n)
    return 0


def cmd_scripts(args) -> int:
    from . import scripting
    for s in scripting.list_scripts():
        flag = "⚠ " if s.error else ""
        print(f"{s.id:20s} {flag}{s.name}" + ("" if s.bundled else "  (vlastní)"))
        for k, spec in s.params.items():
            extra = ""
            if spec.get("type") == "choice":
                extra = " [" + " | ".join(spec.get("options", [])) + "]"
            elif "min" in spec:
                extra = f" [{spec['min']}–{spec['max']}]"
            print(f"    {k}={spec.get('default')}{extra}  {spec.get('label', '')}")
    return 0


def cmd_script(args) -> int:
    from . import scripting
    s = scripting.find_script(args.name)
    if s.error:
        print(f"Chyba ve skriptu {s.path}:\n{s.error}", file=sys.stderr)
        return 2
    values = {}
    for item in args.set or []:
        key, _, val = item.partition("=")
        if key not in s.params:
            print(f"Neznámý parametr „{key}“ (možnosti: {', '.join(s.params)})", file=sys.stderr)
            return 2
        values[key] = scripting.coerce(s.params[key], val)
    try:
        kb = s.run(values)
    except scripting.ScriptError as exc:
        print(f"Chyba ve skriptu:\n{exc}", file=sys.stderr)
        return 2
    state = prof.load_state()
    try:
        p = prof.load_profile(state["profile"]) if state.get("profile") else prof.default_profile()
    except (OSError, ValueError):
        p = prof.default_profile()
    p["lighting"] = kb.to_lighting(p["lighting"])
    if args.save:
        p["script"] = {"id": s.id, "params": {**s.defaults(), **values}}
        prof.save_profile(p)
    apply_profile(p, device_path=args.device)
    print(f"Skript „{s.name}“ nahrán do klávesnice.")
    return 0


def cmd_gui(args) -> int:
    from .gui import main
    return main()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="hexblade",
                                 description="Ovládání klávesnice CZC.Gaming Hexblade")
    ap.add_argument("--device", help="cesta k hidraw zařízení (výchozí: autodetekce)")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("info", help="najít klávesnici").set_defaults(func=cmd_info)
    sub.add_parser("modes", help="vypsat světelné režimy").set_defaults(func=cmd_modes)
    sub.add_parser("keys", help="vypsat klávesy a jejich ID").set_defaults(func=cmd_keys)
    sub.add_parser("profiles", help="vypsat uložené profily").set_defaults(func=cmd_profiles)
    sub.add_parser("gui", help="spustit grafické rozhraní").set_defaults(func=cmd_gui)

    mode_ids = [m for _, m, _ in MODES] + ["custom", "off"]
    lp = sub.add_parser("light", help="nastavit podsvícení")
    lp.add_argument("mode", choices=mode_ids)
    lp.add_argument("-c", "--color", type=_color, help="barva RRGGBB")
    lp.add_argument("-b", "--brightness", type=int, choices=range(1, BRIGHTNESS_MAX + 1),
                    metavar=f"1-{BRIGHTNESS_MAX}")
    lp.add_argument("-s", "--speed", type=int, choices=range(1, SPEED_MAX + 1),
                    metavar=f"1-{SPEED_MAX}")
    lp.add_argument("-d", "--direction", type=int, choices=range(DIRECTIONS),
                    metavar=f"0-{DIRECTIONS - 1}")
    rb = lp.add_mutually_exclusive_group()
    rb.add_argument("--rainbow", dest="rainbow", action="store_true", default=None,
                    help="duhové barvy místo jedné barvy")
    rb.add_argument("--no-rainbow", dest="rainbow", action="store_false")
    lp.set_defaults(func=cmd_light)

    sub.add_parser("scripts", help="vypsat lighting skripty a jejich parametry") \
        .set_defaults(func=cmd_scripts)
    sp = sub.add_parser("script", help="spustit lighting skript a nahrát výsledek")
    sp.add_argument("name", help="ID/název skriptu nebo cesta k .py")
    sp.add_argument("--set", "-p", action="append", metavar="PARAM=HODNOTA",
                    help="hodnota parametru (lze opakovat)")
    sp.add_argument("--save", action="store_true",
                    help="uložit výsledek i do aktivního profilu")
    sp.set_defaults(func=cmd_script)

    pa = sub.add_parser("apply", help="nahrát uložený profil do klávesnice")
    pa.add_argument("profile", help="název profilu nebo cesta k .json")
    pa.add_argument("--keymap", action="store_true",
                    help="nahrát i mapování kláves (přepíše mapování v klávesnici)")
    pa.set_defaults(func=cmd_apply)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        return cmd_gui(args)
    try:
        return args.func(args)
    except DeviceError as exc:
        print(f"Chyba: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Soubor nenalezen: {exc.filename}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
