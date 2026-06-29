"""
search/index.py — SearchIndex：只读索引对象

提供 load_index() / search() / eval_summary() 等统一接口。
原 03_search.py 的模块级全局变量全部迁移为实例属性。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    sys.exit("rank_bm25 未安装，请运行: pip install -r requirements.txt")

from kb_cli.errors import KBIndexError, KBSearchError

# ── 路径默认值 ─────────────────────────────────────────────────
LAB_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
CHUNKS_PATH = LAB_ROOT / "data" / "chunks.jsonl"
SYMBOLS_PATH = LAB_ROOT / "data" / "symbol_index.json"
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC_ROOT = DEFAULT_REPO_ROOT / "src"
CALL_GRAPH_PATH = LAB_ROOT / "data" / "call_graph.json"
DISPATCH_INDEX_PATH = LAB_ROOT / "data" / "dispatch_index.json"
REPOMAP_GRAPH_PATH = LAB_ROOT / "data" / "repomap_graph.json"

EVAL_COV5_GATE = 0.70

# ── 检索权重常量 ───────────────────────────────────────────────
W_SYMBOL = 100.0
W_METHOD = 125.0
W_CLASS_METHOD = 108.0
W_DISPATCH = 140.0
W_RG = 50.0
W_BM25 = 10.0
W_GRAPH = 25.0
TYPE_BONUS: dict[str, float] = {
    "function": 3.0, "class": 2.0, "file_overview": 1.0, "fallback": 0.0,
}

ENABLE_CONTEXT_COHERENCE_BONUS = True
CONTEXT_COHERENCE_BONUS = 8.0
CONTEXT_INCOHERENCE_PENALTY = 5.0
CONTEXT_COHERENCE_MIN_TOKEN_LEN = 4
ENTRY_CHUNK_BONUS = 6.0

ENABLE_REPORANK_ENV = "ENABLE_REPORANK"
REPORANK_DAMPING = 0.85
REPORANK_ITERS = 30
REPORANK_EXTRAS = 3
REPORANK_SCORE_SCALE = 1000.0

SNIPPET_DEFAULT_LINES = 10
SNIPPET_EVENT_MARKERS = ("call_event", "THEKERNEL->call_event")
SNIPPET_SCAN_LINES = 40
SNIPPET_EVENT_CAP = 28

COMMAND_RE = re.compile(r"\b([GM])\s*[-:]?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

FLOW_INTENT_KEYS = (
    "进入", "入口", "变成", "命令", "如何", "怎么", "怎样",
    "触发", "注册", "通信",
    "halt", "stop", "emergency", "停止", "报警",
)
GENERIC_EVENT_HANDLERS = frozenset({
    "on_main_loop", "on_idle", "on_second_tick", "on_module_loaded",
    "on_enable", "on_get_public_data", "on_set_public_data",
})

# ── 中文 Hint groups（模块级，不依赖实例） ─────────────────────

def _hint_entry(query: str, ql: str) -> bool:
    phrases = ("从哪里进入", "从哪进入", "进入系统", "gcode进入", "g-code进入")
    if any(p in query or p in ql for p in phrases):
        return True
    return "进入" in query and "gcode" in ql


def _hint_motion_chain(query: str, ql: str) -> bool:
    if "变成" in query:
        return True
    return "运动" in query and "命令" in query


def _hint_motion_structure(query: str, ql: str) -> bool:
    return any(k in ql for k in ("motion", "planner", "stepper"))


def _hint_halt(query: str, ql: str) -> bool:
    keys = ("halt", "stop", "emergency", "error", "停止", "报警")
    return any(k in ql or k in query for k in keys)


def _hint_module(query: str, ql: str) -> bool:
    if "模块系统" in query:
        return True
    keys = ("注册", "通信", "触发")
    return any(k in query for k in keys)


HINT_GROUPS: list[tuple[str, object, list[str]]] = [
    ("entry", _hint_entry, [
        "gcode", "GcodeDispatch", "SerialConsole", "Player",
        "on_console_line_received", "ON_CONSOLE_LINE_RECEIVED",
        "on_main_loop", "call_event", "console_line",
    ]),
    ("motion_chain", _hint_motion_chain, [
        "Robot", "Planner", "Conveyor", "StepTicker",
        "on_gcode_received", "append_block", "process_move",
        "queue_head_block", "step_tick", "GcodeDispatch",
    ]),
    ("motion_structure", _hint_motion_structure, [
        "Planner", "StepTicker", "StepperMotor", "Robot", "Block", "Conveyor",
        "append_block", "calculate_trapezoid", "step_tick", "manual_step",
    ]),
    ("halt", _hint_halt, [
        "halt", "ON_HALT", "KillButton", "immediate_halt", "Endstops", "on_halt",
        "SerialConsole", "halt_flag", "GcodeDispatch", "Kernel", "Conveyor",
        "StepperMotor",
    ]),
    ("module", _hint_module, [
        "Module", "Kernel", "register_for_event", "call_event", "PublicData",
        "add_module", "get_value", "set_value", "main", "ON_MODULE_LOADED",
    ]),
]


# ── 模块级无状态工具函数 ────────────────────────────────────────

def _query_lower(query: str) -> str:
    return query.lower().replace("g-code", "gcode").replace("G-Code", "gcode")


def tokenize(text: str) -> list[str]:
    text = text.replace("G-code", "gcode").replace("G-Code", "gcode")
    text = text.replace("->", " ").replace("::", " ")
    raw = re.findall(r"[A-Za-z_][\w]*|\d+", text)
    tokens: list[str] = []
    seen: set[str] = set()

    def add(tok: str) -> None:
        t = tok.lower()
        if len(t) >= 2 and t not in seen:
            seen.add(t)
            tokens.append(t)

    for word in raw:
        add(word)
        for p in re.sub(r"([a-z])([A-Z])", r"\1 \2", word).split():
            add(p)
        for p in word.split("_"):
            if p:
                add(p)
    return tokens


def matched_hint_groups(query: str) -> list[str]:
    ql = _query_lower(query)
    return [name for name, trigger, _ in HINT_GROUPS if trigger(query, ql)]


def expand_query_tokens(query: str, tokens: list[str]) -> list[str]:
    ql = _query_lower(query)
    extra: list[str] = []
    seen = set(tokens)
    for _name, trigger, hints in HINT_GROUPS:
        if trigger(query, ql):
            for h in hints:
                t = h.lower()
                if t not in seen:
                    seen.add(t)
                    extra.append(t)
    return tokens + extra


def flow_intent_query(query: str) -> bool:
    q_lower = query.lower()
    return any(k in q_lower or k in query for k in FLOW_INTENT_KEYS)


def flow_entry_query(query: str) -> bool:
    ql = _query_lower(query)
    return _hint_entry(query, ql)


def multi_file_structure_query(query: str) -> bool:
    ql = _query_lower(query)
    return (
        _hint_motion_structure(query, ql)
        or _hint_halt(query, ql)
        or _hint_module(query, ql)
    )


def _norm_command(letter: str, number: str) -> str:
    num = number.rstrip("0").rstrip(".") if "." in number else number
    return f"{letter.upper()}{num}"


def commands_in_query(query: str) -> set[str]:
    return {_norm_command(m.group(1), m.group(2)) for m in COMMAND_RE.finditer(query)}


# ── SearchIndex ────────────────────────────────────────────────

class SearchIndex:
    """只读检索索引对象。

    用法：
        idx = SearchIndex()
        idx.load_index()
        hits = idx.search("G-code 从哪里进入？", top_k=8, bundle=True)
    """

    def __init__(self) -> None:
        self._CHUNKS: list[dict] = []
        self._CHUNK_BY_ID: dict[str, dict] = {}
        self._CHUNKS_BY_FILE: dict[str, list[dict]] = defaultdict(list)
        self._SYMBOL_BY_QUAL: dict[str, list[dict]] = defaultdict(list)
        self._SYMBOL_BY_NAME: dict[str, list[dict]] = defaultdict(list)
        self._SYMBOL_NAME_FREQ: dict[str, int] = {}
        self._BM25: BM25Okapi | None = None
        self._BM25_CHUNK_IDS: list[str] = []
        self._RG_BIN: str = ""
        self._CALL_GRAPH: dict = {}
        self._DISPATCH_INDEX: list[dict] = []
        self._REPOMAP: dict = {}
        self._ENABLE_REPORANK: bool = (
            os.environ.get(ENABLE_REPORANK_ENV, "").strip() == "1"
        )

    # ── 静态工具 ─────────────────────────────────────────────

    @staticmethod
    def find_rg(preferred: str | None = None) -> str:
        if preferred:
            return preferred
        if shutil.which("rg"):
            return "rg"
        winget_base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        for p in winget_base.glob("BurntSushi.ripgrep.*/**/rg.exe"):
            return str(p)
        raise KBSearchError("rg 未找到，请确认已安装 ripgrep")

    # ── 加载 ─────────────────────────────────────────────────

    def _load_chunks(self, path: Path) -> None:
        self._CHUNKS = []
        self._CHUNK_BY_ID = {}
        self._CHUNKS_BY_FILE = defaultdict(list)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            self._CHUNKS.append(c)
            self._CHUNK_BY_ID[c["id"]] = c
            self._CHUNKS_BY_FILE[c["file"]].append(c)
        for flist in self._CHUNKS_BY_FILE.values():
            flist.sort(key=lambda x: (x["start_line"], -(x["end_line"] - x["start_line"])))

    def _load_symbols(self, path: Path) -> None:
        self._SYMBOL_BY_QUAL = defaultdict(list)
        self._SYMBOL_BY_NAME = defaultdict(list)
        symbols = json.loads(path.read_text(encoding="utf-8"))
        freq: dict[str, int] = {}
        for s in symbols:
            if s["kind"] not in ("function", "prototype", "class", "struct"):
                continue
            freq[s["name"]] = freq.get(s["name"], 0) + 1
        self._SYMBOL_NAME_FREQ = freq
        for s in symbols:
            if s["kind"] not in ("function", "prototype", "class", "struct"):
                continue
            name = s["name"]
            cls = s.get("class") or ""
            self._SYMBOL_BY_NAME[name.lower()].append(s)
            if cls:
                self._SYMBOL_BY_QUAL[f"{cls}::{name}".lower()].append(s)

    def _build_bm25(self) -> None:
        corpus = []
        self._BM25_CHUNK_IDS = []
        for c in self._CHUNKS:
            meta = f"{c['file']} {c.get('symbol', '')} {c.get('class', '')} {c['type']}"
            corpus.append(tokenize(c["text"] + " " + meta))
            self._BM25_CHUNK_IDS.append(c["id"])
        self._BM25 = BM25Okapi(corpus)

    def _load_call_graph(self, path: Path = CALL_GRAPH_PATH) -> None:
        self._CALL_GRAPH = (
            json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        )

    def _load_dispatch_index(self, path: Path = DISPATCH_INDEX_PATH) -> None:
        if not path.is_file():
            self._DISPATCH_INDEX = []
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            self._DISPATCH_INDEX = data.get("entries", [])
        elif isinstance(data, list):
            self._DISPATCH_INDEX = data
        else:
            self._DISPATCH_INDEX = []

    def _load_repomap(self, path: Path = REPOMAP_GRAPH_PATH) -> None:
        self._REPOMAP = (
            json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        )

    def load_index(
        self,
        chunks_path: Path = CHUNKS_PATH,
        symbols_path: Path = SYMBOLS_PATH,
        rg_bin: str | None = None,
    ) -> None:
        if not chunks_path.is_file():
            raise KBIndexError(
                f"chunks 不存在: {chunks_path}，请先运行 03_build_chunks.py"
            )
        if not symbols_path.is_file():
            raise KBIndexError(
                f"symbols 不存在: {symbols_path}，请先运行 02_extract_symbols.py"
            )
        self._RG_BIN = self.find_rg(rg_bin)
        self._load_chunks(chunks_path)
        self._load_symbols(symbols_path)
        self._build_bm25()
        self._load_call_graph()
        self._load_dispatch_index()
        self._load_repomap()

    # ── Chunk 查询 ────────────────────────────────────────────

    def chunk_at_line(self, file: str, line: int) -> dict | None:
        best: dict | None = None
        best_key = (-1, 0)
        for c in self._CHUNKS_BY_FILE.get(file, []):
            if c["start_line"] <= line <= c["end_line"]:
                pri = {"function": 4, "class": 3, "fallback": 2, "file_overview": 1}.get(
                    c["type"], 0
                )
                key = (pri, -(c["end_line"] - c["start_line"]))
                if key > best_key:
                    best_key = key
                    best = c
        return best

    def chunks_for_symbol(self, sym: dict) -> list[dict]:
        file, name, cls = sym["file"], sym["name"], sym.get("class") or ""
        hits = [
            c for c in self._CHUNKS_BY_FILE.get(file, [])
            if c.get("symbol") == name
            and not (cls and c.get("class") and c.get("class") != cls)
        ]
        if not hits:
            c = self.chunk_at_line(file, sym["line"])
            if c:
                hits.append(c)
        type_rank = {"function": 0, "class": 1, "file_overview": 2, "fallback": 3}
        hits.sort(key=lambda c: (type_rank.get(c["type"], 9), c["start_line"]))
        return hits

    def _is_impl_function(self, chunk: dict) -> bool:
        return chunk["type"] == "function" and chunk["file"].endswith((".cpp", ".c"))

    def _is_constructor_chunk(self, chunk: dict) -> bool:
        sym = chunk.get("symbol") or ""
        cls = chunk.get("class") or ""
        return bool(sym and cls and sym == cls)

    def _symbol_key(self, sym: dict) -> str:
        return f"{sym['file']}:{sym['name']}:{sym.get('class', '')}:{sym.get('line', 0)}"

    def _implementation_chunks_for_symbol(self, sym: dict) -> list[dict]:
        chunks = self.chunks_for_symbol(sym)
        impl = [c for c in chunks if self._is_impl_function(c)]
        return impl or chunks

    def is_entry_chunk(self, chunk: dict) -> bool:
        sym = chunk.get("symbol")
        if not sym:
            return False
        sym_start = chunk.get("symbol_start", chunk["start_line"])
        return chunk["start_line"] == sym_start

    # ── Snippet & Hit ─────────────────────────────────────────

    def make_snippet(self, chunk: dict, focus_line: int | None = None) -> str:
        lines = chunk["text"].splitlines()
        body_start = 0
        for i, ln in enumerate(lines):
            if ln.startswith("//") or not ln.strip():
                continue
            body_start = i
            break
        if focus_line and chunk["file"]:
            rel = max(0, min(len(lines) - 1, focus_line - chunk["start_line"]))
            start = max(body_start, rel - 2)
            end = min(len(lines), start + SNIPPET_DEFAULT_LINES)
        else:
            start = body_start
            end = min(len(lines), body_start + SNIPPET_DEFAULT_LINES)
        scan_end = min(len(lines), body_start + SNIPPET_SCAN_LINES)
        for i in range(body_start, scan_end):
            if any(m in lines[i] for m in SNIPPET_EVENT_MARKERS):
                end = max(end, min(i + 2, body_start + SNIPPET_EVENT_CAP))
                break
        return "\n".join(lines[start:end])

    def hit_from_chunk(
        self,
        chunk: dict,
        score: float,
        source: str,
        focus_line: int | None = None,
    ) -> dict:
        line_start = focus_line if focus_line else chunk["start_line"]
        return {
            "file": chunk["file"],
            "line_start": line_start,
            "chunk_line_start": chunk["start_line"],
            "chunk_line_end": chunk["end_line"],
            "symbol_start": chunk.get("symbol_start", chunk["start_line"]),
            "type": chunk["type"],
            "symbol": chunk.get("symbol") or "",
            "class": chunk.get("class") or "",
            "snippet": self.make_snippet(chunk, focus_line),
            "score": round(score, 2),
            "source": source,
            "chunk_id": chunk["id"],
            "line_end": chunk["end_line"],
        }

    # ── Retrieval helpers ─────────────────────────────────────

    def _class_tokens(self, tokens: list[str]) -> set[str]:
        classes: set[str] = set()
        for values in self._SYMBOL_BY_NAME.values():
            for s in values:
                if s.get("class"):
                    classes.add(s["class"].lower())
                if s.get("kind") in ("class", "struct"):
                    classes.add(s["name"].lower())
        return {t for t in tokens if t in classes}

    def _chunk_module_stems(self) -> set[str]:
        return {Path(f).stem.lower() for f in self._CHUNKS_BY_FILE}

    def _query_module_tokens(self, tokens: list[str]) -> set[str]:
        stems = self._chunk_module_stems()
        named: set[str] = set()
        for t in tokens:
            if len(t) < CONTEXT_COHERENCE_MIN_TOKEN_LEN:
                continue
            if t in stems:
                named.add(t)
                continue
            for s in stems:
                if len(t) >= 5 and t in s:
                    named.add(t)
                    break
        return named

    def hint_coherent_symbol(self, sym: dict, tokens: list[str]) -> bool:
        stem = Path(sym["file"]).stem.lower()
        cls = (sym.get("class") or "").lower()
        tok_set = set(tokens)
        if stem in tok_set or cls in tok_set:
            return True
        return any(len(t) >= 4 and t in stem for t in tok_set)

    def symbol_match_weight(
        self, sym: dict, chunk: dict, query: str, tokens: list[str]
    ) -> float:
        weight = W_SYMBOL * 0.85
        name = sym["name"]
        if self.hint_coherent_symbol(sym, tokens):
            if flow_entry_query(query) and name == "on_main_loop":
                weight = max(weight, W_SYMBOL * 0.92)
            elif (
                flow_intent_query(query)
                and name.startswith("on_")
                and name not in GENERIC_EVENT_HANDLERS
                and chunk["start_line"] == sym["line"]
            ):
                weight = max(weight, W_SYMBOL * 0.92)
        return weight

    def context_coherence_adjustment(self, chunk: dict, query_tokens: list[str]) -> float:
        if not ENABLE_CONTEXT_COHERENCE_BONUS:
            return 0.0
        stem = Path(chunk["file"]).stem.lower()
        cls = (chunk.get("class") or "").lower()
        sym = chunk.get("symbol") or ""
        tok_set = set(query_tokens)
        named = self._query_module_tokens(query_tokens)

        coherent = (
            stem in tok_set
            or cls in tok_set
            or any(len(t) >= CONTEXT_COHERENCE_MIN_TOKEN_LEN and t in stem for t in tok_set)
            or any(len(t) >= CONTEXT_COHERENCE_MIN_TOKEN_LEN and t in cls for t in tok_set)
        )
        if coherent:
            return CONTEXT_COHERENCE_BONUS
        if sym.startswith("on_") and sym not in GENERIC_EVENT_HANDLERS and named:
            return -CONTEXT_INCOHERENCE_PENALTY
        if stem == "player" and "player" not in tok_set:
            if "register_for_event" in tok_set or "add_module" in tok_set:
                return -CONTEXT_INCOHERENCE_PENALTY * 2
        if stem == "switch" and "register_for_event" in tok_set:
            return -CONTEXT_INCOHERENCE_PENALTY * 2
        return 0.0

    def hint_key_header_boost(self, chunk: dict, query: str) -> float:
        ql = _query_lower(query)
        if not _hint_module(query, ql):
            return 0.0
        if not chunk["file"].endswith((".h", ".hpp")):
            return 0.0
        stem = Path(chunk["file"]).stem.lower()
        if stem in ("module", "kernel"):
            return 14.0
        return 0.0

    def chunk_score_bonus(self, chunk: dict) -> float:
        bonus = TYPE_BONUS.get(chunk["type"], 0)
        if chunk["file"].endswith((".cpp", ".c")) and chunk["type"] == "function":
            bonus += 4.0
        elif chunk["file"].endswith((".h", ".hpp")) and chunk["type"] == "class":
            bonus -= 3.0
        sym = chunk.get("symbol") or ""
        cls = chunk.get("class") or ""
        if sym and sym == cls:
            bonus -= 18.0
        if self.is_entry_chunk(chunk):
            bonus += ENTRY_CHUNK_BONUS
        return bonus

    # ── Search sub-routines ───────────────────────────────────

    def search_method(self, query: str, tokens: list[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        seen: set[str] = set()

        for cls, name in re.findall(
            r"\b([A-Za-z_][\w]*)\s*(?:::|\.)\s*([A-Za-z_][\w]*)\b", query
        ):
            for sym in self._SYMBOL_BY_QUAL.get(f"{cls}::{name}".lower(), []):
                key = self._symbol_key(sym)
                if key in seen:
                    continue
                seen.add(key)
                for chunk in self._implementation_chunks_for_symbol(sym):
                    scores[chunk["id"]] = max(scores.get(chunk["id"], 0), W_METHOD)

        for tok in tokens:
            if len(tok) < 4:
                continue
            impl_syms = [
                s for s in self._SYMBOL_BY_NAME.get(tok, [])
                if s.get("kind") == "function" and s["file"].endswith((".cpp", ".c"))
            ]
            if len({self._symbol_key(s) for s in impl_syms}) != 1:
                continue
            sym = impl_syms[0]
            key = self._symbol_key(sym)
            if key in seen:
                continue
            seen.add(key)
            for chunk in self._implementation_chunks_for_symbol(sym):
                scores[chunk["id"]] = max(scores.get(chunk["id"], 0), W_METHOD)
        return scores

    def search_class(self, query: str, tokens: list[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for cls_l in self._class_tokens(tokens):
            for symbols in self._SYMBOL_BY_NAME.values():
                for sym in symbols:
                    if (sym.get("class") or "").lower() != cls_l:
                        continue
                    if sym.get("kind") != "function":
                        continue
                    for chunk in self._implementation_chunks_for_symbol(sym):
                        if not self._is_impl_function(chunk):
                            continue
                        if self._is_constructor_chunk(chunk):
                            continue
                        scores[chunk["id"]] = max(
                            scores.get(chunk["id"], 0), W_CLASS_METHOD
                        )
        return scores

    def search_symbols(self, query: str, tokens: list[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        seen_sym: set[str] = set()

        for qual in re.findall(r"[A-Za-z_][\w]*::[A-Za-z_][\w]*", query):
            for sym in self._SYMBOL_BY_QUAL.get(qual.lower(), []):
                key = f"{sym['file']}:{sym['name']}:{sym.get('class', '')}"
                if key in seen_sym:
                    continue
                seen_sym.add(key)
                for c in self.chunks_for_symbol(sym):
                    scores[c["id"]] = max(scores.get(c["id"], 0), W_SYMBOL)

        for tok in tokens:
            if len(tok) < 3:
                continue
            for sym in self._SYMBOL_BY_NAME.get(tok, []):
                key = f"{sym['file']}:{sym['name']}:{sym.get('class', '')}"
                if key in seen_sym:
                    continue
                seen_sym.add(key)
                for c in self.chunks_for_symbol(sym):
                    sc = self.symbol_match_weight(sym, c, query, tokens)
                    scores[c["id"]] = max(scores.get(c["id"], 0), sc)
        return scores

    def search_bm25(self, tokens: list[str]) -> dict[str, float]:
        if not tokens or self._BM25 is None:
            return {}
        raw = self._BM25.get_scores(tokens)
        mx = max(raw) if len(raw) else 0.0
        if mx <= 0:
            return {}
        return {
            self._BM25_CHUNK_IDS[i]: (raw[i] / mx) * W_BM25
            for i in range(len(raw))
            if raw[i] > 0
        }

    def _rg_path_to_manifest(self, path_part: str, repo_root: Path) -> str | None:
        try:
            return str(
                Path(path_part).resolve().relative_to(repo_root)
            ).replace("\\", "/")
        except ValueError:
            return None

    def search_rg(
        self, tokens: list[str], src_root: Path, repo_root: Path
    ) -> dict[str, float]:
        if not tokens or not src_root.is_dir():
            return {}
        pats = sorted({t for t in tokens if len(t) >= 3}, key=len, reverse=True)[:8]
        if not pats:
            return {}
        cmd = [
            self._RG_BIN, "-n", "--no-heading", "-i", "--max-count", "40",
            "|".join(re.escape(p) for p in pats), str(src_root),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError):
            return {}
        if result.returncode not in (0, 1):
            return {}

        scores: dict[str, float] = {}
        for line in result.stdout.splitlines():
            if ":" not in line:
                continue
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            rel = self._rg_path_to_manifest(parts[0], repo_root)
            if not rel:
                continue
            try:
                lineno = int(parts[1])
            except ValueError:
                continue
            chunk = self.chunk_at_line(rel, lineno)
            if chunk:
                scores[chunk["id"]] = max(scores.get(chunk["id"], 0), W_RG)
        return scores

    def search_dispatch(self, query: str) -> tuple[dict[str, float], dict[str, int]]:
        commands = commands_in_query(query)
        if not commands or not self._DISPATCH_INDEX:
            return {}, {}
        scores: dict[str, float] = {}
        focus: dict[str, int] = {}
        for entry in self._DISPATCH_INDEX:
            command = str(entry.get("command", "")).upper()
            if command not in commands:
                continue
            file = entry.get("handler_file") or entry.get("file")
            line = int(entry.get("line") or 0)
            if not file or not line:
                continue
            chunk = self.chunk_at_line(file, line)
            if not chunk:
                continue
            bonus = 8.0 if entry.get("confidence") == "static-pattern" else 4.0
            cid = chunk["id"]
            scores[cid] = max(scores.get(cid, 0), W_DISPATCH + bonus)
            focus[cid] = line
        return scores, focus

    def merge_scores(
        self,
        *score_maps: dict[str, float],
        query_tokens: list[str] | None = None,
        query: str | None = None,
    ) -> dict[str, float]:
        merged: dict[str, float] = {}
        for sm in score_maps:
            for cid, sc in sm.items():
                merged[cid] = merged.get(cid, 0) + sc
        for cid in merged:
            chunk = self._CHUNK_BY_ID[cid]
            merged[cid] += self.chunk_score_bonus(chunk)
            if query_tokens is not None:
                merged[cid] += self.context_coherence_adjustment(chunk, query_tokens)
            if query is not None:
                merged[cid] += self.hint_key_header_boost(chunk, query)
        return merged

    def _hit_sort_key(self, h: dict) -> tuple:
        chunk = self._CHUNK_BY_ID[h["chunk_id"]]
        return (-h["score"], 0 if self.is_entry_chunk(chunk) else 1, h["file"], h["line_start"])

    def diversify(self, hits: list[dict], top_k: int, per_file: int = 2) -> list[dict]:
        out: list[dict] = []
        file_cnt: dict[str, int] = defaultdict(int)
        for h in hits:
            if len(out) >= top_k:
                break
            if file_cnt[h["file"]] >= per_file:
                continue
            file_cnt[h["file"]] += 1
            out.append(h)
        return out

    # ── Bundle ────────────────────────────────────────────────

    def _header_path_for_impl(self, file: str) -> str | None:
        p = Path(file)
        if p.suffix not in {".cpp", ".c"}:
            return None
        for ext in (".h", ".hpp"):
            candidate = str(p.with_suffix(ext)).replace("\\", "/")
            if candidate in self._CHUNKS_BY_FILE:
                return candidate
        return None

    def _overview_chunk(self, file: str) -> dict | None:
        for c in self._CHUNKS_BY_FILE.get(file, []):
            if c["type"] == "file_overview":
                return c
        return None

    def _class_chunk(self, file: str, class_name: str) -> dict | None:
        for c in self._CHUNKS_BY_FILE.get(file, []):
            if c["type"] == "class" and c.get("symbol") == class_name:
                return c
        return None

    def expand_bundle(self, primary_hits: list[dict]) -> list[dict]:
        seen: set[str] = set()
        bundle: list[dict] = []

        def add(hit: dict, role: str) -> None:
            cid = hit["chunk_id"]
            if cid in seen:
                if role == "primary":
                    for entry in bundle:
                        if entry["chunk_id"] == cid:
                            entry["bundle_role"] = "primary"
                return
            seen.add(cid)
            entry = dict(hit)
            entry["bundle_role"] = role
            bundle.append(entry)

        for h in primary_hits:
            add(h, "primary")
        for h in primary_hits:
            chunk = self._CHUNK_BY_ID[h["chunk_id"]]
            ov = self._overview_chunk(chunk["file"])
            if ov:
                add(self.hit_from_chunk(ov, round(h["score"] * 0.3, 2), "bundle"), "overview")
            hdr_file = self._header_path_for_impl(chunk["file"])
            cls = chunk.get("class") or ""
            if hdr_file and cls and chunk["type"] == "function":
                hdr = self._class_chunk(hdr_file, cls)
                if hdr:
                    add(self.hit_from_chunk(hdr, round(h["score"] * 0.5, 2), "bundle"), "header")
        return bundle

    # ── Graph extras ──────────────────────────────────────────

    def search_graph(self, primary_hits: list[dict]) -> list[dict]:
        if not self._CALL_GRAPH:
            return []
        mentioned_by = self._CALL_GRAPH.get("mentioned_by", {})
        primary_files = {h["file"] for h in primary_hits}
        primary_ids = {h["chunk_id"] for h in primary_hits}

        cand_scores: dict[str, float] = {}
        for hit in primary_hits:
            sym = hit.get("symbol") or ""
            if not sym:
                continue
            name = sym.split("::")[-1] if "::" in sym else sym
            for cid in mentioned_by.get(name, []):
                if cid in primary_ids:
                    continue
                chunk = self._CHUNK_BY_ID.get(cid)
                if chunk and chunk["file"] not in primary_files:
                    cand_scores[cid] = cand_scores.get(cid, 0) + W_GRAPH

        extras: list[dict] = []
        seen_files: set[str] = set(primary_files)
        for cid, sc in sorted(cand_scores.items(), key=lambda x: -x[1]):
            chunk = self._CHUNK_BY_ID.get(cid)
            if not chunk or chunk["file"] in seen_files:
                continue
            seen_files.add(chunk["file"])
            extras.append(self.hit_from_chunk(
                chunk, sc + self.chunk_score_bonus(chunk), "graph"
            ))
            if len(extras) >= 3:
                break
        return extras

    def _normalize_personalization(
        self, weights: dict[str, float]
    ) -> dict[str, float]:
        valid = {
            cid: w for cid, w in weights.items()
            if w > 0 and cid in self._REPOMAP.get("nodes", {})
        }
        total = sum(valid.values())
        if total <= 0:
            return {}
        return {cid: w / total for cid, w in valid.items()}

    def _personalized_reporank(
        self,
        seed_chunk_ids: dict[str, float],
        seed_tokens: list[str],
        limit: int = 50,
    ) -> list[tuple[str, float]]:
        if not self._REPOMAP:
            return []
        nodes = self._REPOMAP.get("nodes", {})
        edges = self._REPOMAP.get("edges", {})
        symbol_to_chunks = self._REPOMAP.get("symbol_to_chunks", {})
        personalization: dict[str, float] = dict(seed_chunk_ids)

        for tok in seed_tokens:
            if len(tok) < 4:
                continue
            for cid in symbol_to_chunks.get(tok, [])[:8]:
                personalization[cid] = personalization.get(cid, 0.0) + 0.35

        p = self._normalize_personalization(personalization)
        if not p:
            return []

        node_ids = list(nodes)
        rank = {cid: p.get(cid, 0.0) for cid in node_ids}
        out_weight = {
            cid: sum(float(e.get("weight", 0.0)) for e in edges.get(cid, []))
            for cid in node_ids
        }
        for _ in range(REPORANK_ITERS):
            new_rank = {
                cid: (1.0 - REPORANK_DAMPING) * p.get(cid, 0.0) for cid in node_ids
            }
            dangling = sum(
                rank[cid] for cid in node_ids if out_weight.get(cid, 0.0) <= 0.0
            )
            for cid, pval in p.items():
                new_rank[cid] = new_rank.get(cid, 0.0) + REPORANK_DAMPING * dangling * pval
            for src in node_ids:
                denom = out_weight.get(src, 0.0)
                if denom <= 0.0:
                    continue
                for edge in edges.get(src, []):
                    dst = edge.get("to")
                    if dst not in new_rank:
                        continue
                    new_rank[dst] += (
                        REPORANK_DAMPING * rank[src] * float(edge.get("weight", 0.0)) / denom
                    )
            rank = new_rank

        return sorted(rank.items(), key=lambda item: -item[1])[:limit]

    def search_reporank(
        self,
        primary_hits: list[dict],
        query: str,
        top_k: int = REPORANK_EXTRAS,
        exact_seed_ids: set[str] | None = None,
    ) -> list[dict]:
        primary_ids = {h["chunk_id"] for h in primary_hits}
        primary_files = {h["file"] for h in primary_hits}
        seed_weights: dict[str, float] = {}
        for hit in primary_hits:
            seed_weights[hit["chunk_id"]] = max(seed_weights.get(hit["chunk_id"], 0.0), 3.0)
        for cid in exact_seed_ids or set():
            seed_weights[cid] = max(seed_weights.get(cid, 0.0), 2.0)

        ranked = self._personalized_reporank(
            seed_weights, expand_query_tokens(query, tokenize(query))
        )
        extras: list[dict] = []
        seen_files: set[str] = set(primary_files)
        for cid, rank_score in ranked:
            if cid in primary_ids:
                continue
            chunk = self._CHUNK_BY_ID.get(cid)
            if not chunk or chunk["file"] in seen_files:
                continue
            if chunk["type"] not in ("function", "class", "file_overview"):
                continue
            seen_files.add(chunk["file"])
            score = W_GRAPH + rank_score * REPORANK_SCORE_SCALE + self.chunk_score_bonus(chunk)
            extras.append(self.hit_from_chunk(chunk, round(score, 2), "reporank"))
            if len(extras) >= top_k:
                break
        return extras

    # ── Main search ───────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        src_root: Path | None = None,
        repo_root: Path | None = None,
        bundle: bool = False,
        enable_reporank: bool | None = None,
    ) -> list[dict]:
        if not self._CHUNKS:
            raise KBSearchError("索引未加载，请先调用 load_index()")
        src = src_root or SRC_ROOT
        repo = repo_root or DEFAULT_REPO_ROOT
        tokens = expand_query_tokens(query, tokenize(query))

        method_scores = self.search_method(query, tokens)
        class_scores = self.search_class(query, tokens)
        dispatch_scores, dispatch_focus = self.search_dispatch(query)
        sym_scores = self.search_symbols(query, tokens)
        bm25_scores = self.search_bm25(tokens)
        rg_scores = self.search_rg(tokens, src, repo)
        merged = self.merge_scores(
            method_scores, class_scores, dispatch_scores,
            sym_scores, bm25_scores, rg_scores,
            query_tokens=tokens, query=query,
        )

        hits: list[dict] = []
        for cid, score in merged.items():
            chunk = self._CHUNK_BY_ID[cid]
            sources = [
                s for s, m in (
                    ("method", method_scores), ("class", class_scores),
                    ("dispatch", dispatch_scores), ("symbol", sym_scores),
                    ("bm25", bm25_scores), ("rg", rg_scores),
                )
                if cid in m
            ]
            hits.append(self.hit_from_chunk(
                chunk, score, "+".join(sources),
                focus_line=dispatch_focus.get(cid),
            ))

        hits.sort(key=self._hit_sort_key)
        per_file = 1 if multi_file_structure_query(query) else 2
        primary = self.diversify(hits, top_k, per_file=per_file)

        exact_seed_ids = (
            set(method_scores) | set(class_scores)
            | set(dispatch_scores) | set(sym_scores)
        )
        use_reporank = self._ENABLE_REPORANK if enable_reporank is None else enable_reporank
        if flow_intent_query(query) and not multi_file_structure_query(query):
            if use_reporank and self._REPOMAP:
                extras = self.search_reporank(
                    primary, query, top_k=REPORANK_EXTRAS, exact_seed_ids=exact_seed_ids
                )
            elif self._CALL_GRAPH:
                extras = self.search_graph(primary)
            else:
                extras = []
            if extras:
                primary = primary + extras

        return self.expand_bundle(primary) if bundle else primary

    # ── Eval ─────────────────────────────────────────────────

    def eval_question(
        self,
        question: dict,
        k: int,
        src_root: Path | None = None,
        repo_root: Path | None = None,
        enable_reporank: bool | None = None,
    ) -> dict:
        results = self.search(
            question["question"], top_k=k,
            src_root=src_root, repo_root=repo_root,
            enable_reporank=enable_reporank,
        )
        result_files = {r["file"] for r in results}
        expected = question["expected_files"]
        hit = [f for f in expected if f in result_files]
        miss = [f for f in expected if f not in result_files]
        n = len(expected)
        return {
            "passed": len(hit) > 0,
            "hit": hit,
            "miss": miss,
            "hit_n": len(hit),
            "expected_n": n,
            "coverage": len(hit) / n if n else 1.0,
        }

    def _split_stats(
        self,
        questions: list[dict],
        k: int,
        src_root: Path | None = None,
        repo_root: Path | None = None,
        enable_reporank: bool | None = None,
    ) -> list[dict]:
        rows = []
        for q in questions:
            r = self.eval_question(
                q, k, src_root=src_root, repo_root=repo_root,
                enable_reporank=enable_reporank,
            )
            rows.append({"id": q["id"], "split": q.get("split", "tune"),
                         "question": q["question"], **r})
        return rows

    def _aggregate(self, rows: list[dict], split: str | None = None) -> dict:
        subset = [r for r in rows if split is None or r["split"] == split]
        if not subset:
            return {"count": 0, "pass": 0, "mean_coverage": 0.0}
        return {
            "count": len(subset),
            "pass": sum(1 for r in subset if r["passed"]),
            "mean_coverage": sum(r["coverage"] for r in subset) / len(subset),
        }

    def eval_summary(
        self,
        eval_path: Path = EVAL_PATH,
        src_root: Path | None = None,
        repo_root: Path | None = None,
        rg_bin: str | None = None,        # kept for backward compat; ignored
        enable_reporank: bool | None = None,
    ) -> dict:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        questions = data["questions"]
        rows5 = self._split_stats(
            questions, 5, src_root=src_root, repo_root=repo_root,
            enable_reporank=enable_reporank,
        )
        rows10 = self._split_stats(
            questions, 10, src_root=src_root, repo_root=repo_root,
            enable_reporank=enable_reporank,
        )
        by_id10 = {r["id"]: r for r in rows10}

        details = []
        for r5 in rows5:
            r10 = by_id10[r5["id"]]
            details.append({
                "id": r5["id"], "split": r5["split"],
                "ok5": r5["passed"], "ok10": r10["passed"],
                "cov5": r5["coverage"], "cov10": r10["coverage"],
                "hit5_n": r5["hit_n"], "hit10_n": r10["hit_n"],
                "exp_n": r5["expected_n"],
                "hit5": r5["hit"], "miss5": r5["miss"],
            })

        tune5 = self._aggregate(rows5, "tune")
        hold5 = self._aggregate(rows5, "holdout")
        all5 = self._aggregate(rows5)
        return {
            "total": len(questions),
            "pass5": all5["pass"],
            "pass10": sum(1 for r in rows10 if r["passed"]),
            "mean_cov5": all5["mean_coverage"],
            "gate_ok": all5["mean_coverage"] >= EVAL_COV5_GATE,
            "recall5_ok": all5["mean_coverage"] >= EVAL_COV5_GATE,
            "tune": {"pass5": tune5["pass"], "count": tune5["count"],
                     "mean_cov5": tune5["mean_coverage"]},
            "holdout": {"pass5": hold5["pass"], "count": hold5["count"],
                        "mean_cov5": hold5["mean_coverage"]},
            "details": details,
        }

    def run_eval(
        self,
        eval_path: Path = EVAL_PATH,
        src_root: Path | None = None,
        repo_root: Path | None = None,
        enable_reporank: bool | None = None,
    ) -> int:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        questions = data["questions"]
        n_tune = sum(1 for q in questions if q.get("split", "tune") == "tune")
        n_hold = sum(1 for q in questions if q.get("split") == "holdout")
        print(
            f"eval: {eval_path.name} ({len(questions)} questions: "
            f"{n_tune} tune + {n_hold} holdout)\n"
        )
        summary = self.eval_summary(
            eval_path, src_root=src_root, repo_root=repo_root,
            enable_reporank=enable_reporank,
        )
        current_split = None
        for d in summary["details"]:
            sp = d["split"]
            if sp != current_split:
                current_split = sp
                print(f"--- {sp} ---")
            q = next(x for x in questions if x["id"] == d["id"])
            groups = matched_hint_groups(q["question"])
            ghint = ",".join(groups) if groups else "(none)"
            print(
                f"{d['id']} {'PASS' if d['ok5'] else 'FAIL'}@5 / "
                f"{'PASS' if d['ok10'] else 'FAIL'}@10  "
                f"cov@5={_fmt_cov(d['hit5_n'], d['exp_n'], d['cov5'])}  "
                f"cov@10={_fmt_cov(d['hit10_n'], d['exp_n'], d['cov10'])}  "
                f"hints=[{ghint}]"
            )
            print(f"  {q['question']}")
            print(f"  hit@5:  {d['hit5'] or '(none)'}")
            if d["miss5"]:
                print(f"  miss@5: {d['miss5']}")
            print()

        print("=" * 50)
        t, h = summary["tune"], summary["holdout"]
        print(
            f"tune     Recall@5: {t['pass5']}/{t['count']}  "
            f"mean_cov@5: {t['mean_cov5']:.0%}  (report only)"
        )
        print(
            f"holdout  Recall@5: {h['pass5']}/{h['count']}  "
            f"mean_cov@5: {h['mean_cov5']:.0%}  (report only)"
        )
        gate = EVAL_COV5_GATE
        print(
            f"all      Recall@5: {summary['pass5']}/{summary['total']}  "
            f"mean_cov@5: {summary['mean_cov5']:.0%}  "
            f"{'PASS' if summary['gate_ok'] else f'FAIL (need mean cov@5 >= {gate:.0%})'}"
        )
        return 0 if summary["gate_ok"] else 1


def _fmt_cov(hit_n: int, exp_n: int, cov: float) -> str:
    return f"{hit_n}/{exp_n} ({int(round(cov * 100))}%)"
