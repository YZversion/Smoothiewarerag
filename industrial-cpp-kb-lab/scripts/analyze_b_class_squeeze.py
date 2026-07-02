"""B-class squeeze analysis — read-only diagnostic, no retrieval changes."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
OUT_PATH = LAB_ROOT / "notes" / "b_class_squeeze_analysis.md"
SRC = LAB_ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search.index import (  # noqa: E402
    DEFAULT_REPO_ROOT,
    SRC_ROOT,
    SearchIndex,
    expand_query_tokens,
    flow_intent_query,
    matched_hint_groups,
    multi_file_structure_query,
    tokenize,
)

TARGET = {
    "H32": "src/libs/Kernel.cpp",
    "H35": "src/libs/Kernel.cpp",
    "H37": "src/libs/Kernel.cpp",
}


def channel_maps(idx: SearchIndex, query: str, tokens: list[str]) -> dict:
    method_scores = idx.search_method(query, tokens)
    class_scores = idx.search_class(query, tokens)
    dispatch_scores, dispatch_focus = idx.search_dispatch(query)
    sym_scores = idx.search_symbols(query, tokens)
    bm25_scores = idx.search_bm25(tokens)
    rg_candidates = idx._candidate_files_from_scores(
        method_scores, class_scores, dispatch_scores, sym_scores, bm25_scores,
        repo_root=DEFAULT_REPO_ROOT,
    )
    rg_scores = idx.search_rg(tokens, SRC_ROOT, DEFAULT_REPO_ROOT, candidate_files=rg_candidates)
    dense_scores = idx.search_dense(query)
    return {
        "method": method_scores,
        "class": class_scores,
        "dispatch": dispatch_scores,
        "dispatch_focus": dispatch_focus,
        "symbol": sym_scores,
        "bm25": bm25_scores,
        "rg": rg_scores,
        "dense": dense_scores,
        "rg_candidates": rg_candidates,
    }


def breakdown(idx: SearchIndex, cid: str, maps: dict, query: str, tokens: list[str]) -> dict:
    chunk = idx._CHUNK_BY_ID[cid]
    ch = {}
    base = 0.0
    for name in ("method", "class", "dispatch", "symbol", "bm25", "rg", "dense"):
        sc = maps[name].get(cid, 0.0)
        if sc:
            ch[name] = round(sc, 4)
            base += sc
    bonus = idx.chunk_score_bonus(chunk)
    coherence = idx.context_coherence_adjustment(chunk, tokens)
    hint_hdr = idx.hint_key_header_boost(chunk, query)
    graph = 0.0
    total = base + bonus + coherence + hint_hdr + graph
    return {
        "channels": ch,
        "chunk_bonus": round(bonus, 4),
        "coherence": round(coherence, 4),
        "hint_header": round(hint_hdr, 4),
        "graph": graph,
        "total_pre_graph": round(total, 4),
    }


def build_ranked_hits(idx: SearchIndex, query: str, maps: dict, tokens: list[str]) -> list[dict]:
    merged = idx.merge_scores(
        maps["method"], maps["class"], maps["dispatch"],
        maps["symbol"], maps["bm25"], maps["rg"], maps["dense"],
        query_tokens=tokens, query=query,
    )
    rows = []
    for cid, score in merged.items():
        chunk = idx._CHUNK_BY_ID[cid]
        bd = breakdown(idx, cid, maps, query, tokens)
        rows.append({
            "chunk_id": cid,
            "file": chunk["file"],
            "symbol": chunk.get("symbol") or "",
            "type": chunk["type"],
            "lines": f"{chunk['start_line']}-{chunk['end_line']}",
            "score": round(score, 4),
            "breakdown": bd,
        })
    rows.sort(key=lambda r: (-r["score"], r["file"], r["chunk_id"]))
    for i, r in enumerate(rows, 1):
        r["rank_merged"] = i
    return rows


def trace_search(idx: SearchIndex, query: str, top_k: int = 5) -> dict:
    tokens = expand_query_tokens(query, tokenize(query))
    maps = channel_maps(idx, query, tokens)
    ranked = build_ranked_hits(idx, query, maps, tokens)

    hits = []
    for r in ranked:
        chunk = idx._CHUNK_BY_ID[r["chunk_id"]]
        hits.append(idx.hit_from_chunk(
            chunk, r["score"], "merged",
            focus_line=maps["dispatch_focus"].get(r["chunk_id"]),
        ))
    hits.sort(key=idx._hit_sort_key)

    per_file = 1 if multi_file_structure_query(query) else 2
    diversified = idx.diversify(hits, top_k, per_file=per_file)

    exact_seed_ids = (
        set(maps["method"]) | set(maps["class"])
        | set(maps["dispatch"]) | set(maps["symbol"])
    )
    graph_extras: list[dict] = []
    reporank_extras: list[dict] = []
    use_reporank = idx._ENABLE_REPORANK
    if flow_intent_query(query) and not multi_file_structure_query(query):
        if use_reporank and idx._REPOMAP:
            reporank_extras = idx.search_reporank(
                diversified, query, exact_seed_ids=exact_seed_ids,
            )
        elif idx._CALL_GRAPH:
            graph_extras = idx.search_graph(diversified)

    final = diversified + reporank_extras + graph_extras
    for i, h in enumerate(final, 1):
        h["_final_rank"] = i
        h["_stage"] = (
            "graph" if h in graph_extras else
            "reporank" if h in reporank_extras else
            "diversify"
        )
        bd = breakdown(idx, h["chunk_id"], maps, query, tokens)
        if h["_stage"] == "graph":
            bd["graph"] = round(h["score"] - bd["total_pre_graph"], 4)
            bd["total_pre_graph"] = round(h["score"], 4)
        h["_breakdown"] = bd

    return {
        "tokens": tokens,
        "hint_groups": matched_hint_groups(query),
        "flow_intent": flow_intent_query(query),
        "multi_file_structure": multi_file_structure_query(query),
        "per_file": per_file,
        "use_reporank": use_reporank,
        "ranked": ranked,
        "diversified": diversified,
        "graph_extras": graph_extras,
        "final": final,
    }


def best_miss_row(ranked: list[dict], miss_file: str) -> dict | None:
    rows = [r for r in ranked if r["file"] == miss_file]
    if not rows:
        return None
    return min(rows, key=lambda r: r["rank_merged"])


def fmt_channels(bd: dict) -> str:
    parts = []
    for k in ("dense", "symbol", "bm25", "rg", "method", "class", "dispatch"):
        if k in bd["channels"]:
            parts.append(f"{k}={bd['channels'][k]}")
    if bd.get("chunk_bonus"):
        parts.append(f"bonus={bd['chunk_bonus']}")
    if bd.get("coherence"):
        parts.append(f"coherence={bd['coherence']}")
    if bd.get("hint_header"):
        parts.append(f"hint_hdr={bd['hint_header']}")
    if bd.get("graph"):
        parts.append(f"graph={bd['graph']}")
    return ", ".join(parts) if parts else "(无通道分，仅 bonus/coherence)"


def classify_squeeze(div_top5: list[dict], miss_file: str, expected_files: list[str]) -> tuple[str, str]:
    """Return (形态1|形态2, one-line reason)."""
    files_in_top5 = [h["file"] for h in div_top5]
    dup = Counter(files_in_top5)
    redundant_same_file = {f: c for f, c in dup.items() if c > 1}
    expected_set = set(expected_files)
    noise = [f for f in files_in_top5 if f not in expected_set]

    if redundant_same_file:
        offenders = ", ".join(f"{f}×{c}" for f, c in redundant_same_file.items())
        if any(f in expected_set for f in redundant_same_file):
            return "形态1", f"top-5 被同文件多 chunk 占槽（{offenders}），挤掉 {miss_file}"
    if len(noise) >= 3:
        return "形态2", f"top-5 以非 expected 噪音为主（{len(noise)}/5），{miss_file} 被不相关文件挤出"
    if noise:
        return "形态2", f"top-5 含 {len(noise)} 个非 expected 文件（{noise[:2]}…），{miss_file} 未入槽"
    return "形态1", f"top-5 均为 expected 相关文件但 {miss_file} 排名靠后，属同域文件竞争"


def main() -> int:
    os.environ["KB_W_DENSE"] = "20"
    os.environ.pop("KB_DISABLE_DENSE", None)

    questions = {q["id"]: q for q in json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]}

    idx = SearchIndex()
    idx.load_index()
    idx.load_dense_index(force=True)

    lines = [
        "# B 类挤出分析（dense@20，只读诊断）",
        "",
        "- 范围：H32/H35/H37 的 B 类 miss（`src/libs/Kernel.cpp`）",
        "- 配置冻结：`w_dense=20`，不改检索/融合/排序代码",
        "- diversify 基准：`per_file=2`（默认）；`multi_file_structure` 题为 `per_file=1`",
        "",
    ]

    morph_counts: Counter[str] = Counter()

    for qid, miss_file in TARGET.items():
        q = questions[qid]
        trace = trace_search(idx, q["question"], top_k=5)
        ranked = trace["ranked"]
        div5 = trace["diversified"]
        final = trace["final"]

        miss = best_miss_row(ranked, miss_file)
        div5_enriched = []
        for i, h in enumerate(div5, 1):
            bd = breakdown(idx, h["chunk_id"], channel_maps(idx, q["question"], trace["tokens"]), q["question"], trace["tokens"])
            div5_enriched.append({**h, "_slot": i, "_breakdown": bd})

        # re-use breakdown from trace final for diversify slots
        div5_detail = [h for h in final if h.get("_stage") == "diversify"][:5]
        if len(div5_detail) < 5:
            div5_detail = []
            for i, h in enumerate(div5, 1):
                bd = breakdown(idx, h["chunk_id"], channel_maps(idx, q["question"], trace["tokens"]), q["question"], trace["tokens"])
                div5_detail.append({**h, "_slot": i, "_breakdown": bd, "_stage": "diversify"})

        files_top5 = [h["file"] for h in div5_detail]
        dup = Counter(files_top5)

        lines += [
            f"## {qid} — {q['question']}",
            "",
            "### 运行配置",
            f"- hint_groups: `{trace['hint_groups'] or '(none)'}`",
            f"- flow_intent: {trace['flow_intent']}",
            f"- multi_file_structure: {trace['multi_file_structure']}",
            f"- diversify per_file: **{trace['per_file']}**",
            f"- graph extras: {len(trace['graph_extras'])} 条",
            f"- reporank: {trace['use_reporank']}",
            "",
            "### 1) diversify 后 top-5（eval 主槽位）",
            "",
            "| 槽位 | 文件 | chunk_id | symbol | 融合总分 | 分数构成 |",
            "|------|------|----------|--------|----------|----------|",
        ]

        for h in div5_detail:
            slot = h.get("_slot") or h.get("_final_rank")
            bd = h.get("_breakdown") or breakdown(
                idx, h["chunk_id"],
                channel_maps(idx, q["question"], trace["tokens"]),
                q["question"], trace["tokens"],
            )
            lines.append(
                f"| {slot} | `{h['file']}` | `{h['chunk_id']}` | `{h.get('symbol','')}` | "
                f"{h['score']:.2f} | {fmt_channels(bd)} |"
            )

        if trace["graph_extras"]:
            lines += ["", "### graph 追加（不计入 top-5 槽位，但 eval 可能命中文件）", ""]
            for h in trace["graph_extras"]:
                bd = h.get("_breakdown", {})
                lines.append(
                    f"- `{h['file']}` chunk=`{h['chunk_id']}` score={h['score']:.2f} "
                    f"({fmt_channels(bd)})"
                )

        lines += ["", "### 2) miss 文件排名", ""]
        if miss:
            fifth = div5_detail[4] if len(div5_detail) >= 5 else None
            gap = round(fifth["score"] - miss["score"], 4) if fifth else None
            lines += [
                f"- miss 文件：`{miss_file}`",
                f"- 最佳 chunk：`{miss['chunk_id']}`（{miss['symbol']} {miss['lines']}）",
                f"- 全量 merged 排名：**第 {miss['rank_merged']} 名**",
                f"- 融合总分：**{miss['score']:.4f}**",
                f"- 分数构成：{fmt_channels(miss['breakdown'])}",
            ]
            if fifth:
                lines.append(f"- 第 5 名分数：**{fifth['score']:.4f}**（`{fifth['file']}`）")
                lines.append(f"- 与第 5 名分差：**{gap:.4f}**（miss 更低）")
            in_div = any(h["file"] == miss_file for h in div5_detail)
            lines.append(f"- 是否在 diversify top-5：**{'是' if in_div else '否'}**")
        else:
            lines.append(f"- `{miss_file}` 无 merged 分数（零信号）")

        lines += ["", "### 3) 同文件多 chunk 占槽", ""]
        multi = {f: c for f, c in dup.items() if c > 1}
        if multi:
            for f, c in multi.items():
                lines.append(f"- **是**：`{f}` 占 **{c}** 个槽位")
        else:
            lines.append("- **否**：top-5 内每文件至多 1 个 chunk")

        morph, reason = classify_squeeze(div5_detail, miss_file, q["expected_files"])
        morph_counts[morph] += 1
        lines += [
            "",
            "### 4) 一句话结论",
            f"- **{morph}**：{reason}",
            "",
            "---",
            "",
        ]

    lines += [
        "## 形态分布汇总（3 题）",
        "",
        f"- 形态1（被正确文件冗余 chunk 挤出）：**{morph_counts.get('形态1', 0)}** 题",
        f"- 形态2（被不相关噪音文件挤出）：**{morph_counts.get('形态2', 0)}** 题",
        "",
        "决策提示：形态1 为主 → 优先考虑 diversify 局部调整；形态2 为主 → 残留挂起，转向 Phase 7 准备。",
    ]

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"morph: {dict(morph_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
