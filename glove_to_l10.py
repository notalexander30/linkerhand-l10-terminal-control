#!/usr/bin/env python3
"""Bridge a USB KTH5702 glove text stream to a left LinkerHand L10.

The glove shown by the serial console prints lines like:

    KTH5702: | 拇指 | 0 | 0x68 | 193.50° | -30311 | 正常 | 0 |

This script reads those lines from /dev/ttyUSB0, parses the 15 sensor angles,
maps selected glove points to the 10 L10 joint values, ignores glove points
that do not exist on L10, and can send through the official LinkerHand Python
SDK.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import linkerhand_l10_sdk as sdk  # noqa: E402


DEFAULT_CALIBRATION = REPO_ROOT / "glove_l10_calibration.json"
SENSOR_COUNT = 15
OPEN_POSE = [255, 70, 255, 255, 255, 255, 255, 255, 255, 255]
FIST_POSE = [90, 0, 0, 0, 0, 0, 128, 67, 89, 197]

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

FINGER_GROUPS = {
    "thumb": [0, 1, 2],
    "index": [3, 4, 5],
    "middle": [6, 7, 8],
    "ring": [9, 10, 11],
    "little": [12, 13, 14],
}

POSE_GROUPS = {
    "thumb": [0, 1, 9],
    "index": [2, 6],
    "middle": [3],
    "ring": [4, 7],
    "little": [5, 8],
}

FINGER_NAMES = ["index", "middle", "ring", "little"]

DIRECT_L10_SENSOR_TO_JOINT = {
    0: 0,   # thumb sensor 0 -> Thumb Base
    1: 1,   # thumb sensor 1 -> Thumb Side Swing
    2: 9,   # thumb sensor 2 -> Thumb Rotation
    3: 2,   # index sensor 0 -> Index Base
    4: 6,   # index sensor 1 -> Index Side Swing
    6: 3,   # middle sensor 0 -> Middle Base
    9: 4,   # ring sensor 0 -> Ring Base
    10: 7,  # ring sensor 1 -> Ring Side Swing
    12: 5,  # little sensor 0 -> Little Base
    13: 8,  # little sensor 1 -> Little Side Swing
}

IGNORED_DIRECT_L10_SENSORS = [5, 7, 8, 11, 14]
DIRECT_L10_SENSOR_FINGER = {
    0: "thumb",
    1: "thumb",
    2: "thumb",
    3: "index",
    4: "index",
    6: "middle",
    9: "ring",
    10: "ring",
    12: "little",
    13: "little",
}

SELECTABLE_FINGERS = ["all", "thumb", "index", "middle", "ring", "little"]


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def parse_sensor_line(line: str) -> tuple[int, float] | None:
    clean = strip_ansi(line).replace("\\x1b", "").strip()
    if "KTH5702:" not in clean or "|" not in clean:
        return None

    parts = [part.strip() for part in clean.split("|")]
    if len(parts) < 8:
        return None

    try:
        angle_match = re.search(r"-?\d+(?:\.\d+)?", parts[4])
        if angle_match is None:
            return None
        angle = float(angle_match.group(0))
        sensor_index = int(parts[7])
    except (ValueError, IndexError):
        return None

    if 0 <= sensor_index < SENSOR_COUNT:
        return sensor_index, angle
    return None


def open_serial(port: str, baud: int):
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("Missing pyserial. Install it with: python3 -m pip install pyserial") from exc

    try:
        return serial.Serial(port, baudrate=baud, timeout=1)
    except PermissionError as exc:
        raise SystemExit(
            f"No permission to open {port}. Run: sudo usermod -aG dialout $USER && newgrp dialout"
        ) from exc
    except OSError as exc:
        raise SystemExit(f"Could not open {port}: {exc}") from exc


def glove_frames(port: str, baud: int):
    angles: dict[int, float] = {}
    with open_serial(port, baud) as serial_port:
        print(f"Reading glove from {port} at {baud} baud. Press Ctrl+C to stop.")
        while True:
            raw = serial_port.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore")
            parsed = parse_sensor_line(line)
            if parsed is None:
                continue
            index, angle = parsed
            angles[index] = angle
            if index == SENSOR_COUNT - 1 and len(angles) == SENSOR_COUNT:
                yield dict(angles)


def collect_calibration(port: str, baud: int, seconds: float) -> dict[str, float]:
    print(f"Collecting calibration for {seconds:.1f} seconds...")
    deadline = time.monotonic() + seconds
    samples: list[dict[int, float]] = []
    for frame in glove_frames(port, baud):
        samples.append(frame)
        if time.monotonic() >= deadline:
            break

    if len(samples) < 3:
        raise SystemExit("Not enough glove samples. Check the port, baud rate, and glove power.")

    calibration: dict[str, float] = {}
    for index in range(SENSOR_COUNT):
        values = [sample[index] for sample in samples if index in sample]
        if not values:
            raise SystemExit(f"Sensor {index} did not appear during calibration.")
        calibration[str(index)] = round(float(statistics.median(values)), 4)
    return calibration


def load_calibration(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Calibration file not found: {path}\n"
            "First run open and fist calibration commands shown below."
        )
    with path.open("r", encoding="utf-8") as file:
        calibration = json.load(file)
    if "open" not in calibration or "fist" not in calibration:
        raise SystemExit(f"Calibration file is incomplete: {path}")
    return calibration


def save_calibration(path: Path, name: str, values: dict[str, float]) -> None:
    calibration = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            calibration = json.load(file)
    calibration[name] = values
    calibration["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    calibration["source"] = "KTH5702 USB serial text"
    with path.open("w", encoding="utf-8") as file:
        json.dump(calibration, file, indent=2)
        file.write("\n")
    print(f"Saved {name} calibration to {path}")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def sensor_flex(index: int, angle: float, open_angles: dict, fist_angles: dict) -> float | None:
    key = str(index)
    if key not in open_angles or key not in fist_angles:
        return None
    open_angle = float(open_angles[key])
    fist_angle = float(fist_angles[key])
    span = fist_angle - open_angle
    if abs(span) < 1e-6:
        return None
    return clamp((angle - open_angle) / span)


def sensor_flex_map(frame: dict[int, float], open_angles: dict, fist_angles: dict) -> dict[int, float]:
    result: dict[int, float] = {}
    for index, angle in frame.items():
        value = sensor_flex(index, angle, open_angles, fist_angles)
        if value is not None:
            result[index] = value
    return result


def gain_amount(value: float, gain: float) -> float:
    return clamp(value * gain)


def tuned_amount(value: float, args) -> float:
    value = clamp(value)
    deadzone = clamp(args.deadzone, 0.0, 0.95)
    if value <= deadzone:
        return 0.0
    value = (value - deadzone) / (1.0 - deadzone)
    return clamp(value ** max(args.curve, 0.05))


def joint_value(joint: int, amount: float) -> int:
    value = OPEN_POSE[joint] + amount * (FIST_POSE[joint] - OPEN_POSE[joint])
    return int(round(clamp(value, 0, 255)))


def combine_flex_values(values: list[float], mode: str) -> float:
    if not values:
        return 0.0
    if mode == "max":
        return max(values)
    if mode == "min":
        return min(values)
    return float(statistics.mean(values))


def finger_flex(
    frame: dict[int, float],
    open_angles: dict,
    fist_angles: dict,
    mode: str = "max",
) -> dict[str, float]:
    result: dict[str, float] = {}
    for finger, indexes in FINGER_GROUPS.items():
        values = [
            sensor_flex(index, frame[index], open_angles, fist_angles)
            for index in indexes
            if index in frame
        ]
        values = [value for value in values if value is not None]
        result[finger] = combine_flex_values(values, mode)
    return result


def pose_from_flex(flex: dict[str, float], args=None) -> list[int]:
    pose = list(OPEN_POSE)
    for finger, joints in POSE_GROUPS.items():
        amount = flex.get(finger, 0.0)
        if args is not None:
            amount = tuned_amount(amount, args)
        if finger in FINGER_NAMES and args is not None:
            amount = gain_amount(amount, finger_gain(args, finger))
        for joint in joints:
            pose[joint] = joint_value(joint, amount)
    return pose


def pose_from_direct_l10(frame: dict[int, float], open_angles: dict, fist_angles: dict, args) -> tuple[dict[str, float], dict[int, float], list[int]]:
    sensor_amounts = sensor_flex_map(frame, open_angles, fist_angles)
    flex: dict[str, float] = {}
    pose = list(OPEN_POSE)

    for sensor_index, joint in DIRECT_L10_SENSOR_TO_JOINT.items():
        finger = DIRECT_L10_SENSOR_FINGER[sensor_index]
        amount = tuned_amount(sensor_amounts.get(sensor_index, 0.0), args)
        if finger == "thumb":
            amount = gain_amount(amount, args.thumb_gain)
            if args.invert_thumb:
                amount = 1.0 - amount
        else:
            amount = gain_amount(amount, finger_gain(args, finger))
            if is_finger_inverted(args, finger):
                amount = 1.0 - amount

        pose[joint] = joint_value(joint, amount)
        flex[f"{finger}_s{sensor_index}_j{joint}"] = amount

    return flex, sensor_amounts, pose


def pose_from_glove(frame: dict[int, float], open_angles: dict, fist_angles: dict, args) -> tuple[dict[str, float], dict[int, float], list[int]]:
    if args.mapping == "direct-l10":
        flex, sensor_amounts, pose = pose_from_direct_l10(frame, open_angles, fist_angles, args)
        return flex, sensor_amounts, apply_joint_selection(pose, args)

    flex = finger_flex(frame, open_angles, fist_angles, args.finger_mode)
    sensor_amounts = sensor_flex_map(frame, open_angles, fist_angles)
    pose = pose_from_flex(flex, args)

    if args.thumb_mode == "follow-index":
        thumb_base = flex.get("index", 0.0)
        thumb_side = flex.get("index", 0.0)
        thumb_rotation = flex.get("index", 0.0)
    elif args.thumb_mode == "average":
        thumb_base = flex.get("thumb", 0.0)
        thumb_side = flex.get("thumb", 0.0)
        thumb_rotation = flex.get("thumb", 0.0)
    else:
        thumb_base = sensor_amounts.get(0, flex.get("thumb", 0.0))
        thumb_side = sensor_amounts.get(1, flex.get("thumb", 0.0))
        thumb_rotation = sensor_amounts.get(2, flex.get("thumb", 0.0))

    thumb_base = tuned_amount(thumb_base, args)
    thumb_side = tuned_amount(thumb_side, args)
    thumb_rotation = tuned_amount(thumb_rotation, args)
    thumb_base = gain_amount(thumb_base, args.thumb_gain)
    thumb_side = gain_amount(thumb_side, args.thumb_gain)
    thumb_rotation = gain_amount(thumb_rotation, args.thumb_gain)

    if args.invert_thumb:
        thumb_base = 1.0 - thumb_base
        thumb_side = 1.0 - thumb_side
        thumb_rotation = 1.0 - thumb_rotation

    pose[0] = joint_value(0, thumb_base)
    pose[1] = joint_value(1, thumb_side)
    pose[9] = joint_value(9, thumb_rotation)
    flex["thumb_base"] = thumb_base
    flex["thumb_side"] = thumb_side
    flex["thumb_rotation"] = thumb_rotation
    return flex, sensor_amounts, apply_joint_selection(pose, args)


def selected_joints(args) -> list[int]:
    joints: set[int]
    if args.only_joint:
        joints = set(args.only_joint)
    elif args.only == "all":
        joints = set(range(len(OPEN_POSE)))
    else:
        joints = set(POSE_GROUPS[args.only])
    return sorted(joints)


def apply_joint_selection(pose: list[int], args) -> list[int]:
    joints = selected_joints(args)
    if len(joints) == len(OPEN_POSE):
        return pose
    filtered = list(OPEN_POSE)
    for joint in joints:
        filtered[joint] = pose[joint]
    return filtered


def smooth_pose(previous: list[int] | None, pose: list[int], smoothing: float) -> list[int]:
    smoothing = clamp(smoothing, 0.0, 0.98)
    if previous is None or smoothing <= 0.0:
        return pose
    return [
        int(round(previous_value * smoothing + current_value * (1.0 - smoothing)))
        for previous_value, current_value in zip(previous, pose)
    ]


def is_finger_inverted(args, finger: str) -> bool:
    specific = getattr(args, f"invert_{finger}")
    return bool(args.invert_fingers or specific)


def finger_gain(args, finger: str) -> float:
    specific = getattr(args, f"{finger}_gain")
    if specific is not None:
        return specific
    return args.finger_gain


def connect_hand(args):
    sdk_args = SimpleNamespace(can=args.hand_can, hand_type=args.hand, force=args.force)
    api, info = sdk.connect_sdk(sdk_args)
    sdk.require_detected(sdk_args, info)
    return api


def close_hand(api) -> None:
    sdk.close_sdk(api)


def joint_name(index: int) -> str:
    if 0 <= index < len(sdk.JOINT_NAMES):
        return sdk.JOINT_NAMES[index]
    return f"Joint {index}"


def print_preview(
    frame: dict[int, float],
    flex: dict[str, float] | None,
    pose: list[int] | None,
    args,
    last_frame: dict[int, float] | None = None,
    last_pose: list[int] | None = None,
) -> None:
    if args.print_mode == "quiet":
        return

    angles = " ".join(f"{index}:{frame[index]:.1f}" for index in range(SENSOR_COUNT) if index in frame)
    if args.print_mode == "full" or last_frame is None:
        print(f"angles {angles}")
    elif last_frame is not None:
        angle_changes = [
            f"s{index}:{frame[index]:.1f}"
            for index in range(SENSOR_COUNT)
            if index in frame and abs(frame[index] - last_frame.get(index, frame[index])) >= args.angle_threshold
        ]
        if angle_changes:
            print("changed sensors " + " ".join(angle_changes))

    if flex is not None and pose is not None:
        if args.print_mode == "full":
            flex_text = " ".join(f"{finger}={value:.2f}" for finger, value in flex.items())
            print(f"flex {flex_text}")
            print(f"pose {pose}")
            return

        joint_changes = [
            f"j{joint}:{joint_name(joint)}={pose[joint]}"
            for joint in selected_joints(args)
            if last_pose is None or abs(pose[joint] - last_pose[joint]) >= args.change_threshold
        ]
        if joint_changes:
            print("changed joints " + " | ".join(joint_changes))


def run_bridge(args) -> None:
    calibration = load_calibration(args.calibration)
    open_angles = calibration["open"]
    fist_angles = calibration["fist"]
    api = None
    if args.send:
        api = connect_hand(args)
        print("LIVE SEND IS ON. Keep the hand clear. Press Ctrl+C to stop.")
    else:
        print("Preview only. Add --send when the mapping looks correct.")
    if args.mapping == "direct-l10":
        ignored = ", ".join(str(index) for index in IGNORED_DIRECT_L10_SENSORS)
        print(f"Mapping: direct-l10. Ignoring glove sensors: {ignored}")
    else:
        print(f"Mapping: combined. Finger mode: {args.finger_mode}")
    joints = selected_joints(args)
    if len(joints) < len(OPEN_POSE):
        joint_text = ", ".join(f"j{joint}:{joint_name(joint)}" for joint in joints)
        print(f"Tuning only: {joint_text}. Other L10 joints stay open.")
    print(
        f"Tuning: deadzone={args.deadzone}, curve={args.curve}, "
        f"smoothing={args.smoothing}, print-mode={args.print_mode}"
    )

    min_interval = 1.0 / max(args.rate, 1.0)
    last_send = 0.0
    last_frame = None
    last_pose = None
    previous_pose = None
    try:
        for frame in glove_frames(args.glove_port, args.baud):
            now = time.monotonic()
            if now - last_send < min_interval:
                continue
            last_send = now

            flex, _sensor_amounts, pose = pose_from_glove(frame, open_angles, fist_angles, args)
            pose = smooth_pose(previous_pose, pose, args.smoothing)
            previous_pose = list(pose)
            print_preview(frame, flex, pose, args, last_frame, last_pose)
            last_frame = dict(frame)
            last_pose = list(pose)
            if api is not None:
                api.finger_move(pose=pose)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        close_hand(api)


def run_raw_preview(args) -> None:
    last_frame = None
    try:
        for frame in glove_frames(args.glove_port, args.baud):
            print_preview(frame, None, None, args, last_frame, None)
            last_frame = dict(frame)
    except KeyboardInterrupt:
        print("\nStopped.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="USB KTH5702 glove to LinkerHand L10 bridge.")
    parser.add_argument("--glove-port", default="/dev/ttyUSB0", help="USB serial port for the glove.")
    parser.add_argument("--baud", type=int, default=115200, help="Glove serial baud rate.")
    parser.add_argument("--hand-can", default="can0", help="SocketCAN interface for the L10 hand.")
    parser.add_argument("--hand", choices=["left", "right"], default="left", help="Controlled L10 hand side.")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--calibrate-open", action="store_true", help="Hold the glove open and save open calibration.")
    parser.add_argument("--calibrate-fist", action="store_true", help="Hold a fist and save closed/fist calibration.")
    parser.add_argument("--seconds", type=float, default=3.0, help="Calibration duration.")
    parser.add_argument("--raw", action="store_true", help="Only print parsed glove angles.")
    parser.add_argument("--send", action="store_true", help="Actually send mapped poses to the hand.")
    parser.add_argument("--force", action="store_true", help="Allow hand movement even if SDK detection fails.")
    parser.add_argument("--rate", type=float, default=15.0, help="Maximum send/print rate in Hz.")
    parser.add_argument("--only", choices=SELECTABLE_FINGERS, default="all", help="Move only one finger while tuning; other joints stay open.")
    parser.add_argument("--only-joint", action="append", type=int, choices=range(10), help="Move only this L10 joint. Can be used more than once.")
    parser.add_argument("--deadzone", type=float, default=0.0, help="Ignore small glove motion below this 0..1 amount.")
    parser.add_argument("--curve", type=float, default=1.0, help="Sensitivity curve. >1 softer near open, <1 more sensitive.")
    parser.add_argument("--smoothing", type=float, default=0.0, help="Pose smoothing 0..0.98. Higher is smoother but slower.")
    parser.add_argument("--print-mode", choices=["changes", "full", "quiet"], default="changes", help="Terminal output style.")
    parser.add_argument("--change-threshold", type=int, default=2, help="Only print joint changes at least this many L10 units.")
    parser.add_argument("--angle-threshold", type=float, default=2.0, help="Only print glove sensor changes at least this many degrees.")
    parser.add_argument(
        "--mapping",
        choices=["direct-l10", "combined"],
        default="direct-l10",
        help="direct-l10 maps only 10 matching glove points and ignores 5,7,8,11,14.",
    )
    parser.add_argument(
        "--finger-mode",
        choices=["max", "average", "min"],
        default="max",
        help="Only for --mapping combined. How to combine the 3 glove sensors on each non-thumb finger.",
    )
    parser.add_argument("--finger-gain", type=float, default=1.85, help="Increase/decrease non-thumb finger closing strength.")
    parser.add_argument("--index-gain", type=float, default=None, help="Optional index-only gain override.")
    parser.add_argument("--middle-gain", type=float, default=None, help="Optional middle-only gain override.")
    parser.add_argument("--ring-gain", type=float, default=None, help="Optional ring-only gain override.")
    parser.add_argument("--little-gain", type=float, default=None, help="Optional little-only gain override.")
    parser.add_argument("--invert-fingers", action="store_true", help="Invert all non-thumb fingers.")
    parser.add_argument("--invert-index", action="store_true", help="Invert only the index finger.")
    parser.add_argument("--invert-middle", action="store_true", help="Invert only the middle finger.")
    parser.add_argument("--invert-ring", action="store_true", help="Invert only the ring finger.")
    parser.add_argument("--invert-little", action="store_true", help="Invert only the little finger.")
    parser.add_argument(
        "--thumb-mode",
        choices=["direct", "average", "follow-index"],
        default="direct",
        help="Thumb mapping. direct uses sensors 0/1/2 separately; follow-index is a fallback test.",
    )
    parser.add_argument("--thumb-gain", type=float, default=1.35, help="Increase/decrease thumb movement strength.")
    parser.add_argument("--invert-thumb", action="store_true", help="Use only if thumb moves opposite after calibration.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.calibrate_open:
        print("Hold the glove in a relaxed OPEN hand pose.")
        values = collect_calibration(args.glove_port, args.baud, args.seconds)
        save_calibration(args.calibration, "open", values)
        return
    if args.calibrate_fist:
        print("Hold the glove in a closed FIST pose.")
        values = collect_calibration(args.glove_port, args.baud, args.seconds)
        save_calibration(args.calibration, "fist", values)
        return
    if args.raw:
        run_raw_preview(args)
        return
    run_bridge(args)


if __name__ == "__main__":
    main()
