"""
Phase 5 — 知识库一体化 CLI

用法：
    python src/app.py "G-code 从哪里进入系统？"
    python src/app.py "Planner append_block" --search-only
    python src/app.py --demo
    python src/app.py "halt" --json

子命令等价：
    --search-only  → 仅 03_search（不调 LLM）
    默认           → 04_answer（检索 + LLM）
    --demo         → eval Q1–Q5 全流程
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent


def load_module(filename: str):
    path = Path(__file__).parent / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def print_search_hits(query: str, hits: list[dict]) -> None:
    print(f"query: {query!r}  ({len(hits)} hits)\n")
    for i, h in enumerate(hits, 1):
        sym = f" {h['symbol']}" if h.get("symbol") else ""
        print(f"{i:>2}. [{h['score']:>6.1f}] {h['file']}:{h['line_start']} "
              f"({h['type']}){sym}  [{h.get('source', '')}]")
        for ln in h["snippet"].splitlines()[:3]:
            print(f"      {ln[:100]}")
        print()


def print_answer(result: dict, show_context: bool = False) -> None:
    print("=" * 60)
    print(f"Q: {result['question']}")
    print(f"model: {result['provider']} / {result['model']}  "
          f"chunks: {len(result['hits'])}")
    if show_context:
        print("\n--- 引用 ---")
        for h in result["hits"]:
            print(f"  `{h['file']}:{h['line_start']}`  "
                  f"{h.get('symbol', '')}  score={h['score']}")
    print("\n--- 解释 ---\n")
    print(result["answer"])
    print("\n--- 检索引用 ---")
    for h in result["hits"]:
        sym = f" ({h['symbol']})" if h.get("symbol") else ""
        print(f"  - `{h['file']}:{h['line_start']}`{sym}")
    print()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Smoothieware 代码知识库 — 检索 + 问答",
    )
    p.add_argument("question", nargs="?", help="问题或关键词")
    p.add_argument("--top-k", type=int, default=5, help="检索 chunk 数（默认 5）")
    p.add_argument("--search-only", action="store_true", help="仅检索，不调 LLM")
    p.add_argument("--demo", action="store_true", help="运行 eval Q1–Q5")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.add_argument("--show-context", action="store_true", help="回答时打印引用摘要")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    search = load_module("03_search.py")
    answer_mod = load_module("04_answer.py")
    search.load_index()

    if args.demo:
        data = json.loads(answer_mod.EVAL_PATH.read_text(encoding="utf-8"))
        for q in data["questions"]:
            if args.search_only:
                hits = search.search(q["question"], top_k=args.top_k)
                print("=" * 60)
                print_search_hits(q["question"], hits)
            else:
                result = answer_mod.answer(q["question"], top_k=args.top_k,
                                            search_mod=search)
                if args.json:
                    out = {k: v for k, v in result.items() if k != "hits"}
                    out["citations"] = [
                        {"file": h["file"], "line_start": h["line_start"],
                         "symbol": h.get("symbol", ""), "score": h["score"]}
                        for h in result["hits"]
                    ]
                    print(json.dumps(out, ensure_ascii=False, indent=2))
                else:
                    print_answer(result, show_context=args.show_context)
        return

    if not args.question:
        print("用法: python src/app.py \"你的问题\"", file=sys.stderr)
        print("      python src/app.py --demo", file=sys.stderr)
        sys.exit(1)

    if args.search_only:
        hits = search.search(args.question, top_k=args.top_k)
        if args.json:
            print(json.dumps({"question": args.question, "hits": hits},
                             ensure_ascii=False, indent=2))
        else:
            print_search_hits(args.question, hits)
        return

    result = answer_mod.answer(args.question, top_k=args.top_k, search_mod=search)
    if args.json:
        out = {k: v for k, v in result.items() if k != "hits"}
        out["citations"] = [
            {"file": h["file"], "line_start": h["line_start"],
             "symbol": h.get("symbol", ""), "score": h["score"]}
            for h in result["hits"]
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print_answer(result, show_context=args.show_context)


if __name__ == "__main__":
    main()
