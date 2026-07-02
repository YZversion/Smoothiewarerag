"""Revision-gated corpus sync and pin.

Design:
- Prefer SVN in production (TODO: validate inside intranet).
- Support git simulation for local dry-runs.
- Export corpus snapshot into corpus/<rev>/ (no .svn metadata).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = LAB_ROOT / "corpus"
DEFAULT_LOG = LAB_ROOT / "logs" / "sync_history.jsonl"
DEFAULT_MANIFEST = "manifest.json"
DEFAULT_RECON_SUMMARY = LAB_ROOT / "logs" / "corpus_recon_summary.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha16_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


@dataclass
class SyncMeta:
    vcs: str
    revision: str
    source: str


def run_cmd(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def detect_vcs(source: Path, vcs_hint: str) -> str:
    if vcs_hint != "auto":
        return vcs_hint
    if (source / ".git").exists():
        return "git"
    # SVN export target has no .svn; for actual svn source URL/path user should pass --vcs svn
    return "git"


def read_revision(source: Path, vcs: str, svn_url: str | None) -> SyncMeta:
    if vcs == "git":
        rev = run_cmd(["git", "rev-parse", "HEAD"], cwd=source)
        return SyncMeta(vcs="git", revision=rev[:12], source=str(source))

    if vcs == "svn":
        # TODO(intranet): validate with real SVN endpoint and credentials.
        target = svn_url or str(source)
        out = run_cmd(["svn", "info", target])
        revision = ""
        for line in out.splitlines():
            if line.startswith("Revision:"):
                revision = line.split(":", 1)[1].strip()
                break
        if not revision:
            raise RuntimeError("svn info missing Revision")
        return SyncMeta(vcs="svn", revision=f"r{revision}", source=target)

    raise RuntimeError(f"unsupported vcs: {vcs}")


def export_snapshot(meta: SyncMeta, source: Path, out_dir: Path, svn_url: str | None) -> Path:
    snapshot_dir = out_dir / meta.revision
    if snapshot_dir.exists():
        return snapshot_dir
    snapshot_dir.parent.mkdir(parents=True, exist_ok=True)

    if meta.vcs == "git":
        shutil.copytree(
            source,
            snapshot_dir,
            ignore=shutil.ignore_patterns(".git", ".svn", "__pycache__", "*.pyc"),
        )
        return snapshot_dir

    if meta.vcs == "svn":
        # TODO(intranet): run against company svn source once network is available.
        target = svn_url or str(source)
        run_cmd(["svn", "export", "--force", target, str(snapshot_dir)])
        return snapshot_dir

    raise RuntimeError(f"unsupported vcs: {meta.vcs}")


def dir_stats(root: Path) -> tuple[int, int]:
    files = 0
    size = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        files += 1
        size += p.stat().st_size
    return files, size


def load_recon_hash(path: Path) -> str:
    if not path.is_file():
        return "missing"
    data = path.read_bytes()
    return sha16_bytes(data)


def write_manifest(snapshot_dir: Path, meta: SyncMeta, recon_hash: str) -> tuple[Path, dict]:
    files, size = dir_stats(snapshot_dir)
    manifest = {
        "revision": meta.revision,
        "vcs": meta.vcs,
        "source": meta.source,
        "exported_at_utc": now_utc(),
        "source_file_count": files,
        "source_total_size_bytes": size,
        "cloc_summary_hash": recon_hash,
    }
    out = snapshot_dir / DEFAULT_MANIFEST
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, manifest


def latest_record(log_path: Path) -> dict | None:
    if not log_path.is_file():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def append_log(log_path: Path, payload: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Sync corpus snapshot by revision")
    p.add_argument("--source", type=Path, default=LAB_ROOT / "repos" / "Smoothieware")
    p.add_argument("--out", type=Path, default=DEFAULT_CORPUS)
    p.add_argument("--vcs", choices=["auto", "git", "svn"], default="auto")
    p.add_argument("--svn-url", default="", help="SVN URL/path for intranet run")
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p.add_argument("--recon-summary", type=Path, default=DEFAULT_RECON_SUMMARY)
    args = p.parse_args()

    if not args.source.exists() and not args.svn_url:
        raise SystemExit(f"source not found: {args.source}")

    vcs = detect_vcs(args.source, args.vcs)
    meta = read_revision(args.source, vcs, args.svn_url or None)
    target = args.out / meta.revision

    if target.exists():
        print(f"skip: {meta.revision} already exported at {target}")
        return 0

    prev = latest_record(args.log)
    prev_files = int(prev.get("file_count", 0)) if prev else 0

    snapshot = export_snapshot(meta, args.source, args.out, args.svn_url or None)
    recon_hash = load_recon_hash(args.recon_summary)
    manifest_path, manifest = write_manifest(snapshot, meta, recon_hash)
    files, size = manifest["source_file_count"], manifest["source_total_size_bytes"]
    delta = files - prev_files
    record = {
        "revision": meta.revision,
        "vcs": meta.vcs,
        "time_utc": now_utc(),
        "path": str(snapshot),
        "file_count": files,
        "delta_files": delta,
        "total_size_bytes": size,
        "manifest": str(manifest_path),
    }
    append_log(args.log, record)

    print(f"exported: {snapshot}")
    print(f"manifest: {manifest_path}")
    print(f"log append: {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
