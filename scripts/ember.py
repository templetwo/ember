#!/usr/bin/env python3
"""Source-tree entrypoint; use scripts/ember to select the pinned interpreter."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ember.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
