#!/usr/bin/env python3
"""Simple terminal wrapper for the official LinkerHand Python SDK.

The official L10 get/set-state example creates LinkerHandApi, sends a pose with
finger_move(), then reads get_state(). This file keeps that same SDK path, adds
input validation, mock mode, and a small safety gate before movement.
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_HAND_TYPE = "left"
HAND_JOINT = "L10"
DEFAULT_CAN = "can0"
INTERPOLATION_HZ = 10
POSES_PATH = CURRENT_DIR / "poses_l10.json"
SEQUENCES_PATH = CURRENT_DIR / "sequences_l10.json"

JOINT_NAMES = [
    "Thumb Base",
    "Thumb Side Swing",
    "Index Base",
    "Middle Base",
    "Ring Base",
    "Little Base",
    "Index Side Swing",
    "Ring Side Swing",
    "Little Side Swing",
    "Thumb Rotation",
]

HOME_POSE = [255] * 10
ZERO_POSE = [0] * 10


class SafetyError(RuntimeError):
    """Raised when a movement command should not be sent."""


def load_sdk():
    from LinkerHand.linker_hand_api import LinkerHandApi

    return LinkerHandApi


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def normalize_name(name):
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def validate_pose(values):
    if len(values) != 10:
        raise argparse.ArgumentTypeError(f"L10 requires exactly 10 values, got {len(values)}")
    bad_values = [value for value in values if value < 0 or value > 255]
    if bad_values:
        raise argparse.ArgumentTypeError(f"values must be integers from 0 to 255, invalid: {bad_values}")
    return values


def parse_csv_values(text):
    try:
        values = [int(part.strip()) for part in text.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("values must be comma-separated integers") from exc
    return validate_pose(values)


def parse_position_values(values):
    try:
        return validate_pose([int(value) for value in values])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("position values must be integers") from exc


def print_pose(values, title):
    print(f"\n{title}")
    print("-" * len(title))
    for index, (name, value) in enumerate(zip(JOINT_NAMES, values), start=1):
        print(f"{index:2d}. {name:<18} {int(value):3d}")


def get_pose(name):
    poses = load_json(POSES_PATH)
    pose_name = normalize_name(name)
    if pose_name not in poses:
        available = ", ".join(sorted(poses))
        raise SystemExit(f"Unknown pose '{name}'. Available poses: {available}")
    return validate_pose([int(value) for value in poses[pose_name]])


def close_api(api):
    if api is None:
        return

    close_can = getattr(api, "close_can", None)
    if callable(close_can):
        try:
            close_can()
            return
        except Exception:
            pass

    hand = getattr(api, "hand", None)
    close_interface = getattr(hand, "close_can_interface", None)
    if callable(close_interface):
        try:
            close_interface()
            return
        except Exception:
            pass

    bus = getattr(hand, "bus", None)
    shutdown = getattr(bus, "shutdown", None)
    if callable(shutdown):
        shutdown()


def is_valid_version(version):
    return isinstance(version, (list, tuple)) and len(version) >= 7


def bad_serial(serial_number):
    return serial_number in (None, "", -1, "-1", [])


def valid_state(state):
    if not isinstance(state, list) or len(state) != 10:
        return False
    for value in state:
        if not isinstance(value, (int, float)) or value < 0 or value > 255:
            return False
    return True


def read_serial(api):
    serial_number = getattr(api, "serial_number", None)
    if not bad_serial(serial_number):
        return serial_number

    get_serial_number = getattr(api, "get_serial_number", None)
    if callable(get_serial_number):
        try:
            serial_number = get_serial_number()
            if not bad_serial(serial_number):
                return serial_number
        except Exception:
            pass

    hand = getattr(api, "hand", None)
    serial_number = getattr(hand, "sn", None)
    if not bad_serial(serial_number):
        return serial_number

    get_hand_serial = getattr(hand, "get_serial_number", None)
    if callable(get_hand_serial):
        try:
            serial_number = get_hand_serial()
            if not bad_serial(serial_number):
                return serial_number
        except Exception:
            pass

    return -1


def read_detection(api, attempts=3, delay=0.2):
    version = None
    serial_number = -1

    for attempt in range(1, attempts + 1):
        try:
            version = api.get_embedded_version()
        except Exception:
            version = getattr(getattr(api, "hand", None), "version", None)

        if not is_valid_version(version):
            version = getattr(getattr(api, "hand", None), "version", version)

        serial_number = read_serial(api)
        if is_valid_version(version) or not bad_serial(serial_number):
            return version, serial_number, attempt

        time.sleep(delay)

    return version, serial_number, attempts


def read_state_probe(api):
    try:
        state = api.get_state()
    except Exception:
        return None
    if valid_state(state):
        return [int(value) for value in state]
    return None


def format_version(version):
    if not is_valid_version(version):
        return "not detected"

    direction_value = int(version[3])
    direction = chr(direction_value) if 32 <= direction_value <= 126 else str(direction_value)
    software = f"V{int(version[4]) >> 4}.{int(version[4]) & 15}"
    hardware = f"V{int(version[5]) >> 4}.{int(version[5]) & 15}"
    return (
        f"degrees={version[0]}, mechanical={version[1]}, serial/index={version[2]}, "
        f"direction={direction}, software={software}, hardware={hardware}, revision={version[6]}"
    )


def connect_sdk(args, require_movement=False):
    if args.mock:
        print("[MOCK] SDK connection skipped.")
        return None, None

    print(f"Connecting with official SDK: hand_type={args.hand_type}, hand_joint={HAND_JOINT}, can={args.can}")
    api_class = load_sdk()
    api = api_class(hand_type=args.hand_type, hand_joint=HAND_JOINT, can=args.can)
    version, serial_number, attempts = read_detection(api)
    state_probe = None
    if require_movement and not (is_valid_version(version) or not bad_serial(serial_number)):
        state_probe = read_state_probe(api)

    info = {
        "version": version,
        "serial_number": serial_number,
        "attempts": attempts,
        "state_probe": state_probe,
        "detected": is_valid_version(version) or not bad_serial(serial_number) or state_probe is not None,
        "detection_source": "version/serial" if (is_valid_version(version) or not bad_serial(serial_number)) else ("state" if state_probe is not None else "none"),
    }

    print(f"Embedded version raw: {version}")
    print(f"Serial number: {serial_number}")
    print(f"Detection attempts: {attempts}")
    if state_probe is not None:
        print("Version/serial not detected, but SDK get_state() returned a valid 10-value L10 state.")

    if require_movement and not info["detected"] and not args.force:
        close_api(api)
        raise SafetyError(
            "The SDK did not detect a valid embedded version or serial number. "
            "Movement is blocked. Use --mock to test, fix the connection, or use --force only if you accept the risk."
        )

    return api, info


def current_state(api):
    state = api.get_state()
    if not valid_state(state):
        return None
    return [int(value) for value in state]


def send_pose(api, args, values, label):
    print_pose(values, f"About to send: {label}")
    if args.mock:
        print("[MOCK] No hardware command sent.")
        return

    api.finger_move(pose=values)
    time.sleep(0.01)
    print("Sent using LinkerHandApi.finger_move().")


def interpolate(start, end, duration):
    if duration <= 0:
        return [end]

    frame_count = max(1, int(math.ceil(duration * INTERPOLATION_HZ)))
    frames = []
    for frame in range(1, frame_count + 1):
        ratio = frame / frame_count
        frames.append([
            int(round(a + (b - a) * ratio))
            for a, b in zip(start, end)
        ])
    return frames


def command_status(args):
    api, info = connect_sdk(args, require_movement=False)
    try:
        if args.mock:
            info = {
                "version": None,
                "serial_number": -1,
                "attempts": 0,
                "state_probe": None,
                "detected": False,
                "detection_source": "mock",
            }

        print("\nStatus")
        print("------")
        print(f"Mode: {'mock' if args.mock else 'real'}")
        print(f"Hand Type: {args.hand_type}")
        print(f"Joint Model: {HAND_JOINT}")
        print(f"CAN Channel: {args.can}")
        print(f"Embedded Version: {info['version']}")
        print(f"Decoded Version: {format_version(info['version'])}")
        print(f"Serial Number: {info['serial_number']}")
        print(f"Detection Source: {info['detection_source']}")
        print(f"Movement Allowed: {args.mock or args.force or info['detected']}")
    finally:
        close_api(api)


def command_state(args):
    api, _info = connect_sdk(args, require_movement=False)
    try:
        values = HOME_POSE[:] if args.mock else current_state(api)
        if values is None:
            raise SystemExit("SDK returned no valid 10-value L10 state.")
        print_pose(values, "Current state")
    finally:
        close_api(api)


def command_set_state(args):
    api, _info = connect_sdk(args, require_movement=True)
    try:
        send_pose(api, args, args.position, "set-state")
        if not args.mock:
            state = current_state(api)
            if state is not None:
                print_pose(state, "Current state after set-state")
    finally:
        close_api(api)


def command_set_csv(args):
    api, _info = connect_sdk(args, require_movement=True)
    try:
        send_pose(api, args, args.values, "set")
    finally:
        close_api(api)


def command_named_pose(args, name):
    api, _info = connect_sdk(args, require_movement=True)
    try:
        send_pose(api, args, get_pose(name), name)
    finally:
        close_api(api)


def command_home(args):
    api, _info = connect_sdk(args, require_movement=True)
    try:
        send_pose(api, args, HOME_POSE, "home")
    finally:
        close_api(api)


def command_zero(args):
    api, _info = connect_sdk(args, require_movement=True)
    try:
        send_pose(api, args, ZERO_POSE, "zero")
    finally:
        close_api(api)


def command_list_poses(_args):
    print("Available poses:")
    for name in sorted(load_json(POSES_PATH)):
        print(f"  {name}")


def command_save_pose(args):
    pose_name = normalize_name(args.pose_name)
    poses = load_json(POSES_PATH)
    poses[pose_name] = args.position
    save_json(POSES_PATH, poses)
    print_pose(args.position, f"Saved pose: {pose_name}")


def command_list_sequences(_args):
    print("Available sequences:")
    for name, steps in sorted(load_json(SEQUENCES_PATH).items()):
        print(f"  {name} ({len(steps)} steps)")


def sequence_target(step):
    if "pose" in step:
        return get_pose(step["pose"]), step["pose"]
    if "values" in step:
        return validate_pose([int(value) for value in step["values"]]), "direct values"
    raise SystemExit("Each sequence step must contain either 'pose' or 'values'.")


def command_sequence(args):
    sequences = load_json(SEQUENCES_PATH)
    sequence_name = normalize_name(args.sequence_name)
    if sequence_name not in sequences:
        available = ", ".join(sorted(sequences))
        raise SystemExit(f"Unknown sequence '{args.sequence_name}'. Available sequences: {available}")

    api, _info = connect_sdk(args, require_movement=True)
    try:
        start = HOME_POSE[:] if args.mock else current_state(api)
        if start is None:
            start = HOME_POSE[:]
        print_pose(start, "Sequence start")

        for index, step in enumerate(sequences[sequence_name], start=1):
            target, label = sequence_target(step)
            duration = float(step.get("duration_seconds", 0))
            frames = interpolate(start, target, duration)
            delay = duration / len(frames) if duration > 0 else 0
            print(f"\nSequence step {index}: {label}, duration={duration:.2f}s")

            for frame_index, frame in enumerate(frames, start=1):
                send_pose(api, args, frame, f"{sequence_name} {index}/{len(sequences[sequence_name])} frame {frame_index}/{len(frames)}")
                if delay > 0:
                    time.sleep(delay)
            start = target
    except KeyboardInterrupt:
        print("\nSequence interrupted. No extra command sent.")
    finally:
        close_api(api)


def command_stop(_args):
    print("Stop requested.")
    print("This simple SDK wrapper does not invent a raw CAN stop command.")
    print("Stop a foreground sequence with Ctrl+C, or use your hardware power/emergency stop procedure.")


def command_doctor(args):
    print("Simple SDK doctor")
    print("=================")
    print("This is read-only. It does not send movement commands.")

    if sys.platform == "linux":
        if shutil.which("ip") is None:
            print("Missing 'ip'. Install with: sudo apt install iproute2")
        else:
            subprocess.run(["ip", "-statistics", "-details", "link", "show", args.can], check=False)
    command_status(args)


def build_parser():
    parser = argparse.ArgumentParser(description="Simple official-SDK terminal control for a left LinkerHand L10.")
    parser.add_argument("--mock", action="store_true", help="Print what would happen without connecting or sending.")
    parser.add_argument("--force", action="store_true", help="Allow movement even if SDK detection fails.")
    parser.add_argument("--can", default=DEFAULT_CAN, help="CAN channel passed to LinkerHandApi. Default: can0.")
    parser.add_argument("--hand-type", choices=["left", "right"], default=DEFAULT_HAND_TYPE, help="Official SDK hand_type. Default: left.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Connect with SDK and print detected version/serial.")
    subparsers.add_parser("doctor", help="Show CAN details, then run status.")
    subparsers.add_parser("state", help="Read current L10 joint state.")
    subparsers.add_parser("joints", help="Alias for state.")

    set_state_parser = subparsers.add_parser("set-state", help="Official SDK style: finger_move(position), then get_state().")
    set_state_parser.add_argument("--position", nargs=10, required=True, type=int, help="Ten L10 values separated by spaces.")

    set_parser = subparsers.add_parser("set", help="Send comma-separated 10-value pose.")
    set_parser.add_argument("--values", required=True, type=parse_csv_values, help="Example: 255,255,255,255,255,255,255,255,255,255")

    preset_parser = subparsers.add_parser("preset", help="Run a named preset alias.")
    preset_parser.add_argument("preset_name", choices=["open", "fist", "ok"], help="Preset alias.")

    pose_parser = subparsers.add_parser("pose", help="Run a pose from poses_l10.json.")
    pose_parser.add_argument("pose_name", help="Pose name.")

    save_pose_parser = subparsers.add_parser("save-pose", help="Save a pose to poses_l10.json.")
    save_pose_parser.add_argument("pose_name", help="Pose name.")
    save_pose_parser.add_argument("--position", nargs=10, required=True, type=int, help="Ten L10 values separated by spaces.")

    sequence_parser = subparsers.add_parser("sequence", help="Run a sequence from sequences_l10.json.")
    sequence_parser.add_argument("sequence_name", help="Sequence name.")

    subparsers.add_parser("home", help="Send all-255 home pose.")
    subparsers.add_parser("zero", help="Send all-zero pose.")
    subparsers.add_parser("stop", help="Print safe stop instructions.")
    subparsers.add_parser("list-poses", help="List saved poses.")
    subparsers.add_parser("list-sequences", help="List saved sequences.")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "position", None) is not None:
        args.position = parse_position_values(args.position)

    try:
        if args.command == "status":
            command_status(args)
        elif args.command == "doctor":
            command_doctor(args)
        elif args.command in ("state", "joints"):
            command_state(args)
        elif args.command == "set-state":
            command_set_state(args)
        elif args.command == "set":
            command_set_csv(args)
        elif args.command == "preset":
            command_named_pose(args, args.preset_name)
        elif args.command == "pose":
            command_named_pose(args, args.pose_name)
        elif args.command == "save-pose":
            command_save_pose(args)
        elif args.command == "sequence":
            command_sequence(args)
        elif args.command == "home":
            command_home(args)
        elif args.command == "zero":
            command_zero(args)
        elif args.command == "stop":
            command_stop(args)
        elif args.command == "list-poses":
            command_list_poses(args)
        elif args.command == "list-sequences":
            command_list_sequences(args)
        else:
            parser.error(f"unknown command: {args.command}")
    except SafetyError as exc:
        raise SystemExit(f"SAFETY BLOCK: {exc}") from exc


if __name__ == "__main__":
    main()
