"""
四层检索缺口诊断：raw@K → bundle primary@8 → trim primary@8

用法：
    python scripts/diagnose_retrieval.py --ids Q3,Q4,Q5
    python scripts/diagnose_retrieval.py --ids Q3,Q4,Q5 --json -o notes/q345_diag.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC = LAB_ROOT / "src"


def load_module(filename: str):
    path = SRC / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def unique_primary_files(hits: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h.get("bundle_role", "primary") != "primary":
            continue
        f = h["file"]
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
    return out


def trim_primary_files(hits: list[dict], trim_fn, max_chunks: int = 8) -> list[str]:
    trimmed = trim_fn(hits, max_chunks)
    return unique_primary_files(trimmed)


def coverage(expected: list[str], found: set[str]) -> tuple[list[str], list[str], float]:
    hit = [f for f in expected if f in found]
    miss = [f for f in expected if f not in found]
    n = len(expected)
    return hit, miss, len(hit) / n if n else 1.0


def diagnose_question(
    q: dict,
    search,
    trim_fn,
    *,
    ks: list[int],
    bundle_k: int = 8,
    trim_k: int = 8,
) -> dict:
    expected = q["expected_files"]
    exp_syms = q.get("expected_symbols", [])
    layers: dict = {}

    for k in ks:
        raw = search.search(q["question"], top_k=k, bundle=False)
        files = {r["file"] for r in raw}
        hit, miss, cov = coverage(expected, files)
        layers[f"raw@{k}"] = {
            "hit": hit, "miss": miss, "cov": cov,
            "hit_n": len(hit), "exp_n": len(expected),
        }

    bundle_hits = search.search(q["question"], top_k=bundle_k, bundle=True)
    primaries = unique_primary_files(bundle_hits)
    hit, miss, cov = coverage(expected, set(primaries))
    sym_bundle = sum(1 for s in exp_syms if sym_hit(bundle_hits, s))
    layers[f"bundle_primary@{bundle_k}"] = {
        "hit": hit, "miss": miss, "cov": cov,
        "hit_n": len(hit), "exp_n": len(expected),
        "primary_files": primaries,
        "sym_hit": sym_bundle, "sym_n": len(exp_syms),
    }

    trim_primaries = trim_primary_files(bundle_hits, trim_fn, trim_k)
    hit, miss, cov = coverage(expected, set(trim_primaries))
    trimmed = trim_fn(bundle_hits, trim_k)
    sym_trim = sum(1 for s in exp_syms if sym_hit(trimmed, s))
    layers[f"trim_primary@{trim_k}"] = {
        "hit": hit, "miss": miss, "cov": cov,
        "hit_n": len(hit), "exp_n": len(expected),
        "primary_files": trim_primaries,
        "sym_hit": sym_trim, "sym_n": len(exp_syms),
        "trim_loss_sym": sym_bundle - sym_trim,
        "noise_primaries": [f for f in trim_primaries if f not in expected],
    }

    return {
        "id": q["id"],
        "split": q.get("split", "tune"),
        "question": q["question"],
        "expected_files": expected,
        "layers": layers,
    }


def format_report(rows: list[dict], ks: list[int]) -> str:
    lines = [
        "# Q3–Q5 检索四层诊断",
        "",
        "| ID | " + " | ".join(f"cov@{k}" for k in ks) + " | bundle@8 | trim@8 | sym_trim | 根因 |",
        "|----|" + "|".join("------" for _ in ks) + "|----------|--------|----------|------|",
    ]
    for r in rows:
        ly = r["layers"]
        cov_cols = [f"{ly[f'raw@{k}']['hit_n']}/{ly[f'raw@{k}']['exp_n']}" for k in ks]
        b = ly["bundle_primary@8"]
        t = ly["trim_primary@8"]
        root = _root_cause(ly, ks)
        lines.append(
            f"| {r['id']} | " + " | ".join(cov_cols)
            + f" | {b['hit_n']}/{b['exp_n']} | {t['hit_n']}/{t['exp_n']}"
            + f" | {t['sym_hit']}/{t['sym_n']} (loss={t['trim_loss_sym']}) | {root} |"
        )

    lines.append("")
    for r in rows:
        lines.append(f"## {r['id']} — {r['question']}")
        lines.append("")
        ly = r["layers"]
        for k in ks:
            m = ly[f"raw@{k}"]["miss"]
            if m:
                lines.append(f"- **miss@raw{k}**: {', '.join(m)}")
        for layer_key in ("bundle_primary@8", "trim_primary@8"):
            m = ly[layer_key]["miss"]
            if m:
                lines.append(f"- **miss@{layer_key}**: {', '.join(m)}")
        noise = ly["trim_primary@8"].get("noise_primaries", [])
        if noise:
            lines.append(f"- **trim noise** (primary 但非 expected): {', '.join(noise)}")
        lines.append(f"- **bundle primary 全表**: {', '.join(ly['bundle_primary@8']['primary_files'])}")
        lines.append("")
    return "\n".join(lines)


def _root_cause(layers: dict, ks: list[int]) -> str:
    k8 = max(ks) if ks else 8
    raw_miss = layers.get(f"raw@{k8}", {}).get("miss", [])
    bundle_miss = layers.get("bundle_primary@8", {}).get("miss", [])
    trim_miss = layers.get("trim_primary@8", {}).get("miss", [])
    trim_loss = layers.get("trim_primary@8", {}).get("trim_loss_sym", 0)
    if raw_miss:
        return "BM25/排序"
    if bundle_miss:
        return "bundle"
    if trim_miss or trim_loss:
        return "trim"
    return "OK"


def main() -> int:
    p = argparse.ArgumentParser(description="四层检索缺口诊断")
    p.add_argument("--ids", default="Q3,Q4,Q5", help="逗号分隔题号")
    p.add_argument("--k", default="5,8,10", help="raw search K 列表")
    p.add_argument("--json", action="store_true")
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--eval-file", default=str(EVAL_PATH))
    args = p.parse_args()

    ids = {x.strip() for x in args.ids.split(",") if x.strip()}
    ks = [int(x.strip()) for x in args.k.split(",") if x.strip()]

    search = load_module("03_search.py")
    ans = load_module("04_answer.py")
    search.load_index()

    data = json.loads(Path(args.eval_file).read_text(encoding="utf-8"))
    questions = [q for q in data["questions"] if q["id"] in ids]
    if not questions:
        sys.exit(f"no questions for ids={args.ids}")

    rows = [
        diagnose_question(q, search, ans.trim_context_hits, ks=ks)
        for q in questions
    ]

    if args.json:
        out = json.dumps(rows, ensure_ascii=False, indent=2)
        print(out)
    else:
        print(format_report(rows, ks))

    if args.output:
        if args.json:
            args.output.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            args.output.write_text(format_report(rows, ks), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
