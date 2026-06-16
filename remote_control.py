#!/usr/bin/env python3
"""Simple no-Make terminal control for LinkerHand L10.

This is a friendly wrapper around linkerhand_l10_sdk.py. It keeps the same SDK
hardware path, but lets operators run short Python commands instead of Makefile
targets.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import linkerhand_l10_sdk as sdk  # noqa: E402


CONTROL_COMMANDS = {
    "boot",
    "status",
    "state",
    "can-reset",
    "can-show",
    "can-stats",
    "kill",
    "home",
    "zero",
    "stop",
}


HELP_TEXT = """LinkerHand L10 simple terminal control

Basic startup:
  python3 remote_control.py boot
  python3 remote_control.py state
  python3 remote_control.py list
  python3 remote_control.py open

Useful options:
  --can can0           SocketCAN interface, default: can0
  --hand left          Hand side, left or right, default: left
  --mock               Preview command without sending to hardware
  --force              Send even if SDK detection fails

Preset commands:
  python3 remote_control.py list
  python3 remote_control.py show open
  python3 remote_control.py open
  python3 remote_control.py fist
  python3 remote_control.py ok
  python3 remote_control.py preset thumbs_up

CAN and state commands:
  python3 remote_control.py boot
  python3 remote_control.py can-reset
  python3 remote_control.py status
  python3 remote_control.py state
  python3 remote_control.py home
  python3 remote_control.py zero

Examples:
  python3 remote_control.py --can can1 boot
  python3 remote_control.py --hand right open
  python3 remote_control.py --mock fist
  python3 remote_control.py set 255 255 255 255 255 255 255 255 255 255
"""


def available_presets() -> set[str]:
    try:
        return set(sdk.load_presets())
    except FileNotFoundError:
        return set()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simple Python terminal control for LinkerHand L10.",
        add_help=False,
    )
    parser.add_argument("--can", default=sdk.DEFAULT_CAN)
    parser.add_argument("--hand", "--hand-type", dest="hand_type", default=sdk.DEFAULT_HAND_TYPE, choices=["left", "right"])
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-can-setup", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("items", nargs="*")
    return parser


def print_help() -> None:
    print(HELP_TEXT.rstrip())
    presets = sorted(available_presets())
    if presets:
        print("\nAvailable presets:")
        print("  " + ", ".join(presets))


def base_args(args: argparse.Namespace) -> list[str]:
    translated = ["--can", args.can, "--hand-type", args.hand_type]
    if args.mock:
        translated.append("--mock")
    if args.force:
        translated.append("--force")
    return translated


def parse_set_values(values: list[str]) -> list[str]:
    if len(values) == 1 and "," in values[0]:
        values = [part.strip() for part in values[0].split(",")]
    if len(values) != 10:
        raise SystemExit("set needs exactly 10 values, for example: python3 remote_control.py set 255 255 255 255 255 255 255 255 255 255")
    return values


def translate_to_sdk(argv: list[str]) -> list[str] | None:
    parser = build_parser()
    parse = getattr(parser, "parse_intermixed_args", parser.parse_args)
    args = parse(argv)
    command = args.items[0] if args.items else None
    command_args = args.items[1:]

    if args.help or command is None:
        print_help()
        return None

    command = sdk.normalize_name(command)
    translated = base_args(args)

    if command in {"list", "presets", "list_presets"}:
        return translated + ["list-presets"]

    if command in {"show", "show_preset"}:
        if not command_args:
            raise SystemExit("show needs a preset name, for example: python3 remote_control.py show open")
        return translated + ["show-preset", command_args[0]]

    if command == "preset":
        if not command_args:
            raise SystemExit("preset needs a name, for example: python3 remote_control.py preset open")
        return translated + ["preset", command_args[0]]

    if command in {"set", "set_state"}:
        return translated + ["set-state", "--position"] + parse_set_values(command_args)

    if command in CONTROL_COMMANDS:
        sdk_command = command.replace("_", "-")
        if sdk_command == "boot" and args.no_can_setup:
            return translated + [sdk_command, "--no-can-setup"]
        return translated + [sdk_command]

    presets = available_presets()
    if command in presets:
        return translated + ["preset", command]

    available = ", ".join(sorted(presets)) if presets else "no presets found"
    raise SystemExit(f"Unknown command or preset: {command}\nAvailable presets: {available}")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    sdk_argv = translate_to_sdk(argv)
    if sdk_argv is None:
        return
    print("Running SDK command:", "python3 linkerhand_l10_sdk.py", shlex.join(sdk_argv))
    sdk.main(sdk_argv)


if __name__ == "__main__":
    main()
