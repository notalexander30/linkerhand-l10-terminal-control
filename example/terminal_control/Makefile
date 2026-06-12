# Forward helper commands to the repository root Makefile.
# This lets you run the same commands from example/terminal_control.

.DEFAULT_GOAL := help

.PHONY: help

# Show the root helper menu.
help:
	@$(MAKE) -C ../.. help

# Forward any other target, for example: make can-reset, make doctor, make status.
%:
	@$(MAKE) -C ../.. $@
