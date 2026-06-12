# Short, safe helpers for the LinkerHand L10 terminal controller.
# Run these after activating your conda environment:
#   conda activate linkerhand-l10-terminal-control

CAN ?= can0
BITRATE ?= 1000000
HAND_TYPE ?= left
PY ?= python3
TC := example/terminal_control/terminal_control.py

.DEFAULT_GOAL := help

.PHONY: help install py-check can-down can-up can-reset can-show can-stats candump status mock-status doctor debug joints list-poses list-sequences stop kill

# Show the short commands available in this Makefile.
help:
	@echo "LinkerHand L10 helper commands"
	@echo ""
	@echo "CAN setup/debug:"
	@echo "  make can-reset      Reset $(CAN) at $(BITRATE) bps and show interface details"
	@echo "  make can-show       Show basic $(CAN) link details"
	@echo "  make can-stats      Show $(CAN) packet/error counters"
	@echo "  make candump        Watch all CAN frames on $(CAN); stop with Ctrl+C"
	@echo "  make doctor         Run read-only SDK/CAN diagnostics"
	@echo "  make debug          Run can-reset, then doctor"
	@echo ""
	@echo "Terminal controller:"
	@echo "  make mock-status    Run terminal status without touching hardware"
	@echo "  make status         Run read-only real hardware status"
	@echo "  make joints         Read current joints, only when hardware is detected"
	@echo "  make list-poses     List saved L10 poses"
	@echo "  make list-sequences List saved L10 sequences"
	@echo "  make stop           Print safe stop instructions"
	@echo ""
	@echo "Maintenance:"
	@echo "  make install        Install common Python/Linux dependencies"
	@echo "  make py-check       Syntax-check terminal_control.py"
	@echo "  make kill           Kill old terminal/gui controller Python processes"
	@echo ""
	@echo "Override CAN like this: make CAN=can1 can-reset"
	@echo "Override SDK hand ID like this: make HAND_TYPE=right status"

# Install common dependencies used by this terminal controller and SocketCAN tools.
install:
	@echo "Installing Python dependencies in the active environment..."
	@$(PY) -m pip install python-can tabulate pyyaml numpy pexpect pycryptodome
	@echo "Installing Linux CAN utilities..."
	@sudo apt update
	@sudo apt install -y can-utils ethtool iproute2

# Syntax-check the terminal controller without running the GUI or moving hardware.
py-check:
	@$(PY) -m py_compile $(TC)

# Stop old controller processes so they do not keep reading/writing CAN while debugging.
kill:
	@pkill -f terminal_control.py 2>/dev/null || true
	@pkill -f gui_control.py 2>/dev/null || true

# Put the CAN interface down; errors are ignored because it may already be down.
can-down:
	@echo "Putting $(CAN) down..."
	@sudo ip link set $(CAN) down 2>/dev/null || true

# Configure bitrate/queue and bring the CAN interface up. Use after can-down.
can-up:
	@echo "Configuring $(CAN) as SocketCAN at $(BITRATE) bps..."
	@sudo ip link set $(CAN) type can bitrate $(BITRATE) restart-ms 100
	@sudo ip link set $(CAN) txqueuelen 1000
	@sudo ip link set $(CAN) up

# Full safe CAN reset: down, wait, configure, up, then show current state.
can-reset: can-down
	@echo "Waiting for $(CAN) to settle..."
	@sleep 1
	@$(MAKE) --no-print-directory can-up
	@$(MAKE) --no-print-directory can-show

# Show whether $(CAN) is UP/LOWER_UP/ECHO and confirm bitrate.
can-show:
	@ip -details link show $(CAN)

# Show RX/TX packet counters and CAN error counters for debugging replies.
can-stats:
	@ip -statistics -details link show $(CAN)

# Watch CAN traffic. Use this in one terminal, then run make status in another.
candump:
	@echo "Listening on $(CAN). Stop with Ctrl+C."
	@candump -tz -x -e $(CAN)

# Run the terminal controller status without connecting to real hardware.
mock-status:
	@$(PY) $(TC) --mock --can $(CAN) --sdk-hand-type $(HAND_TYPE) status

# Run read-only real hardware status through the SDK.
status:
	@$(PY) $(TC) --can $(CAN) --sdk-hand-type $(HAND_TYPE) status

# Run read-only diagnostics that compare CAN counters and SDK version probes.
doctor:
	@$(PY) $(TC) --can $(CAN) --sdk-hand-type $(HAND_TYPE) doctor

# Reset CAN, then run read-only diagnostics.
debug: can-reset doctor

# Read current joint values through the SDK; movement is still safety-gated.
joints:
	@$(PY) $(TC) --can $(CAN) --sdk-hand-type $(HAND_TYPE) joints

# List pose names from example/terminal_control/poses_l10.json.
list-poses:
	@$(PY) $(TC) list-poses

# List sequence names from example/terminal_control/sequences_l10.json.
list-sequences:
	@$(PY) $(TC) list-sequences

# Print how to stop foreground terminal sequences safely.
stop:
	@$(PY) $(TC) stop
