from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from search.index import SearchIndex

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = LAB_ROOT / "src"
DATA_DIR = LAB_ROOT / "data"
REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
REPL_HISTORY = DATA_DIR / "repl_history.txt"

_SEARCH_INDEX: "SearchIndex | None" = None


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def search_module() -> "SearchIndex":
    """Return the cached SearchIndex, loading on first call."""
    global _SEARCH_INDEX
    if _SEARCH_INDEX is not None:
        return _SEARCH_INDEX

    # Add src/ to path so search/ and kb_cli/ are importable
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from search.index import SearchIndex  # noqa: PLC0415

    idx = SearchIndex()
    idx.load_index()
    _SEARCH_INDEX = idx
    return idx


def answer_module():
    """Return the 04_answer module (loaded via importlib for legacy compat)."""
    import importlib.util  # noqa: PLC0415

    path = SRC_DIR / "04_answer.py"
    spec = importlib.util.spec_from_file_location("_kb_04_answer", path)
    if spec is None or spec.loader is None:
        sys.exit(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def model_label() -> str:
    answer = answer_module()
    answer.load_dotenv(answer.ENV_PATH)
    provider = os.environ.get("LLM_PROVIDER", "zhipu").lower().strip()
    model = os.environ.get(
        "LLM_MODEL", answer.DEFAULT_MODEL.get(provider, "glm-4-flash")
    )
    return f"{provider} / {model}"


def repo_file(path: str) -> Path:
    return REPO_ROOT / path.replace("\\", "/")


@lru_cache(maxsize=64)
def _read_lines_cached(repo_relative_path: str) -> tuple[str, ...]:
    path = repo_file(repo_relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"file not found: {repo_relative_path}")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise OSError(f"cannot read {repo_relative_path}: {exc}") from exc
    return tuple(text.splitlines())


def read_lines(repo_relative_path: str) -> list[str]:
    """Read a repo file by relative path; cache the most recent 64 files."""
    return list(_read_lines_cached(repo_relative_path))


def index_stats(search_mod: "SearchIndex | None" = None) -> dict[str, int | str]:
    idx = search_mod or search_module()
    return {
        "repo": REPO_ROOT.name,
        "chunks": len(idx._CHUNKS),
        "symbols": sum(idx._SYMBOL_NAME_FREQ.values()),
        "files": len(idx._CHUNKS_BY_FILE),
    }
