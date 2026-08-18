#!/usr/bin/env python3
"""Path-stable entry so MCP/skill work before pip install."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cell.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
