# SDK-first helper commands for left LinkerHand L10.

CAN ?= can0
HAND_TYPE ?= left
PY ?= python3
SDK := linkerhand_l10_sdk.py

.DEFAULT_GOAL := help

.PHONY: help install boot kill can-reset can-replug can-show can-stats candump status state set-state preset mock-preset list-presets home zero stop py-check

# Show the command menu.
help:
	@echo "LinkerHand L10 SDK-first commands"
	@echo ""
	@echo "Boot/debug:"
	@echo "  make install        Install Python + Linux CAN dependencies"
	@echo "  make boot           Kill old scripts, bring CAN up, run SDK detection/state"
	@echo "  make kill           Kill old controller/example scripts only"
	@echo "  make can-reset      Reset CAN without running SDK"
	@echo "  make can-replug     Manual USB-CAN unplug/replug flow"
	@echo "  make can-show       Show CAN link"
	@echo "  make can-stats      Show CAN counters"
	@echo "  make candump        Watch CAN frames"
	@echo ""
	@echo "SDK control:"
	@echo "  make status         SDK detection only"
	@echo "  make state          Read current 10 joint values"
	@echo "  make list-presets   List preset names"
	@echo "  make preset NAME=open"
	@echo "  make mock-preset NAME=open"
	@echo "  make set-state POS='255 255 255 255 255 255 255 255 255 255'"
	@echo "  make home           Send all-255 home pose"
	@echo "  make zero           Send all-zero pose"
	@echo ""
	@echo "Override examples:"
	@echo "  make CAN=can1 boot"
	@echo "  make HAND_TYPE=right status"

# Install dependencies for the official SDK path.
install:
	@$(PY) -m pip install python-can python-can-candle pyyaml tabulate numpy jinja2 typeguard
	@sudo apt update
	@sudo apt install -y can-utils ethtool iproute2 make

# Syntax-check the SDK-first tool.
py-check:
	@$(PY) -m py_compile $(SDK) example/terminal_control/terminal_control.py

# Kill old Python control scripts without killing this make command.
kill:
	@$(PY) $(SDK) kill

# Main boot: CAN setup plus SDK detection/state. No movement command.
boot:
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) boot

# Reset CAN only. No SDK and no movement command.
can-reset:
	@$(PY) $(SDK) --can $(CAN) can-reset

# Manual USB-CAN unplug/replug flow. No SDK and no movement command.
can-replug: kill
	@sudo ip link set $(CAN) down 2>/dev/null || true
	@echo "Unplug USB-CAN, wait a few seconds, plug it back in, and keep hand power ON."
	@bash -c 'read -r -p "Press Enter after replugging USB-CAN... " _; for i in $$(seq 1 15); do if ip link show "$(CAN)" >/dev/null 2>&1; then exit 0; fi; echo "Waiting for $(CAN) ($$i/15)..."; sleep 1; done; echo "$(CAN) did not appear."; exit 1'
	@$(PY) $(SDK) --can $(CAN) can-reset

# Show CAN link only.
can-show:
	@$(PY) $(SDK) --can $(CAN) can-show

# Show CAN counters only.
can-stats:
	@$(PY) $(SDK) --can $(CAN) can-stats

# Watch CAN traffic.
candump:
	@candump -tz -x -e $(CAN)

# SDK detection only.
status:
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) status

# Read joint state.
state:
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) state

# Send official SDK style position.
set-state:
	@if [ -z "$(POS)" ]; then echo "Usage: make set-state POS='255 255 255 255 255 255 255 255 255 255'"; exit 2; fi
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) set-state --position $(POS)

# List presets.
list-presets:
	@$(PY) $(SDK) list-presets

# Send a named preset.
preset:
	@if [ -z "$(NAME)" ]; then echo "Usage: make preset NAME=open"; exit 2; fi
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) preset $(NAME)

# Preview a named preset without sending.
mock-preset:
	@if [ -z "$(NAME)" ]; then echo "Usage: make mock-preset NAME=open"; exit 2; fi
	@$(PY) $(SDK) --mock --can $(CAN) --hand-type $(HAND_TYPE) preset $(NAME)

# Send all-255 home pose.
home:
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) home

# Send all-zero pose.
zero:
	@$(PY) $(SDK) --can $(CAN) --hand-type $(HAND_TYPE) zero

# Stop instructions.
stop:
	@$(PY) $(SDK) stop
