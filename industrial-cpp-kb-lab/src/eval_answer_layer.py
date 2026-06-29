"""
Phase 6.1 / 10 — 检索上下文 vs LLM 答案分层评估

用法：
    python src/eval_answer_layer.py              # 仅检索+trim 符号覆盖
    python src/eval_answer_layer.py --llm        # 含 LLM 调用（需 LLM_API_KEY）
    python src/eval_answer_layer.py --llm --json # JSON 报告（stdout）
    python src/eval_answer_layer.py --llm --json -o notes/phase10_after.json
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


def load_module(filename: str):
    path = Path(__file__).parent / filename
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


def sym_in_answer(answer: str, exp_sym: str) -> bool:
    if "::" in exp_sym:
        cls, name = exp_sym.split("::", 1)
        return name in answer and (cls in answer or cls.lower() in answer.lower())
    return exp_sym in answer


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true")
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--split", choices=("tune", "holdout", "all"), default="all")
    p.add_argument("--json", action="store_true", help="JSON report to stdout")
    p.add_argument("-o", "--output", type=Path, help="also write JSON report to file")
    p.add_argument("--resume", action="store_true",
                   help="skip LLM rows already present in --output JSON")
    p.add_argument("--ids", default="",
                   help="comma-separated question ids (e.g. Q3,H26)")
    args = p.parse_args()
    load_dotenv(ENV_PATH)

    search = load_module("03_search.py")
    ans = load_module("04_answer.py")
    search.load_index()
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    if args.split != "all":
        data = {"questions": [q for q in data["questions"]
                              if q.get("split", "tune") == args.split]}
    questions = data["questions"]
    if args.ids.strip():
        id_set = {x.strip() for x in args.ids.split(",") if x.strip()}
        questions = [q for q in questions if q["id"] in id_set]
    context_rows: list[dict] = []
    print(f"=== Context layer (top_k={args.top_k}, bundle, trim<=8, n={len(questions)}) ===\n")
    for q in questions:
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
        context_rows.append(row)
        if not args.json:
            print(f"{q['id']:4} file={len(hit_files)}/{len(exp_files)}  "
                  f"sym_trim={sym_trim}/{len(exp_syms)}  "
                  f"(bundle {sym_bundle})  trim_loss={row['trim_loss']}")

    mean_file = sum(r["file_cov"] for r in context_rows) / len(context_rows)
    mean_sym = sum(r["sym_trim"] / r["sym_n"] if r["sym_n"] else 1 for r in context_rows) / len(context_rows)
    if not args.json:
        print(f"\nmean file_cov@primary: {mean_file:.0%}")
        print(f"mean sym_cov@trim:       {mean_sym:.0%}")

    report: dict = {
        "top_k": args.top_k,
        "context": {
            "mean_file_cov_primary": mean_file,
            "mean_sym_cov_trim": mean_sym,
            "rows": context_rows,
        },
    }

    if not args.llm:
        if not args.json:
            print("\n(skip LLM; use --llm to run answer layer)")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        return 0
    if not os.environ.get("LLM_API_KEY", "").strip():
        print("\nLLM_API_KEY not set", file=sys.stderr)
        return 1

    llm_rows: list[dict] = []
    done_ids: set[str] = set()
    if args.resume and args.output and args.output.is_file():
        try:
            partial = json.loads(args.output.read_text(encoding="utf-8"))
            llm_rows = list(partial.get("llm", {}).get("rows", []))
            done_ids = {r["id"] for r in llm_rows}
            if done_ids and not args.json:
                print(f"(resume: {len(done_ids)} LLM rows from {args.output})\n")
        except (json.JSONDecodeError, OSError):
            pass

    cite_ok = exp_all_ok = ctx_ok = 0
    tune_exp_ok = tune_n = 0
    ctx_ratios: list[float] = []

    def write_checkpoint() -> None:
        if not args.output:
            return
        n_done = len(llm_rows)
        mean_ctx = sum(ctx_ratios) / len(ctx_ratios) if ctx_ratios else 0.0
        report["llm"] = {
            "citation_ok": cite_ok,
            "citation_ok_rate": cite_ok / n_done if n_done else 0,
            "all_expected_files": exp_all_ok,
            "all_expected_files_rate": exp_all_ok / n_done if n_done else 0,
            "context_primary_full": ctx_ok,
            "context_primary_full_rate": ctx_ok / n_done if n_done else 0,
            "mean_context_primary_ratio": mean_ctx,
            "tune_all_expected_files": tune_exp_ok,
            "tune_all_expected_files_rate": tune_exp_ok / tune_n if tune_n else 0,
            "rows": llm_rows,
            "partial": n_done < len(questions),
        }
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")

    if not args.json:
        print(f"\n=== LLM layer (top_k={args.top_k}) ===\n")
    for q in questions:
        if q["id"] in done_ids:
            continue
        result = ans.answer(q["question"], top_k=args.top_k, search_mod=search)
        text = result["answer"]
        cites = result["citations"]
        cov = result.get("coverage", {})
        exp_files = q["expected_files"]
        exp_syms = q.get("expected_symbols", [])
        f_hit = sum(1 for f in exp_files
                    if ans.file_mentioned_in_answer(text, f))
        s_hit = sum(1 for s in exp_syms if sym_in_answer(text, s))
        c_ok = cites.get("ok", False)
        ctx_n = len(cov.get("primary_files", []))
        ctx_m = len(cov.get("mentioned", []))
        cite_ok += int(c_ok)
        exp_all_ok += int(f_hit == len(exp_files))
        ctx_ok += int(cov.get("ok", False))
        if ctx_n:
            ctx_ratios.append(ctx_m / ctx_n)
        split = q.get("split", "tune")
        if split == "tune":
            tune_n += 1
            tune_exp_ok += int(f_hit == len(exp_files))
        row = {
            "id": q["id"],
            "split": split,
            "cite_ok": c_ok,
            "ctx_primary": f"{ctx_m}/{ctx_n}",
            "ctx_ratio": cov.get("ratio", 0),
            "ctx_primary_ok": cov.get("ok", False),
            "expected": f"{f_hit}/{len(exp_files)}",
            "expected_all": f_hit == len(exp_files),
            "syms_in_ans": f"{s_hit}/{len(exp_syms)}",
            "missing_primary": cov.get("missing", []),
        }
        llm_rows.append(row)
        if not args.json:
            print(f"{q['id']:4} cite={'OK' if c_ok else 'WARN'}  "
                  f"ctx_primary={ctx_m}/{ctx_n}  "
                  f"expected={f_hit}/{len(exp_files)}  "
                  f"syms={s_hit}/{len(exp_syms)}")
        write_checkpoint()

    # Recompute aggregates from full llm_rows (resume-safe)
    cite_ok = exp_all_ok = ctx_ok = 0
    tune_exp_ok = tune_n = 0
    ctx_ratios = []
    for row in llm_rows:
        cite_ok += int(row["cite_ok"])
        exp_all_ok += int(row["expected_all"])
        ctx_ok += int(row.get("ctx_primary_ok", False))
        parts = row.get("ctx_primary", "0/0").split("/")
        if len(parts) == 2 and int(parts[1]) > 0:
            ctx_ratios.append(int(parts[0]) / int(parts[1]))
        if row.get("split") == "tune":
            tune_n += 1
            tune_exp_ok += int(row["expected_all"])

    n = len(questions)
    mean_ctx = sum(ctx_ratios) / len(ctx_ratios) if ctx_ratios else 0.0
    report["llm"] = {
        "citation_ok": cite_ok,
        "citation_ok_rate": cite_ok / n,
        "all_expected_files": exp_all_ok,
        "all_expected_files_rate": exp_all_ok / n,
        "context_primary_full": ctx_ok,
        "context_primary_full_rate": ctx_ok / n,
        "mean_context_primary_ratio": mean_ctx,
        "tune_all_expected_files": tune_exp_ok,
        "tune_all_expected_files_rate": tune_exp_ok / tune_n if tune_n else 0,
        "rows": llm_rows,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"\nCitation OK:           {cite_ok}/{n} ({cite_ok/n:.0%})")
        print(f"All expected files:    {exp_all_ok}/{n} ({exp_all_ok/n:.0%})")
        print(f"All ctx primary:       {ctx_ok}/{n} ({ctx_ok/n:.0%})")
        print(f"Mean ctx_primary cov:  {mean_ctx:.0%}")
        print(f"Tune all expected:     {tune_exp_ok}/{tune_n}")

    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
