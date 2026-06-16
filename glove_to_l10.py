#!/usr/bin/env python3
"""Bridge a USB KTH5702 glove text stream to a left LinkerHand L10.

The glove shown by the serial console prints lines like:

    KTH5702: | 拇指 | 0 | 0x68 | 193.50° | -30311 | 正常 | 0 |

This script reads those lines from /dev/ttyUSB0, parses the 15 sensor angles,
maps them to the 10 L10 joint values, and can send them through the official
LinkerHand Python SDK.
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


def finger_flex(frame: dict[int, float], open_angles: dict, fist_angles: dict) -> dict[str, float]:
    result: dict[str, float] = {}
    for finger, indexes in FINGER_GROUPS.items():
        values = [
            sensor_flex(index, frame[index], open_angles, fist_angles)
            for index in indexes
            if index in frame
        ]
        values = [value for value in values if value is not None]
        result[finger] = float(statistics.mean(values)) if values else 0.0
    return result


def pose_from_flex(flex: dict[str, float]) -> list[int]:
    pose = list(OPEN_POSE)
    for finger, joints in POSE_GROUPS.items():
        amount = flex.get(finger, 0.0)
        for joint in joints:
            value = OPEN_POSE[joint] + amount * (FIST_POSE[joint] - OPEN_POSE[joint])
            pose[joint] = int(round(clamp(value, 0, 255)))
    return pose


def connect_hand(args):
    sdk_args = SimpleNamespace(can=args.hand_can, hand_type=args.hand, force=args.force)
    api, info = sdk.connect_sdk(sdk_args)
    sdk.require_detected(sdk_args, info)
    return api


def close_hand(api) -> None:
    sdk.close_sdk(api)


def print_preview(frame: dict[int, float], flex: dict[str, float] | None, pose: list[int] | None) -> None:
    angles = " ".join(f"{index}:{frame[index]:.1f}" for index in range(SENSOR_COUNT) if index in frame)
    print(f"angles {angles}")
    if flex is not None and pose is not None:
        flex_text = " ".join(f"{finger}={value:.2f}" for finger, value in flex.items())
        print(f"flex {flex_text}")
        print(f"pose {pose}")


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

    min_interval = 1.0 / max(args.rate, 1.0)
    last_send = 0.0
    try:
        for frame in glove_frames(args.glove_port, args.baud):
            now = time.monotonic()
            if now - last_send < min_interval:
                continue
            last_send = now

            flex = finger_flex(frame, open_angles, fist_angles)
            pose = pose_from_flex(flex)
            print_preview(frame, flex, pose)
            if api is not None:
                api.finger_move(pose=pose)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        close_hand(api)


def run_raw_preview(args) -> None:
    try:
        for frame in glove_frames(args.glove_port, args.baud):
            print_preview(frame, None, None)
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
