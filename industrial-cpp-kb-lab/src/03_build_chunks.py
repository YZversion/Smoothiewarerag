"""
Phase 3.1 — 按符号边界切分源码，输出 chunks.jsonl

切分策略：
  .cpp/.c  → function 实现边界切分 + file_overview
  .h/.hpp  → class/struct 定义切分 + file_overview
  无符号文件 → 固定窗口 100 行 / overlap 20 行
  过长 chunk (>180 行) → 子窗口 180 行 / overlap 40 行

用法：
    python src/03_build_chunks.py
输出：
    industrial-cpp-kb-lab/data/chunks.jsonl
"""

import json
import re
from collections import defaultdict
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
LAB_ROOT      = Path(__file__).parent.parent
REPO_ROOT     = LAB_ROOT / "repos" / "Smoothieware"
MANIFEST_PATH = LAB_ROOT / "data" / "file_manifest.json"
SYMBOLS_PATH  = LAB_ROOT / "data" / "symbol_index.json"
OUTPUT_PATH   = LAB_ROOT / "data" / "chunks.jsonl"

# ── 切分参数 ──────────────────────────────────────────────
MAX_CHUNK_LINES    = 180   # 超过这个长度才拆子窗口
SUBWIN_SIZE        = 180
SUBWIN_OVERLAP     = 40
FALLBACK_WIN_SIZE  = 100
FALLBACK_OVERLAP   = 20
OVERVIEW_HEAD_LINES = 40   # file overview 取文件头部行数

IMPL_EXTS   = {".cpp", ".c"}    # 按 function 切分
HEADER_EXTS = {".h", ".hpp"}    # 按 class/struct 切分

# ── 工具函数 ──────────────────────────────────────────────

def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def find_end_by_brace(lines: list[str], start_1idx: int) -> int:
    """
    极端兜底：从 start_1idx（1-based）做 brace matching。
    忽略字符串/注释/预处理器中的括号——仅当 ctags end 缺失时使用。
    """
    depth = 0
    found_open = False
    for i in range(start_1idx - 1, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
                found_open = True
            elif ch == '}':
                depth -= 1
                if found_open and depth == 0:
                    return i + 1  # 1-based
    return min(start_1idx + 100, len(lines))


def find_end(sym: dict, lines: list[str], next_sym_start: int | None = None) -> int:
    """
    结束行优先级：
      1. ctags end_line（最可靠，由 C++ 语法解析器给出）
      2. brace matching（极端兜底，处理 ctags 漏报的极少数情况）
      3. 下一个同级符号前一行（brace matching 也失败时收尾）
    """
    # 1. ctags end 字段
    end = sym.get("end_line", 0)
    if end and end >= sym["line"]:
        return min(end, len(lines))

    # 2. brace matching
    brace_end = find_end_by_brace(lines, sym["line"])

    # 3. 下一个符号收尾（防止 brace matching 越界吃掉下一个函数）
    if next_sym_start:
        return min(brace_end, next_sym_start - 1)
    return brace_end


def make_context_header(file: str, symbol: str, kind: str,
                        start: int, end: int, cls: str) -> str:
    parts = [
        f"// file: {file}",
        f"// symbol: {symbol}",
        f"// kind: {kind}",
        f"// lines: {start}-{end}",
    ]
    if cls:
        parts.append(f"// class: {cls}")
    return "\n".join(parts)


def make_id(file: str, start: int, end: int) -> str:
    key = re.sub(r"[/\\.]", "_", file)
    return f"{key}::{start}-{end}"


def split_subwindows(lines: list[str], start_1idx: int, end_1idx: int,
                     win: int, overlap: int) -> list[tuple[int, int]]:
    """将 [start_1idx, end_1idx] 切成子窗口，返回 (start, end) 列表（1-based）。"""
    windows = []
    cur = start_1idx
    while cur <= end_1idx:
        w_end = min(cur + win - 1, end_1idx)
        windows.append((cur, w_end))
        if w_end >= end_1idx:
            break
        cur += win - overlap
    return windows


def build_chunk(file: str, lines: list[str],
                start: int, end: int,
                chunk_type: str, symbol: str = "",
                kind: str = "", cls: str = "",
                sub_idx: int | None = None) -> dict:
    header = make_context_header(file, symbol, kind, start, end, cls)
    body   = "\n".join(lines[start - 1: end])
    text   = header + "\n" + body

    sym_label = symbol if not cls else f"{cls}::{symbol}"
    if sub_idx is not None:
        sym_label += f"[{sub_idx}]"

    chunk_id = make_id(file, start, end)
    return {
        "id":         chunk_id,
        "type":       chunk_type,
        "file":       file,
        "start_line": start,
        "end_line":   end,
        "symbol":     symbol,
        "kind":       kind,
        "class":      cls,
        "text":       text,
    }


# ── 各类切分逻辑 ──────────────────────────────────────────

def chunk_impl_file(file: str, lines: list[str],
                    func_syms: list[dict]) -> list[dict]:
    """对 .cpp/.c 按 function 实现切分。"""
    chunks = []
    # 只保留 function（不要 prototype/macro），按行号排序
    funcs = sorted([s for s in func_syms if s["kind"] == "function"],
                   key=lambda s: s["line"])

    for i, sym in enumerate(funcs):
        start = sym["line"]
        next_start = funcs[i + 1]["line"] if i + 1 < len(funcs) else None
        end = find_end(sym, lines, next_start)

        length = end - start + 1
        if length <= MAX_CHUNK_LINES:
            chunks.append(build_chunk(
                file, lines, start, end,
                chunk_type="function",
                symbol=sym["name"], kind="function", cls=sym["class"]
            ))
        else:
            for sub_i, (ws, we) in enumerate(
                    split_subwindows(lines, start, end, SUBWIN_SIZE, SUBWIN_OVERLAP)):
                chunks.append(build_chunk(
                    file, lines, ws, we,
                    chunk_type="function",
                    symbol=sym["name"], kind="function", cls=sym["class"],
                    sub_idx=sub_i
                ))
    return chunks


def chunk_header_file(file: str, lines: list[str],
                      class_syms: list[dict]) -> list[dict]:
    """对 .h/.hpp 按 class/struct 切分。"""
    chunks = []
    classes = sorted([s for s in class_syms if s["kind"] in ("class", "struct")],
                     key=lambda s: s["line"])

    for i, sym in enumerate(classes):
        start = sym["line"]
        next_start = classes[i + 1]["line"] if i + 1 < len(classes) else None
        end = find_end(sym, lines, next_start)

        length = end - start + 1
        if length <= MAX_CHUNK_LINES:
            chunks.append(build_chunk(
                file, lines, start, end,
                chunk_type="class",
                symbol=sym["name"], kind=sym["kind"], cls=sym["class"]
            ))
        else:
            for sub_i, (ws, we) in enumerate(
                    split_subwindows(lines, start, end, SUBWIN_SIZE, SUBWIN_OVERLAP)):
                chunks.append(build_chunk(
                    file, lines, ws, we,
                    chunk_type="class",
                    symbol=sym["name"], kind=sym["kind"], cls=sym["class"],
                    sub_idx=sub_i
                ))
    return chunks


def chunk_fallback(file: str, lines: list[str]) -> list[dict]:
    """无符号文件：固定窗口兜底。"""
    chunks = []
    windows = split_subwindows(lines, 1, len(lines), FALLBACK_WIN_SIZE, FALLBACK_OVERLAP)
    for ws, we in windows:
        chunks.append(build_chunk(
            file, lines, ws, we,
            chunk_type="fallback"
        ))
    return chunks


def make_file_overview(file: str, lines: list[str],
                       file_syms: list[dict], manifest_rec: dict) -> dict:
    """为每个文件生成一个 overview chunk（文件头 + 符号列表）。"""
    head_end = min(OVERVIEW_HEAD_LINES, len(lines))
    head_text = "\n".join(lines[:head_end])

    # 提取 include 行
    includes = [l.strip() for l in lines[:head_end] if l.strip().startswith("#include")]

    # 主要符号摘要（class + function，最多列 30 个）
    sym_summary = []
    for s in sorted(file_syms, key=lambda x: x["line"])[:30]:
        entry = f"  {s['kind']:12} {s['name']}"
        if s["class"]:
            entry += f"  (in {s['class']})"
        entry += f"  line {s['line']}"
        sym_summary.append(entry)

    overview_body = (
        f"// [file overview]\n"
        f"// file:    {file}\n"
        f"// top_dir: {manifest_rec['top_dir']}\n"
        f"// lines:   {manifest_rec['lines']}\n"
        f"//\n"
        f"// includes ({len(includes)}):\n"
        + "".join(f"//   {inc}\n" for inc in includes[:15])
        + f"//\n"
        f"// symbols ({len(file_syms)}):\n"
        + "\n".join(f"//{s}" for s in sym_summary)
        + f"\n//\n// --- file head (lines 1-{head_end}) ---\n"
        + head_text
    )

    return {
        "id":         make_id(file, 1, head_end) + "::overview",
        "type":       "file_overview",
        "file":       file,
        "start_line": 1,
        "end_line":   head_end,
        "symbol":     "",
        "kind":       "file_overview",
        "class":      "",
        "text":       overview_body,
    }


# ── 主流程 ────────────────────────────────────────────────

def main():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(SYMBOLS_PATH, encoding="utf-8") as f:
        symbols = json.load(f)

    # 按文件路径建符号倒排
    sym_by_file: dict[str, list[dict]] = defaultdict(list)
    for s in symbols:
        sym_by_file[s["file"]].append(s)

    manifest_by_path = {r["path"]: r for r in manifest}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    type_counts: dict[str, int] = {}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        for rec in manifest:
            file   = rec["path"]           # e.g. "src/modules/robot/Robot.cpp"
            ext    = Path(file).suffix.lower()
            abs_path = REPO_ROOT / file
            lines  = read_lines(abs_path)
            if not lines:
                continue

            file_syms = sym_by_file.get(file, [])

            # 1. file overview（每个文件都生成）
            ov = make_file_overview(file, lines, file_syms, rec)
            out.write(json.dumps(ov, ensure_ascii=False) + "\n")
            type_counts["file_overview"] = type_counts.get("file_overview", 0) + 1

            # 2. 按文件类型切分内容 chunk
            if ext in IMPL_EXTS and file_syms:
                content_chunks = chunk_impl_file(file, lines, file_syms)
            elif ext in HEADER_EXTS and file_syms:
                content_chunks = chunk_header_file(file, lines, file_syms)
            elif file_syms:
                # 有符号但扩展名不在预设（少见）—— 按 function 切
                content_chunks = chunk_impl_file(file, lines, file_syms)
            else:
                content_chunks = chunk_fallback(file, lines)

            for c in content_chunks:
                out.write(json.dumps(c, ensure_ascii=False) + "\n")
                type_counts[c["type"]] = type_counts.get(c["type"], 0) + 1

            total_chunks += 1 + len(content_chunks)

    print(f"分块完成：共 {total_chunks} 个 chunk")
    print(f"输出：{OUTPUT_PATH}\n")
    print("按类型分布：")
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<16} {cnt:>5} 个")


if __name__ == "__main__":
    main()
