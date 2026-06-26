"""
Phase 3.2 — BM25 + symbol + ripgrep 融合检索

用法：
    python src/03_search.py "Planner append_block"
    python src/03_search.py "G-code 从哪里进入" --top-k 10
    python src/03_search.py --eval
输出：
    检索结果（stdout）或 eval 报告（--eval）
"""

import argparse
import json
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

# ── 路径配置 ──────────────────────────────────────────────
LAB_ROOT = Path(__file__).parent.parent
DEFAULT_REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
CHUNKS_PATH = LAB_ROOT / "data" / "chunks.jsonl"
SYMBOLS_PATH = LAB_ROOT / "data" / "symbol_index.json"
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"
SRC_ROOT = DEFAULT_REPO_ROOT / "src"

# 中文问句 → 英文代码种子 token（eval 驱动，仅扩展 query）
QUERY_HINTS: list[tuple[tuple[str, ...], list[str]]] = [
    (("进入", "入口"), [
        "gcode", "GcodeDispatch", "SerialConsole", "Player",
        "on_console_line_received", "ON_CONSOLE_LINE_RECEIVED",
        "on_main_loop", "call_event", "console_line",
    ]),
    (("运动", "变成", "命令"), [
        "Robot", "Planner", "Conveyor", "StepTicker",
        "on_gcode_received", "append_block", "process_move",
        "queue_head_block", "step_tick", "GcodeDispatch",
    ]),
    (("motion", "planner", "stepper"), [
        "Planner", "StepTicker", "StepperMotor", "Robot", "Block", "Conveyor",
    ]),
    (("halt", "stop", "emergency", "error", "停止", "报警"), [
        "halt", "ON_HALT", "KillButton", "immediate_halt", "Endstops", "on_halt",
    ]),
    (("模块", "注册", "通信", "触发"), [
        "Module", "Kernel", "register_for_event", "call_event", "PublicData",
    ]),
]

FLOW_INTENT_KEYS = (
    "进入", "入口", "变成", "命令", "如何", "怎么", "怎样",
    "触发", "注册", "通信",
    "halt", "stop", "emergency", "停止", "报警",
)
ON_HANDLER_ENTRY_BOOST = 5.0
# 几乎每个 Module 都有的钩子；流程题里不应与 on_gcode_received 等抢前排
GENERIC_EVENT_HANDLERS = frozenset({
    "on_main_loop", "on_idle", "on_second_tick", "on_module_loaded",
    "on_enable", "on_get_public_data", "on_set_public_data",
})

# ── 融合权重 ──────────────────────────────────────────────
W_SYMBOL = 100.0
W_RG = 50.0
W_BM25 = 10.0
TYPE_BONUS = {"function": 3.0, "class": 2.0, "file_overview": 1.0, "fallback": 0.0}

DISTINCT_HANDLER_MAX_FREQ = 20

# ── 全局索引（load 后填充）────────────────────────────────
_CHUNKS: list[dict] = []
_CHUNK_BY_ID: dict[str, dict] = {}
_CHUNKS_BY_FILE: dict[str, list[dict]] = defaultdict(list)
_SYMBOL_BY_QUAL: dict[str, list[dict]] = defaultdict(list)
_SYMBOL_BY_NAME: dict[str, list[dict]] = defaultdict(list)
_SYMBOL_NAME_FREQ: dict[str, int] = {}
_BM25: BM25Okapi | None = None
_BM25_CHUNK_IDS: list[str] = []
_RG_BIN: str = ""


def find_rg(preferred: str | None = None) -> str:
    if preferred:
        return preferred
    if shutil.which("rg"):
        return "rg"
    winget_base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for p in winget_base.glob("BurntSushi.ripgrep.*/**/rg.exe"):
        return str(p)
    sys.exit("rg 未找到，请确认已安装 ripgrep")


def expand_query_tokens(query: str, tokens: list[str]) -> list[str]:
    q_lower = query.lower()
    extra: list[str] = []
    seen = set(tokens)
    for keys, hints in QUERY_HINTS:
        if any(k in q_lower or k in query for k in keys):
            for h in hints:
                t = h.lower()
                if t not in seen:
                    seen.add(t)
                    extra.append(t)
    return tokens + extra


def tokenize(text: str) -> list[str]:
    """代码友好分词：保留原词 + snake/camel 拆分 + :: 两侧标识符。"""
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
        parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", word).split()
        for p in parts:
            add(p)
        for p in word.split("_"):
            if p:
                add(p)
    return tokens


def load_chunks(path: Path) -> None:
    global _CHUNKS, _CHUNK_BY_ID, _CHUNKS_BY_FILE
    _CHUNKS = []
    _CHUNK_BY_ID = {}
    _CHUNKS_BY_FILE = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        _CHUNKS.append(c)
        _CHUNK_BY_ID[c["id"]] = c
        _CHUNKS_BY_FILE[c["file"]].append(c)
    for flist in _CHUNKS_BY_FILE.values():
        flist.sort(key=lambda x: (x["start_line"], -(x["end_line"] - x["start_line"])))


def load_symbols(path: Path) -> None:
    global _SYMBOL_BY_QUAL, _SYMBOL_BY_NAME, _SYMBOL_NAME_FREQ
    _SYMBOL_BY_QUAL = defaultdict(list)
    _SYMBOL_BY_NAME = defaultdict(list)
    symbols = json.loads(path.read_text(encoding="utf-8"))
    freq: dict[str, int] = {}
    for s in symbols:
        if s["kind"] not in ("function", "prototype", "class", "struct"):
            continue
        freq[s["name"]] = freq.get(s["name"], 0) + 1
    _SYMBOL_NAME_FREQ = freq
    for s in symbols:
        if s["kind"] not in ("function", "prototype", "class", "struct"):
            continue
        name = s["name"]
        cls = s.get("class") or ""
        _SYMBOL_BY_NAME[name.lower()].append(s)
        if cls:
            _SYMBOL_BY_QUAL[f"{cls}::{name}".lower()].append(s)


def build_bm25() -> None:
    global _BM25, _BM25_CHUNK_IDS
    corpus = []
    _BM25_CHUNK_IDS = []
    for c in _CHUNKS:
        meta = f"{c['file']} {c.get('symbol', '')} {c.get('class', '')} {c['type']}"
        corpus.append(tokenize(c["text"] + " " + meta))
        _BM25_CHUNK_IDS.append(c["id"])
    _BM25 = BM25Okapi(corpus)


def chunk_at_line(file: str, line: int) -> dict | None:
    """取覆盖该行的最具体 chunk（function/class 优先于 overview）。"""
    best = None
    best_key = (-1, 0)
    for c in _CHUNKS_BY_FILE.get(file, []):
        if c["start_line"] <= line <= c["end_line"]:
            pri = {"function": 4, "class": 3, "fallback": 2, "file_overview": 1}.get(c["type"], 0)
            span = c["end_line"] - c["start_line"]
            key = (pri, -span)
            if key > best_key:
                best_key = key
                best = c
    return best


def chunks_for_symbol(sym: dict) -> list[dict]:
    """符号 → 对应 chunk（.cpp function 优先）。"""
    file, name, cls = sym["file"], sym["name"], sym.get("class") or ""
    hits = []
    for c in _CHUNKS_BY_FILE.get(file, []):
        if c.get("symbol") != name:
            continue
        if cls and c.get("class") and c.get("class") != cls:
            continue
        hits.append(c)
    if not hits:
        c = chunk_at_line(file, sym["line"])
        if c:
            hits.append(c)
    type_rank = {"function": 0, "class": 1, "file_overview": 2, "fallback": 3}
    hits.sort(key=lambda c: (type_rank.get(c["type"], 9), c["start_line"]))
    return hits


SNIPPET_DEFAULT_LINES = 10
SNIPPET_EVENT_MARKERS = ("call_event", "THEKERNEL->call_event")
SNIPPET_SCAN_LINES = 40
SNIPPET_EVENT_CAP = 28


def make_snippet(chunk: dict, focus_line: int | None = None) -> str:
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


def flow_intent_query(query: str) -> bool:
    """流程/触发/入口类问句（非「文件在哪」类结构题）。"""
    q_lower = query.lower()
    return any(k in q_lower or k in query for k in FLOW_INTENT_KEYS)


def is_distinct_event_handler(name: str) -> bool:
    """跨模块罕见的 on_* 钩子才加权；on_gcode_received 等虚函数实现不抬。"""
    if name in GENERIC_EVENT_HANDLERS:
        return False
    if not name.startswith("on_"):
        return False
    return _SYMBOL_NAME_FREQ.get(name, 0) <= DISTINCT_HANDLER_MAX_FREQ


def flow_entry_query(query: str) -> bool:
    return any(k in query or k in query.lower() for k in ("进入", "入口"))


def hint_coherent_symbol(sym: dict, tokens: list[str]) -> bool:
    """handler 加权需与 query/hints 中的模块名一致，避免同名钩子跨文件抬分。"""
    stem = Path(sym["file"]).stem.lower()
    cls = (sym.get("class") or "").lower()
    tok_set = set(tokens)
    if stem in tok_set or cls in tok_set:
        return True
    return any(len(t) >= 4 and t in stem for t in tok_set)


def symbol_match_weight(sym: dict, chunk: dict, query: str,
                        tokens: list[str]) -> float:
    """事件驱动架构：流程题里优先与 hints 一致的罕见 on_* 处理函数。"""
    weight = W_SYMBOL * 0.85
    name = sym["name"]
    if hint_coherent_symbol(sym, tokens):
        if (flow_intent_query(query) and is_distinct_event_handler(name)):
            weight = W_SYMBOL
            if chunk["start_line"] == sym["line"]:
                weight += ON_HANDLER_ENTRY_BOOST
        elif flow_entry_query(query) and name == "on_main_loop":
            weight = max(weight, W_SYMBOL * 0.92)
    return weight


def hit_from_chunk(chunk: dict, score: float, source: str,
                   focus_line: int | None = None) -> dict:
    line_start = focus_line if focus_line else chunk["start_line"]
    return {
        "file": chunk["file"],
        "line_start": line_start,
        "chunk_line_start": chunk["start_line"],
        "chunk_line_end": chunk["end_line"],
        "symbol_start": chunk.get("symbol_start", chunk["start_line"]),
        "type": chunk["type"],
        "symbol": chunk.get("symbol") or "",
        "snippet": make_snippet(chunk, focus_line),
        "score": round(score, 2),
        "source": source,
        "chunk_id": chunk["id"],
        "line_end": chunk["end_line"],
    }


def search_symbols(query: str, tokens: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    qual_pat = re.findall(r"[A-Za-z_][\w]*::[A-Za-z_][\w]*", query)
    seen_sym: set[str] = set()

    for qual in qual_pat:
        for sym in _SYMBOL_BY_QUAL.get(qual.lower(), []):
            key = f"{sym['file']}:{sym['name']}:{sym.get('class', '')}"
            if key in seen_sym:
                continue
            seen_sym.add(key)
            for c in chunks_for_symbol(sym):
                scores[c["id"]] = max(scores.get(c["id"], 0), W_SYMBOL)

    for tok in tokens:
        if len(tok) < 3:
            continue
        for sym in _SYMBOL_BY_NAME.get(tok, []):
            key = f"{sym['file']}:{sym['name']}:{sym.get('class', '')}"
            if key in seen_sym:
                continue
            seen_sym.add(key)
            for c in chunks_for_symbol(sym):
                sc = symbol_match_weight(sym, c, query, tokens)
                scores[c["id"]] = max(scores.get(c["id"], 0), sc)

    return scores


def search_bm25(tokens: list[str]) -> dict[str, float]:
    if not tokens or _BM25 is None:
        return {}
    raw = _BM25.get_scores(tokens)
    mx = max(raw) if len(raw) else 0.0
    if mx <= 0:
        return {}
    return {
        _BM25_CHUNK_IDS[i]: (raw[i] / mx) * W_BM25
        for i in range(len(raw)) if raw[i] > 0
    }


def rg_path_to_manifest(path_part: str, repo_root: Path) -> str | None:
    try:
        return str(Path(path_part).resolve().relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return None


def search_rg(tokens: list[str], src_root: Path, repo_root: Path,
              rg_bin: str) -> dict[str, float]:
    if not tokens or not src_root.is_dir():
        return {}
    pats = sorted({t for t in tokens if len(t) >= 3}, key=len, reverse=True)[:8]
    if not pats:
        return {}
    pattern = "|".join(re.escape(p) for p in pats)
    cmd = [
        rg_bin, "-n", "--no-heading", "-i", "--max-count", "40",
        pattern, str(src_root),
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
        path_part, line_no, _ = line.split(":", 2)
        rel = rg_path_to_manifest(path_part, repo_root)
        if not rel:
            continue
        try:
            lineno = int(line_no)
        except ValueError:
            continue
        chunk = chunk_at_line(rel, lineno)
        if chunk:
            scores[chunk["id"]] = max(scores.get(chunk["id"], 0), W_RG)
    return scores


def chunk_score_bonus(chunk: dict) -> float:
    bonus = TYPE_BONUS.get(chunk["type"], 0)
    if chunk["file"].endswith((".cpp", ".c")) and chunk["type"] == "function":
        bonus += 4.0
    elif chunk["file"].endswith((".h", ".hpp")) and chunk["type"] == "class":
        bonus -= 3.0
    sym, cls = chunk.get("symbol") or "", chunk.get("class") or ""
    if sym and sym == cls:
        bonus -= 4.0
    return bonus


def merge_scores(*score_maps: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for sm in score_maps:
        for cid, sc in sm.items():
            merged[cid] = merged.get(cid, 0) + sc
    for cid in merged:
        merged[cid] += chunk_score_bonus(_CHUNK_BY_ID[cid])
    return merged


def diversify(hits: list[dict], top_k: int, per_file: int = 2) -> list[dict]:
    """按分数排序，限制每文件 chunk 数，避免 Top-K 被单文件占满。"""
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


def header_path_for_impl(file: str) -> str | None:
    p = Path(file)
    if p.suffix not in {".cpp", ".c"}:
        return None
    for ext in (".h", ".hpp"):
        candidate = str(p.with_suffix(ext)).replace("\\", "/")
        if candidate in _CHUNKS_BY_FILE:
            return candidate
    return None


def overview_chunk(file: str) -> dict | None:
    for c in _CHUNKS_BY_FILE.get(file, []):
        if c["type"] == "file_overview":
            return c
    return None


def class_chunk(file: str, class_name: str) -> dict | None:
    for c in _CHUNKS_BY_FILE.get(file, []):
        if c["type"] == "class" and c.get("symbol") == class_name:
            return c
    return None


def expand_bundle(primary_hits: list[dict]) -> list[dict]:
    """主命中 + 同文件 overview + 配对 .h class（Phase 3.3）。"""
    seen: set[str] = set()
    bundle: list[dict] = []

    def add(hit: dict, role: str) -> None:
        cid = hit["chunk_id"]
        if cid in seen:
            return
        seen.add(cid)
        entry = dict(hit)
        entry["bundle_role"] = role
        bundle.append(entry)

    for h in primary_hits:
        add(h, "primary")
        chunk = _CHUNK_BY_ID[h["chunk_id"]]
        ov = overview_chunk(chunk["file"])
        if ov:
            add(hit_from_chunk(ov, round(h["score"] * 0.3, 2), "bundle"), "overview")
        hdr_file = header_path_for_impl(chunk["file"])
        cls = chunk.get("class") or ""
        if hdr_file and cls and chunk["type"] == "function":
            hdr = class_chunk(hdr_file, cls)
            if hdr:
                add(hit_from_chunk(hdr, round(h["score"] * 0.5, 2), "bundle"), "header")
    return bundle


def search(query: str, top_k: int = 10, src_root: Path | None = None,
           repo_root: Path | None = None, rg_bin: str | None = None,
           bundle: bool = False) -> list[dict]:
    if not _CHUNKS:
        raise RuntimeError("索引未加载，请先调用 load_index()")
    src = src_root or SRC_ROOT
    repo = repo_root or DEFAULT_REPO_ROOT
    rg = rg_bin or _RG_BIN or find_rg()
    tokens = expand_query_tokens(query, tokenize(query))

    sym_scores = search_symbols(query, tokens)
    bm25_scores = search_bm25(tokens)
    rg_scores = search_rg(tokens, src, repo, rg)
    merged = merge_scores(sym_scores, bm25_scores, rg_scores)

    hits = []
    for cid, score in merged.items():
        chunk = _CHUNK_BY_ID[cid]
        sources = []
        if cid in sym_scores:
            sources.append("symbol")
        if cid in bm25_scores:
            sources.append("bm25")
        if cid in rg_scores:
            sources.append("rg")
        h = hit_from_chunk(chunk, score, "+".join(sources))
        hits.append(h)

    hits.sort(key=lambda x: (-x["score"], x["file"], x["line_start"]))
    primary = diversify(hits, top_k)
    if bundle:
        return expand_bundle(primary)
    return primary


def eval_summary(eval_path: Path = EVAL_PATH) -> dict:
    """返回 Recall 统计，供回归脚本调用。"""
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    questions = data["questions"]
    pass5 = pass10 = 0
    details = []
    for q in questions:
        ok5, hit5, miss5 = eval_recall(q, 5)
        ok10, hit10, miss10 = eval_recall(q, 10)
        if ok5:
            pass5 += 1
        if ok10:
            pass10 += 1
        details.append({
            "id": q["id"], "ok5": ok5, "ok10": ok10,
            "hit5": hit5, "miss5": miss5,
        })
    total = len(questions)
    return {
        "pass5": pass5, "pass10": pass10, "total": total,
        "recall5_ok": pass5 >= 4, "details": details,
    }


def load_index(chunks_path: Path = CHUNKS_PATH, symbols_path: Path = SYMBOLS_PATH,
               rg_bin: str | None = None) -> None:
    global _RG_BIN
    if not chunks_path.is_file():
        sys.exit(f"chunks 不存在: {chunks_path}，请先运行 03_build_chunks.py")
    if not symbols_path.is_file():
        sys.exit(f"symbols 不存在: {symbols_path}，请先运行 02_extract_symbols.py")
    _RG_BIN = rg_bin or find_rg()
    load_chunks(chunks_path)
    load_symbols(symbols_path)
    build_bm25()


def eval_recall(question: dict, k: int) -> tuple[bool, list[str], list[str]]:
    results = search(question["question"], top_k=k)
    result_files = {r["file"] for r in results}
    expected = question["expected_files"]
    hit = [f for f in expected if f in result_files]
    miss = [f for f in expected if f not in result_files]
    passed = len(hit) > 0
    return passed, hit, miss


def run_eval(eval_path: Path = EVAL_PATH) -> int:
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    questions = data["questions"]
    print(f"eval: {eval_path.name} ({len(questions)} questions)\n")

    pass5 = pass10 = 0
    for q in questions:
        ok5, hit5, miss5 = eval_recall(q, 5)
        ok10, hit10, miss10 = eval_recall(q, 10)
        if ok5:
            pass5 += 1
        if ok10:
            pass10 += 1
        mark5 = "PASS" if ok5 else "FAIL"
        mark10 = "PASS" if ok10 else "FAIL"
        print(f"{q['id']} {mark5}@5 / {mark10}@10 — {q['question']}")
        print(f"  hit@5:  {hit5 or '(none)'}")
        print(f"  miss@5: {miss5}")
        if not ok10:
            print(f"  hit@10: {hit10}")
        print()

    total = len(questions)
    print("=" * 50)
    print(f"Recall@5:  {pass5}/{total}  {'PASS' if pass5 >= 4 else 'FAIL (need >= 4)'}")
    print(f"Recall@10: {pass10}/{total}")
    return 0 if pass5 >= 4 else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BM25 + symbol + rg 融合检索")
    p.add_argument("query", nargs="?", help="检索关键词")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--eval", action="store_true", help="运行 eval_questions.json 回归")
    p.add_argument("--json", action="store_true", help="JSON 输出检索结果")
    p.add_argument("--chunks", default=str(CHUNKS_PATH))
    p.add_argument("--symbols", default=str(SYMBOLS_PATH))
    p.add_argument("--eval-file", default=str(EVAL_PATH))
    p.add_argument("--src-root", default=str(SRC_ROOT))
    p.add_argument("--rg-bin", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    load_index(Path(args.chunks), Path(args.symbols), args.rg_bin)

    if args.eval:
        sys.exit(run_eval(Path(args.eval_file)))

    if not args.query:
        print("请提供 query，或使用 --eval", file=sys.stderr)
        sys.exit(1)

    results = search(args.query, top_k=args.top_k, src_root=Path(args.src_root),
                     repo_root=DEFAULT_REPO_ROOT, rg_bin=args.rg_bin)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"query: {args.query!r}  ({len(results)} hits)\n")
    for i, r in enumerate(results, 1):
        sym = f"{r['symbol']} " if r["symbol"] else ""
        print(f"{i:>2}. [{r['score']:>6.1f}] {r['file']}:{r['line_start']} "
              f"({r['type']}) {sym}[{r.get('source', '')}]")
        for ln in r["snippet"].splitlines()[:3]:
            print(f"      {ln[:100]}")
        print()


if __name__ == "__main__":
    main()
