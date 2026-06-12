# LinkerHand L10 SDK-First Tool

The main tool is now:

```bash
python3 linkerhand_l10_sdk.py
```

It uses the official SDK as the control path:

```python
LinkerHandApi(hand_type="left", hand_joint="L10", can="can0")
api.get_embedded_version()
api.get_state()
api.finger_move(pose=...)
```

No raw CAN frames are written by this tool.

## Boot

```bash
cd ~/linkerhand-l10-terminal-control
conda activate linkerhand-l10-terminal-control
git pull
make install
make boot
```

`make boot`:

```text
1. kills old controller/example Python scripts
2. resets can0 at 1000000 bitrate
3. opens the official SDK
4. prints SDK detection and current state
```

It does not send a movement preset.

## State

```bash
make state
```

Direct:

```bash
python3 linkerhand_l10_sdk.py state
```

If version/serial is missing but `get_state()` returns ten values, the tool
treats that as hardware communication.

## Presets

List presets:

```bash
make list-presets
```

Preview without sending:

```bash
make mock-preset NAME=open
```

Send a preset:

```bash
make preset NAME=open
```

Send home/open:

```bash
make home
```

Official SDK-style set-state:

```bash
make set-state POS='255 255 255 255 255 255 255 255 255 255'
```

## Manual CAN Debug

Reset CAN without opening the SDK:

```bash
make can-reset
```

Unplug/replug USB-CAN flow:

```bash
make can-replug
```

Watch CAN frames:

```bash
make candump
```

Then in another terminal:

```bash
make state
```

## Compatibility

The old path still works, but it just launches the root SDK tool:

```bash
python3 example/terminal_control/terminal_control.py status
```
