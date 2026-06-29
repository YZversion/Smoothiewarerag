"""kb_cli/manifest.py — 索引版本清单

每次 kb index build 写入 data/index_manifest.json，
kb index check 读取并验证，kb index stats 展示。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from kb_cli.errors import KBIndexError


@dataclass
class IndexManifest:
    version: str = "1"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    repo_root: str = ""
    git_sha: str = ""          # 可选；构建时如能获取则填写
    file_count: int = 0
    chunk_count: int = 0
    symbol_count: int = 0
    dispatch_count: int = 0
    chunks_file: str = ""
    symbols_file: str = ""

    # ── 持久化 ──────────────────────────────────────────────

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "IndexManifest":
        if not path.is_file():
            raise KBIndexError(f"index_manifest.json 不存在: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    # ── 验证 ──────────────────────────────────────────────

    def validate(self, data_dir: Path) -> list[str]:
        """返回问题列表；空列表表示通过。"""
        problems: list[str] = []
        for fname, count_attr in (
            (self.chunks_file, "chunk_count"),
            (self.symbols_file, "symbol_count"),
        ):
            if not fname:
                continue
            p = data_dir / fname if not Path(fname).is_absolute() else Path(fname)
            if not p.is_file():
                problems.append(f"缺少文件: {p}")
                continue
            if count_attr == "chunk_count":
                actual = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip())
                if actual != self.chunk_count:
                    problems.append(
                        f"chunk_count 不一致: manifest={self.chunk_count}, 实际={actual}"
                    )
        return problems

    def summary(self) -> str:
        return (
            f"version={self.version}  created={self.created_at[:19]}\n"
            f"repo_root={self.repo_root}\n"
            f"files={self.file_count}  chunks={self.chunk_count}  "
            f"symbols={self.symbol_count}  dispatch={self.dispatch_count}"
        )
