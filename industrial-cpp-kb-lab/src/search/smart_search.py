"""
Smart search — LLM query planner + multi-query retrieval merge.

Does not modify SearchIndex.search(); calls it per sub-query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from query_planner import QueryPlan, fallback_plan, plan_query

if TYPE_CHECKING:
    from search.index import SearchIndex

MAX_SUB_QUERIES = 10
MULTI_HIT_BOOST = 0.15
RAW_HIT_BOOST = 0.1
MUST_HAVE_PENALTY = 0.25


def _dedupe_queries(raw: str, plan: QueryPlan) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(q: str) -> None:
        q = q.strip()
        if not q:
            return
        key = q.lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(q)

    add(raw)
    for q in plan.search_queries:
        add(q)
    for sym in plan.symbols:
        add(sym)
    return ordered[:MAX_SUB_QUERIES]


def _chunk_matches_must_have(hit: dict, must_have: list[str]) -> bool:
    if not must_have:
        return True
    blob = " ".join(
        [
            hit.get("file", ""),
            hit.get("symbol", ""),
            hit.get("class", ""),
            hit.get("snippet", ""),
        ]
    ).lower()
    return any(m.lower() in blob for m in must_have)


def _merge_hits(
    raw_query: str,
    per_query_hits: list[tuple[str, list[dict]]],
    plan: QueryPlan,
    top_k: int,
) -> list[dict]:
    merged: dict[str, dict] = {}
    match_counts: dict[str, int] = {}
    raw_lower = raw_query.strip().lower()

    for sub_q, hits in per_query_hits:
        sub_lower = sub_q.strip().lower()
        for hit in hits:
            cid = hit["chunk_id"]
            base_score = float(hit.get("score", 0))
            if cid not in merged:
                merged[cid] = dict(hit)
                match_counts[cid] = 1
                merged[cid]["matched_queries"] = [sub_q]
            else:
                match_counts[cid] += 1
                if base_score > float(merged[cid].get("score", 0)):
                    merged[cid]["score"] = base_score
                    for k in ("file", "line_start", "symbol", "source", "snippet"):
                        if hit.get(k):
                            merged[cid][k] = hit[k]
                merged[cid]["matched_queries"].append(sub_q)

            if sub_lower == raw_lower:
                merged[cid]["score"] = float(merged[cid].get("score", 0)) + RAW_HIT_BOOST

    out: list[dict] = []
    for cid, hit in merged.items():
        extra = match_counts[cid] - 1
        if extra > 0:
            hit["score"] = round(float(hit["score"]) + MULTI_HIT_BOOST * extra, 2)
        if not _chunk_matches_must_have(hit, plan.must_have):
            hit["score"] = round(max(0.0, float(hit["score"]) - MUST_HAVE_PENALTY), 2)
        src = hit.get("source", "")
        if "smart" not in src.split("+"):
            hit["source"] = f"{src}+smart" if src else "smart"
        hit["planner_intent"] = plan.intent
        out.append(hit)

    out.sort(key=lambda h: (-float(h.get("score", 0)), h.get("file", ""), h.get("line_start", 0)))
    return out[:top_k]


def smart_search(
    idx: "SearchIndex",
    query: str,
    top_k: int = 10,
    *,
    plan: QueryPlan | None = None,
    skip_planner: bool = False,
) -> tuple[QueryPlan, list[dict]]:
    raw = query.strip()
    if not raw:
        return fallback_empty_plan(), []

    if skip_planner:
        effective_plan = plan or fallback_plan(raw)
    else:
        effective_plan = plan or plan_query(raw)

    sub_queries = _dedupe_queries(raw, effective_plan)
    if not sub_queries:
        return effective_plan, []

    per_query_hits: list[tuple[str, list[dict]]] = []
    for sub_q in sub_queries:
        hits = idx.search(sub_q, top_k=top_k, bundle=False)
        per_query_hits.append((sub_q, hits))

    merged = _merge_hits(raw, per_query_hits, effective_plan, top_k)
    return effective_plan, merged


def fallback_empty_plan() -> QueryPlan:
    return fallback_plan("", reason="planner fallback: empty query")
