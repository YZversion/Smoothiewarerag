"""
Phase 3.4 — 轻量符号引用图（mention graph）

扫描每个 function/class chunk 的文本，记录哪些已知符号名出现在其中。
自引用（chunk 自身的 symbol/class 名）被过滤。

输出：data/call_graph.json
  {
    "mentioned_by": {sym_name: [chunk_id, ...]},
    "mentions":     {chunk_id: [sym_name, ...]}
  }

用法：
    python src/03_build_callgraph.py
依赖：data/chunks.jsonl + data/symbol_index.json（先跑 03_build_chunks.py）
"""

import json
import re
from collections import defaultdict
from pathlib import Path

LAB_ROOT     = Path(__file__).parent.parent
CHUNKS_PATH  = LAB_ROOT / "data" / "chunks.jsonl"
SYMBOLS_PATH = LAB_ROOT / "data" / "symbol_index.json"
OUTPUT_PATH  = LAB_ROOT / "data" / "call_graph.json"

MIN_SYM_LEN = 4  # 过短的名字噪声太多


def _extract_tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_]\w*", text))


def main() -> None:
    symbols = json.loads(SYMBOLS_PATH.read_text(encoding="utf-8"))

    # 已知符号名集合（function / class / struct / prototype）
    known: set[str] = set()
    for s in symbols:
        if s["kind"] not in ("function", "prototype", "class", "struct"):
            continue
        name = s["name"]
        if len(name) >= MIN_SYM_LEN:
            known.add(name)

    mentioned_by: dict[str, list[str]] = defaultdict(list)
    mentions:     dict[str, list[str]] = defaultdict(list)

    for raw in CHUNKS_PATH.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        chunk = json.loads(raw)
        if chunk["type"] not in ("function", "class"):
            continue

        cid     = chunk["id"]
        own_sym = chunk.get("symbol") or ""
        own_cls = chunk.get("class") or ""

        found: list[str] = []
        seen:  set[str]  = set()
        for tok in _extract_tokens(chunk["text"]):
            if tok not in known:
                continue
            if tok == own_sym or tok == own_cls:
                continue  # 自引用
            if tok not in seen:
                seen.add(tok)
                found.append(tok)

        if found:
            mentions[cid] = found
            for sym in found:
                mentioned_by[sym].append(cid)

    result = {
        "mentioned_by": dict(mentioned_by),
        "mentions":     dict(mentions),
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    edge_count = sum(len(v) for v in mentions.values())
    print(f"call_graph.json 生成完毕")
    print(f"  chunks with mentions : {len(mentions)}")
    print(f"  unique symbols indexed: {len(mentioned_by)}")
    print(f"  total edges          : {edge_count}")
    print(f"  output               : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
