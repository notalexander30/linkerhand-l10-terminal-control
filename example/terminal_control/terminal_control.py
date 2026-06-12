#!/usr/bin/env python3
"""Compatibility launcher for the root SDK-first L10 tool."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from linkerhand_l10_sdk import main  # noqa: E402


if __name__ == "__main__":
    main()
