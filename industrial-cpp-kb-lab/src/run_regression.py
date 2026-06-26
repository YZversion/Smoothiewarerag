"""
Phase 5.2 — 一键回归：检索 Recall + bundle +（可选）LLM 引用校验

用法：
    python src/run_regression.py
    python src/run_regression.py --skip-llm    # 不调 LLM，只测检索
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
ENV_PATH = LAB_ROOT / ".env"

# 需要 bundle 含 overview/header 的函数类问题
BUNDLE_IDS = {"Q1", "Q2", "Q3"}


def load_module(filename: str):
    path = Path(__file__).parent / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"无法加载 {path}")
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


def check_bundle(search, question: str, top_k: int = 5) -> bool:
    hits = search.search(question, top_k=top_k, bundle=True)
    roles = {h.get("bundle_role") for h in hits}
    primaries = [h for h in hits if h.get("bundle_role") == "primary"]
    has_impl = any(
        h["type"] == "function" and h["file"].endswith((".cpp", ".c"))
        for h in primaries
    )
    if not has_impl:
        return True
    return "overview" in roles or "header" in roles


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="知识库回归测试")
    p.add_argument("--skip-llm", action="store_true", help="跳过 LLM 引用校验")
    p.add_argument("--top-k", type=int, default=5)
    return p.parse_args()


def main(skip_llm: bool | None = None) -> int:
    if skip_llm is None:
        args = parse_args()
        skip_llm = args.skip_llm
        top_k = args.top_k
    else:
        top_k = 5
    load_dotenv(ENV_PATH)
    search = load_module("03_search.py")
    answer_mod = load_module("04_answer.py")
    search.load_index()

    failed = False
    print("=== [1/3] Recall@K (03_search) ===\n")
    summary = search.eval_summary(EVAL_PATH)
    for d in summary["details"]:
        mark = "PASS" if d["ok5"] else "FAIL"
        print(f"  {d['id']} {mark}@5  hit={d['hit5']}")
    print(f"\nRecall@5: {summary['pass5']}/{summary['total']}")
    if not summary["recall5_ok"]:
        failed = True
        print("FAIL: Recall@5 需要 >= 4/5")
    else:
        print("PASS")

    print("\n=== [2/3] Bundle coverage (03_search --bundle) ===\n")
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    bundle_pass = 0
    for q in data["questions"]:
        if q["id"] not in BUNDLE_IDS:
            continue
        ok = check_bundle(search, q["question"], top_k)
        mark = "PASS" if ok else "FAIL"
        print(f"  {q['id']} {mark}")
        if ok:
            bundle_pass += 1
        else:
            failed = True
    need = len(BUNDLE_IDS)
    print(f"\nBundle: {bundle_pass}/{need}  ", end="")
    if bundle_pass >= 3:
        print("PASS")
    else:
        print("FAIL (need >= 3)")
        failed = True

    print("\n=== [3/3] Citation check (04_answer, optional) ===\n")
    if skip_llm or not os.environ.get("LLM_API_KEY", "").strip():
        print("SKIP (无 LLM_API_KEY 或 --skip-llm)")
    else:
        cite_ok = 0
        for q in data["questions"]:
            result = answer_mod.answer(q["question"], top_k=top_k,
                                       search_mod=search)
            ok = result.get("citations", {}).get("ok", False)
            mark = "PASS" if ok else "WARN"
            inv = result.get("citations", {}).get("invalid", [])
            print(f"  {q['id']} {mark}" + (f"  invalid={inv[:2]}" if inv else ""))
            if ok:
                cite_ok += 1
        print(f"\nCitation: {cite_ok}/{summary['total']}  ", end="")
        if cite_ok >= 4:
            print("PASS")
        else:
            print("WARN (非阻断，人工复核)")
            # citation warnings don't fail regression hard

    print("\n" + "=" * 50)
    if failed:
        print("REGRESSION FAILED")
        return 1
    print("REGRESSION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
