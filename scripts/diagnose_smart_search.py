"""
Run smart-search diagnostics from repo root (forwards to industrial-cpp-kb-lab).

Usage (from Smoothiewarerag/):
    python scripts/diagnose_smart_search.py
    python scripts/diagnose_smart_search.py --no-llm
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parent.parent / "industrial-cpp-kb-lab"
_TARGET = _LAB / "scripts" / "diagnose_smart_search.py"

if not _TARGET.is_file():
    print(f"Not found: {_TARGET}", file=sys.stderr)
    print("Expected industrial-cpp-kb-lab next to this scripts/ folder.", file=sys.stderr)
    raise SystemExit(1)

# Preserve forwarded CLI args; replace argv[0] so argparse help shows the real script.
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
