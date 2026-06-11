# LinkerHand L10 Terminal Control

Safe terminal-based controller for a real left LinkerHand L10.

This tool reuses `LinkerHandApi`, the same SDK layer used by the PyQt GUI. It does not write raw CAN frames, and it does not modify `setting.yaml`.

## Safety

- Keep the hand clear of people, cables, tools, and table edges before sending a real command.
- Use `--mock` first for every new pose or sequence.
- Real movement is blocked when the embedded serial/version number cannot be detected, unless `--force` is provided.
- `stop` does not send a low-level emergency stop frame. It explains how to stop terminal-controlled foreground sequences. Use your normal hardware power/emergency procedure for real emergencies.

## Setup

Run from this folder:

```bash
cd ~/linkerhand-l10-terminal-control/example/terminal_control
```

Or from the repository root:

```bash
cd ~/linkerhand-l10-terminal-control
python3 example/terminal_control/terminal_control.py --mock status
```

## Status

```bash
python3 terminal_control.py status
```

Mock status without touching hardware:

```bash
python3 terminal_control.py --mock status
```

## Read Current Joints

```bash
python3 terminal_control.py joints
```

## Send Direct Joint Values

Always test with mock first:

```bash
python3 terminal_control.py --mock set --values 255,255,255,255,255,255,255,255,255,255
```

Then real hardware:

```bash
python3 terminal_control.py set --values 255,255,255,255,255,255,255,255,255,255
```

## Built-In Presets

```bash
python3 terminal_control.py preset open
python3 terminal_control.py preset fist
python3 terminal_control.py preset ok
```

## List And Run Poses

```bash
python3 terminal_control.py list-poses
python3 terminal_control.py --mock pose thumbs_up
python3 terminal_control.py pose thumbs_up
```

## Save A Pose

```bash
python3 terminal_control.py save-pose custom_open --values 255,255,255,255,255,255,255,255,255,255
python3 terminal_control.py --mock pose custom_open
```

Saved poses are written to `poses_l10.json`.

## Run A Sequence

```bash
python3 terminal_control.py list-sequences
python3 terminal_control.py --mock sequence open_close_demo
python3 terminal_control.py sequence open_close_demo
```

Sequences live in `sequences_l10.json`. Each step must contain either:

```json
{"pose": "open", "duration_seconds": 1.0}
```

or:

```json
{"values": [255,255,255,255,255,255,255,255,255,255], "duration_seconds": 1.0}
```

When `duration_seconds` is greater than `0`, the tool interpolates gradually to the next pose. Use `Ctrl+C` to interrupt a running sequence.

## Stop

```bash
python3 terminal_control.py stop
```

This does not send a raw CAN frame. It only documents the safe terminal behavior: stop the foreground sequence with `Ctrl+C`, or stop the process running that sequence.
