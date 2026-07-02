"""
扩 holdout 题集后评估报告：分桶 + 新题 miss 通道级 trace。

用法：
    python scripts/run_eval_expansion_report.py
    python scripts/run_eval_expansion_report.py --from-json notes/eval_expansion_summary.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC = LAB_ROOT / "src"
REPORT_PATH = LAB_ROOT / "notes" / "eval_expansion_report.md"
SUMMARY_JSON = LAB_ROOT / "notes" / "eval_expansion_summary.json"

_TRACE_PATH = LAB_ROOT / "scripts" / "trace_kernel_h3_h8.py"
_spec = importlib.util.spec_from_file_location("_trace", _TRACE_PATH)
_trace = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_trace)

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_search():
    path = SRC / "03_search.py"
    spec = importlib.util.spec_from_file_location("_kb_search", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.load_index()
    return mod


def parse_note(note: str) -> dict:
    out = {"category": "", "vocab_mismatch": False}
    for part in note.split(";"):
        part = part.strip()
        if part.startswith("category="):
            out["category"] = part.split("=", 1)[1]
        elif part.startswith("vocab_mismatch="):
            out["vocab_mismatch"] = part.split("=", 1)[1].lower() == "true"
    return out


def bucket_stats(rows: list[dict]) -> dict:
    def mean(sub):
        return sum(r["cov5"] for r in sub) / len(sub) if sub else 0.0

    return {
        "n": len(rows),
        "mean_cov5": mean(rows),
        "single_mean": mean([r for r in rows if r["multiplicity"] == "single"]),
        "multi_mean": mean([r for r in rows if r["multiplicity"] == "multi"]),
    }


def file_channel_detail(search_mod, question: dict, miss_file: str) -> dict:
    idx = search_mod._INSTANCE
    from search.index import DEFAULT_REPO_ROOT, SRC_ROOT, expand_query_tokens, tokenize

    query = question["question"]
    tokens = expand_query_tokens(query, tokenize(query))
    channels = _trace.channel_maps(idx, query, tokens, SRC_ROOT, DEFAULT_REPO_ROOT)
    merged = idx.merge_scores(
        channels["method"], channels["class"], channels["dispatch"],
        channels["symbol"], channels["bm25"], channels["rg"],
        query_tokens=tokens, query=query,
    )
    file_chunks = [c for c in idx._CHUNKS_BY_FILE.get(miss_file, [])]
    in_pool = [c for c in file_chunks if c["id"] in merged]
    per_ch = {}
    for name in ("method", "class", "dispatch", "symbol", "bm25", "rg"):
        hits = {cid: sc for cid, sc in channels[name].items()
                if idx._CHUNK_BY_ID.get(cid, {}).get("file") == miss_file}
        if hits:
            per_ch[name] = hits
    pf = _trace.rg_prefilter_kernel_rank(idx, {
        "method": channels["method"], "class": channels["class"],
        "dispatch": channels["dispatch"], "symbol": channels["symbol"],
        "bm25": channels["bm25"], "rg": channels["rg"],
    })
    # generalize prefilter rank for any file
    file_scores: dict[str, float] = {}
    for name in ("method", "class", "dispatch", "symbol", "bm25"):
        for cid, score in channels[name].items():
            ch = idx._CHUNK_BY_ID.get(cid)
            if not ch:
                continue
            f = ch["file"]
            file_scores[f] = max(file_scores.get(f, 0.0), float(score))
    ranked = sorted(file_scores.items(), key=lambda x: -x[1])
    file_rank = next((i for i, (f, _) in enumerate(ranked, 1) if f == miss_file), None)
    file_score = file_scores.get(miss_file, 0.0)
    from search.index import RG_CANDIDATE_FILE_LIMIT
    return {
        "file": miss_file,
        "chunks_in_pool": len(in_pool),
        "total_chunks": len(file_chunks),
        "prefilter_rank": file_rank,
        "prefilter_score": file_score,
        "prefilter_in_top_n": file_rank is not None and file_rank <= RG_CANDIDATE_FILE_LIMIT,
        "channels": per_ch,
        "zero_signal": len(in_pool) == 0,
    }



def run_eval() -> dict:
    questions = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]
    search = load_search()
    t0 = time.perf_counter()
    summary = search.eval_summary()
    elapsed = time.perf_counter() - t0

    by_id = {d["id"]: d for d in summary["details"]}
    rows = []
    for q in questions:
        d = by_id[q["id"]]
        note = parse_note(q.get("note", ""))
        rows.append({
            "id": q["id"],
            "split": q.get("split", "tune"),
            "batch": q.get("batch", "original"),
            "multiplicity": "multi" if len(q["expected_files"]) > 1 else "single",
            "category": note["category"],
            "vocab_mismatch": note["vocab_mismatch"],
            "cov5": d["cov5"],
            "hit5": d["hit5"],
            "miss5": d["miss5"],
            "question": q["question"],
            "expected_files": q["expected_files"],
        })

    orig35 = [r for r in rows if r["batch"] == "original"]
    old_holdout = [r for r in rows if r["split"] == "holdout" and r["batch"] == "original"]
    new_holdout = [r for r in rows if r["batch"] == "expansion_v1"]
    hub_new = [r for r in new_holdout if r["category"] == "hub召回"]

    misses = [r for r in rows if r["cov5"] < 1.0]
    miss_traces = {}
    for r in misses:
        q = next(x for x in questions if x["id"] == r["id"])
        miss_traces[r["id"]] = {
            "question": r["question"],
            "cov5": r["cov5"],
            "miss5": r["miss5"],
            "files": [
                file_channel_detail(search, q, f) for f in r["miss5"]
            ],
        }

    # hub category1 H8-style failures
    hub_h8_style = []
    for r in hub_new:
        if r["cov5"] >= 1.0:
            continue
        q = next(x for x in questions if x["id"] == r["id"])
        for f in r["miss5"]:
            det = file_channel_detail(search, q, f)
            if det["zero_signal"]:
                hub_h8_style.append({"id": r["id"], "file": f, **det})

    return {
        "eval_time_sec": round(elapsed, 3),
        "summary": summary,
        "rows": rows,
        "buckets": {
            "all": bucket_stats(rows),
            "original_35": bucket_stats(orig35),
            "old_holdout": bucket_stats(old_holdout),
            "new_holdout": bucket_stats(new_holdout),
            "hub_expansion": bucket_stats(hub_new),
            "by_category": {
                cat: bucket_stats([r for r in new_holdout if r["category"] == cat])
                for cat in sorted({r["category"] for r in new_holdout})
            },
        },
        "miss_traces": miss_traces,
        "hub_h8_style_zero_signal": hub_h8_style,
    }


def format_report(data: dict) -> str:
    b = data["buckets"]
    s = data["summary"]
    lines = [
        "# Eval 扩 holdout 题集报告",
        "",
        f"> baseline（halt hint 转正后）eval 耗时 {data['eval_time_sec']}s",
        f"> gate_ok={s.get('gate_ok')}  全体 mean_cov@5={s.get('mean_cov5', 0):.1%}  "
        f"({s.get('total')} 题)",
        "",
        "## 分桶统计",
        "",
        "| 分桶 | n | mean cov@5 | single | multi |",
        "|------|---|------------|--------|-------|",
    ]
    for name, st in [
        ("全体", b["all"]),
        ("原 35 题", b["original_35"]),
        ("旧 holdout H1-H30", b["old_holdout"]),
        ("新 holdout H31-H43", b["new_holdout"]),
        ("新题·hub召回", b["hub_expansion"]),
    ]:
        lines.append(
            f"| {name} | {st['n']} | {st['mean_cov5']:.1%} | "
            f"{st['single_mean']:.1%} | {st['multi_mean']:.1%} |"
        )
    lines.append("")
    lines.append("### 新题按 note 类别")
    lines.append("")
    for cat, st in b["by_category"].items():
        lines.append(f"- **{cat}**: n={st['n']} mean={st['mean_cov5']:.1%} multi={st['multi_mean']:.1%}")

    lines += ["", "## 原 35 题 baseline 确认", ""]
    orig = [r for r in data["rows"] if r["batch"] == "original"]
    orig_mean = sum(r["cov5"] for r in orig) / len(orig)
    lines.append(f"- 原 35 题 mean cov@5: **{orig_mean:.1%}**（预期 ≈96.4% / hint_only）")
    old_single_miss = [r["id"] for r in orig if r["split"] == "holdout"
                       and r["multiplicity"] == "single" and r["cov5"] < 1.0]
    lines.append(f"- 旧 holdout 单文件题 miss: {old_single_miss or '无（100%）'}")

    lines += ["", "## 新题逐题结果（H31-H43）", ""]
    lines.append("| ID | 类别 | cov@5 | hit/miss | vocab_mismatch |")
    lines.append("|----|------|-------|----------|----------------|")
    for r in data["rows"]:
        if r["batch"] != "expansion_v1":
            continue
        hit_n = len(r["hit5"])
        exp_n = len(r["expected_files"])
        lines.append(
            f"| {r['id']} | {r['category']} | {r['cov5']:.0%} | "
            f"{hit_n}/{exp_n} | {r['vocab_mismatch']} |"
        )

    lines += ["", "## Miss 题通道级明细", ""]
    for qid, tr in sorted(data["miss_traces"].items()):
        lines.append(f"### {qid} — {tr['question']}")
        lines.append(f"cov@5={tr['cov5']:.0%}  miss={tr['miss5']}")
        for fd in tr["files"]:
            lines.append(
                f"- `{fd['file']}`: pool={fd['chunks_in_pool']}/{fd['total_chunks']}  "
                f"prefilter_rank={fd['prefilter_rank']} score={fd['prefilter_score']:.1f}  "
                f"zero_signal={fd['zero_signal']}"
            )
            if fd["channels"]:
                lines.append(f"  - channels: {list(fd['channels'].keys())}")
            else:
                lines.append("  - channels: **(none)**")
        lines.append("")

    lines += ["", "## 关键问题：类别1 hub 题有多少与 H8 同机制（目标文件全通道零信号）？", ""]
    hz = data["hub_h8_style_zero_signal"]
    hub_ids = sorted({x["id"] for x in hz})
    hub_cat = [r for r in data["rows"] if r["batch"] == "expansion_v1" and r["category"] == "hub召回"]
    lines.append(
        f"- hub 类新题共 **{len(hub_cat)}** 道；其中 **{len(hub_ids)}** 道至少有一个 expected 文件全通道零信号。"
    )
    if hz:
        lines.append("- 零信号清单：")
        for item in hz:
            lines.append(
                f"  - {item['id']}: `{item['file']}` prefilter_rank={item['prefilter_rank']} "
                f"score={item['prefilter_score']:.1f}"
            )
    else:
        lines.append("- **无** — hub 类新题未观察到与 H8 相同的全零信号 miss（或全部命中）。")

    lines += ["", "## 结论留白", "", "（待人工判断：hub 扩展机制是否值得建、dense 实验是否提前）", ""]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--from-json", type=Path)
    args = p.parse_args()

    if args.from_json:
        data = json.loads(args.from_json.read_text(encoding="utf-8"))
    else:
        data = run_eval()
        SUMMARY_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(format_report(data), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
