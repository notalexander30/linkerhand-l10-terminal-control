# LinkerHand L10 Terminal Control

SDK-first terminal control for a LinkerHand L10 dexterous hand on a Linux laptop.

This project uses the official LinkerHand Python SDK as the hardware path:

- `LinkerHandApi(hand_type=..., hand_joint="L10", can=...)`
- `api.get_embedded_version()`
- `api.get_state()`
- `api.finger_move(pose=...)`

No raw CAN frames are written by this terminal tool. The reference SDK is here:
[linker-bot/linkerhand-python-sdk](https://github.com/linker-bot/linkerhand-python-sdk).

## Safety First

- Mount or hold the hand securely before sending any movement command.
- Keep fingers, tools, and cables away from the hand while testing.
- Run only one controller at a time. Close ROS nodes, GUI dashboards, motion-capture glove controllers, and other LinkerHand scripts before using this tool.
- Start with `boot`, `state`, `list-presets`, and `mock-preset` before sending motion.
- If detection fails, do not use `--force` unless you understand and accept the risk.
- `stop` in this project prints safe stop instructions. It does not send a hardware emergency-stop frame. Use your hardware power switch or emergency stop if motion is unsafe.

## What You Need

- Ubuntu 20.04 or newer is recommended.
- Python 3.8 or newer.
- Git.
- A USB-to-CAN adapter supported by SocketCAN.
- A powered LinkerHand L10.
- Linux CAN tools: `iproute2`, `can-utils`, and `ethtool`.
- Optional but recommended: Conda or another Python virtual environment.

## First Setup On A Linux Laptop

### 1. Clone the project

```bash
cd ~
git clone https://github.com/notalexander30/linkerhand-l10-terminal-control.git
cd linkerhand-l10-terminal-control
```

If you cloned somewhere else, always `cd` into the project directory before running the commands below.

### 2. Create and activate a Python environment

Using Conda:

```bash
conda create -n linkerhand-l10 python=3.10 -y
conda activate linkerhand-l10
python3 -m pip install --upgrade pip
```

Without Conda:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

### 3. Install dependencies

Recommended for this terminal tool:

```bash
make install
```

If `make` is not installed yet:

```bash
sudo apt update
sudo apt install -y make iproute2 can-utils ethtool
python3 -m pip install python-can python-can-candle pyyaml tabulate numpy jinja2 typeguard
```

The upstream `requirements.txt` contains many extra simulation and GUI packages. Use it only if you need the full SDK examples:

```bash
python3 -m pip install -r requirements.txt
```

### 4. Connect the hardware

1. Connect the USB-to-CAN adapter to the laptop.
2. Connect CAN-H, CAN-L, and ground according to your adapter and hand wiring.
3. Power on the LinkerHand L10.
4. Make sure no other LinkerHand controller is running.

### 5. Find the CAN interface

```bash
ip link
ip -br link show type can
```

You should see `can0` or `can1`.

Optional helper:

```bash
chmod +x find_can.sh
./find_can.sh
```

If you do not see any CAN interface, stop here and check the USB-to-CAN adapter, cable, driver, and power.

### 6. Reset CAN: down, configure, up

Most L10 setups use 1 Mbps.

For `can0`:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000 restart-ms 100
sudo ip link set can0 txqueuelen 1000
sudo ip link set can0 up
ip -details link show can0
```

For `can1`, replace `can0` with `can1`.

You can watch CAN traffic with:

```bash
candump can0
```

Press `Ctrl+C` to stop `candump`.

If `candump` prints frames while the hardware is active, the CAN link is alive. If it prints nothing, continue with SDK detection, but be ready to check wiring, power, bitrate, and interface name if detection fails.

### 7. Boot and detect the hand

Default command, for a left hand on `can0`:

```bash
make boot
```

For a right hand or a different CAN interface:

```bash
make HAND_TYPE=right CAN=can1 boot
```

Direct Python version:

```bash
python3 linkerhand_l10_sdk.py --can can0 --hand-type left boot
```

`boot` does this:

1. Kills old LinkerHand controller/example Python scripts.
2. Runs CAN down/configure/up at 1 Mbps.
3. Opens the official SDK.
4. Reads embedded version, serial, and current state.
5. Prints detection information.

`boot` does not send a movement preset.

Good signs:

- `Hardware Detected: True`
- `Detected By: version`, `serial`, or `state`
- `Current State` prints ten values from 0 to 255

Bad signs:

- `Hardware Detected: False`
- `SAFETY BLOCK`
- No valid ten-value state
- `can0 interface is not open`

If you see a bad sign, go to [Troubleshooting](#troubleshooting) before sending any movement.

## Daily Start

Use this after the first setup is complete:

```bash
cd ~/linkerhand-l10-terminal-control
conda activate linkerhand-l10
make boot
make state
make list-presets
```

Then preview a preset without moving:

```bash
make mock-preset NAME=open
```

Send a safe first pose:

```bash
make preset NAME=open
```

## Common Commands

| Task | Command |
| --- | --- |
| Show command menu | `make help` |
| Install terminal dependencies | `make install` |
| Kill old controller scripts | `make kill` |
| Reset CAN only | `make CAN=can0 can-reset` |
| Show CAN link details | `make CAN=can0 can-show` |
| Show CAN counters | `make CAN=can0 can-stats` |
| Watch CAN frames | `make CAN=can0 candump` |
| Boot and run SDK detection | `make CAN=can0 HAND_TYPE=left boot` |
| SDK detection only | `make CAN=can0 HAND_TYPE=left status` |
| Read current 10 joint values | `make CAN=can0 HAND_TYPE=left state` |
| List presets | `make list-presets` |
| Preview preset without sending | `make mock-preset NAME=open` |
| Send preset | `make CAN=can0 HAND_TYPE=left preset NAME=open` |
| Send all-255 home pose | `make CAN=can0 HAND_TYPE=left home` |
| Send all-zero pose | `make CAN=can0 HAND_TYPE=left zero` |
| Send exact ten values | `make CAN=can0 HAND_TYPE=left set-state POS='255 255 255 255 255 255 255 255 255 255'` |
| Print stop instructions | `make stop` |

## Presets

Preset poses live in:

```text
example/terminal_control/poses_l10.json
```

Each L10 preset must contain exactly ten values from `0` to `255`.

Show available presets:

```bash
make list-presets
```

Preview one preset:

```bash
python3 linkerhand_l10_sdk.py --mock preset open
```

Save a new preset:

```bash
python3 linkerhand_l10_sdk.py save-preset my_pose --position 255 255 255 255 255 255 255 255 255 255
```

The L10 joint order is:

1. Thumb Base
2. Thumb Side Swing
3. Index Base
4. Middle Base
5. Ring Base
6. Little Base
7. Index Side Swing
8. Ring Side Swing
9. Little Side Swing
10. Thumb Rotation

## Using `can1`

The terminal tool supports any SocketCAN interface:

```bash
make CAN=can1 HAND_TYPE=left boot
make CAN=can1 HAND_TYPE=left state
make CAN=can1 HAND_TYPE=left preset NAME=open
```

Or with Python:

```bash
python3 linkerhand_l10_sdk.py --can can1 --hand-type left boot
```

## Troubleshooting

| Problem or return message | What to do first |
| --- | --- |
| `git clone` fails on Windows with `Filename too long` | Use a Linux laptop for this SocketCAN project, or clone into a very short path such as `C:\src`. On Windows you can also try `git config --global core.longpaths true`, then clone again. |
| `make: command not found` | Run `sudo apt update && sudo apt install -y make`, or use the direct `python3 linkerhand_l10_sdk.py ...` commands. |
| `ip: command not found` | Run `sudo apt update && sudo apt install -y iproute2`. |
| `candump: command not found` | Run `sudo apt update && sudo apt install -y can-utils`. |
| `can0` does not appear in `ip link` | Check USB-to-CAN connection, driver, USB port, and cable. Replug the adapter. Run `ip -br link show type can` and `./find_can.sh`. The interface may be `can1`. |
| `Cannot find device "can0"` | Use the interface that exists, for example `make CAN=can1 boot`, or fix the adapter/driver until `can0` appears. |
| `RTNETLINK answers: Device or resource busy` | Stop other controllers with `make kill`, then run `sudo ip link set can0 down` and retry `make CAN=can0 can-reset`. |
| `Operation not permitted` | Use `sudo` for `ip link` commands. |
| `SIOCSIFBITRATE: Invalid argument` | The adapter/driver may not support SocketCAN bitrate changes, or the interface is not a CAN interface. Check the USB-to-CAN driver and try another adapter. |
| `can0 interface is not open` | Run `sudo ip link set can0 down`, configure bitrate, then `sudo ip link set can0 up`. Then retry `make boot`. |
| `candump can0` shows no traffic | Confirm hand power, CAN-H/CAN-L/GND wiring, termination, 1 Mbps bitrate, and interface name. Run `ip -statistics -details link show can0` to check error counters. |
| CAN error counters increase | Reset CAN with `make can-reset`. Check wiring, termination, bitrate, and whether another process is transmitting. |
| `ModuleNotFoundError` for `can`, `yaml`, or `LinkerHand` | Activate the environment, run `make install`, and run commands from the repository root. |
| `SAFETY BLOCK: SDK did not detect the hand` | Do not move the hand yet. Check CAN setup, power, `HAND_TYPE`, and `CAN`. Run `make status` and `make state`. Use `--force` only if you accept the risk. |
| `SDK did not return a valid 10-value state` | Confirm the hand is an L10, the correct hand side is selected, and CAN is working. Power-cycle the hand and reset CAN. |
| Wrong hand side responds or detection is inconsistent | Use `HAND_TYPE=left` or `HAND_TYPE=right` explicitly. The SDK uses different CAN IDs for left and right hands. |
| Movement is unexpected | Stop sending commands. Use `make mock-preset NAME=open` to inspect values before sending. Send `make home` only when the hand is safely mounted. |
| Another tool seems to control the hand | Close GUI dashboards, ROS nodes, glove/mocap controllers, and old Python scripts. Run `make kill`. |
| `sudo` asks for a password often | That is normal for CAN setup. You can run the CAN setup commands manually before using `status` or `state`. |
| `pip install -r requirements.txt` is slow or fails on simulation packages | Use `make install` for the terminal tool. The full requirements file is only needed for all upstream SDK examples. |

## When You Are Done

Stop any running terminal command with `Ctrl+C`.

Optionally bring CAN down:

```bash
sudo ip link set can0 down
```

Power off the hand when it is safe to do so.
