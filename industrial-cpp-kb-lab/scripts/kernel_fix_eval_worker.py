"""
单配置 kernel-fix 验证 worker（由 run_kernel_fix_validation.py 子进程调用）。

环境变量：
  KB_HALT_HINT_EXTENDED=1   改动 A
  RG_CANDIDATE_FILE_LIMIT=N 改动 B
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC = LAB_ROOT / "src"
OUT_DIR = LAB_ROOT / "notes" / "kernel_fix_validation"
KERNEL_FILE = "src/libs/Kernel.cpp"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# trace 复用
_TRACE_PATH = LAB_ROOT / "scripts" / "trace_kernel_h3_h8.py"
_spec = importlib.util.spec_from_file_location("_trace_kernel", _TRACE_PATH)
_trace = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_trace)


def load_search():
    path = SRC / "03_search.py"
    spec = importlib.util.spec_from_file_location("_kb_search", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.load_index()
    return mod


def multiplicity_from_summary(summary: dict, questions: list[dict]) -> dict:
    by_id = {d["id"]: d for d in summary["details"]}
    rows = []
    for q in questions:
        d = by_id[q["id"]]
        exp = q["expected_files"]
        mult = "multi" if len(exp) > 1 else "single"
        rows.append({
            "id": q["id"], "split": q.get("split", "tune"),
            "multiplicity": mult, "cov5": d["cov5"],
            "hit5": d["hit5"], "miss5": d["miss5"],
        })

    def mean_cov(subset):
        return sum(r["cov5"] for r in subset) / len(subset) if subset else 0.0

    def pick(**kw):
        return [r for r in rows if all(r[k] == v for k, v in kw.items())]

    single_holdout_miss = [
        r["id"] for r in pick(multiplicity="single", split="holdout") if r["cov5"] < 1.0
    ]
    return {
        "all_mean": mean_cov(rows),
        "single_mean": mean_cov(pick(multiplicity="single")),
        "multi_mean": mean_cov(pick(multiplicity="multi")),
        "tune_mean": mean_cov(pick(split="tune")),
        "holdout_mean": mean_cov(pick(split="holdout")),
        "holdout_single_mean": mean_cov(pick(multiplicity="single", split="holdout")),
        "holdout_multi_mean": mean_cov(pick(multiplicity="multi", split="holdout")),
        "single_holdout_regressions": single_holdout_miss,
        "per_question": {r["id"]: r for r in rows},
    }


def kernel_topk_channel(retrieval: dict) -> dict:
    """Which channel brought Kernel into eval top-k, if any."""
    in_eval = KERNEL_FILE in retrieval["eval_top_k_files"]
    if not in_eval:
        return {"in_eval_top5": False, "winning_channel": None}
    detail = retrieval.get("kernel_merged_detail") or []
    in_top = [d for d in detail if d.get("in_eval_top_k")]
    if not in_top:
        return {"in_eval_top5": True, "winning_channel": "file_via_other_chunk"}
    best = min(in_top, key=lambda x: x["rank_all"])
    ch = best.get("base_channels") or {}
    dominant = max(ch.items(), key=lambda x: x[1])[0] if ch else best.get("source", "")
    return {
        "in_eval_top5": True,
        "winning_channel": dominant,
        "rank": best["rank_all"],
        "score": best["score"],
        "source": best.get("source"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    questions = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]
    search = load_search()

    t0 = time.perf_counter()
    summary = search.eval_summary()
    eval_elapsed = time.perf_counter() - t0

    # per-query search latency (35 questions, top_k=5, no bundle)
    latencies: list[float] = []
    for q in questions:
        tq = time.perf_counter()
        search.search(q["question"], top_k=5, bundle=False)
        latencies.append(time.perf_counter() - tq)
    mean_q_ms = (sum(latencies) / len(latencies)) * 1000 if latencies else 0.0
    max_q_ms = max(latencies) * 1000 if latencies else 0.0

    mult = multiplicity_from_summary(summary, questions)

    traces = {}
    for qid in ("H3", "H8", "Q4"):
        q = next(x for x in questions if x["id"] == qid)
        retr = _trace.trace_retrieval(search, q, top_k=5)
        traces[qid] = {
            "retrieval": retr,
            "topk_channel": kernel_topk_channel(retr),
            "rg_prefilter": retr.get("rg_prefilter", {}),
        }

    payload = {
        "label": args.label,
        "env": {
            "KB_HALT_HINT_EXTENDED": __import__("os").environ.get("KB_HALT_HINT_EXTENDED", ""),
            "RG_CANDIDATE_FILE_LIMIT": __import__("os").environ.get("RG_CANDIDATE_FILE_LIMIT", ""),
        },
        "eval_summary": summary,
        "multiplicity": mult,
        "timing": {
            "eval_summary_sec": round(eval_elapsed, 3),
            "mean_query_ms": round(mean_q_ms, 2),
            "max_query_ms": round(max_q_ms, 2),
        },
        "traces": traces,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {args.label} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
