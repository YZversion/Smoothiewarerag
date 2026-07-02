"""
Dense retrieval index — FAISS IndexFlatIP + sentence-transformers.

离线索引：chunk 原文 + 文件/类/符号元信息拼接后向量化。
在线检索：query 向量 → Flat 全量相似度 → top-K chunk 分数。

环境变量：
  KB_DENSE_MODEL       模型名（默认 BAAI/bge-m3）
  KB_DENSE_INDEX_DIR   索引目录（默认 data/dense_index）
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

LAB_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_INDEX_DIR = LAB_ROOT / "data" / "dense_index"
CHUNKS_PATH = LAB_ROOT / "data" / "chunks.jsonl"
MANIFEST_NAME = "manifest.json"
INDEX_NAME = "index.faiss"
CHUNK_IDS_NAME = "chunk_ids.json"
REQUIRED_MANIFEST_KEYS = (
    "model",
    "dim",
    "chunk_count",
    "chunks_fingerprint",
    "built_at_utc",
)

# 拼接格式定义（见 notes/dense_experiment.md）
EMBED_TEMPLATE = (
    "file: {file}\n"
    "class: {cls}\n"
    "symbol: {symbol}\n"
    "type: {chunk_type}\n"
    "\n"
    "{text}"
)


def chunks_fingerprint(chunks_path: Path) -> str:
    h = hashlib.sha256()
    with chunks_path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def format_chunk_for_embed(chunk: dict) -> str:
    return EMBED_TEMPLATE.format(
        file=chunk.get("file", ""),
        cls=chunk.get("class") or "",
        symbol=chunk.get("symbol") or "",
        chunk_type=chunk.get("type", ""),
        text=chunk.get("text", ""),
    )


_MODEL_CACHE: dict[str, object] = {}


class DenseIndex:
    def __init__(
        self,
        index_dir: Path = DEFAULT_INDEX_DIR,
        model_name: str | None = None,
    ) -> None:
        self.index_dir = Path(index_dir)
        self.model_name = model_name or os.environ.get("KB_DENSE_MODEL", DEFAULT_MODEL)
        self._model = None
        self._index: faiss.IndexFlatIP | None = None
        self._chunk_ids: list[str] = []
        self._dim = 0
        self._manifest: dict = {}

    def _load_model(self):
        if self._model is not None:
            return
        cached = _MODEL_CACHE.get(self.model_name)
        if cached is not None:
            self._model = cached
            return
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)
        _MODEL_CACHE[self.model_name] = self._model

    def is_stale(self, chunks_path: Path = CHUNKS_PATH) -> bool:
        manifest_path = self.index_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            return True
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return True
        for key in REQUIRED_MANIFEST_KEYS:
            if key not in manifest:
                return True
        return manifest.get("chunks_fingerprint") != chunks_fingerprint(chunks_path)

    def verify_compatibility(self, chunks_path: Path = CHUNKS_PATH) -> tuple[bool, str]:
        manifest_path = self.index_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            return False, f"manifest missing: {manifest_path}"
        if not chunks_path.is_file():
            return False, f"chunks missing: {chunks_path}"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False, "manifest unreadable"
        expected = manifest.get("chunks_fingerprint", "")
        actual = chunks_fingerprint(chunks_path)
        if expected != actual:
            return (
                False,
                f"chunks fingerprint mismatch: index={expected} chunks={actual}",
            )
        return True, "ok"

    def build(self, chunks_path: Path = CHUNKS_PATH) -> dict:
        chunks: list[dict] = []
        for line in chunks_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(json.loads(line))
        texts = [format_chunk_for_embed(c) for c in chunks]
        self._chunk_ids = [c["id"] for c in chunks]

        self._load_model()
        assert self._model is not None
        t0 = time.perf_counter()
        vecs = self._model.encode(
            texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True
        )
        encode_sec = time.perf_counter() - t0
        vecs = np.asarray(vecs, dtype=np.float32)
        self._dim = vecs.shape[1]
        index = faiss.IndexFlatIP(self._dim)
        index.add(vecs)
        self._index = index

        self.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_dir / INDEX_NAME))
        (self.index_dir / CHUNK_IDS_NAME).write_text(
            json.dumps(self._chunk_ids, ensure_ascii=False), encoding="utf-8"
        )
        self._manifest = {
            "model": self.model_name,
            "dim": self._dim,
            "chunk_count": len(chunks),
            "chunks_fingerprint": chunks_fingerprint(chunks_path),
            "chunks_path": str(chunks_path),
            "built_at_utc": utc_now_iso(),
            "index_type": "IndexFlatIP",
            "embed_template": "file/class/symbol/type + text",
            "encode_sec": round(encode_sec, 2),
        }
        (self.index_dir / MANIFEST_NAME).write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self._manifest

    def load(self) -> bool:
        index_path = self.index_dir / INDEX_NAME
        ids_path = self.index_dir / CHUNK_IDS_NAME
        manifest_path = self.index_dir / MANIFEST_NAME
        if not (index_path.is_file() and ids_path.is_file() and manifest_path.is_file()):
            return False
        self._index = faiss.read_index(str(index_path))
        self._chunk_ids = json.loads(ids_path.read_text(encoding="utf-8"))
        self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._dim = int(self._manifest.get("dim", self._index.d))
        self.model_name = self._manifest.get("model", self.model_name)
        return True

    def search(self, query: str, top_k: int = 50) -> tuple[list[tuple[str, float]], float]:
        """Return ([(chunk_id, score)], elapsed_ms). Scores are inner product (cosine)."""
        if self._index is None and not self.load():
            return [], 0.0
        assert self._index is not None
        self._load_model()
        assert self._model is not None
        t0 = time.perf_counter()
        qv = self._model.encode([query], normalize_embeddings=True)
        qv = np.asarray(qv, dtype=np.float32)
        k = min(top_k, len(self._chunk_ids))
        scores, indices = self._index.search(qv, k)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        out: list[tuple[str, float]] = []
        for idx, sc in zip(indices[0], scores[0]):
            if idx < 0:
                continue
            out.append((self._chunk_ids[int(idx)], float(sc)))
        return out, elapsed_ms
