#!/usr/bin/env python3
"""Run the simple L10 terminal control from this example directory."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from remote_control import main  # noqa: E402


if __name__ == "__main__":
    main()
