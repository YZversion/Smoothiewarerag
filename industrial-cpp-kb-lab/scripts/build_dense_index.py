"""Build FAISS dense index from chunks.jsonl."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search.dense_index import CHUNKS_PATH, DEFAULT_INDEX_DIR, DenseIndex


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    p.add_argument("--out", type=Path, default=DEFAULT_INDEX_DIR)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    di = DenseIndex(args.out)
    if not args.force and not di.is_stale(args.chunks) and di.load():
        print(f"index up-to-date: {args.out}")
        return 0
    manifest = di.build(args.chunks)
    print(f"built {manifest['chunk_count']} chunks -> {args.out}")
    print(f"model={manifest['model']} dim={manifest['dim']} encode_sec={manifest['encode_sec']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
