"""Diagnose residual vocab_mismatch misses under dense@20 (tune only)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
SRC = LAB_ROOT / "src"
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
OUT_PATH = LAB_ROOT / "notes" / "vocab_mismatch_residual.md"

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


def load_questions() -> list[dict]:
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    return data["questions"]


def is_vocab_tune(q: dict) -> bool:
    note = q.get("note", "")
    vocab = "vocab_mismatch=true" in note.lower()
    if not vocab:
        return False
    if q.get("dev_split") != "tune":
        return False
    if q.get("dev_split") == "sealed":
        return False
    return True


def channel_maps(idx: SearchIndex, query: str, tokens: list[str]) -> dict[str, dict[str, float]]:
    method_scores = idx.search_method(query, tokens)
    class_scores = idx.search_class(query, tokens)
    dispatch_scores, _dispatch_focus = idx.search_dispatch(query)
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
        "symbol": sym_scores,
        "bm25": bm25_scores,
        "rg": rg_scores,
        "dense": dense_scores,
    }


def dense_file_rank(idx: SearchIndex, dense_scores: dict[str, float], target_file: str) -> tuple[bool, int | None, float]:
    rows: list[tuple[str, str, float]] = []
    for cid, sc in dense_scores.items():
        chunk = idx._CHUNK_BY_ID.get(cid)
        if not chunk:
            continue
        rows.append((cid, chunk["file"], float(sc)))
    rows.sort(key=lambda x: -x[2])
    best_rank = None
    best_score = 0.0
    for i, (_cid, file, score) in enumerate(rows, 1):
        if file == target_file:
            best_rank = i
            best_score = score
            break
    return best_rank is not None, best_rank, best_score


def non_dense_signals_for_file(idx: SearchIndex, maps: dict[str, dict[str, float]], target_file: str) -> dict[str, bool]:
    by_channel = {}
    for name in ("symbol", "bm25", "rg", "method", "class", "dispatch"):
        hit = False
        for cid in maps[name]:
            chunk = idx._CHUNK_BY_ID.get(cid)
            if chunk and chunk["file"] == target_file:
                hit = True
                break
        by_channel[name] = hit
    return by_channel


def main() -> int:
    os.environ["KB_W_DENSE"] = "20"
    os.environ.pop("KB_DISABLE_DENSE", None)

    idx = SearchIndex()
    idx.load_index()
    idx.load_dense_index(force=True)

    questions = [q for q in load_questions() if is_vocab_tune(q)]
    questions.sort(key=lambda q: q["id"])

    records: list[dict] = []
    class_a_qids: set[str] = set()
    class_b_qids: set[str] = set()
    class_a_files = 0
    class_b_files = 0

    for q in questions:
        query = q["question"]
        expected = q["expected_files"]
        top5 = idx.search(query, top_k=5, bundle=False)
        top10 = idx.search(query, top_k=10, bundle=False)
        top5_files = [h["file"] for h in top5]
        top10_files = [h["file"] for h in top10]
        missed = [f for f in expected if f not in set(top5_files)]
        if not missed:
            continue

        tokens = expand_query_tokens(query, tokenize(query))
        maps = channel_maps(idx, query, tokens)
        hint_groups = matched_hint_groups(query)
        graph_used = flow_intent_query(query) and (not multi_file_structure_query(query))

        misses = []
        for mf in missed:
            in_dense, d_rank, d_score = dense_file_rank(idx, maps["dense"], mf)
            non_dense = non_dense_signals_for_file(idx, maps, mf)
            final_rank10 = None
            for i, f in enumerate(top10_files, 1):
                if f == mf:
                    final_rank10 = i
                    break

            if not in_dense:
                cls = "A"
                cls_reason = "dense top-50未覆盖该文件"
                class_a_qids.add(q["id"])
                class_a_files += 1
            else:
                cls = "B"
                if final_rank10 is None:
                    cls_reason = "dense命中但融合后未进top-10"
                elif 6 <= final_rank10 <= 10:
                    cls_reason = "dense命中但融合后卡在6-10"
                else:
                    cls_reason = "dense命中但融合后仍未进top-5"
                class_b_qids.add(q["id"])
                class_b_files += 1

            misses.append({
                "file": mf,
                "class": cls,
                "reason": cls_reason,
                "dense_in_top50": in_dense,
                "dense_rank": d_rank,
                "dense_score": round(d_score, 4),
                "final_rank10": final_rank10,
                "non_dense_signals": non_dense,
            })

        records.append({
            "id": q["id"],
            "question": query,
            "hint_groups": hint_groups,
            "graph_path_active": graph_used,
            "top5_files": top5_files,
            "top10_files": top10_files,
            "misses": misses,
        })

    lines = [
        "# vocab_mismatch 残留诊断（dense@20, tune-only）",
        "",
        "- 范围：仅 `dev_split=tune` 且 `vocab_mismatch=true` 题目；不触碰 sealed。",
        "- 配置：`KB_W_DENSE=20`，沿用正式检索逻辑；本报告只诊断不修复。",
        "",
    ]
    for rec in records:
        lines += [
            f"## {rec['id']}",
            "",
            f"- 问题：{rec['question']}",
            f"- hint_groups: `{rec['hint_groups'] or '(none)'}`",
            f"- graph 路径是否活跃：{rec['graph_path_active']}",
            f"- top5: `{rec['top5_files']}`",
            f"- top10: `{rec['top10_files']}`",
            "",
        ]
        for miss in rec["misses"]:
            lines += [
                f"### miss: `{miss['file']}`",
                f"- 分类：**{miss['class']}类**（{miss['reason']}）",
                f"- dense：in_top50={miss['dense_in_top50']} rank={miss['dense_rank']} score={miss['dense_score']}",
                f"- 融合后排名(top10口径)：{miss['final_rank10']}",
                "- 其他通道是否有文件级信号："
                + f" symbol={miss['non_dense_signals']['symbol']},"
                + f" bm25={miss['non_dense_signals']['bm25']},"
                + f" rg={miss['non_dense_signals']['rg']},"
                + f" method={miss['non_dense_signals']['method']},"
                + f" class={miss['non_dense_signals']['class']},"
                + f" dispatch={miss['non_dense_signals']['dispatch']}",
                "",
            ]

    lines += [
        "## A/B 分布汇总",
        "",
        f"- A类（dense也接不住）: 题数 {len(class_a_qids)}，miss文件数 {class_a_files}",
        f"- B类（dense接住但未进top-5）: 题数 {len(class_b_qids)}，miss文件数 {class_b_files}",
        "",
        "结论仅用于下一步方向决策（拼接格式 / 融合层 / 图扩展），本轮不改逻辑。",
    ]

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
