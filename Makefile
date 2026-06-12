# Short helpers for the simple LinkerHand L10 terminal wrapper.
# Activate your Python environment first:
#   conda activate linkerhand-l10-terminal-control

CAN ?= can0
BITRATE ?= 1000000
HAND_TYPE ?= left
PY ?= python3
TC := example/terminal_control/terminal_control.py

.DEFAULT_GOAL := help

.PHONY: help install py-check kill can-down can-up can-reset can-replug can-show can-stats candump status doctor debug mock-status state joints set-state home zero list-poses list-sequences stop

# Show available shortcuts.
help:
	@echo "LinkerHand L10 simple SDK helper commands"
	@echo ""
	@echo "Setup/debug:"
	@echo "  make install        Install Python and Linux CAN dependencies"
	@echo "  make kill           Stop old terminal/gui controller processes"
	@echo "  make can-reset      Reset $(CAN) at $(BITRATE) bps"
	@echo "  make can-replug     Kill programs, drop CAN, wait for USB replug, bring CAN up"
	@echo "  make can-show       Show $(CAN) link details"
	@echo "  make can-stats      Show $(CAN) packet/error counters"
	@echo "  make candump        Watch CAN frames; stop with Ctrl+C"
	@echo "  make doctor         Show CAN details and SDK status"
	@echo "  make debug          Run can-reset, then doctor"
	@echo ""
	@echo "Official-SDK style control:"
	@echo "  make status         Read SDK embedded version/serial"
	@echo "  make state          Read current 10 joint values"
	@echo "  make set-state POS='255 255 255 255 255 255 255 255 255 255'"
	@echo "  make home           Send all-255 home pose"
	@echo "  make zero           Send all-zero pose"
	@echo "  make mock-status    Test status without hardware"
	@echo ""
	@echo "Override examples:"
	@echo "  make CAN=can1 can-reset"
	@echo "  make HAND_TYPE=right status"

# Install dependencies used by the official SDK path and SocketCAN tools.
install:
	@$(PY) -m pip install python-can python-can-candle pyyaml tabulate numpy jinja2 typeguard
	@sudo apt update
	@sudo apt install -y can-utils ethtool iproute2 make

# Syntax-check without running hardware commands.
py-check:
	@$(PY) -m py_compile $(TC)

# Stop old controller processes before debugging CAN.
kill:
	@pkill -f terminal_control.py 2>/dev/null || true
	@pkill -f gui_control.py 2>/dev/null || true
	@pkill -f get_set_state.py 2>/dev/null || true

# Put CAN down; ignore failure because it may already be down.
can-down:
	@sudo ip link set $(CAN) down 2>/dev/null || true

# Configure CAN bitrate and bring it up.
can-up:
	@sudo ip link set $(CAN) type can bitrate $(BITRATE) restart-ms 100
	@sudo ip link set $(CAN) txqueuelen 1000
	@sudo ip link set $(CAN) up

# Full CAN reset.
can-reset: can-down
	@sleep 1
	@$(MAKE) --no-print-directory can-up
	@$(MAKE) --no-print-directory can-show

# Manual USB-CAN recovery flow. This does not run the SDK or send hand commands.
can-replug: kill
	@echo "Putting $(CAN) down before USB-CAN replug..."
	@sudo ip link set $(CAN) down 2>/dev/null || true
	@echo ""
	@echo "Now unplug the USB-CAN adapter, wait a few seconds, plug it back in,"
	@echo "and make sure the hand power is ON."
	@bash -c 'read -r -p "Press Enter after replugging USB-CAN... " _; for i in $$(seq 1 15); do if ip link show "$(CAN)" >/dev/null 2>&1; then exit 0; fi; echo "Waiting for $(CAN) to appear ($$i/15)..."; sleep 1; done; echo "$(CAN) did not appear. Check USB-CAN cable/driver."; exit 1'
	@$(MAKE) --no-print-directory can-up
	@$(MAKE) --no-print-directory can-stats

# Show CAN link details.
can-show:
	@ip -details link show $(CAN)

# Show RX/TX/error counters.
can-stats:
	@ip -statistics -details link show $(CAN)

# Watch CAN traffic.
candump:
	@candump -tz -x -e $(CAN)

# Read SDK status.
status:
	@$(PY) $(TC) --can $(CAN) --hand-type $(HAND_TYPE) status

# Read SDK status without hardware.
mock-status:
	@$(PY) $(TC) --mock --can $(CAN) --hand-type $(HAND_TYPE) status

# Show CAN details and SDK status.
doctor:
	@$(PY) $(TC) --can $(CAN) --hand-type $(HAND_TYPE) doctor

# Reset CAN and diagnose.
debug: can-reset doctor

# Read current joint state.
state:
	@$(PY) $(TC) --can $(CAN) --hand-type $(HAND_TYPE) state

# Alias for state.
joints: state

# Official SDK get_set_state style: send position then read state.
set-state:
	@if [ -z "$(POS)" ]; then echo "Usage: make set-state POS='255 255 255 255 255 255 255 255 255 255'"; exit 2; fi
	@$(PY) $(TC) --can $(CAN) --hand-type $(HAND_TYPE) set-state --position $(POS)

# Send all-255 home pose.
home:
	@$(PY) $(TC) --can $(CAN) --hand-type $(HAND_TYPE) home

# Send all-zero pose.
zero:
	@$(PY) $(TC) --can $(CAN) --hand-type $(HAND_TYPE) zero

# List saved poses.
list-poses:
	@$(PY) $(TC) list-poses

# List saved sequences.
list-sequences:
	@$(PY) $(TC) list-sequences

# Print safe stop instructions.
stop:
	@$(PY) $(TC) stop
