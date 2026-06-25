"""
Phase 2.2 — 用 ctags 提取 C++ 符号，输出 symbol_index.json

用法：
    python src/02_extract_symbols.py
    python src/02_extract_symbols.py --repo-root path/to/repo
输出：
    industrial-cpp-kb-lab/data/symbol_index.json
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
LAB_ROOT    = Path(__file__).parent.parent
DEFAULT_REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
DEFAULT_MANIFEST = LAB_ROOT / "data" / "file_manifest.json"
DEFAULT_OUTPUT = LAB_ROOT / "data" / "symbol_index.json"

# ctags 可执行文件：优先 PATH，找不到再找 winget 安装路径
def find_ctags(preferred: str | None = None) -> str:
    if preferred:
        return preferred
    if shutil.which("ctags"):
        return "ctags"
    winget_base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for p in winget_base.glob("UniversalCtags*/**/ctags.exe"):
        return str(p)
    sys.exit("ctags 未找到，请确认已安装 UniversalCtags")

# ── 保留的符号类型 ─────────────────────────────────────────
KEEP_KINDS = {"class", "function", "prototype", "macro", "enum", "struct", "typedef"}

# prototype = 头文件中的函数声明；function = .cpp 中的实现
# 两者都保留，检索时 .cpp 实现优先


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 Universal Ctags 提取 C/C++ 符号")
    parser.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="源码仓库根目录，默认 industrial-cpp-kb-lab/repos/Smoothieware",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="file_manifest.json 路径",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="symbol_index.json 输出路径",
    )
    parser.add_argument(
        "--ctags-bin",
        default=None,
        help="ctags 可执行文件路径；默认从 PATH 或 WinGet 目录查找",
    )
    return parser.parse_args()


def extract_symbols(ctags_bin: str, file_paths: list[str], repo_root: Path, output_dir: Path) -> list[dict]:
    """对给定文件列表调用 ctags，返回符号记录列表。"""
    # 把文件列表写到临时文件，避免命令行过长
    list_file = output_dir / "_ctags_input.txt"
    list_file.parent.mkdir(parents=True, exist_ok=True)
    list_file.write_text("\n".join(file_paths), encoding="utf-8")

    cmd = [
        ctags_bin,
        "--output-format=json",
        "--c++-kinds=+pfscetud",   # prototype/function/struct/class/enum/typedef/union/define
        "--fields=+nKz",           # line number / kind / scope
        "--extras=-F",             # 不输出 file-scope 伪标签
        "-L", str(list_file),      # 从文件列表读取
        "-f", "-",                 # 输出到 stdout
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode not in (0, 1):  # ctags 在无符号时也会返回 0
        print(f"ctags 警告: {result.stderr[:200]}", file=sys.stderr)

    records = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            tag = json.loads(line)
        except json.JSONDecodeError:
            continue
        if tag.get("_type") != "tag":
            continue
        if tag.get("kind") not in KEEP_KINDS:
            continue

        # 路径转相对（相对于 repo_root）
        abs_path = Path(tag["path"]).resolve()
        try:
            rel_path = abs_path.relative_to(repo_root)
        except ValueError:
            rel_path = abs_path

        records.append({
            "name":      tag["name"],
            "kind":      tag["kind"],
            "file":      str(rel_path).replace("\\", "/"),
            "line":      tag.get("line", 0),
            "class":     tag.get("scope", ""),       # 所属 class/namespace
            "scope_kind": tag.get("scopeKind", ""),
        })

    list_file.unlink(missing_ok=True)
    return records


def main():
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest).resolve()
    output = Path(args.output).resolve()

    # 读 file_manifest.json 获取绝对路径列表
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    abs_paths = [str((repo_root / r["path"]).resolve()) for r in manifest]
    print(f"处理 {len(abs_paths)} 个文件...")

    ctags_bin = find_ctags(args.ctags_bin)
    records = extract_symbols(ctags_bin, abs_paths, repo_root, output.parent)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # ── 摘要 ─────────────────────────────────────────────
    kind_counts: dict[str, int] = {}
    for r in records:
        kind_counts[r["kind"]] = kind_counts.get(r["kind"], 0) + 1

    print(f"\n源码仓库：{repo_root}")
    print(f"符号提取完成：共 {len(records)} 条")
    print(f"输出：{output}\n")
    print("按类型分布：")
    for k, cnt in sorted(kind_counts.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} {cnt:>5} 条")


if __name__ == "__main__":
    main()
