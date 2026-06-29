"""
03_search.py — CLI 入口（BM25 + symbol + rg 融合检索）

检索逻辑已迁移至 search/index.py SearchIndex 类。
本文件保留：
  1. CLI argparse 入口（python src/03_search.py --eval / query）
  2. 模块级向后兼容 shim（run_regression.py / eval_answer_layer.py 用 importlib 加载本模块后
     直接调用 search.load_index() / search.search() / search._CHUNK_BY_ID 等）。

用法：
    python src/03_search.py "Planner append_block"
    python src/03_search.py --eval
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── 把 src/ 加入 sys.path（保证从脚本直接运行时也能 import search / kb_cli）──
_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from search.index import (  # noqa: E402
    SearchIndex,
    CHUNKS_PATH,
    EVAL_PATH,
    SYMBOLS_PATH,
    DEFAULT_REPO_ROOT,
    SRC_ROOT,
    EVAL_COV5_GATE,
    matched_hint_groups,
)

# ── 模块级 SearchIndex 实例（backward-compat shim）────────────────────────
# run_regression.py / eval_answer_layer.py / 04_answer.py 通过 importlib 加载本模块，
# 然后直接访问 mod.search() / mod._CHUNK_BY_ID / mod.load_index() 等。
# 这里把实例属性/方法透传到模块级。

_INSTANCE: SearchIndex = SearchIndex()

# 初始时指向空容器，load_index() 之后通过 _sync_globals() 刷新
_CHUNKS: list[dict] = _INSTANCE._CHUNKS
_CHUNK_BY_ID: dict[str, dict] = _INSTANCE._CHUNK_BY_ID
_CHUNKS_BY_FILE = _INSTANCE._CHUNKS_BY_FILE
_SYMBOL_BY_QUAL = _INSTANCE._SYMBOL_BY_QUAL
_SYMBOL_BY_NAME = _INSTANCE._SYMBOL_BY_NAME
_SYMBOL_NAME_FREQ = _INSTANCE._SYMBOL_NAME_FREQ


def _sync_globals() -> None:
    """load_index() 后把模块级别名指向实例的新容器。"""
    global _CHUNKS, _CHUNK_BY_ID, _CHUNKS_BY_FILE
    global _SYMBOL_BY_QUAL, _SYMBOL_BY_NAME, _SYMBOL_NAME_FREQ
    _CHUNKS = _INSTANCE._CHUNKS
    _CHUNK_BY_ID = _INSTANCE._CHUNK_BY_ID
    _CHUNKS_BY_FILE = _INSTANCE._CHUNKS_BY_FILE
    _SYMBOL_BY_QUAL = _INSTANCE._SYMBOL_BY_QUAL
    _SYMBOL_BY_NAME = _INSTANCE._SYMBOL_BY_NAME
    _SYMBOL_NAME_FREQ = _INSTANCE._SYMBOL_NAME_FREQ


# ── backward-compat 函数转发 ──────────────────────────────────────────────

def load_index(
    chunks_path: Path = CHUNKS_PATH,
    symbols_path: Path = SYMBOLS_PATH,
    rg_bin: str | None = None,
) -> None:
    _INSTANCE.load_index(Path(chunks_path), Path(symbols_path), rg_bin)
    _sync_globals()


def search(
    query: str,
    top_k: int = 10,
    src_root: Path | None = None,
    repo_root: Path | None = None,
    rg_bin: str | None = None,     # backward-compat param (ignored; rg set at load time)
    bundle: bool = False,
    enable_reporank: bool | None = None,
) -> list[dict]:
    return _INSTANCE.search(
        query, top_k=top_k, src_root=src_root,
        repo_root=repo_root, bundle=bundle,
        enable_reporank=enable_reporank,
    )


def eval_summary(
    eval_path: Path = EVAL_PATH,
    src_root: Path | None = None,
    repo_root: Path | None = None,
    rg_bin: str | None = None,
    enable_reporank: bool | None = None,
) -> dict:
    return _INSTANCE.eval_summary(
        Path(eval_path), src_root=src_root,
        repo_root=repo_root, enable_reporank=enable_reporank,
    )


def chunks_for_symbol(sym: dict) -> list[dict]:
    return _INSTANCE.chunks_for_symbol(sym)


def hit_from_chunk(
    chunk: dict, score: float, source: str, focus_line: int | None = None
) -> dict:
    return _INSTANCE.hit_from_chunk(chunk, score, source, focus_line)


def chunk_at_line(file: str, line: int) -> dict | None:
    return _INSTANCE.chunk_at_line(file, line)


def is_entry_chunk(chunk: dict) -> bool:
    return _INSTANCE.is_entry_chunk(chunk)


def make_snippet(chunk: dict, focus_line: int | None = None) -> str:
    return _INSTANCE.make_snippet(chunk, focus_line)


# ── CLI ───────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BM25 + symbol + rg 融合检索")
    p.add_argument("query", nargs="?", help="检索关键词")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--eval", action="store_true", help="运行 eval_questions.json 回归")
    p.add_argument("--json", action="store_true", help="JSON 输出检索结果")
    p.add_argument("--chunks", default=str(CHUNKS_PATH))
    p.add_argument("--symbols", default=str(SYMBOLS_PATH))
    p.add_argument("--eval-file", default=str(EVAL_PATH))
    p.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    p.add_argument("--src-root", default=None)
    p.add_argument("--rg-bin", default=None)
    p.add_argument(
        "--enable-reporank", action="store_true",
        help="Phase 9 A/B: use optional repomap PageRank extras",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    idx = SearchIndex()
    try:
        idx.load_index(Path(args.chunks), Path(args.symbols), args.rg_bin)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(args.repo_root)
    src_root = Path(args.src_root) if args.src_root else repo_root / "src"
    enable_reporank = True if args.enable_reporank else None

    if args.eval:
        sys.exit(
            idx.run_eval(
                Path(args.eval_file), src_root=src_root,
                repo_root=repo_root, enable_reporank=enable_reporank,
            )
        )

    if not args.query:
        print("请提供 query，或使用 --eval", file=sys.stderr)
        sys.exit(1)

    results = idx.search(
        args.query, top_k=args.top_k,
        src_root=src_root, repo_root=repo_root,
        enable_reporank=enable_reporank,
    )
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"query: {args.query!r}  ({len(results)} hits)\n")
    for i, r in enumerate(results, 1):
        sym = f"{r['symbol']} " if r["symbol"] else ""
        print(
            f"{i:>2}. [{r['score']:>6.1f}] {r['file']}:{r['line_start']} "
            f"({r['type']}) {sym}[{r.get('source', '')}]"
        )
        for ln in r["snippet"].splitlines()[:3]:
            print(f"      {ln[:100]}")
        print()


if __name__ == "__main__":
    main()
