"""Profile retrieval hotspots with cProfile and synthetic merge scaling.

Constraints:
- No retrieval logic changes.
- No LLM layer.
- Synthetic enlarged chunk maps are in-memory only.
"""

from __future__ import annotations

import cProfile
import copy
import io
import json
import math
import pstats
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
OUT_NOTE = LAB_ROOT / "notes" / "merge_scores_profile.md"

import sys

SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search.index import SearchIndex, expand_query_tokens, tokenize  # noqa: E402


@dataclass
class FnStat:
    func: str
    ncalls: int
    tottime: float
    cumtime: float


def load_questions() -> list[dict]:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]


def is_tune13(q: dict) -> bool:
    if q.get("split") == "tune":
        return True
    return q.get("dev_split") == "tune"


def pstats_rows(stats: pstats.Stats) -> list[FnStat]:
    rows: list[FnStat] = []
    for (filename, _line, funcname), v in stats.stats.items():
        cc, nc, tt, ct, _callers = v
        rows.append(
            FnStat(
                func=f"{Path(filename).name}:{funcname}",
                ncalls=nc if isinstance(nc, int) else int(nc),
                tottime=float(tt),
                cumtime=float(ct),
            )
        )
    return rows


def top_rows(rows: list[FnStat], key: str, n: int = 20) -> list[FnStat]:
    if key == "cumtime":
        return sorted(rows, key=lambda r: r.cumtime, reverse=True)[:n]
    return sorted(rows, key=lambda r: r.tottime, reverse=True)[:n]


def func_time(rows: list[FnStat], contains: str) -> tuple[float, float]:
    tt = sum(r.tottime for r in rows if contains in r.func)
    ct = sum(r.cumtime for r in rows if contains in r.func)
    return tt, ct


def run_baseline_profile(idx: SearchIndex, questions: list[dict]) -> tuple[list[FnStat], dict]:
    merge_ms = 0.0
    total_ms = 0.0
    merge_calls = 0
    orig_merge = idx.merge_scores

    def wrapped_merge(*args, **kwargs):
        nonlocal merge_ms, merge_calls
        t0 = time.perf_counter()
        out = orig_merge(*args, **kwargs)
        merge_ms += (time.perf_counter() - t0) * 1000
        merge_calls += 1
        return out

    idx.merge_scores = wrapped_merge  # type: ignore[method-assign]

    # Warm-up once to remove one-time model/download/init noise from profile.
    if questions:
        idx.search(questions[0]["question"], top_k=5, bundle=False)

    profiler = cProfile.Profile()
    profiler.enable()
    for q in questions:
        t0 = time.perf_counter()
        idx.search(q["question"], top_k=5, bundle=False)
        total_ms += (time.perf_counter() - t0) * 1000
    profiler.disable()
    idx.merge_scores = orig_merge  # type: ignore[method-assign]

    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.strip_dirs()
    rows = pstats_rows(stats)
    meta = {
        "queries": len(questions),
        "total_ms": total_ms,
        "mean_ms": total_ms / len(questions) if questions else 0.0,
        "merge_ms": merge_ms,
        "merge_ratio": (merge_ms / total_ms) if total_ms else 0.0,
        "merge_calls": merge_calls,
    }
    return rows, meta


def make_scaled_ids(base_ids: list[str], factor: int) -> list[str]:
    ids = list(base_ids)
    if factor == 1:
        return ids
    for k in range(2, factor + 1):
        ids.extend([f"{cid}__x{k}" for cid in base_ids])
    return ids


def prepare_scaled_index(idx: SearchIndex, factor: int) -> tuple[dict, dict, list, dict]:
    """Patch in-memory chunk maps for synthetic scaling; returns backup state."""
    backup = {
        "CHUNKS": idx._CHUNKS,
        "CHUNK_BY_ID": idx._CHUNK_BY_ID,
        "CHUNKS_BY_FILE": idx._CHUNKS_BY_FILE,
        "CHUNK_MODULE_STEMS": idx._CHUNK_MODULE_STEMS,
    }

    if factor == 1:
        return backup

    base_chunks = idx._CHUNKS
    new_chunks = list(base_chunks)
    new_by_id = dict(idx._CHUNK_BY_ID)
    new_by_file = {k: list(v) for k, v in idx._CHUNKS_BY_FILE.items()}

    for k in range(2, factor + 1):
        suffix = f"__x{k}"
        for c in base_chunks:
            nc = copy.copy(c)
            nc["id"] = f"{c['id']}{suffix}"
            new_chunks.append(nc)
            new_by_id[nc["id"]] = nc
            new_by_file[nc["file"]].append(nc)

    idx._CHUNKS = new_chunks
    idx._CHUNK_BY_ID = new_by_id
    idx._CHUNKS_BY_FILE = new_by_file
    # keep module stems unchanged (same files), matching "copy-paste corpus" instruction
    return backup


def restore_index(idx: SearchIndex, backup: dict) -> None:
    idx._CHUNKS = backup["CHUNKS"]
    idx._CHUNK_BY_ID = backup["CHUNK_BY_ID"]
    idx._CHUNKS_BY_FILE = backup["CHUNKS_BY_FILE"]
    idx._CHUNK_MODULE_STEMS = backup["CHUNK_MODULE_STEMS"]


def measure_merge_only(idx: SearchIndex, queries: list[str], factor: int) -> dict:
    backup = prepare_scaled_index(idx, factor)
    try:
        cids = list(idx._CHUNK_BY_ID.keys())
        dense_scores = {cid: 1.0 for cid in cids}
        ms_list: list[float] = []
        for q in queries:
            tokens = expand_query_tokens(q, tokenize(q))
            t0 = time.perf_counter()
            idx.merge_scores(
                {},
                {},
                {},
                {},
                {},
                {},
                dense_scores,
                query_tokens=tokens,
                query=q,
            )
            ms_list.append((time.perf_counter() - t0) * 1000)
        return {
            "factor": factor,
            "chunk_n": len(cids),
            "mean_ms": statistics.mean(ms_list),
            "p95_ms": sorted(ms_list)[max(0, int(len(ms_list) * 0.95) - 1)],
        }
    finally:
        restore_index(idx, backup)


def fit_power_law(points: list[dict]) -> tuple[float, float]:
    """Fit y = a * n^b on log space. Returns (a, b)."""
    xs = [math.log(p["chunk_n"]) for p in points]
    ys = [math.log(max(1e-9, p["mean_ms"])) for p in points]
    x_bar = statistics.mean(xs)
    y_bar = statistics.mean(ys)
    num = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    den = sum((x - x_bar) ** 2 for x in xs) or 1e-9
    b = num / den
    a = math.exp(y_bar - b * x_bar)
    return a, b


def order_label(b: float) -> str:
    if b < 1.2:
        return "近线性"
    if b < 1.6:
        return "介于线性与 N·logN/N^1.5"
    if b < 2.2:
        return "接近 N²"
    return "高于 N²（需复核）"


def build_note(
    rows: list[FnStat],
    meta: dict,
    scale_points: list[dict],
    power: tuple[float, float],
) -> str:
    top_cum = top_rows(rows, "cumtime", 20)
    top_tot = top_rows(rows, "tottime", 20)
    total_tottime = sum(r.tottime for r in rows)
    total_cumtime = sum(r.cumtime for r in rows)

    chunk_tt, chunk_ct = func_time(rows, "_chunk_module_stems")
    class_tt, class_ct = func_time(rows, "_class_tokens")

    merge_tt, merge_ct = func_time(rows, "merge_scores")
    coh_tt, coh_ct = func_time(rows, "context_coherence_adjustment")
    qmod_tt, qmod_ct = func_time(rows, "_query_module_tokens")

    a, b = power
    pred_8k = a * (8000 ** b)
    pred_15k = a * (15000 ** b)

    lines = [
        "# merge_scores Profiling Report",
        "",
        "## Baseline workload",
        "",
        f"- workload: 48 eval queries, retrieval only (no LLM)",
        f"- mean query latency: {meta['mean_ms']:.2f} ms",
        f"- total query time: {meta['total_ms']:.2f} ms",
        f"- merge_scores total: {meta['merge_ms']:.2f} ms",
        f"- merge_scores ratio: {meta['merge_ratio']*100:.1f}%",
        "",
        "## Hotspot check (target hypothesis)",
        "",
        f"- `_chunk_module_stems` tottime share: {(chunk_tt/total_tottime*100 if total_tottime else 0):.3f}%",
        f"- `_chunk_module_stems` cumtime share: {(chunk_ct/total_cumtime*100 if total_cumtime else 0):.3f}%",
        f"- `_class_tokens` tottime share: {(class_tt/total_tottime*100 if total_tottime else 0):.3f}%",
        f"- `_class_tokens` cumtime share: {(class_ct/total_cumtime*100 if total_cumtime else 0):.3f}%",
        "",
        f"- real major chain (cumtime): `search -> merge_scores -> context_coherence_adjustment -> _query_module_tokens`",
        f"- chain shares: merge_scores={merge_ct:.3f}s, context_coherence_adjustment={coh_ct:.3f}s, _query_module_tokens={qmod_ct:.3f}s",
        "",
        "## cProfile Top20 by cumtime",
        "",
        "| func | ncalls | tottime(s) | cumtime(s) |",
        "|------|-------:|-----------:|-----------:|",
    ]
    for r in top_cum:
        lines.append(f"| `{r.func}` | {r.ncalls} | {r.tottime:.4f} | {r.cumtime:.4f} |")

    lines += [
        "",
        "## cProfile Top20 by tottime",
        "",
        "| func | ncalls | tottime(s) | cumtime(s) |",
        "|------|-------:|-----------:|-----------:|",
    ]
    for r in top_tot:
        lines.append(f"| `{r.func}` | {r.ncalls} | {r.tottime:.4f} | {r.cumtime:.4f} |")

    lines += [
        "",
        "## Synthetic scaling (merge_scores only, in-memory copied chunks)",
        "",
        "| scale | chunk_n | mean_ms | p95_ms |",
        "|------:|--------:|--------:|------:|",
    ]
    for p in scale_points:
        lines.append(f"| {p['factor']}x | {p['chunk_n']} | {p['mean_ms']:.3f} | {p['p95_ms']:.3f} |")

    lines += [
        "",
        f"- fitted order exponent b = {b:.3f} ({order_label(b)})",
        f"- predicted merge_scores mean @8k chunks: {pred_8k:.2f} ms",
        f"- predicted merge_scores mean @15k chunks: {pred_15k:.2f} ms",
        "",
        "## Notes",
        "",
        "- synthetic scaling duplicates chunk ids in-memory only (no corpus/index persistence).",
        "- retrieval logic unchanged; measurement-only pass.",
    ]
    return "\n".join(lines)


def main() -> int:
    questions = load_questions()
    tune13 = [q for q in questions if is_tune13(q)]

    idx = SearchIndex()
    idx.load_index()
    idx.load_dense_index(force=True)

    rows, meta = run_baseline_profile(idx, questions)
    qtexts = [q["question"] for q in tune13]
    scale_points = [measure_merge_only(idx, qtexts, f) for f in (1, 2, 5, 10)]
    power = fit_power_law(scale_points)

    note = build_note(rows, meta, scale_points, power)
    OUT_NOTE.write_text(note, encoding="utf-8")
    print(f"Wrote {OUT_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
