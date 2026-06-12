#!/usr/bin/env python3
"""Safe terminal controller for a left LinkerHand L10.

This tool reuses LinkerHandApi, the same SDK layer used by the PyQt GUI.
It does not write raw CAN frames and does not change setting.yaml.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
sys.path.append(str(REPO_ROOT))


PHYSICAL_HAND_TYPE = "left"
DEFAULT_SDK_HAND_TYPE = "left"
HAND_JOINT = "L10"
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
INTERPOLATION_HZ = 10
DETECTION_ATTEMPTS = 5
DETECTION_DELAY_SECONDS = 0.2
POSES_PATH = CURRENT_DIR / "poses_l10.json"
SEQUENCES_PATH = CURRENT_DIR / "sequences_l10.json"
LinkerHandApi = None


class SafetyError(RuntimeError):
    """Raised when a real hardware command should be blocked."""


def load_linker_hand_api():
    """Import the SDK only when a real hardware read/write needs it."""
    global LinkerHandApi
    if LinkerHandApi is None:
        from LinkerHand.linker_hand_api import LinkerHandApi as sdk_api  # noqa: WPS433

        LinkerHandApi = sdk_api
    return LinkerHandApi


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def parse_values(values_text):
    try:
        values = [int(part.strip()) for part in values_text.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("values must be comma-separated integers") from exc
    return validate_pose(values)


def validate_pose(values):
    if len(values) != 10:
        raise argparse.ArgumentTypeError(f"exactly 10 values are required, got {len(values)}")
    bad_values = [value for value in values if not isinstance(value, int) or value < 0 or value > 255]
    if bad_values:
        raise argparse.ArgumentTypeError(f"each value must be an integer from 0 to 255, invalid: {bad_values}")
    return values


def print_pose(values, title="Joint command"):
    print(f"\n{title}")
    print("-" * len(title))
    for index, (name, value) in enumerate(zip(JOINT_NAMES, values), start=1):
        print(f"{index:2d}. {name:<18} {value:3d}")


def normalize_name(name):
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def get_pose(name):
    poses = load_json(POSES_PATH)
    pose_name = normalize_name(name)
    if pose_name not in poses:
        available = ", ".join(sorted(poses))
        raise SystemExit(f"Unknown pose '{name}'. Available poses: {available}")
    return validate_pose(poses[pose_name])


def is_bad_serial(serial_number):
    return serial_number in (None, "", -1, "-1")


def embedded_serial_number(version):
    """Infer the SDK hardware serial/version index.

    The L10 CAN class exposes embedded version bytes from get_version().
    Byte index 2 is labeled as the version serial number in show_fun_table().
    Missing/empty data is treated as -1 for safety.
    """
    if version in (None, [], -1):
        return -1
    if isinstance(version, int):
        return version
    if isinstance(version, (list, tuple)) and len(version) >= 3:
        return int(version[2])
    return -1


def normalize_serial_number(serial_number):
    if serial_number in (None, "", -1, "-1"):
        return -1
    return serial_number


def is_valid_embedded_version(version):
    return isinstance(version, (list, tuple)) and len(version) >= 7


def describe_embedded_version(version):
    if not is_valid_embedded_version(version):
        return "No valid embedded version reply."

    direction_value = version[3]
    direction = chr(direction_value) if isinstance(direction_value, int) and 32 <= direction_value <= 126 else str(direction_value)
    software = f"V{version[4] >> 4}.{version[4] & 0x0F}"
    hardware = f"V{version[5] >> 4}.{version[5] & 0x0F}"
    return (
        f"degrees={version[0]}, mechanical={version[1]}, serial/index={version[2]}, "
        f"direction={direction}, software={software}, hardware={hardware}, revision={version[6]}"
    )


def sdk_hand_type(args):
    return getattr(args, "sdk_hand_type", DEFAULT_SDK_HAND_TYPE)


def read_sdk_serial_number(api):
    """Read serial number when the installed SDK exposes it.

    SDK 2.1.x does not expose get_serial_number() for L10, while newer SDKs may.
    Missing serial support is not treated as an exception; the embedded version
    read remains the main L10 detection path.
    """
    serial_number = getattr(api, "serial_number", None)
    if not is_bad_serial(serial_number):
        return normalize_serial_number(serial_number)

    for owner in (api, getattr(api, "hand", None)):
        if owner is None:
            continue
        get_serial = getattr(owner, "get_serial_number", None)
        if not callable(get_serial):
            continue
        try:
            serial_number = get_serial()
        except Exception:
            continue
        if not is_bad_serial(serial_number):
            return normalize_serial_number(serial_number)

    return -1


def read_detection(api):
    """Read hand detection data with retries for the SDK receive thread.

    The L10 CAN class updates embedded version data from a background receive
    thread. A single immediate get_embedded_version() call can return None if
    the reply arrives slightly later, so this helper retries without changing
    any low-level CAN behavior.
    """
    version = None
    serial_number = -1

    for attempt in range(1, DETECTION_ATTEMPTS + 1):
        try:
            version = api.get_embedded_version()
        except Exception:
            version = getattr(getattr(api, "hand", None), "version", None)

        if not is_valid_embedded_version(version):
            version = getattr(getattr(api, "hand", None), "version", version)

        if is_valid_embedded_version(version):
            serial_number = embedded_serial_number(version)
            return version, serial_number, attempt

        serial_number = read_sdk_serial_number(api)
        if not is_bad_serial(serial_number):
            return version, serial_number, attempt

        time.sleep(DETECTION_DELAY_SECONDS)

    return version, serial_number, DETECTION_ATTEMPTS


def connect_api(args, require_movement=False):
    if args.mock:
        print("[MOCK] Hardware connection skipped.")
        return None, -1, None

    hand_type = sdk_hand_type(args)
    print(f"Connecting through SDK: hand_type={hand_type}, hand_joint={HAND_JOINT}, can={args.can}")
    if hand_type != PHYSICAL_HAND_TYPE:
        print(
            f"Note: physical hand is treated as {PHYSICAL_HAND_TYPE}, "
            f"but SDK hand_type={hand_type} is being used for CAN addressing."
        )
    try:
        sdk_api = load_linker_hand_api()
        api = sdk_api(hand_type=hand_type, hand_joint=HAND_JOINT, can=args.can)
        version, serial_number, detection_attempts = read_detection(api)
    except Exception as exc:
        message = f"Hand connection failed: {exc}"
        if require_movement:
            raise SafetyError(message) from exc
        print(message)
        return None, -1, None

    print(f"Embedded version raw: {version}")
    print(f"Detected serial/version number: {serial_number}")
    print(f"Detection attempts: {detection_attempts}")

    if require_movement and is_bad_serial(serial_number) and not args.force:
        close_api(api)
        raise SafetyError(
            "Hardware serial/version number is -1 or not detected. "
            "Real movement is blocked. Use --mock to test commands or fix the connection. "
            "Use --force only if you intentionally accept the risk."
        )
    return api, serial_number, version


def probe_embedded_version(hand_type, can_channel):
    print(f"\nRead-only SDK probe: hand_type={hand_type}, hand_joint={HAND_JOINT}, can={can_channel}")
    api = None
    try:
        sdk_api = load_linker_hand_api()
        api = sdk_api(hand_type=hand_type, hand_joint=HAND_JOINT, can=can_channel)
        version, serial_number, detection_attempts = read_detection(api)
        print(f"CAN ID: {hex(api.hand_id)}")
        print(f"Embedded version raw: {version}")
        print(f"Detected serial/version number: {serial_number}")
        print(f"Detection attempts: {detection_attempts}")
        print(describe_embedded_version(version))
        return {
            "hand_type": hand_type,
            "version": version,
            "serial_number": serial_number,
            "detection_attempts": detection_attempts,
        }
    except Exception as exc:
        print(f"Probe failed: {exc}")
        return {
            "hand_type": hand_type,
            "version": None,
            "serial_number": -1,
            "detection_attempts": 0,
            "error": str(exc),
        }
    finally:
        close_api(api)


def close_api(api):
    if api is None:
        return
    hand = getattr(api, "hand", None)
    close_method = getattr(hand, "close_can_interface", None)
    if callable(close_method):
        close_method()
        return
    bus = getattr(hand, "bus", None)
    shutdown = getattr(bus, "shutdown", None)
    if callable(shutdown):
        shutdown()


def run_system(command):
    try:
        return subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return None


def parse_counter_block(lines, prefix):
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(f"{prefix}:"):
            continue
        headers = stripped.split(":", 1)[1].split()
        if index + 1 >= len(lines):
            return {}
        values = []
        for part in lines[index + 1].split():
            try:
                values.append(int(part))
            except ValueError:
                pass
        return dict(zip(headers, values))
    return {}


def parse_can_counters(ip_output):
    lines = ip_output.splitlines()
    return {
        "rx": parse_counter_block(lines, "RX"),
        "tx": parse_counter_block(lines, "TX"),
    }


def counter_delta(before, after, section, key):
    return after.get(section, {}).get(key, 0) - before.get(section, {}).get(key, 0)


def show_can_interface(can_channel):
    result = run_system(["ip", "-statistics", "-details", "link", "show", can_channel])
    if result is None:
        print("The 'ip' command was not found. Install iproute2/can-utils on Linux.")
        return {}, ""
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip())
        return {}, result.stdout

    print(result.stdout.rstrip())
    counters = parse_can_counters(result.stdout)
    return counters, result.stdout


def summarize_can_flags(ip_output):
    first_line = next((line for line in ip_output.splitlines() if line.strip()), "")
    flag_match = re.search(r"<([^>]+)>", first_line)
    flags = set(flag_match.group(1).split(",")) if flag_match else set()
    state_match = re.search(r"\bstate\s+(\S+)", first_line)
    state = state_match.group(1) if state_match else "unknown"
    bitrate_ok = "bitrate 1000000" in ip_output

    print("\nCAN interface interpretation")
    print("----------------------------")
    print(f"State: {state}")
    print(f"Flags: {', '.join(sorted(flags)) if flags else 'not detected'}")
    print(f"Bitrate 1000000: {'yes' if bitrate_ok else 'no or not shown'}")

    if "UP" not in flags:
        print("Problem: interface is not UP. Run 'make can-reset'.")
    if "LOWER_UP" not in flags:
        print("Problem: adapter link is not LOWER_UP. Replug USB-CAN and check the driver.")
    if not bitrate_ok:
        print("Problem: bitrate does not show 1000000. Run 'make can-reset'.")


def send_pose(api, args, values, label):
    print_pose(values, title=f"About to send: {label}")
    if args.mock:
        print("[MOCK] No hardware command sent.")
        return
    api.finger_move(pose=values)
    print("Command sent through LinkerHandApi.finger_move().")


def current_state(api):
    if api is None:
        return HOME_POSE[:]
    state = api.get_state()
    if not isinstance(state, list) or len(state) != 10:
        return HOME_POSE[:]
    if any(value == -1 for value in state):
        return HOME_POSE[:]
    return [int(value) for value in state]


def interpolate(start, end, duration_seconds):
    if duration_seconds <= 0:
        return [end]
    steps = max(1, int(math.ceil(duration_seconds * INTERPOLATION_HZ)))
    frames = []
    for step in range(1, steps + 1):
        ratio = step / steps
        frames.append([
            int(round(start_value + (end_value - start_value) * ratio))
            for start_value, end_value in zip(start, end)
        ])
    return frames


def command_status(args):
    api, serial_number, version = connect_api(args, require_movement=False)
    try:
        print("\nStatus")
        print("------")
        print(f"Mode: {'mock' if args.mock else 'real'}")
        print(f"Physical Hand Type: {PHYSICAL_HAND_TYPE}")
        print(f"SDK Hand Type: {sdk_hand_type(args)}")
        print(f"Joint Model: {HAND_JOINT}")
        print(f"CAN Channel: {args.can}")
        print(f"Embedded Version: {version}")
        print(f"Serial/Version Number: {serial_number}")
        print(f"Movement Allowed: {args.mock or args.force or not is_bad_serial(serial_number)}")
    finally:
        close_api(api)


def command_doctor(args):
    print("L10 CAN doctor")
    print("==============")
    print("This command performs read-only checks and does not send movement commands.")
    print(f"CAN Channel: {args.can}")
    print(f"Selected SDK Hand Type: {sdk_hand_type(args)}")

    if sys.platform != "linux":
        print("Doctor is intended for Linux SocketCAN systems.")
        return

    if shutil.which("ip") is None:
        print("Missing 'ip'. Install it with: sudo apt install iproute2")
        return

    if shutil.which("candump") is None:
        print("Note: 'candump' not found. Install it with: sudo apt install can-utils")

    print("\nCAN counters before SDK probe")
    print("-----------------------------")
    before, ip_output = show_can_interface(args.can)
    summarize_can_flags(ip_output)

    probe_results = []
    if args.mock:
        print("\n[MOCK] SDK probe skipped.")
    else:
        probe_results.append(probe_embedded_version("left", args.can))
        probe_results.append(probe_embedded_version("right", args.can))

    print("\nCAN counters after SDK probe")
    print("----------------------------")
    after, _ = show_can_interface(args.can)

    rx_packets = counter_delta(before, after, "rx", "packets")
    tx_packets = counter_delta(before, after, "tx", "packets")
    rx_errors = counter_delta(before, after, "rx", "errors")
    tx_errors = counter_delta(before, after, "tx", "errors")

    print("\nDoctor conclusion")
    print("-----------------")
    detected = [
        result for result in probe_results
        if is_valid_embedded_version(result["version"]) or not is_bad_serial(result["serial_number"])
    ]
    if detected:
        for result in detected:
            print(f"Detected hand data on hand_type={result['hand_type']}:")
            print(f"  Embedded: {describe_embedded_version(result['version'])}")
            print(f"  Serial/version number: {result['serial_number']}")
            if result["hand_type"] != sdk_hand_type(args):
                print(f"  To use this SDK ID, run: make HAND_TYPE={result['hand_type']} status")
        print("The SDK can read the hand. Use status again before sending any real movement.")
        return

    print(f"Packet delta during probe: RX={rx_packets}, TX={tx_packets}, RX errors={rx_errors}, TX errors={tx_errors}")
    if tx_errors > 0 or rx_errors > 0:
        print("CAN errors increased. Check CAN-H/CAN-L wiring, termination, bitrate, hand power, and USB-CAN adapter.")
    elif tx_packets > 0 and rx_packets == 0:
        print("The computer sent SDK version requests, but no reply was received from the hand.")
        print("Most likely causes: hand not powered, CAN-H/CAN-L swapped, missing GND, no termination, loose connector, or adapter issue.")
    elif rx_packets > 0:
        print("CAN traffic was received, but the SDK did not parse a valid L10 version.")
        print("Run 'make candump' in one terminal and 'make status' in another, then compare the received frame IDs/data.")
    else:
        print("No CAN traffic changed during the SDK probe. Check that the adapter is really can0 and that no process is holding it.")


def command_joints(args):
    api, _, _ = connect_api(args, require_movement=False)
    try:
        values = HOME_POSE[:] if args.mock else current_state(api)
        print_pose(values, title="Current joint values")
    finally:
        close_api(api)


def command_set(args):
    api, _, _ = connect_api(args, require_movement=True)
    try:
        send_pose(api, args, args.values, "direct joint values")
    finally:
        close_api(api)


def command_named_pose(args, pose_name):
    values = get_pose(pose_name)
    api, _, _ = connect_api(args, require_movement=True)
    try:
        send_pose(api, args, values, pose_name)
    finally:
        close_api(api)


def command_home(args):
    api, _, _ = connect_api(args, require_movement=True)
    try:
        send_pose(api, args, HOME_POSE, "home")
    finally:
        close_api(api)


def command_stop(args):
    print("Stop requested.")
    print("No raw CAN stop frame is sent by this terminal tool.")
    print("Foreground terminal sequences stop when this process exits or when Ctrl+C is pressed.")
    print("If another terminal process is running a sequence, stop that process directly.")


def command_list_poses(_args):
    poses = load_json(POSES_PATH)
    print("Available poses:")
    for name in sorted(poses):
        print(f"  {name}")


def command_save_pose(args):
    pose_name = normalize_name(args.pose_name)
    poses = load_json(POSES_PATH)
    poses[pose_name] = args.values
    save_json(POSES_PATH, poses)
    print_pose(args.values, title=f"Saved pose: {pose_name}")
    print(f"Updated {POSES_PATH}")


def command_list_sequences(_args):
    sequences = load_json(SEQUENCES_PATH)
    print("Available sequences:")
    for name, steps in sorted(sequences.items()):
        print(f"  {name} ({len(steps)} steps)")


def step_target(step):
    if "pose" in step:
        return get_pose(step["pose"]), step["pose"]
    if "values" in step:
        return validate_pose(step["values"]), "direct values"
    raise SystemExit("Each sequence step must contain either 'pose' or 'values'.")


def command_sequence(args):
    sequences = load_json(SEQUENCES_PATH)
    sequence_name = normalize_name(args.sequence_name)
    if sequence_name not in sequences:
        available = ", ".join(sorted(sequences))
        raise SystemExit(f"Unknown sequence '{args.sequence_name}'. Available sequences: {available}")

    api, _, _ = connect_api(args, require_movement=True)
    try:
        start = current_state(api)
        print_pose(start, title="Sequence start pose")
        for index, step in enumerate(sequences[sequence_name], start=1):
            target, label = step_target(step)
            duration = float(step.get("duration_seconds", 0))
            print(f"\nSequence step {index}: {label}, duration={duration:.2f}s")
            frames = interpolate(start, target, duration)
            frame_delay = (duration / len(frames)) if duration > 0 else 0
            for frame_index, frame in enumerate(frames, start=1):
                send_pose(api, args, frame, f"{sequence_name} step {index}/{len(sequences[sequence_name])} frame {frame_index}/{len(frames)}")
                if frame_delay > 0:
                    time.sleep(frame_delay)
            start = target
    except KeyboardInterrupt:
        print("\nSequence interrupted by user. No additional command sent.")
    finally:
        close_api(api)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Safe terminal controller for a left LinkerHand L10.",
    )
    parser.add_argument("--mock", action="store_true", help="Print commands without connecting or sending to hardware.")
    parser.add_argument("--force", action="store_true", help="Allow movement even if hardware serial/version is not detected.")
    parser.add_argument("--can", default="can0", help="CAN channel passed to LinkerHandApi. Default: can0.")
    parser.add_argument(
        "--sdk-hand-type",
        choices=["left", "right"],
        default=DEFAULT_SDK_HAND_TYPE,
        help="SDK hand_type/CAN ID to use. Default: left. Try right if doctor detects the hand on the right SDK ID.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Connect and print SDK/hardware status.")
    subparsers.add_parser("doctor", help="Run read-only CAN/SDK diagnostics for connection debugging.")
    subparsers.add_parser("joints", help="Read and print current joint values.")

    set_parser = subparsers.add_parser("set", help="Send direct L10 joint values.")
    set_parser.add_argument("--values", required=True, type=parse_values, help="Comma-separated 10-value pose.")

    preset_parser = subparsers.add_parser("preset", help="Run a built-in preset alias.")
    preset_parser.add_argument("preset_name", choices=["open", "fist", "ok"], help="Preset alias to run.")

    subparsers.add_parser("home", help="Return to initial all-255 home pose.")
    subparsers.add_parser("stop", help="Explain how to stop terminal-controlled actions safely.")
    subparsers.add_parser("list-poses", help="List poses from poses_l10.json.")

    pose_parser = subparsers.add_parser("pose", help="Run any named pose from poses_l10.json.")
    pose_parser.add_argument("pose_name", help="Pose name.")

    save_pose_parser = subparsers.add_parser("save-pose", help="Save a named pose to poses_l10.json.")
    save_pose_parser.add_argument("pose_name", help="Pose name to create/update.")
    save_pose_parser.add_argument("--values", required=True, type=parse_values, help="Comma-separated 10-value pose.")

    subparsers.add_parser("list-sequences", help="List sequences from sequences_l10.json.")

    sequence_parser = subparsers.add_parser("sequence", help="Run a named sequence from sequences_l10.json.")
    sequence_parser.add_argument("sequence_name", help="Sequence name.")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            command_status(args)
        elif args.command == "doctor":
            command_doctor(args)
        elif args.command == "joints":
            command_joints(args)
        elif args.command == "set":
            command_set(args)
        elif args.command == "preset":
            command_named_pose(args, args.preset_name)
        elif args.command == "home":
            command_home(args)
        elif args.command == "stop":
            command_stop(args)
        elif args.command == "list-poses":
            command_list_poses(args)
        elif args.command == "pose":
            command_named_pose(args, args.pose_name)
        elif args.command == "save-pose":
            command_save_pose(args)
        elif args.command == "list-sequences":
            command_list_sequences(args)
        elif args.command == "sequence":
            command_sequence(args)
        else:
            parser.error(f"unknown command: {args.command}")
    except SafetyError as exc:
        raise SystemExit(f"SAFETY BLOCK: {exc}") from exc


if __name__ == "__main__":
    main()
