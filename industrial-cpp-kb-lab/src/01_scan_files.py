"""
Phase 2.1 — 扫描 Smoothieware 源码文件，输出 file_manifest.json

用法：
    python src/01_scan_files.py
    python src/01_scan_files.py --repo-root path/to/repo --src-root path/to/repo/src
输出：
    industrial-cpp-kb-lab/data/file_manifest.json
"""

import argparse
import json
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
LAB_ROOT = Path(__file__).parent.parent
DEFAULT_REPO_ROOT = LAB_ROOT / "repos" / "Smoothieware"
DEFAULT_OUTPUT = LAB_ROOT / "data" / "file_manifest.json"

# ── 过滤规则 ──────────────────────────────────────────────
# 跳过这些目录（相对于 REPO_ROOT）
DEFAULT_SKIP_DIRS = {
    "build",           # 编译产物
    "mbed",            # 第三方 mbed 库
    "mri",             # 第三方 MRI 调试库（预编译 .ar）
    "FirmwareBin",     # 固件二进制
    "bootloader",      # 独立 bootloader 固件
    "testframework",   # 单元测试框架
    "LPC17xx",         # src/libs/LPC17xx 硬件寄存器定义（第三方）
    "ChaNFS",          # src/libs/ChaNFS FatFs 第三方库
    "USBDevice",       # src/libs/USBDevice 第三方 USB 栈
    "Network",         # src/libs/Network 第三方网络栈
    "ADC",             # src/libs/ADC 第三方 ADC 库
}

# 只收集这些扩展名
SOURCE_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描 C/C++ 源码文件并生成 file_manifest.json")
    parser.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="源码仓库根目录，默认 industrial-cpp-kb-lab/repos/Smoothieware",
    )
    parser.add_argument(
        "--src-root",
        default=None,
        help="实际扫描的源码目录；默认使用 <repo-root>/src",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="file_manifest.json 输出路径",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="额外跳过的目录名，可重复传入，也可用逗号分隔",
    )
    return parser.parse_args()


def split_excludes(values: list[str]) -> set[str]:
    extra: set[str] = set()
    for value in values:
        extra.update(part.strip() for part in value.split(",") if part.strip())
    return extra


def should_skip(path: Path, skip_dirs: set[str]) -> bool:
    """如果路径的任意父目录名在 SKIP_DIRS 中，则跳过。"""
    return any(part in skip_dirs for part in path.parts)


def count_lines(path: Path) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def top_dir(path: Path, src_root: Path) -> str:
    """返回相对于 SRC_ROOT 的一级目录名，根文件返回 '.'。"""
    try:
        rel = path.relative_to(src_root)
        return rel.parts[0] if len(rel.parts) > 1 else "."
    except ValueError:
        return "."


def scan(repo_root: Path, src_root: Path, skip_dirs: set[str]) -> list[dict]:
    records = []
    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in SOURCE_EXTS:
            continue
        rel = path.relative_to(repo_root)
        if should_skip(rel, skip_dirs):
            continue

        records.append({
            "path":      str(rel).replace("\\", "/"),
            "size_bytes": path.stat().st_size,
            "lines":     count_lines(path),
            "top_dir":   top_dir(path, src_root),
        })
    return records


def main():
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    src_root = Path(args.src_root).resolve() if args.src_root else repo_root / "src"
    output = Path(args.output).resolve()
    skip_dirs = DEFAULT_SKIP_DIRS | split_excludes(args.exclude)

    output.parent.mkdir(parents=True, exist_ok=True)

    records = scan(repo_root, src_root, skip_dirs)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # ── 摘要 ─────────────────────────────────────────────
    total_lines = sum(r["lines"] for r in records)
    by_dir: dict[str, int] = {}
    for r in records:
        by_dir[r["top_dir"]] = by_dir.get(r["top_dir"], 0) + 1

    print(f"源码根目录：{src_root}")
    print(f"扫描完成：{len(records)} 个文件，共 {total_lines:,} 行")
    print(f"输出：{output}\n")
    print("按一级目录分布：")
    for d, cnt in sorted(by_dir.items(), key=lambda x: -x[1]):
        print(f"  {d:<20} {cnt:>4} 个文件")


if __name__ == "__main__":
    main()
