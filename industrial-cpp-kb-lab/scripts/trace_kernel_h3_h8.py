"""
H3/H8 Kernel.cpp 候选链路追踪（只读诊断，不改检索/排序/生成逻辑）。

用法：
    python scripts/trace_kernel_h3_h8.py
    python scripts/trace_kernel_h3_h8.py --llm   # 额外跑 LLM 层（需 LLM_API_KEY）
    python scripts/trace_kernel_h3_h8.py -o notes/kernel_trace_H3_H8.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC = LAB_ROOT / "src"
KERNEL_FILE = "src/libs/Kernel.cpp"
TARGET_IDS = ("H3", "H8")

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_module(filename: str):
    path = SRC / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def rg_prefilter_kernel_rank(inst, channels: dict) -> dict:
    """Kernel.cpp rank in BM25/symbol prefilter file list (before rg runs)."""
    from search.index import RG_CANDIDATE_FILE_LIMIT
    KERNEL = "src/libs/Kernel.cpp"
    file_scores: dict[str, float] = {}
    for name in ("method", "class", "dispatch", "symbol", "bm25"):
        for cid, score in channels[name].items():
            chunk = inst._CHUNK_BY_ID.get(cid)
            if not chunk:
                continue
            f = chunk["file"]
            file_scores[f] = max(file_scores.get(f, 0.0), float(score))
    ranked = sorted(file_scores.items(), key=lambda x: -x[1])
    limit = RG_CANDIDATE_FILE_LIMIT
    kernel_rank = None
    kernel_prefilter_score = 0.0
    for i, (f, sc) in enumerate(ranked, 1):
        if f == KERNEL:
            kernel_rank = i
            kernel_prefilter_score = sc
            break
    rg_kernel_scores = [
        {"chunk_id": cid, "score": sc}
        for cid, sc in channels["rg"].items()
        if inst._CHUNK_BY_ID.get(cid, {}).get("file") == KERNEL
    ]
    return {
        "prefilter_limit": limit,
        "prefilter_total_files_scored": len(ranked),
        "kernel_prefilter_rank": kernel_rank,
        "kernel_prefilter_score": kernel_prefilter_score,
        "kernel_in_prefilter_top_n": kernel_rank is not None and kernel_rank <= limit,
        "kernel_rg_chunk_scores": rg_kernel_scores,
        "kernel_rg_max": max((x["score"] for x in rg_kernel_scores), default=0.0),
    }


def channel_maps(inst, query: str, tokens: list[str], src, repo):
    """Mirror search() score channels without modifying index.py."""
    method_scores = inst.search_method(query, tokens)
    class_scores = inst.search_class(query, tokens)
    dispatch_scores, dispatch_focus = inst.search_dispatch(query)
    sym_scores = inst.search_symbols(query, tokens)
    bm25_scores = inst.search_bm25(tokens)
    rg_candidates = inst._candidate_files_from_scores(
        method_scores, class_scores, dispatch_scores, sym_scores, bm25_scores,
        repo_root=repo,
    )
    rg_scores = inst.search_rg(tokens, src, repo, candidate_files=rg_candidates)
    return {
        "method": method_scores,
        "class": class_scores,
        "dispatch": dispatch_scores,
        "symbol": sym_scores,
        "bm25": bm25_scores,
        "rg": rg_scores,
        "dispatch_focus": dispatch_focus,
        "rg_candidate_files": [str(p) for p in rg_candidates],
        "rg_prefilter": rg_prefilter_kernel_rank(inst, {
            "method": method_scores, "class": class_scores,
            "dispatch": dispatch_scores, "symbol": sym_scores, "bm25": bm25_scores,
            "rg": rg_scores,
        }),
    }


def score_breakdown(idx, cid: str, channels: dict, query: str, tokens: list[str]) -> dict:
    chunk = idx._CHUNK_BY_ID[cid]
    base = 0.0
    per_channel: dict[str, float] = {}
    for name in ("method", "class", "dispatch", "symbol", "bm25", "rg"):
        sc = channels[name].get(cid, 0.0)
        if sc:
            per_channel[name] = sc
            base += sc
    bonus = idx.chunk_score_bonus(chunk)
    coherence = idx.context_coherence_adjustment(chunk, tokens)
    hint_hdr = idx.hint_key_header_boost(chunk, query)
    total = base + bonus + coherence + hint_hdr
    return {
        "base_channels": per_channel,
        "chunk_score_bonus": bonus,
        "context_coherence": coherence,
        "hint_key_header_boost": hint_hdr,
        "merged_pre_sort": total,
    }


def kernel_chunks(idx) -> list[dict]:
    return list(idx._CHUNKS_BY_FILE.get(KERNEL_FILE, []))


def why_kernel_not_recalled(idx, query: str, tokens: list[str], channels: dict) -> list[str]:
    """Explain per-channel why Kernel.cpp chunks got zero score."""
    lines: list[str] = []
    k_chunk_ids = {c["id"] for c in kernel_chunks(idx)}
    channel_names = ("method", "class", "dispatch", "symbol", "bm25", "rg")
    for name in channel_names:
        hits = [cid for cid in channels[name] if cid in k_chunk_ids]
        if hits:
            lines.append(f"- **{name}**: {len(hits)} Kernel chunk(s) scored")
        else:
            lines.append(f"- **{name}**: 0 Kernel chunk(s)")

    lines.append("")
    lines.append("**symbol 通道细查（expected symbols）：**")
    for sym_name in ("immediate_halt", "add_module", "Kernel"):
        syms = idx._SYMBOL_BY_NAME.get(sym_name.lower(), [])
        kernel_syms = [s for s in syms if KERNEL_FILE in s.get("file", "")]
        if kernel_syms:
            in_tokens = sym_name.lower() in tokens or "kernel" in tokens
            lines.append(
                f"- `{sym_name}` → Kernel.cpp 有 {len(kernel_syms)} 个符号；"
                f"query token 命中={in_tokens}"
            )
        else:
            lines.append(f"- `{sym_name}` → 无 Kernel.cpp 符号条目")

    rg_files = channels.get("rg_candidate_files", [])
    kernel_in_rg_pool = any(KERNEL_FILE.replace("/", "\\") in f or KERNEL_FILE in f for f in rg_files)
    lines.append("")
    lines.append(
        f"**rg 预筛**: Kernel.cpp {'在' if kernel_in_rg_pool else '不在'} top-{len(rg_files)} 候选文件列表；"
        f"rg 仅在预筛文件内跑 pattern 匹配"
    )
    pats = sorted({t for t in tokens if len(t) >= 3}, key=len, reverse=True)[:8]
    lines.append(f"- rg patterns（来自 tokens）: `{pats}` — Kernel.cpp 内无这些 token 的字面匹配则 rg=0")

    from search.index import matched_hint_groups, expand_query_tokens, tokenize
    base = tokenize(query)
    expanded = expand_query_tokens(query, base)
    added = [t for t in expanded if t not in base]
    hints = matched_hint_groups(query)
    lines.append("")
    lines.append(f"**hint 扩展**: groups=`{hints or '(none)'}`；扩展 token=`{added or '(none)'}`")
    if not hints and "KillButton" in query:
        lines.append(
            "- 「急停」未触发 `_hint_halt`（仅匹配 halt/stop/emergency/停止/报警）；"
            "未注入 Kernel / immediate_halt 等 hint token"
        )
    elif not hints and "main" in query.lower():
        lines.append(
            "- 未触发 entry/module hint；query 仅含 `main`，未注入 Kernel / add_module"
        )
    return lines


def trace_retrieval(search_mod, q: dict, *, top_k: int = 5) -> dict:
    idx = search_mod._INSTANCE
    from search.index import (
        DEFAULT_REPO_ROOT,
        SRC_ROOT,
        expand_query_tokens,
        flow_intent_query,
        matched_hint_groups,
        multi_file_structure_query,
        tokenize,
    )

    query = q["question"]
    src = SRC_ROOT
    repo = DEFAULT_REPO_ROOT
    tokens = expand_query_tokens(query, tokenize(query))
    channels = channel_maps(idx, query, tokens, src, repo)

    merged = idx.merge_scores(
        channels["method"], channels["class"], channels["dispatch"],
        channels["symbol"], channels["bm25"], channels["rg"],
        query_tokens=tokens, query=query,
    )

    all_hits: list[dict] = []
    for cid, score in merged.items():
        chunk = idx._CHUNK_BY_ID[cid]
        sources = [
            s for s, m in (
                ("method", channels["method"]), ("class", channels["class"]),
                ("dispatch", channels["dispatch"]), ("symbol", channels["symbol"]),
                ("bm25", channels["bm25"]), ("rg", channels["rg"]),
            )
            if cid in m
        ]
        all_hits.append(idx.hit_from_chunk(
            chunk, score, "+".join(sources) or "(bonus only)",
            focus_line=channels["dispatch_focus"].get(cid),
        ))
    all_hits.sort(key=idx._hit_sort_key)

    per_file = 1 if multi_file_structure_query(query) else 2
    diversified = idx.diversify(all_hits, top_k, per_file=per_file)

    exact_seed_ids = (
        set(channels["method"]) | set(channels["class"])
        | set(channels["dispatch"]) | set(channels["symbol"])
    )
    reporank_extras: list[dict] = []
    graph_extras: list[dict] = []
    use_reporank = idx._ENABLE_REPORANK
    if flow_intent_query(query) and not multi_file_structure_query(query):
        if use_reporank and idx._REPOMAP:
            reporank_extras = idx.search_reporank(
                diversified, query, exact_seed_ids=exact_seed_ids,
            )
        elif idx._CALL_GRAPH:
            graph_extras = idx.search_graph(diversified)

    final_primary = diversified + reporank_extras + graph_extras
    eval_hits = search_mod.search(query, top_k=top_k, bundle=False)

    k_chunks = kernel_chunks(idx)
    k_in_merged = [c for c in k_chunks if c["id"] in merged]
    k_not_in_merged = [c for c in k_chunks if c["id"] not in merged]

    def rank_in_list(hits: list[dict], file: str = KERNEL_FILE) -> list[dict]:
        out = []
        for i, h in enumerate(hits, 1):
            if h["file"] == file:
                out.append({**h, "rank": i})
        return out

    def diversify_drop_reason(h: dict) -> str | None:
        """If hit is in all_hits but not in diversified, explain per_file cap."""
        rank = next(i for i, x in enumerate(all_hits, 1) if x["chunk_id"] == h["chunk_id"])
        same_file_before = sum(
            1 for x in all_hits[: rank - 1] if x["file"] == h["file"]
        )
        if same_file_before >= per_file:
            return f"diversify per_file={per_file}: {same_file_before} earlier chunk(s) from same file"
        higher_rank_kept = diversified[-1]["chunk_id"] if len(diversified) >= top_k else None
        if rank > top_k:
            return f"rank {rank} > top_k={top_k}" + (
                f"; cutoff score ~{diversified[-1]['score']}" if diversified else ""
            )
        return "unknown"

    k_merged_detail = []
    for c in k_in_merged:
        cid = c["id"]
        br = score_breakdown(idx, cid, channels, query, tokens)
        hit = next(h for h in all_hits if h["chunk_id"] == cid)
        rank = next(i for i, h in enumerate(all_hits, 1) if h["chunk_id"] == cid)
        in_div = any(h["chunk_id"] == cid for h in diversified)
        in_eval = any(h["chunk_id"] == cid for h in eval_hits)
        k_merged_detail.append({
            "chunk_id": cid,
            "symbol": c.get("symbol", ""),
            "type": c["type"],
            "lines": f"{c['start_line']}-{c['end_line']}",
            "rank_all": rank,
            "score": hit["score"],
            "source": hit.get("source", ""),
            "in_top_k_diversified": in_div,
            "in_eval_top_k": in_eval,
            "diversify_drop": None if in_div else diversify_drop_reason(hit),
            **br,
        })

    return {
        "id": q["id"],
        "question": query,
        "expected_files": q["expected_files"],
        "expected_symbols": q.get("expected_symbols", []),
        "tokens": tokens,
        "why_not_recalled": why_kernel_not_recalled(idx, query, tokens, channels),
        "hint_groups": matched_hint_groups(query),
        "flow_intent": flow_intent_query(query),
        "multi_file_structure": multi_file_structure_query(query),
        "per_file_diversify": per_file,
        "use_reporank": use_reporank,
        "rg_candidate_files": channels["rg_candidate_files"],
        "rg_prefilter": channels.get("rg_prefilter", {}),
        "kernel_chunk_total": len(k_chunks),
        "kernel_in_merged_pool": len(k_in_merged),
        "kernel_not_in_merged": [
            {
                "chunk_id": c["id"],
                "symbol": c.get("symbol", ""),
                "type": c["type"],
                "lines": f"{c['start_line']}-{c['end_line']}",
            }
            for c in k_not_in_merged
        ],
        "kernel_merged_detail": sorted(k_merged_detail, key=lambda x: x["rank_all"]),
        "top5_diversified": [
            {
                "rank": i, "file": h["file"], "symbol": h.get("symbol", ""),
                "score": h["score"], "source": h.get("source", ""),
                "lines": f"{h['line_start']}-{h.get('line_end', h['line_start'])}",
            }
            for i, h in enumerate(diversified, 1)
        ],
        "reporank_extras": [
            {"file": h["file"], "symbol": h.get("symbol", ""), "score": h["score"]}
            for h in reporank_extras
        ],
        "graph_extras": [
            {"file": h["file"], "symbol": h.get("symbol", ""), "score": h["score"]}
            for h in graph_extras
        ],
        "eval_top_k_files": [h["file"] for h in eval_hits],
        "all_hits_kernel_ranks": rank_in_list(all_hits),
    }


def trace_bundle_llm(search_mod, ans_mod, q: dict, *, top_k: int = 8, run_llm: bool) -> dict:
    idx = search_mod._INSTANCE
    query = q["question"]
    bundle_hits = search_mod.search(query, top_k=top_k, bundle=True)
    primaries = [h for h in bundle_hits if h.get("bundle_role", "primary") == "primary"]
    trimmed = ans_mod.trim_context_hits(bundle_hits, 8)
    kernel_in_bundle_primary = [h for h in primaries if h["file"] == KERNEL_FILE]
    kernel_in_trimmed = [h for h in trimmed if h["file"] == KERNEL_FILE]

    out = {
        "bundle_primary_files": list(dict.fromkeys(h["file"] for h in primaries)),
        "kernel_in_bundle_primary": bool(kernel_in_bundle_primary),
        "kernel_bundle_primary_chunks": [
            {
                "symbol": h.get("symbol", ""),
                "score": h["score"],
                "role": h.get("bundle_role"),
                "lines": f"{h['line_start']}-{h.get('line_end', h['line_start'])}",
            }
            for h in kernel_in_bundle_primary
        ],
        "trimmed_files": list(dict.fromkeys(h["file"] for h in trimmed)),
        "kernel_in_trimmed_context": bool(kernel_in_trimmed),
        "kernel_trimmed_chunks": [
            {
                "symbol": h.get("symbol", ""),
                "role": h.get("bundle_role"),
                "score": h["score"],
            }
            for h in kernel_in_trimmed
        ],
    }

    if not run_llm:
        out["llm"] = {"skipped": True, "reason": "no --llm or LLM_API_KEY"}
        return out

    if not os.environ.get("LLM_API_KEY", "").strip():
        out["llm"] = {"skipped": True, "reason": "LLM_API_KEY not set"}
        return out

    prompt = ans_mod.build_prompt(ans_mod.load_prompt_template(), query, bundle_hits)
    provider, api_key, model, base_url = ans_mod.llm_config()
    text = ans_mod.call_llm(prompt, provider, api_key, model, base_url)
    prompt_path = LAB_ROOT / "notes" / f"kernel_trace_{q['id']}_prompt.md"
    answer_path = LAB_ROOT / "notes" / f"kernel_trace_{q['id']}_answer.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    answer_path.write_text(text, encoding="utf-8")
    cites = ans_mod.validate_citations(text, bundle_hits, idx._CHUNK_BY_ID)
    coverage = ans_mod.validate_answer_coverage(text, bundle_hits)
    kernel_mentioned = ans_mod.file_mentioned_in_answer(text, KERNEL_FILE)

    out["llm"] = {
        "model": f"{provider}/{model}",
        "kernel_mentioned_in_answer": kernel_mentioned,
        "expected_files_mentioned": {
            f: ans_mod.file_mentioned_in_answer(text, f) for f in q["expected_files"]
        },
        "coverage": coverage,
        "citations": cites,
        "answer_excerpt": text[:800] + ("..." if len(text) > 800 else ""),
        "prompt_chars": len(prompt),
        "prompt_path": str(prompt_path.relative_to(LAB_ROOT)),
        "answer_path": str(answer_path.relative_to(LAB_ROOT)),
    }
    return out


def verdict(retrieval: dict, llm_layer: dict) -> tuple[str, str]:
    """Return (layer, one-line reason)."""
    k_in_pool = retrieval["kernel_in_merged_pool"]
    k_in_eval = KERNEL_FILE in retrieval["eval_top_k_files"]
    k_detail = retrieval["kernel_merged_detail"]

    if k_in_pool == 0:
        gen_note = ""
        llm = llm_layer.get("llm", {})
        if not llm.get("skipped") and not llm_layer.get("kernel_in_trimmed_context"):
            gen_note = "；生成层亦未收到 Kernel（context 缺失），非 LLM 漏引用"
        return "丢在召回层", (
            f"Kernel.cpp 的 {retrieval['kernel_chunk_total']} 个 chunk 均未进入 merge_scores 候选池"
            f"{gen_note}"
        )

    if not k_in_eval:
        in_merged = [d for d in k_detail if d["in_top_k_diversified"]]
        if not in_merged:
            best = min(k_detail, key=lambda x: x["rank_all"])
            drop = best.get("diversify_drop") or f"rank={best['rank_all']}"
            return "丢在排序层", (
                f"Kernel.cpp 有 {k_in_pool} chunk 进入候选池，最高 rank={best['rank_all']} "
                f"score={best['score']:.1f}，未进 top-{len(retrieval['top5_diversified'])} diversify 输出：{drop}"
            )
        return "丢在排序层", "Kernel chunk 在 diversify 内但未出现在 eval top-k（reporank/graph 路径差异）"

    # Kernel in eval top-k — for cov@5 file-level, check file presence
  # eval checks file set, not chunk
    llm = llm_layer.get("llm", {})
    if llm.get("skipped"):
        return "未测生成层", (
            f"检索 top-5 已含 Kernel.cpp；生成层未跑（{llm.get('reason', '')}）"
        )

    if not llm_layer.get("kernel_in_trimmed_context"):
        return "丢在排序层（bundle/trim）", "eval@5 命中但 bundle+trim LLM 上下文未含 Kernel.cpp"

    if not llm.get("kernel_mentioned_in_answer"):
        return "丢在生成层", "Kernel.cpp 在 trimmed context 中但 LLM 答案未提及"

    return "生成层已引用", "Kernel.cpp 在 context 且答案有提及"


def format_markdown(traces: list[dict]) -> str:
    lines = [
        "# H3 / H8 — Kernel.cpp 候选链路追踪",
        "",
        "> 只读诊断；未修改检索/排序/生成逻辑。",
        "> eval cov@5 路径：`search(top_k=5, bundle=False)`。",
        "> LLM 路径：`search(top_k=8, bundle=True)` → `trim_context_hits(8)`。",
        "",
    ]
    for t in traces:
        r = t["retrieval"]
        b = t["bundle_llm"]
        v_layer, v_reason = t["verdict"]
        lines += [
            f"## {r['id']} — {r['question']}",
            "",
            f"**判定：{v_layer}** — {v_reason}",
            "",
            "### 0. 查询元数据",
            f"- tokens（含 hint 扩展）: `{', '.join(r['tokens'][:20])}{'...' if len(r['tokens'])>20 else ''}`",
            f"- hint_groups: `{r['hint_groups'] or '(none)'}`",
            f"- flow_intent={r['flow_intent']}  multi_file_structure={r['multi_file_structure']}  "
            f"diversify per_file={r['per_file_diversify']}  reporank={r['use_reporank']}",
            f"- expected_files: {r['expected_files']}",
            "",
            "### 1. 候选召回层",
            f"- Kernel.cpp 索引内 chunk 总数: **{r['kernel_chunk_total']}**",
            f"- 进入 merge_scores 候选池: **{r['kernel_in_merged_pool']}**",
            "",
        ]
        if r["kernel_in_merged_pool"] == 0:
            lines.append("**未召回** — Kernel.cpp 无任何 chunk 得分 > 0。")
            lines.append(f"- rg 预筛候选文件（前 12）: `{r['rg_candidate_files']}`")
            lines.append("")
            lines.extend(r.get("why_not_recalled", []))
            lines.append("")
            lines.append("未入池 chunk 列表：")
            for c in r["kernel_not_in_merged"][:8]:
                lines.append(
                    f"  - `{c['chunk_id']}` {c['type']} `{c['symbol']}` lines {c['lines']}"
                )
            if len(r["kernel_not_in_merged"]) > 8:
                lines.append(f"  - ... 另有 {len(r['kernel_not_in_merged'])-8} 个 chunk")
        else:
            lines.append("Kernel.cpp 在候选池中的 chunk（按全局 rank 排序）：")
            lines.append("")
            lines.append(
                "| rank | symbol | lines | score | source | coherence | bonus | in_top5 | drop_reason |"
            )
            lines.append("|------|--------|-------|-------|--------|-----------|-------|---------|-------------|")
            for d in r["kernel_merged_detail"]:
                drop = d["diversify_drop"] or ("yes" if d["in_top_k_diversified"] else "-")
                lines.append(
                    f"| {d['rank_all']} | {d['symbol']} | {d['lines']} | {d['score']:.1f} | "
                    f"{d['source']} | {d['context_coherence']:+.1f} | {d['chunk_score_bonus']:+.1f} | "
                    f"{'Y' if d['in_top_k_diversified'] else 'N'} | {drop} |"
                )
            lines.append("")
            lines.append("通道得分明细（merged 前）：")
            for d in r["kernel_merged_detail"][:5]:
                ch = d["base_channels"] or "(无通道命中，仅 bonus/coherence)"
                lines.append(f"- `{d['symbol']}` rank={d['rank_all']}: channels={ch}")

        lines += [
            "",
            "### 2. 排序层（diversify top-5 vs eval）",
            f"- eval top-5 文件: `{r['eval_top_k_files']}`",
            f"- Kernel.cpp in eval@5: **{KERNEL_FILE in r['eval_top_k_files']}**",
            "",
            "diversify 后 top-5 primary:",
            "",
        ]
        for h in r["top5_diversified"]:
            lines.append(
                f"  {h['rank']}. `{h['file']}` `{h['symbol']}` score={h['score']:.1f} "
                f"source={h['source']} lines={h['lines']}"
            )
        if r["reporank_extras"]:
            lines.append(f"- reporank extras: `{r['reporank_extras']}`")
        if r["graph_extras"]:
            lines.append(f"- graph extras: `{r['graph_extras']}`")

        lines += [
            "",
            "### 3. 生成层（bundle@8 + trim@8）",
            f"- bundle primary 文件: `{b['bundle_primary_files']}`",
            f"- Kernel in bundle primary: **{b['kernel_in_bundle_primary']}**",
            f"- trimmed context 文件: `{b['trimmed_files']}`",
            f"- Kernel in trimmed context: **{b['kernel_in_trimmed_context']}**",
            "",
        ]
        llm = b.get("llm", {})
        if llm.get("skipped"):
            lines.append(f"- LLM: 跳过（{llm.get('reason', '')}）")
            lines.append("- 历史 phase10_after.json：H3/H8 expected_files 均 1/2，Kernel 未在 primary。")
        else:
            lines.append(f"- LLM model: {llm.get('model')}")
            lines.append(f"- prompt 存档: `{llm.get('prompt_path')}` ({llm.get('prompt_chars')} chars)")
            lines.append(f"- 原始输出存档: `{llm.get('answer_path')}`")
            lines.append(f"- Kernel mentioned in answer: **{llm.get('kernel_mentioned_in_answer')}**")
            lines.append(f"- expected_files mentioned: `{llm.get('expected_files_mentioned')}`")
            cov = llm.get("coverage", {})
            lines.append(f"- primary coverage: {cov.get('mentioned')}/{cov.get('primary_files')}")
            lines.append("")
            lines.append("<details><summary>LLM answer excerpt</summary>")
            lines.append("")
            lines.append(llm.get("answer_excerpt", ""))
            lines.append("")
            lines.append("</details>")

        lines.append("")
        lines.append("---")
        lines.append("")

    lines += [
        "## 观测缺口说明",
        "",
        "- `merge_scores` 各通道分与 `context_coherence` / `hint_key_header_boost` 可通过本脚本复现；"
        "  **diversify 前完整候选列表**未持久化，本报告用全量 merged 排序列表代替。",
        "- eval 与 LLM 使用不同 top_k / bundle 路径；结论分两层标注。",
        "- 无内置 prompt/response 日志；`--llm` 可当场抓取 prompt 字符数与原始输出。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="H3/H8 Kernel.cpp trace")
    p.add_argument("--ids", default=",".join(TARGET_IDS))
    p.add_argument("--llm", action="store_true", help="run LLM layer (needs API key)")
    p.add_argument("-o", "--output", type=Path, default=LAB_ROOT / "notes" / "kernel_trace_H3_H8.md")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    load_dotenv(LAB_ROOT / ".env")
    search = load_module("03_search.py")
    ans = load_module("04_answer.py")
    search.load_index()

    ids = {x.strip() for x in args.ids.split(",") if x.strip()}
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    questions = [q for q in data["questions"] if q["id"] in ids]

    traces = []
    for q in questions:
        retrieval = trace_retrieval(search, q, top_k=5)
        bundle_llm = trace_bundle_llm(search, ans, q, top_k=8, run_llm=args.llm)
        layer, reason = verdict(retrieval, bundle_llm)
        traces.append({
            "retrieval": retrieval,
            "bundle_llm": bundle_llm,
            "verdict": (layer, reason),
        })

    if args.json:
        print(json.dumps(traces, ensure_ascii=False, indent=2, default=str))
    else:
        md = format_markdown(traces)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(md, encoding="utf-8")
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
