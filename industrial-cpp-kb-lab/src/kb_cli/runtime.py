from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = LAB_ROOT / "src"
DATA_DIR = LAB_ROOT / "data"
REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
REPL_HISTORY = DATA_DIR / "repl_history.txt"

_MODULE_CACHE: dict[str, ModuleType] = {}


def configure_console_encoding() -> None:
    """Make Windows PowerShell less likely to mojibake Chinese help text."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def load_module(filename: str) -> ModuleType:
    if filename in _MODULE_CACHE:
        return _MODULE_CACHE[filename]
    path = SRC_DIR / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODULE_CACHE[filename] = mod
    return mod


def search_module() -> ModuleType:
    mod = load_module("03_search.py")
    if not mod._CHUNKS:
        mod.load_index()
    return mod


def answer_module() -> ModuleType:
    return load_module("04_answer.py")


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


def index_stats(search_mod: ModuleType | None = None) -> dict[str, int | str]:
    search = search_mod or search_module()
    return {
        "repo": REPO_ROOT.name,
        "chunks": len(search._CHUNKS),
        "symbols": sum(search._SYMBOL_NAME_FREQ.values()),
        "files": len(search._CHUNKS_BY_FILE),
    }

