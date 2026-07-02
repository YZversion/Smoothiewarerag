from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
SRC = LAB_ROOT / "src"
EVAL = LAB_ROOT / "eval" / "eval_questions.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search.index import SearchIndex  # noqa: E402


def main() -> int:
    os.environ["KB_W_DENSE"] = "20"
    qs = json.loads(EVAL.read_text(encoding="utf-8"))["questions"]
    idx = SearchIndex()
    idx.load_index()
    idx.load_dense_index(force=True)

    rg_ms = 0.0
    path_ms = 0.0
    q_ms = 0.0
    rg_calls = 0
    path_calls = 0

    orig_rg = idx.search_rg
    orig_path = idx._rg_path_to_manifest

    def wrap_rg(*args, **kwargs):
        nonlocal rg_ms, rg_calls
        t0 = time.perf_counter()
        out = orig_rg(*args, **kwargs)
        rg_ms += (time.perf_counter() - t0) * 1000
        rg_calls += 1
        return out

    def wrap_path(*args, **kwargs):
        nonlocal path_ms, path_calls
        t0 = time.perf_counter()
        out = orig_path(*args, **kwargs)
        path_ms += (time.perf_counter() - t0) * 1000
        path_calls += 1
        return out

    idx.search_rg = wrap_rg  # type: ignore[method-assign]
    idx._rg_path_to_manifest = wrap_path  # type: ignore[method-assign]

    # warmup
    idx.search(qs[0]["question"], top_k=5, bundle=False)

    for q in qs:
        t0 = time.perf_counter()
        idx.search(q["question"], top_k=5, bundle=False)
        q_ms += (time.perf_counter() - t0) * 1000

    n = len(qs)
    print(f"queries={n}")
    print(f"mean_query_ms={q_ms/n:.4f}")
    print(f"search_rg_ms_total={rg_ms:.4f}")
    print(f"search_rg_ms_per_query={rg_ms/n:.4f}")
    print(f"path_map_ms_total={path_ms:.4f}")
    print(f"path_map_ms_per_query={path_ms/n:.4f}")
    print(f"search_rg_share={(rg_ms/q_ms*100):.2f}")
    print(f"path_map_share={(path_ms/q_ms*100):.2f}")
    print(f"rg_calls={rg_calls} path_calls={path_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
