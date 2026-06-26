"""
Phase 6.1 — 检索上下文 vs LLM 答案分层评估（一次性脚本）

用法：
    python src/eval_answer_layer.py              # 仅检索+trim 符号覆盖
    python src/eval_answer_layer.py --llm        # 含 LLM 调用（需 LLM_API_KEY）
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
ENV_PATH = LAB_ROOT / ".env"


def load_module(filename: str):
    path = Path(__file__).parent / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
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


def sym_hit(hits: list[dict], exp_sym: str) -> bool:
    if "::" in exp_sym:
        cls, name = exp_sym.split("::", 1)
        cls_l, name_l = cls.lower(), name.lower()
        for h in hits:
            if h.get("symbol", "").lower() != name_l:
                continue
            hcls = (h.get("class") or "").lower()
            if hcls == cls_l or cls_l in h["file"].lower():
                return True
    else:
        name_l = exp_sym.lower()
        for h in hits:
            if h.get("symbol", "").lower() == name_l:
                return True
    return False


def file_in_answer(answer: str, path: str) -> bool:
    stem = Path(path).name
    return stem.lower() in answer.lower() or path.replace("\\", "/") in answer


def sym_in_answer(answer: str, exp_sym: str) -> bool:
    if "::" in exp_sym:
        cls, name = exp_sym.split("::", 1)
        return name in answer and (cls in answer or cls.lower() in answer.lower())
    return exp_sym in answer


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true")
    p.add_argument("--top-k", type=int, default=8)
    args = p.parse_args()
    load_dotenv(ENV_PATH)

    search = load_module("03_search.py")
    ans = load_module("04_answer.py")
    search.load_index()
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))

    rows = []
    print(f"=== Context layer (top_k={args.top_k}, bundle, trim<=8) ===\n")
    for q in data["questions"]:
        hits = search.search(q["question"], top_k=args.top_k, bundle=True)
        primaries = [h for h in hits if h.get("bundle_role", "primary") == "primary"]
        trimmed = ans.trim_context_hits(hits, 8)
        exp_files = q["expected_files"]
        exp_syms = q.get("expected_symbols", [])
        hit_files = [f for f in exp_files if f in {h["file"] for h in primaries}]
        sym_bundle = sum(1 for s in exp_syms if sym_hit(hits, s))
        sym_trim = sum(1 for s in exp_syms if sym_hit(trimmed, s))
        row = {
            "id": q["id"], "split": q.get("split", "tune"),
            "file_cov": len(hit_files) / len(exp_files) if exp_files else 1,
            "sym_bundle": sym_bundle, "sym_trim": sym_trim,
            "sym_n": len(exp_syms),
            "trim_loss": sym_bundle - sym_trim,
        }
        rows.append(row)
        print(f"{q['id']:4} file={len(hit_files)}/{len(exp_files)}  "
              f"sym_trim={sym_trim}/{len(exp_syms)}  "
              f"(bundle {sym_bundle})  trim_loss={row['trim_loss']}")

    mean_file = sum(r["file_cov"] for r in rows) / len(rows)
    mean_sym = sum(r["sym_trim"] / r["sym_n"] if r["sym_n"] else 1 for r in rows) / len(rows)
    print(f"\nmean file_cov@primary: {mean_file:.0%}")
    print(f"mean sym_cov@trim:       {mean_sym:.0%}")

    if not args.llm:
        print("\n(skip LLM; use --llm to run answer layer)")
        return 0
    if not os.environ.get("LLM_API_KEY", "").strip():
        print("\nLLM_API_KEY not set", file=sys.stderr)
        return 1

    print(f"\n=== LLM layer (top_k={args.top_k}) ===\n")
    cite_ok = file_ok = sym_ok = 0
    for q in data["questions"]:
        result = ans.answer(q["question"], top_k=args.top_k, search_mod=search)
        text = result["answer"]
        cites = result["citations"]
        exp_files = q["expected_files"]
        exp_syms = q.get("expected_symbols", [])
        f_hit = sum(1 for f in exp_files if file_in_answer(text, f))
        s_hit = sum(1 for s in exp_syms if sym_in_answer(text, s))
        c_ok = cites.get("ok", False)
        cite_ok += int(c_ok)
        file_ok += int(f_hit == len(exp_files))
        sym_ok += int(s_hit >= max(1, len(exp_syms) // 2))
        print(f"{q['id']:4} cite={'OK' if c_ok else 'WARN'}  "
              f"files_in_ans={f_hit}/{len(exp_files)}  "
              f"syms_in_ans={s_hit}/{len(exp_syms)}")
    n = len(data["questions"])
    print(f"\nCitation OK:     {cite_ok}/{n} ({cite_ok/n:.0%})")
    print(f"All files cited: {file_ok}/{n} ({file_ok/n:.0%})")
    print(f"Half+ symbols:   {sym_ok}/{n} ({sym_ok/n:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
