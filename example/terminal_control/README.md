# LinkerHand L10 Simple Terminal Control

This is a small terminal wrapper around the official LinkerHand Python SDK.

It follows the same pattern as the official L10 `get_set_state.py` example:

```python
hand = LinkerHandApi(hand_joint="L10", hand_type="left", can="can0")
hand.finger_move(pose=position)
state = hand.get_state()
```

The wrapper adds validation, mock mode, readable joint names, and a safety gate
before movement when the SDK does not detect an embedded version or serial.

## Safety

- The target hardware is a left LinkerHand L10.
- This tool does not write raw CAN frames.
- This tool does not modify `setting.yaml`.
- Use `--mock` first for new values.
- Keep the hand clear of people, cables, tools, and table edges.
- If SDK detection fails, movement is blocked unless `--force` is used.

## Setup

```bash
cd ~/linkerhand-l10-terminal-control
conda activate linkerhand-l10-terminal-control
make install
```

## CAN Setup

```bash
make kill
make can-reset
make can-show
```

`can-show` should show `can0` as `UP` and bitrate `1000000`.

## Read Status

```bash
make status
```

Direct Python:

```bash
python3 example/terminal_control/terminal_control.py status
```

## Read Current State

```bash
make state
```

Direct Python:

```bash
python3 example/terminal_control/terminal_control.py state
```

## Set State Like The Official SDK Example

Test with mock first:

```bash
python3 example/terminal_control/terminal_control.py --mock set-state --position 255 255 255 255 255 255 255 255 255 255
```

Real command:

```bash
make set-state POS='255 255 255 255 255 255 255 255 255 255'
```

## Other Commands

```bash
make list-poses
python3 example/terminal_control/terminal_control.py --mock pose open
python3 example/terminal_control/terminal_control.py pose open

make list-sequences
python3 example/terminal_control/terminal_control.py --mock sequence open_close_demo
python3 example/terminal_control/terminal_control.py sequence open_close_demo
```

## Useful Debug Commands

```bash
make doctor
make can-stats
make candump
```

If `status` cannot detect the hand but the previous SDK can, test the same SDK
arguments directly:

```bash
python3 example/terminal_control/terminal_control.py --hand-type left --can can0 status
```

If you intentionally need the SDK right-hand address for a special test:

```bash
make HAND_TYPE=right status
```
