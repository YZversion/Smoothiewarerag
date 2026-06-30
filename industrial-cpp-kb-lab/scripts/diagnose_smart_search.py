"""
Smart search 定向诊断：口语化 query + 两条 plain search 不退化检查。

用法：
    python scripts/diagnose_smart_search.py
    python scripts/diagnose_smart_search.py --no-llm   # 跳过 planner LLM 调用
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
SRC = LAB_ROOT / "src"

SMART_QUERY = "gcode运行流程"
PLAIN_CASES = [
    ("G-code 从哪里进入系统？", ["GcodeDispatch", "SerialConsole", "Player"]),
    ("halt emergency 在哪里处理？", ["halt", "ON_HALT", "KillButton", "on_halt"]),
]
GCODE_EVIDENCE = ("GcodeDispatch", "SerialConsole", "gcode", "console_line", "Player")


def hit_evidence(hits: list[dict], needles: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for needle in needles:
        n = needle.lower()
        for h in hits:
            blob = " ".join(
                [h.get("file", ""), h.get("symbol", ""), h.get("class", "")]
            ).lower()
            if n in blob:
                found.append(needle)
                break
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose smart search retrieval")
    parser.add_argument("--no-llm", action="store_true", help="Use planner fallback only")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    from query_planner import load_dotenv, parse_query_plan
    from search.index import SearchIndex
    from search.smart_search import smart_search

    sample = (
        '{"intent":"call_flow","normalized_question":"test",'
        '"entities":[],"symbols":["GcodeDispatch"],'
        '"search_queries":["GcodeDispatch","SerialConsole"],'
        '"must_have":["gcode"],"target_kinds":["entry"],"notes":"ok"}'
    )
    parsed = parse_query_plan(sample, "test")
    if parsed.intent != "call_flow" or len(parsed.search_queries) < 2:
        print("FAIL parse_query_plan")
        return 1
    print("OK  parse_query_plan")

    idx = SearchIndex()
    idx.load_index()

    failures = 0

    # plain search regression
    for question, needles in PLAIN_CASES:
        hits = idx.search(question, top_k=args.top_k, bundle=False)
        if not hits:
            print(f"FAIL plain empty: {question!r}")
            failures += 1
            continue
        found = hit_evidence(hits, tuple(needles))
        print(f"OK  plain {question!r} -> {len(hits)} hits, evidence={found[:3]}")

    # smart search
    if args.no_llm:
        from query_planner import QueryPlan

        mock_plan = QueryPlan(
            intent="call_flow",
            normalized_question=SMART_QUERY,
            search_queries=[
                "G-code 从哪里进入系统",
                "GcodeDispatch on_console_line_received",
                "SerialConsole on_main_loop call_event",
            ],
            symbols=["GcodeDispatch", "SerialConsole"],
            must_have=["gcode"],
            notes="diagnose mock plan (no LLM)",
        )
        plan, hits = smart_search(
            idx, SMART_QUERY, top_k=args.top_k, plan=mock_plan, skip_planner=True
        )
    else:
        load_dotenv()
        plan, hits = smart_search(idx, SMART_QUERY, top_k=args.top_k)

    print(f"smart plan intent={plan.intent} fallback={plan.planner_fallback}")
    print(f"  queries={plan.search_queries[:5]}")
    if not hits:
        print(f"FAIL smart empty: {SMART_QUERY!r}")
        failures += 1
    else:
        found = hit_evidence(hits, GCODE_EVIDENCE)
        print(f"OK  smart {SMART_QUERY!r} -> {len(hits)} hits, evidence={found}")
        if not found:
            print("WARN smart hits lack G-code entry/dispatch evidence (check manually)")

    if failures:
        print(f"\n{failures} check(s) failed")
        return 1
    print("\nAll diagnose_smart_search checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
