"""
Phase 8.3 — 静态抽取 G/M-code 与 handler 的分发索引。

用法：
    python src/05_extract_dispatch_index.py

输出：
    data/dispatch_index.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
DEFAULT_REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
CHUNKS_PATH = LAB_ROOT / "data" / "chunks.jsonl"
OUTPUT_PATH = LAB_ROOT / "data" / "dispatch_index.json"

DIRECT_RE = re.compile(r"gcode->([gm])\s*==\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
VAR_RE = re.compile(r"gcode->([gm])\s*==\s*this->([A-Za-z_]\w*)", re.IGNORECASE)
SWITCH_RE = re.compile(r"switch\s*\(\s*gcode->([gm])\s*\)", re.IGNORECASE)
CASE_RE = re.compile(r"\bcase\s+(\d+(?:\.\d+)?)\s*:")
DEFAULT_RE = re.compile(
    r"this->([A-Za-z_]\w*)\s*=.*?by_default\((\d+(?:\.\d+)?)\)->as_number",
    re.IGNORECASE,
)
LETTER_VALUE_RE = re.compile(
    r"has_letter\(\s*['\"]([GM])['\"]\s*\).*?get_value\(\s*['\"]\1['\"]\s*\)",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抽取 G/M-code dispatch index")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--chunks", default=str(CHUNKS_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    return parser.parse_args()


def load_chunks(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_repo_lines(repo_root: Path, file: str) -> list[str]:
    path = repo_root / file
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def normalize_number(value: str) -> str:
    return value.rstrip("0").rstrip(".") if "." in value else value


def command(letter: str, value: str) -> str:
    return f"{letter.upper()}{normalize_number(value)}"


def handler_symbol(chunk: dict) -> str:
    cls = chunk.get("class") or ""
    sym = chunk.get("symbol") or ""
    return f"{cls}::{sym}" if cls and sym else sym


def variable_defaults(lines: list[str]) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for line in lines:
        for match in DEFAULT_RE.finditer(line):
            defaults[match.group(1)] = normalize_number(match.group(2))
    return defaults


def make_entry(chunk: dict, line_no: int, evidence: str, cmd: str,
               confidence: str) -> dict:
    return {
        "command": cmd,
        "kind": "gcode",
        "handler_file": chunk["file"],
        "handler_symbol": handler_symbol(chunk),
        "target_symbol": handler_symbol(chunk),
        "line": line_no,
        "evidence": evidence.strip(),
        "confidence": confidence,
        "chunk_id": chunk["id"],
    }


def extract_from_chunk(chunk: dict, repo_lines: list[str],
                       defaults: dict[str, str]) -> list[dict]:
    entries: list[dict] = []
    if chunk.get("type") != "function":
        return entries

    start = int(chunk["start_line"])
    end = int(chunk["end_line"])
    body = repo_lines[start - 1:end]
    current_switch: str | None = None

    for offset, line in enumerate(body):
        line_no = start + offset

        switch_match = SWITCH_RE.search(line)
        if switch_match:
            current_switch = switch_match.group(1).upper()

        if current_switch:
            for case in CASE_RE.finditer(line):
                entries.append(make_entry(
                    chunk,
                    line_no,
                    line,
                    command(current_switch, case.group(1)),
                    "switch-case",
                ))

        for match in DIRECT_RE.finditer(line):
            entries.append(make_entry(
                chunk,
                line_no,
                line,
                command(match.group(1), match.group(2)),
                "static-pattern",
            ))

        for match in VAR_RE.finditer(line):
            var_name = match.group(2)
            if var_name not in defaults:
                continue
            entries.append(make_entry(
                chunk,
                line_no,
                line,
                command(match.group(1), defaults[var_name]),
                "config-default",
            ))

        # Generic dynamic dispatch clue: it identifies a handler but not a fixed code.
        if LETTER_VALUE_RE.search(line):
            entries.append(make_entry(
                chunk,
                line_no,
                line,
                "unknown",
                "dynamic-letter-value",
            ))
    return entries


def dedupe(entries: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, int, str]] = set()
    out: list[dict] = []
    for entry in entries:
        key = (
            entry["command"],
            entry["handler_file"],
            int(entry["line"]),
            entry["handler_symbol"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root)
    chunks = load_chunks(Path(args.chunks))

    lines_by_file: dict[str, list[str]] = {}
    defaults_by_file: dict[str, dict[str, str]] = {}
    entries: list[dict] = []

    for chunk in chunks:
        file = chunk["file"]
        if file not in lines_by_file:
            lines_by_file[file] = read_repo_lines(repo_root, file)
            defaults_by_file[file] = variable_defaults(lines_by_file[file])
        if not lines_by_file[file]:
            continue
        entries.extend(extract_from_chunk(
            chunk,
            lines_by_file[file],
            defaults_by_file[file],
        ))

    entries = dedupe(entries)
    entries.sort(key=lambda e: (e["command"], e["handler_file"], e["line"]))

    output = {
        "version": 1,
        "description": "Static G/M-code dispatch index extracted from function chunks.",
        "entries": entries,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    known = [e for e in entries if e["command"] != "unknown"]
    print(f"dispatch_index.json 生成完毕")
    print(f"  entries: {len(entries)}")
    print(f"  fixed commands: {len({e['command'] for e in known})}")
    print(f"  output: {out_path}")


if __name__ == "__main__":
    main()
