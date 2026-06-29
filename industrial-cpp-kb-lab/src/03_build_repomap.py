"""
Phase 9 — Repomap graph builder (stdlib only).

Builds a small weighted code graph for optional personalized PageRank A/B.
The graph is a ranking aid only; source chunks and dispatch evidence remain the
facts shown to the user.

Usage:
    python src/03_build_repomap.py

Inputs:
    data/chunks.jsonl
    data/symbol_index.json
    data/call_graph.json
    data/dispatch_index.json

Outputs:
    data/repomap_graph.json
    data/repomap_scores.json
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
CHUNKS_PATH = LAB_ROOT / "data" / "chunks.jsonl"
SYMBOLS_PATH = LAB_ROOT / "data" / "symbol_index.json"
CALL_GRAPH_PATH = LAB_ROOT / "data" / "call_graph.json"
DISPATCH_INDEX_PATH = LAB_ROOT / "data" / "dispatch_index.json"
GRAPH_OUTPUT_PATH = LAB_ROOT / "data" / "repomap_graph.json"
SCORES_OUTPUT_PATH = LAB_ROOT / "data" / "repomap_scores.json"

NOISY_MENTION_MAX_CHUNKS = 30
MIN_SYMBOL_LEN = 4
PAGERANK_DAMPING = 0.85
PAGERANK_ITERS = 40

MENTION_FWD_WEIGHT = 3.0
MENTION_REV_WEIGHT = 1.5
SAME_FILE_OVERVIEW_WEIGHT = 0.45
SAME_FILE_ADJACENT_WEIGHT = 0.25
INCLUDE_WEIGHT = 1.0
INCLUDE_REV_WEIGHT = 0.2
DISPATCH_WEIGHT = 4.0
DISPATCH_REV_WEIGHT = 2.0

INCLUDE_RE = re.compile(r'#\s*include\s+[<"]([^>"]+)[>"]')


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def chunk_at_line(chunks_by_file: dict[str, list[dict]],
                  file: str, line: int) -> dict | None:
    for chunk in chunks_by_file.get(file, []):
        if chunk["start_line"] <= line <= chunk["end_line"]:
            return chunk
    return None


def symbol_key(symbol: dict) -> str:
    return f"{symbol['file']}:{symbol['name']}:{symbol.get('class', '')}:{symbol.get('line', 0)}"


def add_edge(edge_weights: dict[tuple[str, str, str, str], float],
             src: str, dst: str, kind: str, weight: float,
             label: str = "") -> None:
    if not src or not dst or src == dst:
        return
    key = (src, dst, kind, label)
    edge_weights[key] = edge_weights.get(key, 0.0) + weight


def build_file_indexes(chunks: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[str]]]:
    chunks_by_file: dict[str, list[dict]] = defaultdict(list)
    files_by_suffix: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_file[chunk["file"]].append(chunk)
    for flist in chunks_by_file.values():
        flist.sort(key=lambda c: (c["start_line"], c["end_line"]))
    for file in chunks_by_file:
        p = Path(file)
        files_by_suffix[p.name].append(file)
        files_by_suffix[file].append(file)
    return chunks_by_file, files_by_suffix


def target_files_for_include(include: str,
                             files_by_suffix: dict[str, list[str]]) -> list[str]:
    include = include.replace("\\", "/")
    direct = files_by_suffix.get(include, [])
    if direct:
        return direct
    by_name = files_by_suffix.get(Path(include).name, [])
    if by_name:
        return by_name
    return [f for f in files_by_suffix if f.endswith(include)]


def representative_chunks_for_file(chunks_by_file: dict[str, list[dict]],
                                   file: str) -> list[dict]:
    chunks = chunks_by_file.get(file, [])
    reps = [c for c in chunks if c["type"] in ("file_overview", "class")]
    return reps[:4] or chunks[:1]


def build_symbol_maps(symbols: list[dict],
                      chunks_by_file: dict[str, list[dict]],
                      mentioned_by: dict[str, list[str]]) -> tuple[dict[str, list[str]], set[str]]:
    symbol_to_chunks: dict[str, list[str]] = defaultdict(list)
    low_noise_names: set[str] = set()
    seen_symbols: set[str] = set()

    for sym in symbols:
        if sym.get("kind") not in ("function", "class", "struct"):
            continue
        name = sym.get("name", "")
        if len(name) < MIN_SYMBOL_LEN:
            continue
        if len(mentioned_by.get(name, [])) > NOISY_MENTION_MAX_CHUNKS:
            continue
        low_noise_names.add(name)
        key = symbol_key(sym)
        if key in seen_symbols:
            continue
        seen_symbols.add(key)
        chunk = chunk_at_line(chunks_by_file, sym["file"], int(sym.get("line") or 0))
        if not chunk or chunk["type"] not in ("function", "class"):
            continue
        symbol_to_chunks[name].append(chunk["id"])
        if sym.get("class"):
            symbol_to_chunks[f"{sym['class']}::{name}"].append(chunk["id"])

    for name, ids in list(symbol_to_chunks.items()):
        deduped = list(dict.fromkeys(ids))
        symbol_to_chunks[name] = deduped
        symbol_to_chunks[name.lower()] = deduped
    return dict(symbol_to_chunks), low_noise_names


def add_mention_edges(edge_weights: dict[tuple[str, str, str, str], float],
                      call_graph: dict,
                      symbol_to_chunks: dict[str, list[str]],
                      low_noise_names: set[str]) -> int:
    count = 0
    mentions = call_graph.get("mentions", {})
    for src_cid, names in mentions.items():
        for name in names:
            if name not in low_noise_names:
                continue
            for dst_cid in symbol_to_chunks.get(name, []):
                add_edge(edge_weights, src_cid, dst_cid, "mention", MENTION_FWD_WEIGHT, name)
                add_edge(edge_weights, dst_cid, src_cid, "mention_rev", MENTION_REV_WEIGHT, name)
                count += 2
    return count


def add_same_file_edges(edge_weights: dict[tuple[str, str, str, str], float],
                        chunks_by_file: dict[str, list[dict]]) -> int:
    count = 0
    for chunks in chunks_by_file.values():
        code_chunks = [c for c in chunks if c["type"] in ("function", "class")]
        overview = next((c for c in chunks if c["type"] == "file_overview"), None)
        if overview:
            for chunk in code_chunks:
                add_edge(edge_weights, overview["id"], chunk["id"], "same_file", SAME_FILE_OVERVIEW_WEIGHT)
                add_edge(edge_weights, chunk["id"], overview["id"], "same_file", SAME_FILE_OVERVIEW_WEIGHT)
                count += 2
        ordered = sorted(code_chunks, key=lambda c: (c["start_line"], c["end_line"]))
        for left, right in zip(ordered, ordered[1:]):
            add_edge(edge_weights, left["id"], right["id"], "same_file", SAME_FILE_ADJACENT_WEIGHT)
            add_edge(edge_weights, right["id"], left["id"], "same_file", SAME_FILE_ADJACENT_WEIGHT)
            count += 2
    return count


def add_include_edges(edge_weights: dict[tuple[str, str, str, str], float],
                      chunks: list[dict],
                      chunks_by_file: dict[str, list[dict]],
                      files_by_suffix: dict[str, list[str]]) -> int:
    count = 0
    for chunk in chunks:
        includes = INCLUDE_RE.findall(chunk.get("text", ""))
        if not includes:
            continue
        for inc in includes:
            for file in target_files_for_include(inc, files_by_suffix):
                for dst in representative_chunks_for_file(chunks_by_file, file):
                    add_edge(edge_weights, chunk["id"], dst["id"], "include", INCLUDE_WEIGHT, inc)
                    add_edge(edge_weights, dst["id"], chunk["id"], "include_rev", INCLUDE_REV_WEIGHT, inc)
                    count += 2
    return count


def add_dispatch_edges(edge_weights: dict[tuple[str, str, str, str], float],
                       dispatch_index,
                       chunks_by_file: dict[str, list[dict]],
                       symbol_to_chunks: dict[str, list[str]]) -> int:
    entries = dispatch_index.get("entries", dispatch_index) if dispatch_index else []
    count = 0
    for entry in entries:
        src_cid = entry.get("chunk_id")
        if not src_cid:
            file = entry.get("handler_file") or entry.get("file")
            line = int(entry.get("line") or 0)
            chunk = chunk_at_line(chunks_by_file, file, line) if file and line else None
            src_cid = chunk["id"] if chunk else ""
        targets: list[str] = []
        target_symbol = entry.get("target_symbol") or ""
        if target_symbol:
            targets.extend(symbol_to_chunks.get(target_symbol, []))
            targets.extend(symbol_to_chunks.get(target_symbol.split("::")[-1], []))
        handler_symbol = entry.get("handler_symbol") or ""
        if handler_symbol:
            targets.extend(symbol_to_chunks.get(handler_symbol, []))
            targets.extend(symbol_to_chunks.get(handler_symbol.split("::")[-1], []))
        for dst_cid in dict.fromkeys(targets):
            add_edge(edge_weights, src_cid, dst_cid, "dispatch", DISPATCH_WEIGHT, entry.get("command", ""))
            add_edge(edge_weights, dst_cid, src_cid, "dispatch_rev", DISPATCH_REV_WEIGHT, entry.get("command", ""))
            count += 2
    return count


def serialize_edges(edge_weights: dict[tuple[str, str, str, str], float]) -> dict[str, list[dict]]:
    edges: dict[str, list[dict]] = defaultdict(list)
    for (src, dst, kind, label), weight in edge_weights.items():
        edges[src].append({
            "to": dst,
            "weight": round(weight, 4),
            "kind": kind,
            "label": label,
        })
    for src in edges:
        edges[src].sort(key=lambda e: (e["to"], e["kind"], e["label"]))
    return dict(edges)


def global_pagerank(nodes: list[str], edges: dict[str, list[dict]]) -> dict[str, float]:
    if not nodes:
        return {}
    n = len(nodes)
    base = 1.0 / n
    rank = {node: base for node in nodes}
    out_weight = {
        node: sum(edge["weight"] for edge in edges.get(node, []))
        for node in nodes
    }
    for _ in range(PAGERANK_ITERS):
        new_rank = {node: (1.0 - PAGERANK_DAMPING) * base for node in nodes}
        dangling = sum(rank[node] for node in nodes if out_weight.get(node, 0.0) <= 0.0)
        dangling_share = PAGERANK_DAMPING * dangling * base
        for node in nodes:
            new_rank[node] += dangling_share
            denom = out_weight.get(node, 0.0)
            if denom <= 0.0:
                continue
            for edge in edges.get(node, []):
                new_rank[edge["to"]] += PAGERANK_DAMPING * rank[node] * edge["weight"] / denom
        rank = new_rank
    return rank


def main() -> None:
    chunks = load_chunks()
    symbols = load_json(SYMBOLS_PATH, [])
    call_graph = load_json(CALL_GRAPH_PATH, {})
    dispatch_index = load_json(DISPATCH_INDEX_PATH, {"entries": []})
    chunks_by_file, files_by_suffix = build_file_indexes(chunks)
    mentioned_by = call_graph.get("mentioned_by", {})
    symbol_to_chunks, low_noise_names = build_symbol_maps(symbols, chunks_by_file, mentioned_by)

    edge_weights: dict[tuple[str, str, str, str], float] = {}
    counts = {
        "mention": add_mention_edges(edge_weights, call_graph, symbol_to_chunks, low_noise_names),
        "same_file": add_same_file_edges(edge_weights, chunks_by_file),
        "include": add_include_edges(edge_weights, chunks, chunks_by_file, files_by_suffix),
        "dispatch": add_dispatch_edges(edge_weights, dispatch_index, chunks_by_file, symbol_to_chunks),
    }
    edges = serialize_edges(edge_weights)
    nodes = {
        c["id"]: {
            "file": c["file"],
            "type": c["type"],
            "symbol": c.get("symbol", ""),
            "class": c.get("class", ""),
            "start_line": c["start_line"],
            "end_line": c["end_line"],
        }
        for c in chunks
    }
    filtered_mentioned_symbols = sum(
        1 for name in mentioned_by
        if name not in low_noise_names
    )
    graph = {
        "version": 1,
        "params": {
            "noisy_mention_max_chunks": NOISY_MENTION_MAX_CHUNKS,
            "pagerank_damping": PAGERANK_DAMPING,
            "pagerank_iters": PAGERANK_ITERS,
        },
        "nodes": nodes,
        "edges": edges,
        "symbol_to_chunks": symbol_to_chunks,
        "stats": {
            "nodes": len(nodes),
            "edge_count": sum(len(v) for v in edges.values()),
            "low_noise_symbols": len(low_noise_names),
            "filtered_mentioned_symbols": filtered_mentioned_symbols,
            "edge_sources": counts,
        },
    }
    GRAPH_OUTPUT_PATH.write_text(
        json.dumps(graph, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    ranks = global_pagerank(list(nodes), edges)
    indegree: dict[str, float] = defaultdict(float)
    indegree_by_kind: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for src_edges in edges.values():
        for edge in src_edges:
            indegree[edge["to"]] += edge["weight"]
            indegree_by_kind[edge["to"]][edge["kind"]] += edge["weight"]
    top = sorted(ranks.items(), key=lambda item: -item[1])[:100]
    scores = {
        "version": 1,
        "stats": graph["stats"],
        "top_global_pagerank": [
            {
                "chunk_id": cid,
                "score": round(score, 8),
                "file": nodes[cid]["file"],
                "symbol": nodes[cid]["symbol"],
                "type": nodes[cid]["type"],
                "weighted_indegree": round(indegree.get(cid, 0.0), 4),
                "indegree_by_kind": {
                    kind: round(weight, 4)
                    for kind, weight in sorted(indegree_by_kind.get(cid, {}).items())
                },
            }
            for cid, score in top
        ],
    }
    SCORES_OUTPUT_PATH.write_text(
        json.dumps(scores, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("repomap graph 生成完毕")
    print(f"  nodes             : {graph['stats']['nodes']}")
    print(f"  edges             : {graph['stats']['edge_count']}")
    print(f"  low-noise symbols : {graph['stats']['low_noise_symbols']}")
    print(f"  filtered mentions : {graph['stats']['filtered_mentioned_symbols']}")
    print(f"  edge sources      : {counts}")
    print(f"  graph             : {GRAPH_OUTPUT_PATH}")
    print(f"  scores            : {SCORES_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
