"""
Dense retrieval 实验：tune 组调权 → 全量 48 题验收。

用法：
    pip install faiss-cpu sentence-transformers
    python scripts/build_dense_index.py
    python scripts/run_dense_experiment.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import argparse
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC = LAB_ROOT / "src"
REPORT_PATH = LAB_ROOT / "notes" / "dense_experiment.md"
DATA_PATH = LAB_ROOT / "notes" / "dense_experiment_data.json"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search.dense_index import DEFAULT_MODEL, DenseIndex, DEFAULT_INDEX_DIR
from search.index import SearchIndex

COV5_CAPS = {"Q3": 6 / 6, "Q4": 5 / 7, "Q5": 5 / 6}  # min(5,n)/n
WEIGHTS = [0, 5, 10, 15, 20, 25]
SEALED_IDS = {"H31", "H33", "H34", "H41", "H43"}
KERNEL = "src/libs/Kernel.cpp"
KILLBUTTON = "src/modules/utils/killbutton/KillButton.cpp"


def load_questions() -> list[dict]:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]


def is_tune_dev(q: dict) -> bool:
    if q.get("split") == "tune":
        return True
    return q.get("dev_split") == "tune"


def parse_note(note: str) -> dict:
    out = {"vocab_mismatch": False, "category": ""}
    for part in (note or "").split(";"):
        part = part.strip()
        if part.startswith("vocab_mismatch="):
            out["vocab_mismatch"] = part.split("=", 1)[1].lower() == "true"
        elif part.startswith("category="):
            out["category"] = part.split("=", 1)[1]
    return out


def eval_rows(idx: SearchIndex, questions: list[dict], k: int = 5) -> list[dict]:
    rows = []
    for q in questions:
        r = idx.eval_question(q, k)
        rows.append({
            "id": q["id"],
            "split": q.get("split", "tune"),
            "dev_split": q.get("dev_split"),
            "cov5": r["coverage"],
            "hit_n": r["hit_n"],
            "exp_n": r["expected_n"],
            "passed": r["passed"],
            "hit": r["hit"],
            "miss": r["miss"],
            "vocab_mismatch": parse_note(q.get("note", ""))["vocab_mismatch"],
            "category": parse_note(q.get("note", ""))["category"],
            "batch": q.get("batch", "original"),
        })
    return rows


def mean_cov(rows: list[dict]) -> float:
    return sum(r["cov5"] for r in rows) / len(rows) if rows else 0.0


def bucket_stats(rows: list[dict]) -> dict:
    orig35 = [r for r in rows if r["batch"] == "original" or r["id"].startswith("Q") or (
        r["id"].startswith("H") and int(r["id"][1:]) <= 30
    )]
    # simpler: original = id in Q1-5 or H1-30 without batch field
    all_q = load_questions()
    orig_ids = {q["id"] for q in all_q if q.get("batch", "original") == "original"}
    orig35 = [r for r in rows if r["id"] in orig_ids]
    vocab = [r for r in rows if r["vocab_mismatch"]]
    single_hold = [
        r for r in rows
        if r["id"] in orig_ids and r["split"] == "holdout" and r["exp_n"] == 1
    ]
    sealed = [r for r in rows if r["id"] in SEALED_IDS]
    return {
        "all_mean": mean_cov(rows),
        "orig35_mean": mean_cov(orig35),
        "vocab_mismatch_mean": mean_cov(vocab),
        "vocab_mismatch_n": len(vocab),
        "single_holdout_pass": sum(1 for r in single_hold if r["cov5"] >= 1.0),
        "single_holdout_n": len(single_hold),
        "single_holdout_miss": [r["id"] for r in single_hold if r["cov5"] < 1.0],
        "sealed_pass5": sum(1 for r in sealed if r["passed"]),
        "sealed_n": len(sealed),
        "q_caps": {
            qid: {
                "cov5": next(r["cov5"] for r in rows if r["id"] == qid),
                "cap": COV5_CAPS[qid],
                "normalized": next(r["cov5"] for r in rows if r["id"] == qid) / COV5_CAPS[qid],
            }
            for qid in ("Q3", "Q4", "Q5")
            if any(r["id"] == qid for r in rows)
        },
    }


def run_config(
    w_dense: float,
    questions: list[dict],
    idx: SearchIndex | None = None,
    *,
    disable_halt_syn: bool = False,
) -> tuple[dict, SearchIndex]:
    os.environ["KB_W_DENSE"] = str(w_dense)
    if disable_halt_syn:
        os.environ["KB_DISABLE_HALT_SYNONYMS"] = "1"
    else:
        os.environ.pop("KB_DISABLE_HALT_SYNONYMS", None)

    if idx is None:
        idx = SearchIndex()
        idx.load_index()
    if w_dense > 0:
        if not idx.load_dense_index(force=True):
            raise RuntimeError("dense index not loaded; run scripts/build_dense_index.py")

    dense_times: list[float] = []
    baseline_times: list[float] = []
    for q in questions:
        t0 = time.perf_counter()
        idx.search(q["question"], top_k=5, bundle=False)
        baseline_times.append((time.perf_counter() - t0) * 1000)
        if w_dense > 0:
            dense_times.append(idx._last_dense_ms)

    rows = eval_rows(idx, questions)
    return {
        "w_dense": w_dense,
        "disable_halt_syn": disable_halt_syn,
        "rows": rows,
        "stats": bucket_stats(rows),
        "timing": {
            "mean_query_ms": round(sum(baseline_times) / len(baseline_times), 2),
            "mean_dense_ms": round(sum(dense_times) / len(dense_times), 2) if dense_times else 0.0,
        },
    }, idx


def h3_kernel_check(idx: SearchIndex, question: dict) -> dict:
    hits = idx.search(question["question"], top_k=5, bundle=False)
    files = [h["file"] for h in hits]
    return {
        "cov5": len([f for f in question["expected_files"] if f in set(files)]) / len(question["expected_files"]),
        "kernel_in_top5": KERNEL in files,
        "killbutton_in_top5": KILLBUTTON in files,
        "top5_files": files,
    }


def format_report(data: dict) -> str:
    sweep = data["weight_sweep"]
    best_w = data["best_w"]
    final = data["final"]
    baseline = data["baseline_dense0"]
    h3 = data["h3_ablation"]

    def pct(x):
        return f"{x:.1%}"

    lines = [
        "# Dense retrieval 实验报告",
        "",
        "## 模型与索引",
        "",
        f"- **模型**: `{data['model']}`",
        f"- **维度**: {data['dim']}",
        f"- **License**: MIT（BGE 系列，见 HuggingFace model card）",
        f"- **索引**: FAISS `IndexFlatIP`（L2-normalized 向量，内积=余弦）",
        f"- **chunk 数**: {data['chunk_count']}",
        f"- **嵌入格式**:",
        "  ```",
        "  file: {path}",
        "  class: {class}",
        "  symbol: {symbol}",
        "  type: {chunk_type}",
        "",
        "  {chunk code text}",
        "  ```",
        "",
        "## 权重扫描（tune 组，n=13）",
        "",
        "| w_dense | tune mean cov@5 | vocab_mismatch mean |",
        "|---------|-----------------|---------------------|",
    ]
    for s in sweep:
        tune_rows = [r for r in s["rows"] if is_tune_dev(next(q for q in data["questions"] if q["id"] == r["id"]))]
        vm = [r for r in tune_rows if r["vocab_mismatch"]]
        lines.append(
            f"| {s['w_dense']} | {pct(mean_cov(tune_rows))} | "
            f"{pct(mean_cov(vm)) if vm else 'n/a'} |"
        )
    lines += [
        "",
        f"**选定权重**: `w_dense={best_w}`（tune mean cov@5 最高）",
        "",
        "## 全量 48 题 vs baseline（w_dense=0）",
        "",
        "| 指标 | baseline | dense@best | Δ |",
        "|------|----------|------------|---|",
    ]
    b_stats, f_stats = baseline["stats"], final["stats"]
    lines.append(f"| 全体 mean cov@5 | {pct(b_stats['all_mean'])} | {pct(f_stats['all_mean'])} | {pct(f_stats['all_mean']-b_stats['all_mean'])} |")
    lines.append(f"| 原 35 题 mean | {pct(b_stats['orig35_mean'])} | {pct(f_stats['orig35_mean'])} | {pct(f_stats['orig35_mean']-b_stats['orig35_mean'])} |")
    lines.append(
        f"| vocab_mismatch 桶 | {pct(b_stats['vocab_mismatch_mean'])} (n={b_stats['vocab_mismatch_n']}) | "
        f"{pct(f_stats['vocab_mismatch_mean'])} | "
        f"{pct(f_stats['vocab_mismatch_mean']-b_stats['vocab_mismatch_mean'])} |"
    )
    lines.append(
        f"| 单文件 holdout | {b_stats['single_holdout_pass']}/{b_stats['single_holdout_n']} | "
        f"{f_stats['single_holdout_pass']}/{f_stats['single_holdout_n']} | "
        f"{f_stats['single_holdout_miss'] or '无回归'} |"
    )
    lines.append(
        f"| **封存 5 题 Recall@5** | {b_stats['sealed_pass5']}/{b_stats['sealed_n']} | "
        f"{f_stats['sealed_pass5']}/{f_stats['sealed_n']} | "
        f"{f_stats['sealed_pass5']-b_stats['sealed_pass5']:+d} |"
    )

    lines += ["", "### Q3/Q4/Q5 cov@5 与归一化值", "", "| ID | cov@5 | 理论上限 | cov@5/上限 |", "|----|-------|----------|-------------|"]
    for qid, cap in COV5_CAPS.items():
        c = f_stats["q_caps"][qid]
        lines.append(f"| {qid} | {pct(c['cov5'])} | {pct(cap)} | {c['normalized']:.2f} |")

    lines += [
        "",
        "## 耗时（mean per query）",
        "",
        f"- baseline（无 dense）: {baseline['timing']['mean_query_ms']} ms",
        f"- dense@best 总查询: {final['timing']['mean_query_ms']} ms",
        f"- dense 通道（embed+检索）: {final['timing']['mean_dense_ms']} ms",
        "",
        "## H3 专项：关闭「急停」hint，裸靠 dense",
        "",
        f"- w_dense=0, hint 急停 ON: cov@5={pct(h3['hint_on_w0']['cov5'])}, Kernel@5={h3['hint_on_w0']['kernel_in_top5']}",
        f"- w_dense=0, hint 急停 OFF: cov@5={pct(h3['hint_off_w0']['cov5'])}, Kernel@5={h3['hint_off_w0']['kernel_in_top5']}",
        f"- w_dense={best_w}, hint 急停 OFF: cov@5={pct(h3['hint_off_wbest']['cov5'])}, Kernel@5={h3['hint_off_wbest']['kernel_in_top5']}",
        "",
        f"top@5 (hint OFF, w={best_w}): `{h3['hint_off_wbest']['top5_files']}`",
        "",
        "## 退出条件判定",
        "",
    ]
    vm_delta = (f_stats["vocab_mismatch_mean"] - b_stats["vocab_mismatch_mean"]) * 100
    sealed_delta = f_stats["sealed_pass5"] - b_stats["sealed_pass5"]
    regress = f_stats["single_holdout_miss"]
    fail_reasons = []
    if vm_delta < 10:
        fail_reasons.append(f"vocab_mismatch 桶提升 {vm_delta:.1f}pp < 10pp")
    if sealed_delta < 0:
        fail_reasons.append(f"封存 5 题 Recall@5 下降 {sealed_delta}")
    if regress:
        fail_reasons.append(f"单文件 holdout 回归: {regress}")

    if fail_reasons:
        lines.append("**实验失败（按预设退出条件）**：")
        for r in fail_reasons:
            lines.append(f"- {r}")
        lines.append("")
        lines.append("建议：拔除 dense 通道，转向图扩展/结构化路径。")
    else:
        lines.append("**未触发失败退出条件**（需人工决定是否转正）。")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--from-data",
        action="store_true",
        help="Regenerate report from notes/dense_experiment_data.json only",
    )
    args = p.parse_args()
    if args.from_data:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        REPORT_PATH.write_text(format_report(data), encoding="utf-8")
        print(f"Wrote {REPORT_PATH}", file=sys.stderr)
        return 0

    questions = load_questions()

    di = DenseIndex()
    if di.is_stale() or not di.load():
        print("building dense index...", file=sys.stderr)
        manifest = di.build()
    else:
        manifest = json.loads((DEFAULT_INDEX_DIR / "manifest.json").read_text(encoding="utf-8"))
        print("dense index loaded", file=sys.stderr)

    di._load_model()
    print("embedding model ready", file=sys.stderr)

    tune_qs = [q for q in questions if is_tune_dev(q)]

    sweep_results = []
    sweep_idx: SearchIndex | None = None
    for w in WEIGHTS:
        print(f"sweep w_dense={w}...", file=sys.stderr)
        result, sweep_idx = run_config(w, tune_qs, sweep_idx)
        sweep_results.append(result)

    best = max(sweep_results, key=lambda s: mean_cov(s["rows"]))
    best_w = best["w_dense"]

    print("baseline w=0 full 48...", file=sys.stderr)
    baseline, _ = run_config(0, questions)
    print(f"final w={best_w} full 48...", file=sys.stderr)
    final, final_idx = run_config(best_w, questions, sweep_idx)

    h3_q = next(q for q in questions if q["id"] == "H3")
    os.environ["KB_W_DENSE"] = "0"
    os.environ.pop("KB_DISABLE_HALT_SYNONYMS", None)
    hint_on_w0 = h3_kernel_check(final_idx, h3_q)

    os.environ["KB_DISABLE_HALT_SYNONYMS"] = "1"
    hint_off_w0 = h3_kernel_check(final_idx, h3_q)

    os.environ["KB_W_DENSE"] = str(best_w)
    final_idx.load_dense_index(force=True)
    hint_off_wbest = h3_kernel_check(final_idx, h3_q)

    data = {
        "model": manifest.get("model", DEFAULT_MODEL),
        "dim": manifest.get("dim"),
        "chunk_count": manifest.get("chunk_count"),
        "questions": questions,
        "weight_sweep": sweep_results,
        "best_w": best_w,
        "baseline_dense0": baseline,
        "final": final,
        "h3_ablation": {
            "hint_on_w0": hint_on_w0,
            "hint_off_w0": hint_off_w0,
            "hint_off_wbest": hint_off_wbest,
        },
    }
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(format_report(data), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
