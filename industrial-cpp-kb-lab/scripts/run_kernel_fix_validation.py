"""
Kernel.cpp 召回修复假设验证：baseline / hint / rg / combo × 35 题回归。

用法：
    python scripts/run_kernel_fix_validation.py
    python scripts/run_kernel_fix_validation.py --skip-run   # 仅从已有 JSON 生成报告
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = LAB_ROOT / "notes" / "kernel_fix_validation"
REPORT_PATH = LAB_ROOT / "notes" / "kernel_fix_validation.md"

CONFIGS: list[tuple[str, dict[str, str]]] = [
    ("baseline", {}),
    ("hint_only", {"KB_HALT_HINT_EXTENDED": "1"}),
    ("rg_20", {"RG_CANDIDATE_FILE_LIMIT": "20"}),
    ("rg_30", {"RG_CANDIDATE_FILE_LIMIT": "30"}),
    ("hint_rg_30", {"KB_HALT_HINT_EXTENDED": "1", "RG_CANDIDATE_FILE_LIMIT": "30"}),
]


def run_config(label: str, extra_env: dict[str, str]) -> Path:
    out = OUT_DIR / f"{label}.json"
    env = os.environ.copy()
    env.pop("KB_HALT_HINT_EXTENDED", None)
    env.pop("RG_CANDIDATE_FILE_LIMIT", None)
    env.update(extra_env)
    cmd = [
        sys.executable,
        str(LAB_ROOT / "scripts" / "kernel_fix_eval_worker.py"),
        "--label", label,
        "--out", str(out),
    ]
    subprocess.run(cmd, env=env, check=True, cwd=str(LAB_ROOT))
    return out


def cov5(payload: dict, qid: str) -> float:
    return payload["multiplicity"]["per_question"][qid]["cov5"]


def fmt_pct(x: float) -> str:
    return f"{x:.1%}"


def regression_vs_baseline(base: dict, cur: dict) -> list[dict]:
    out = []
    base_pq = base["multiplicity"]["per_question"]
    cur_pq = cur["multiplicity"]["per_question"]
    for qid, br in base_pq.items():
        cr = cur_pq[qid]
        if br["cov5"] >= 1.0 and cr["cov5"] < 1.0:
            out.append({
                "id": qid,
                "split": br["split"],
                "multiplicity": br["multiplicity"],
                "baseline_cov": br["cov5"],
                "new_cov": cr["cov5"],
                "new_miss": cr["miss5"],
                "new_hit": cr["hit5"],
            })
    return out


def format_report(results: dict[str, dict]) -> str:
    labels = [c[0] for c in CONFIGS]
    base = results["baseline"]
    lines = [
        "# Kernel.cpp 召回修复 — 假设验证报告",
        "",
        "> 改动 A：`KB_HALT_HINT_EXTENDED=1` → `_hint_halt` 增加「急停」「紧急停止」",
        "> 改动 B：`RG_CANDIDATE_FILE_LIMIT=20|30`",
        "> 默认（baseline）两 env 均未设置，行为与改动前一致。",
        "",
        "## 配置对比表",
        "",
        "| 配置 | 全体 cov@5 | single | multi | holdout single | tune | H3 | H8 | Q4 | eval耗时(s) | 均查询(ms) |",
        "|------|-----------|--------|-------|----------------|------|----|----|-----|------------|-----------|",
    ]
    for label in labels:
        p = results[label]
        m = p["multiplicity"]
        t = p["timing"]
        lines.append(
            f"| {label} | {fmt_pct(m['all_mean'])} | {fmt_pct(m['single_mean'])} | "
            f"{fmt_pct(m['multi_mean'])} | {fmt_pct(m['holdout_single_mean'])} | "
            f"{fmt_pct(m['tune_mean'])} | {fmt_pct(cov5(p, 'H3'))} | "
            f"{fmt_pct(cov5(p, 'H8'))} | {fmt_pct(cov5(p, 'Q4'))} | "
            f"{t['eval_summary_sec']} | {t['mean_query_ms']} |"
        )

    lines += ["", "## 各改动独立结论", ""]
    conclusions = {
        "hint_only": _conclude_hint(results),
        "rg_20": _conclude_rg(results, "rg_20", 20),
        "rg_30": _conclude_rg(results, "rg_30", 30),
        "hint_rg_30": _conclude_combo(results),
    }
    for k, text in conclusions.items():
        lines.append(f"### {k}")
        lines.append(text)
        lines.append("")

    lines += ["## H3 / H8 / Q4 — Kernel 通道明细", ""]
    for label in labels:
        lines.append(f"### {label}")
        for qid in ("H3", "H8", "Q4"):
            tr = results[label]["traces"][qid]
            r = tr["retrieval"]
            pf = tr.get("rg_prefilter", {})
            ch = tr.get("topk_channel", {})
            lines.append(f"**{qid}** cov@5={cov5(results[label], qid):.0%}  "
                         f"kernel_in_pool={r['kernel_in_merged_pool']}  "
                         f"eval_top5_has_kernel={KERNEL_FILE in r['eval_top_k_files']}")
            lines.append(
                f"- hint_groups={r.get('hint_groups')}  tokens_extra={len(r.get('tokens', []))}"
            )
            lines.append(
                f"- rg预筛: limit={pf.get('prefilter_limit')}  "
                f"Kernel排名={pf.get('kernel_prefilter_rank')}  "
                f"预筛分={pf.get('kernel_prefilter_score', 0):.1f}  "
                f"进top-N={pf.get('kernel_in_prefilter_top_n')}  "
                f"rg_max={pf.get('kernel_rg_max', 0):.1f}"
            )
            if r.get("kernel_merged_detail"):
                d = r["kernel_merged_detail"][0]
                lines.append(
                    f"- 最佳Kernel chunk: rank={d['rank_all']} score={d['score']:.1f} "
                    f"channels={d.get('base_channels')} source={d.get('source')}"
                )
            if ch.get("in_eval_top5"):
                lines.append(
                    f"- **进top-5通道**: {ch.get('winning_channel')} "
                    f"(rank={ch.get('rank')} score={ch.get('score')})"
                )
            elif r["kernel_in_merged_pool"]:
                lines.append("- 进池但未进 top-5（排序/ diversify 截断）")
            lines.append("")
        lines.append("")

    lines += ["## 单文件 holdout 回归检查（相对 baseline）", ""]
    for label in labels:
        if label == "baseline":
            continue
        regs = regression_vs_baseline(base, results[label])
        if not regs:
            lines.append(f"- **{label}**: 无 holdout 单文件题从绿变红")
        else:
            lines.append(f"- **{label}**: {len(regs)} 题回归")
            for r in regs:
                if r["multiplicity"] == "single" and r["split"] == "holdout":
                    lines.append(
                        f"  - {r['id']}: {r['baseline_cov']:.0%}→{r['new_cov']:.0%}  "
                        f"miss={r['new_miss']}"
                    )
        lines.append("")

    lines += ["## 耗时对比", ""]
    lines.append("| 配置 | eval_summary(s) | mean_query(ms) | max_query(ms) | vs baseline |")
    lines.append("|------|-----------------|----------------|---------------|-------------|")
    b_t = base["timing"]
    for label in labels:
        t = results[label]["timing"]
        delta = t["mean_query_ms"] - b_t["mean_query_ms"]
        lines.append(
            f"| {label} | {t['eval_summary_sec']} | {t['mean_query_ms']} | "
            f"{t['max_query_ms']} | {delta:+.1f}ms |"
        )

    lines += [
        "",
        "## Revert 说明",
        "",
        "- 改动 A：不设置 `KB_HALT_HINT_EXTENDED`（或设为 0）",
        "- 改动 B：不设置 `RG_CANDIDATE_FILE_LIMIT`（默认 12）",
        "- 代码中的 env 门控保留在 `search/index.py`，未改 diversify/coherence/reporank",
        "",
    ]
    return "\n".join(lines)


KERNEL_FILE = "src/libs/Kernel.cpp"


def _conclude_hint(results: dict) -> str:
    p = results["hint_only"]
    b = results["baseline"]
    h3 = cov5(p, "H3") >= 1.0
    h8 = cov5(p, "H8") >= 1.0
    q4 = cov5(p, "Q4")
    regs = regression_vs_baseline(b, p)
    hold_single = [r for r in regs if r["split"] == "holdout" and r["multiplicity"] == "single"]
    ch_h3 = p["traces"]["H3"]["topk_channel"]
    if h3 or q4 > cov5(b, "Q4"):
        mech = ch_h3.get("winning_channel") or (
            "symbol(hint注入)" if p["traces"]["H3"]["retrieval"]["kernel_in_merged_pool"] else "无"
        )
        verdict = f"**部分有效** — H3={cov5(p,'H3'):.0%} H8={cov5(p,'H8'):.0%} Q4={q4:.0%}；"
        verdict += f"H3进top-5通道≈{mech}。"
    else:
        verdict = "**无效（对 H3/H8/Q4 无提升）** — hint 触发后仍不足以召回 Kernel。"
    if hold_single:
        verdict += f" **有回归**：{[r['id'] for r in hold_single]}"
    else:
        verdict += " holdout单文件无回归。"
    return verdict


def _conclude_rg(results: dict, key: str, n: int) -> str:
    p = results[key]
    b = results["baseline"]
    h3_pf = p["traces"]["H3"]["rg_prefilter"]
    h8_pf = p["traces"]["H8"]["rg_prefilter"]
    h3_in = h3_pf.get("kernel_in_prefilter_top_n")
    h8_in = h8_pf.get("kernel_in_prefilter_top_n")
    h3_green = cov5(p, "H3") >= 1.0
    h8_green = cov5(p, "H8") >= 1.0
    regs = [r for r in regression_vs_baseline(b, p)
            if r["split"] == "holdout" and r["multiplicity"] == "single"]
    text = (
        f"top-{n}: H3预筛Kernel rank={h3_pf.get('kernel_prefilter_rank')} "
        f"in_top={h3_in} rg_max={h3_pf.get('kernel_rg_max',0):.0f}; "
        f"H8 rank={h8_pf.get('kernel_prefilter_rank')} in_top={h8_in} "
        f"rg_max={h8_pf.get('kernel_rg_max',0):.0f}。"
    )
    if not h3_in and h3_pf.get("kernel_prefilter_rank"):
        text += f" H3 Kernel 排在第{h3_pf['kernel_prefilter_rank']}位（未进top-{n}）。"
    if h3_green or h8_green:
        text += f" **部分有效** cov H3={cov5(p,'H3'):.0%} H8={cov5(p,'H8'):.0%}。"
    else:
        text += " **对 H3/H8 无效** — 加宽预筛仍不足以让 Kernel 进池或 top-5。"
    if regs:
        text += f" 回归题：{[r['id'] for r in regs]}"
    return text


def _conclude_combo(results: dict) -> str:
    p = results["hint_rg_30"]
    b = results["baseline"]
    h3 = cov5(p, "H3")
    h8 = cov5(p, "H8")
    q4 = cov5(p, "Q4")
    ch3 = p["traces"]["H3"]["topk_channel"]
    regs = [r for r in regression_vs_baseline(b, p)
            if r["split"] == "holdout" and r["multiplicity"] == "single"]
    text = f"A+B@30: H3={h3:.0%} H8={h8:.0%} Q4={q4:.0%}。"
    if h3 >= 1.0:
        text += f" H3通道={ch3.get('winning_channel')}。"
    if h3 >= 1.0 and h8 >= 1.0 and not regs:
        text += " **两题均绿且无 holdout 单文件回归。**"
    elif (h3 >= 1.0 or h8 >= 1.0) and not regs:
        text += " **部分有效，无 holdout 单文件回归。**"
    elif regs:
        text += f" **有效但有回归**：{[r['id'] for r in regs]}"
    else:
        text += " **组合仍不足以修复 H3/H8。**"
    return text


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-run", action="store_true")
    args = p.parse_args()

    results: dict[str, dict] = {}
    if not args.skip_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for label, env in CONFIGS:
            print(f"Running {label}...", file=sys.stderr)
            run_config(label, env)
    for label, _ in CONFIGS:
        path = OUT_DIR / f"{label}.json"
        if not path.is_file():
            sys.exit(f"missing {path}")
        results[label] = json.loads(path.read_text(encoding="utf-8"))

    report = format_report(results)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
