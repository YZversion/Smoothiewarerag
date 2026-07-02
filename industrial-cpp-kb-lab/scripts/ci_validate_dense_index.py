"""CI guard: validate committed dense index matches current chunks."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search.dense_index import CHUNKS_PATH, DEFAULT_INDEX_DIR, DenseIndex


def main() -> int:
    di = DenseIndex(DEFAULT_INDEX_DIR)
    if not di.load():
        print(
            "[ERROR] dense index artifacts missing at data/dense_index. "
            "Please run `python scripts/build_dense_index.py` locally and commit artifacts."
        )
        return 2

    ok, reason = di.verify_compatibility(CHUNKS_PATH)
    if not ok:
        print(
            "[ERROR] dense index is stale/incompatible with current chunks. "
            f"{reason}. Rebuild locally and commit updated data/dense_index artifacts."
        )
        return 3

    print("[OK] dense index artifacts are present and fingerprint-compatible with chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
