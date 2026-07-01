"""
按 expected_files 数量分层统计 retrieval cov@5（纯诊断，不改检索逻辑）。

用法：
    python eval/analyze_by_multiplicity.py
    python eval/analyze_by_multiplicity.py --from-json path/to/eval_summary.json
    python eval/analyze_by_multiplicity.py --markdown -o notes/eval_multiplicity_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC = LAB_ROOT / "src"


@dataclass
class QuestionRow:
    qid: str
    split: str
    question: str
    expected_files: list[str]
    multiplicity: str  # single | multi
    cov5: float
    hit5: list[str]
    miss5: list[str]

    @property
    def is_miss(self) -> bool:
        return self.cov5 < 1.0


@dataclass
class BucketStats:
    label: str
    rows: list[QuestionRow] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.rows)

    @property
    def mean_cov5(self) -> float:
        if not self.rows:
            return 0.0
        return sum(r.cov5 for r in self.rows) / len(self.rows)

    @property
    def misses(self) -> list[QuestionRow]:
        return [r for r in self.rows if r.is_miss]


def _load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["questions"]


def _run_eval_summary(eval_path: Path) -> dict:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from search.index import SearchIndex

    idx = SearchIndex()
    idx.load_index()
    return idx.eval_summary(eval_path)


def _load_summary_from_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "details" not in data:
        raise ValueError(
            f"{path} missing 'details' array — expected eval_summary() JSON, "
            "not eval_answer_layer report"
        )
    return data


def _merge_rows(questions: list[dict], details: list[dict]) -> list[QuestionRow]:
    by_id = {d["id"]: d for d in details}
    rows: list[QuestionRow] = []
    for q in questions:
        qid = q["id"]
        if qid not in by_id:
            raise ValueError(f"eval details missing question id {qid}")
        d = by_id[qid]
        expected = list(q["expected_files"])
        mult = "multi" if len(expected) > 1 else "single"
        rows.append(
            QuestionRow(
                qid=qid,
                split=q.get("split", "tune"),
                question=q["question"],
                expected_files=expected,
                multiplicity=mult,
                cov5=float(d["cov5"]),
                hit5=list(d.get("hit5") or []),
                miss5=list(d.get("miss5") or []),
            )
        )
    return rows


def _bucket(rows: list[QuestionRow], *, multiplicity: str | None, split: str | None) -> BucketStats:
    label_parts = []
    if split:
        label_parts.append(split)
    if multiplicity:
        label_parts.append(multiplicity)
    label = "/".join(label_parts) if label_parts else "all"
    filtered = rows
    if multiplicity:
        filtered = [r for r in filtered if r.multiplicity == multiplicity]
    if split:
        filtered = [r for r in filtered if r.split == split]
    return BucketStats(label=label, rows=filtered)


def _mean_cov5(rows: list[QuestionRow]) -> float:
    if not rows:
        return 0.0
    return sum(r.cov5 for r in rows) / len(rows)


def _format_text_report(rows: list[QuestionRow], summary: dict) -> str:
    lines: list[str] = []
    lines.append("Eval cov@5 by expected_files multiplicity (retrieval only)")
    lines.append(f"eval: {EVAL_PATH.name}")
    lines.append(f"gate_ok: {summary.get('gate_ok')}  mean_cov5 (all): {summary.get('mean_cov5', 0):.1%}")
    lines.append("")

    single_n = sum(1 for r in rows if r.multiplicity == "single")
    multi_n = sum(1 for r in rows if r.multiplicity == "multi")
    lines.append("Dataset shape:")
    lines.append(f"  total: {len(rows)}  single-file: {single_n}  multi-file: {multi_n}")
    lines.append(
        f"  tune multi-file: {sum(1 for r in rows if r.split == 'tune' and r.multiplicity == 'multi')}/5"
    )
    lines.append(
        f"  holdout multi-file: "
        f"{sum(1 for r in rows if r.split == 'holdout' and r.multiplicity == 'multi')}/30"
        f"  (H3, H8, H9 only)"
    )
    lines.append("")

    sections = [
        ("ALL", None, None),
        ("TUNE", None, "tune"),
        ("HOLDOUT", None, "holdout"),
        ("SINGLE-FILE (all splits)", "single", None),
        ("MULTI-FILE (all splits)", "multi", None),
        ("TUNE / single", "single", "tune"),
        ("TUNE / multi", "multi", "tune"),
        ("HOLDOUT / single", "single", "holdout"),
        ("HOLDOUT / multi", "multi", "holdout"),
    ]

    lines.append("--- mean cov@5 by bucket ---")
    for title, mult, split in sections:
        bucket = _bucket(rows, multiplicity=mult, split=split)
        lines.append(f"{title:28s}  n={bucket.count:2d}  mean_cov@5={bucket.mean_cov5:.1%}")
    lines.append("")

    for mult in ("single", "multi"):
        bucket = _bucket(rows, multiplicity=mult, split=None)
        lines.append(f"=== MULTIPLICITY={mult.upper()} (n={bucket.count}) mean_cov@5={bucket.mean_cov5:.1%} ===")
        misses = bucket.misses
        if not misses:
            lines.append("  (no misses — all cov@5 == 100%)")
        else:
            lines.append(f"  misses: {len(misses)}")
            for r in sorted(misses, key=lambda x: (x.split, x.qid)):
                lines.append(f"  [{r.split}] {r.qid}  cov@5={r.cov5:.1%}")
                lines.append(f"    Q: {r.question}")
                lines.append(f"    expected: {r.expected_files}")
                lines.append(f"    hit@5:    {r.hit5 or ['(none)']}")
                lines.append(f"    miss@5:   {r.miss5}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stratify eval cov@5 by len(expected_files) (diagnostic only)"
    )
    parser.add_argument(
        "--eval",
        type=Path,
        default=EVAL_PATH,
        help="eval_questions.json path",
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="reuse eval_summary() JSON with 'details' (skip re-running search)",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="wrap output as markdown (for -o)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="write report to file",
    )
    args = parser.parse_args()

    questions = _load_questions(args.eval)
    if args.from_json:
        summary = _load_summary_from_json(args.from_json)
    else:
        print("Running eval_summary() (read-only on ranking logic)...", file=sys.stderr)
        summary = _run_eval_summary(args.eval)

    rows = _merge_rows(questions, summary["details"])
    text = _format_text_report(rows, summary)
    if args.markdown:
        text = f"# Eval multiplicity report\n\n```\n{text}\n```\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
