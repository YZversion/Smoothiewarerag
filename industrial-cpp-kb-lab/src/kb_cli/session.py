from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import DATA_DIR

HISTORY_PATH = DATA_DIR / "session_history.jsonl"
LAST_RESULT_PATH = DATA_DIR / "last_result.json"
LAST_ANSWER_PATH = DATA_DIR / "last_answer.md"


def _hit_summary(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": hit.get("file"),
        "line_start": hit.get("line_start"),
        "line_end": hit.get("line_end"),
        "symbol": hit.get("symbol", ""),
        "class": hit.get("class", ""),
        "type": hit.get("type", ""),
        "source": hit.get("source", ""),
        "score": hit.get("score", 0),
        "bundle_role": hit.get("bundle_role", "primary"),
        "snippet": hit.get("snippet", ""),
        "chunk_id": hit.get("chunk_id", ""),
    }


class SessionStore:
    def __init__(self, path: Path = HISTORY_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        item = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            **record,
        }
        if "hits" in item:
            item["hits"] = [_hit_summary(h) for h in item["hits"]]
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        LAST_RESULT_PATH.write_text(
            json.dumps(item, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if item.get("answer"):
            LAST_ANSWER_PATH.write_text(self._markdown(item), encoding="utf-8")

    def recent(self, limit: int = 12) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows[-limit:]

    def last(self) -> dict[str, Any] | None:
        if not LAST_RESULT_PATH.is_file():
            return None
        return json.loads(LAST_RESULT_PATH.read_text(encoding="utf-8"))

    def export_last(self, output: Path) -> Path:
        item = self.last()
        if not item:
            raise FileNotFoundError("还没有可导出的 session 记录")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(self._markdown(item), encoding="utf-8")
        return output

    def _markdown(self, item: dict[str, Any]) -> str:
        title = item.get("question") or item.get("query") or "(no question)"
        lines = [
            f"# {title}",
            "",
            f"- time: `{item.get('ts', '')}`",
            f"- kind: `{item.get('kind', '')}`",
        ]
        if item.get("model"):
            lines.append(f"- model: `{item['model']}`")
        lines.extend(["", "## Answer", "", item.get("answer") or ""])
        hits = item.get("hits") or []
        if hits:
            lines.extend(["", "## Sources", ""])
            for i, h in enumerate(hits, 1):
                sym = f" `{h.get('symbol')}`" if h.get("symbol") else ""
                score = h.get("score", 0)
                lines.append(
                    f"{i}. `{h.get('file')}:{h.get('line_start')}`{sym}"
                    f" score={score:.1f} source={h.get('source', '')}"
                )
        return "\n".join(lines).rstrip() + "\n"

