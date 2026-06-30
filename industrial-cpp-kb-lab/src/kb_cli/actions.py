from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.panel import Panel

from . import render
from .runtime import DATA_DIR, LAB_ROOT, SRC_DIR, answer_module, model_label, search_module
from .session import SessionStore

store = SessionStore()

_QUERY_LOG = LAB_ROOT / "logs" / "query.jsonl"
_ERROR_LOG  = LAB_ROOT / "logs" / "error.jsonl"


def _log_query(record: dict) -> None:
    try:
        _QUERY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _QUERY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _log_error(record: dict) -> None:
    try:
        _ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _get_git_sha(repo_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def answer_json(result: dict) -> None:
    out = {k: v for k, v in result.items() if k != "hits"}
    out["context_citations"] = [
        {
            "file": h["file"],
            "line_start": h["line_start"],
            "symbol": h.get("symbol", ""),
            "score": h["score"],
            "source": h.get("source", ""),
        }
        for h in result["hits"]
    ]
    print(json.dumps(out, ensure_ascii=False, indent=2))


def search_action(
    query: str,
    *,
    top_k: int = 8,
    preview: bool = False,
    explain: bool = False,
    show_context: bool = False,
    json_out: bool = False,
    bundle: bool = False,
) -> list[dict]:
    search = search_module()
    t0 = time.monotonic()
    with render.pipeline_progress() as progress:
        task = progress.add_task("Load index -> BM25 -> symbol fusion -> rg", total=3)
        progress.advance(task)
        hits = search.search(query, top_k=top_k, bundle=bundle)
        progress.advance(task, 2)
    latency_ms = int((time.monotonic() - t0) * 1000)
    if json_out:
        print(json.dumps({"query": query, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        render.render_search_results(query, hits, preview=preview,
                                     explain=explain, show_context=show_context)
    store.append({"kind": "search", "query": query, "top_k": top_k, "hits": hits})
    _log_query({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "search",
        "question": query,
        "top_k": top_k,
        "hits_count": len(hits),
        "latency_ms": latency_ms,
        "llm_called": False,
        "citation_ok": None,
    })
    return hits


def _render_plan_panel(query: str, plan_dict: dict) -> None:
    intent = plan_dict.get("intent", "unknown")
    lines = [f"[bold]intent[/]: {intent}"]
    if plan_dict.get("normalized_question"):
        lines.append(f"[bold]question[/]: {plan_dict['normalized_question']}")
    if plan_dict.get("planner_fallback"):
        lines.append(f"[yellow]{plan_dict.get('notes', 'planner fallback')}[/yellow]")
    sq = plan_dict.get("search_queries") or []
    if sq:
        lines.append("[bold]search_queries[/]:")
        lines.extend(f"  · {q}" for q in sq)
    syms = plan_dict.get("symbols") or []
    if syms:
        lines.append("[bold]symbols[/]: " + ", ".join(syms))
    render.console.print(
        Panel("\n".join(lines), title=f"Smart Plan  {query}", border_style="magenta")
    )


def smart_search_action(
    query: str,
    *,
    top_k: int = 8,
    preview: bool = True,
    explain: bool = False,
    show_context: bool = False,
    json_out: bool = False,
) -> tuple[dict, list[dict]]:
    import os

    from query_planner import load_dotenv
    from search.smart_search import smart_search

    search = search_module()
    load_dotenv()
    t0 = time.monotonic()

    if not os.environ.get("LLM_API_KEY", "").strip():
        render.console.print(
            "[yellow]LLM_API_KEY not set — planner unavailable, using plain search[/yellow]"
        )
        hits = search.search(query, top_k=top_k, bundle=False)
        plan_dict = {
            "intent": "unknown",
            "normalized_question": query,
            "search_queries": [query],
            "planner_fallback": True,
            "notes": "LLM_API_KEY not set",
        }
        llm_called = False
    else:
        with render.pipeline_progress() as progress:
            task = progress.add_task("Planner -> multi-search -> merge", total=3)
            progress.advance(task)
            plan, hits = smart_search(search, query, top_k=top_k)
            progress.advance(task, 2)
        plan_dict = plan.to_dict()
        llm_called = not plan.planner_fallback

    latency_ms = int((time.monotonic() - t0) * 1000)
    if json_out:
        print(json.dumps({"query": query, "plan": plan_dict, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        _render_plan_panel(query, plan_dict)
        render.render_search_results(
            query, hits, preview=preview, explain=explain, show_context=show_context
        )

    ask_question = (plan_dict.get("normalized_question") or query).strip()
    if hits and os.environ.get("LLM_API_KEY", "").strip() and not json_out:
        render.console.print(
            "[dim]Smart search complete — generating LLM answer…[/dim]"
        )
        ask_action(ask_question, top_k=top_k, hits=hits, show_context=show_context)

    store.append({"kind": "smart", "query": query, "top_k": top_k, "plan": plan_dict, "hits": hits})
    _log_query({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "smart",
        "question": query,
        "top_k": top_k,
        "hits_count": len(hits),
        "latency_ms": latency_ms,
        "llm_called": llm_called,
        "planner_intent": plan_dict.get("intent"),
        "citation_ok": None,
    })
    return plan_dict, hits


def ask_action(
    question: str,
    *,
    top_k: int = 8,
    hits: list[dict] | None = None,
    json_out: bool = False,
    show_context: bool = False,
    stream: bool = True,
) -> dict | None:
    search = search_module()
    answer = answer_module()
    if hits is not None:
        hits = search.expand_bundle(hits[:top_k]) if hits else []
    if json_out or not stream:
        if hits is not None:
            template = answer.load_prompt_template()
            prompt = answer.build_prompt(template, question, hits)
            provider, api_key, model, base_url = answer.llm_config()
            text = answer.call_llm(prompt, provider, api_key, model, base_url)
            cites = answer.validate_citations(text, hits, search._CHUNK_BY_ID)
            coverage = answer.validate_answer_coverage(text, hits)
            result = {
                "question": question,
                "top_k": top_k,
                "hits": hits,
                "answer": text,
                "provider": provider,
                "model": model,
                "citations": cites,
                "coverage": coverage,
            }
        else:
            result = answer.answer(question, top_k=top_k, search_mod=search)
        if json_out:
            answer_json(result)
        else:
            render.console.print(Panel(result["answer"], title="Answer",
                                       border_style="green"))
            render.console.print(render.citation_panel(result.get("citations")))
            render.console.print(render.coverage_panel(result.get("coverage")))
            render.console.print(render.sources_table(result["hits"]))
            if show_context:
                render.render_context(result["hits"])
        store.append({
            "kind": "ask",
            "question": question,
            "top_k": top_k,
            "answer": result["answer"],
            "model": f"{result['provider']} / {result['model']}",
            "citations": result.get("citations"),
            "coverage": result.get("coverage"),
            "hits": result["hits"],
        })
        _log_query({
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "ask",
            "question": question,
            "top_k": top_k,
            "hits_count": len(result["hits"]),
            "latency_ms": None,
            "llm_called": True,
            "citation_ok": result.get("citations", {}).get("ok"),
        })
        return result

    with render.pipeline_progress() as progress:
        task = progress.add_task("Search -> bundle context -> build prompt", total=3)
        if hits is None:
            hits = search.search(question, top_k=top_k, bundle=True)
        progress.advance(task)
        template = answer.load_prompt_template()
        prompt = answer.build_prompt(template, question, hits)
        progress.advance(task)
        provider, api_key, model, base_url = answer.llm_config()
        progress.advance(task)

    if show_context:
        render.render_context(hits)

    token_iter = answer.call_llm_stream(prompt, provider, api_key, model, base_url)
    text = render.stream_answer_dashboard(
        question,
        hits,
        token_iter,
        model=f"{provider} / {model}",
    )
    cites = answer.validate_citations(text, hits, search._CHUNK_BY_ID)
    coverage = answer.validate_answer_coverage(text, hits)
    render.console.print(render.checks_footer(cites, coverage))
    store.append({
        "kind": "ask",
        "question": question,
        "top_k": top_k,
        "answer": text,
        "model": f"{provider} / {model}",
        "citations": cites,
        "coverage": coverage,
        "hits": hits,
    })
    _log_query({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "ask-stream",
        "question": question,
        "top_k": top_k,
        "hits_count": len(hits),
        "latency_ms": None,
        "llm_called": True,
        "citation_ok": cites.get("ok") if cites else None,
    })
    return {
        "question": question,
        "top_k": top_k,
        "answer": text,
        "provider": provider,
        "model": model,
        "citations": cites,
        "coverage": coverage,
        "hits": hits,
    }


def eval_action(*, live: bool = True) -> int:
    search = search_module()
    if live:
        with render.pipeline_progress() as progress:
            task = progress.add_task("Running Recall@5 / Recall@10", total=1)
            summary = search.eval_summary()
            progress.advance(task)
    else:
        summary = search.eval_summary()
    render.render_eval(summary)
    store.append({"kind": "eval", "query": "eval", "summary": summary})
    return 0 if summary["gate_ok"] else 1


def demo_action(*, top_k: int = 8, search_only: bool = False) -> None:
    answer = answer_module()
    data = json.loads(answer.EVAL_PATH.read_text(encoding="utf-8"))
    for q in data["questions"]:
        render.console.rule(q["id"])
        if search_only:
            search_action(q["question"], top_k=top_k, preview=True)
        else:
            ask_action(q["question"], top_k=top_k)


def sources_action(query: str, *, top_k: int = 8, preview: bool = True) -> None:
    search_action(query, top_k=top_k, preview=preview, explain=True,
                  show_context=True, bundle=True)


def inspect_symbol_action(symbol: str, *, preview: bool = True) -> None:
    search = search_module()
    matches = []
    key = symbol.lower()
    matches.extend(search._SYMBOL_BY_QUAL.get(key, []))
    if not matches:
        matches.extend(search._SYMBOL_BY_NAME.get(key, []))
    if not matches:
        render.console.print(
            Panel(f"未找到精确 symbol: {symbol}\n退回普通 search。", border_style="yellow")
        )
        search_action(symbol, preview=preview, explain=True)
        return
    hits = []
    for sym in matches:
        for chunk in search.chunks_for_symbol(sym):
            hits.append(search.hit_from_chunk(chunk, 100.0, "symbol", sym.get("line")))
    hits.sort(key=lambda h: (h["file"], h["line_start"]))
    render.render_search_results(symbol, hits, preview=preview, explain=True,
                                 show_context=True)
    store.append({"kind": "inspect", "query": symbol, "hits": hits})


def history_action(limit: int = 12) -> None:
    render.render_history(store.recent(limit))


def export_action(output: str | Path = "answer.md") -> Path:
    path = Path(output)
    exported = store.export_last(path)
    render.console.print(f"[green]exported[/] {exported}")
    return exported


def require_question(parts: list[str]) -> str:
    question = " ".join(p for p in parts if p).strip()
    if not question:
        render.console.print("[red]需要提供问题或关键词[/]")
        raise typer_exit()
    return question


def typer_exit() -> SystemExit:
    return SystemExit(2)


# ── Index management actions ───────────────────────────────────────────────

def build_index_action(repo_root: Path, out: Path | None = None, src_root: Path | None = None) -> int:
    from .manifest import IndexManifest

    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        render.console.print(f"[red]repo_root 不存在: {repo_root}[/]")
        return 1

    scan_cmd = [sys.executable, str(SRC_DIR / "01_scan_files.py"), "--repo-root", str(repo_root)]
    if src_root is not None:
        scan_cmd += ["--src-root", str(src_root.resolve())]

    stages = [
        ("01 scan",      scan_cmd),
        ("02 symbols",   [sys.executable, str(SRC_DIR / "02_extract_symbols.py"),
                          "--repo-root", str(repo_root)]),
        ("03 chunks",    [sys.executable, str(SRC_DIR / "03_build_chunks.py"),
                          "--repo-root", str(repo_root)]),
        ("03 callgraph", [sys.executable, str(SRC_DIR / "03_build_callgraph.py")]),
        ("05 dispatch",  [sys.executable, str(SRC_DIR / "05_extract_dispatch_index.py"),
                          "--repo-root", str(repo_root)]),
    ]

    render.console.rule("[bold]kb index build[/]")
    ts_start = datetime.now(timezone.utc)
    for name, cmd in stages:
        render.console.print(f"  [cyan]→[/cyan] {name}…")
        r = subprocess.run(
            cmd, cwd=str(LAB_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            render.console.print(f"  [red]✗ {name} FAILED (exit {r.returncode})[/]")
            if r.stderr:
                render.console.print(r.stderr[-2000:])
            _log_error({
                "ts": ts_start.isoformat(), "stage": name, "file": "",
                "msg": (r.stderr or "")[-500:], "traceback": "",
            })
            return 1
        last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else name
        render.console.print(f"  [green]✓[/green] {last_line}")

    chunks_path   = DATA_DIR / "chunks.jsonl"
    symbols_path  = DATA_DIR / "symbol_index.json"
    dispatch_path = DATA_DIR / "dispatch_index.json"
    file_man_path = DATA_DIR / "file_manifest.json"

    try:
        chunk_count    = sum(1 for ln in chunks_path.read_text(encoding="utf-8").splitlines() if ln.strip())
        symbols        = json.loads(symbols_path.read_text(encoding="utf-8"))
        files          = json.loads(file_man_path.read_text(encoding="utf-8"))
        dispatch_data  = json.loads(dispatch_path.read_text(encoding="utf-8"))
        dispatch_count = len(dispatch_data.get("entries", dispatch_data if isinstance(dispatch_data, list) else []))
    except Exception as exc:
        render.console.print(f"[red]读取索引产物失败: {exc}[/]")
        return 1

    manifest = IndexManifest(
        repo_root      = str(repo_root),
        git_sha        = _get_git_sha(repo_root),
        file_count     = len(files),
        chunk_count    = chunk_count,
        symbol_count   = len(symbols),
        dispatch_count = dispatch_count,
        chunks_file    = str(chunks_path),
        symbols_file   = str(symbols_path),
    )
    manifest_dir  = out.resolve() if out else DATA_DIR
    manifest_path = manifest_dir / "index_manifest.json"
    manifest.save(manifest_path)

    render.console.rule("[bold green]索引构建完成[/]")
    render.console.print(manifest.summary())
    render.console.print(f"[dim]manifest → {manifest_path}[/]")
    return 0


def check_index_action(index: Path) -> int:
    from .manifest import IndexManifest
    from .errors import KBIndexError

    manifest_path = (index / "index_manifest.json") if index.is_dir() else index
    try:
        m = IndexManifest.load(manifest_path)
    except KBIndexError as exc:
        render.console.print(f"[red]✗ {exc}[/]")
        return 1

    problems = m.validate(manifest_path.parent)
    if not problems:
        render.console.print(f"[green]✓ 索引正常[/]\n{m.summary()}")
        return 0

    has_missing = any("缺少文件" in p for p in problems)
    for p in problems:
        style = "red" if "缺少文件" in p else "yellow"
        icon  = "✗" if style == "red" else "⚠"
        render.console.print(f"[{style}]{icon} {p}[/]")
    return 1 if has_missing else 2


def stats_index_action(index: Path) -> None:
    from .manifest import IndexManifest
    from .errors import KBIndexError
    from rich import box as rbox
    from rich.table import Table

    manifest_path = (index / "index_manifest.json") if index.is_dir() else index
    try:
        m = IndexManifest.load(manifest_path)
    except KBIndexError as exc:
        render.console.print(f"[red]{exc}[/]")
        raise SystemExit(1)

    tbl = Table(title="IndexManifest", show_header=False, box=rbox.SIMPLE)
    tbl.add_column("Field", style="bold cyan", min_width=16)
    tbl.add_column("Value")
    for k, v in [
        ("version",        m.version),
        ("created_at",     m.created_at[:19]),
        ("repo_root",      m.repo_root),
        ("git_sha",        m.git_sha or "(unknown)"),
        ("file_count",     str(m.file_count)),
        ("chunk_count",    str(m.chunk_count)),
        ("symbol_count",   str(m.symbol_count)),
        ("dispatch_count", str(m.dispatch_count)),
    ]:
        tbl.add_row(k, v)
    render.console.print(tbl)

    for label, fpath in [("chunks_file", m.chunks_file), ("symbols_file", m.symbols_file)]:
        if fpath:
            p = Path(fpath)
            size = f"{p.stat().st_size // 1024} KB" if p.is_file() else "[red]文件不存在[/]"
            render.console.print(f"  {label}: [dim]{p.name}[/]  ({size})")


def serve_action(index: Path, port: int = 8080) -> int:
    try:
        import fastapi   # noqa: PLC0415
        import uvicorn   # noqa: PLC0415
    except ImportError:
        render.console.print(
            "[red]kb serve 需要额外依赖：[/]\n"
            "  pip install fastapi \"uvicorn[standard]\""
        )
        return 1

    from .manifest import IndexManifest
    from .errors import KBIndexError

    manifest_path = (index / "index_manifest.json") if index.is_dir() else index
    try:
        m = IndexManifest.load(manifest_path)
    except KBIndexError as exc:
        render.console.print(f"[red]{exc}[/]")
        return 1

    search = search_module()
    answer = answer_module()

    fa = fastapi.FastAPI(title="kb serve", version=m.version)

    @fa.get("/health")
    def health():
        return {"status": "ok", "index_version": m.version, "chunk_count": m.chunk_count}

    @fa.post("/ask")
    async def ask_endpoint(request: fastapi.Request):
        body = await request.json()
        question = body.get("question", "")
        top_k    = int(body.get("top_k", 8))
        return answer.answer(question, top_k=top_k, search_mod=search)

    render.console.print(
        f"[green bold]kb serve[/]  http://localhost:{port}\n"
        f"  GET  /health\n"
        f"  POST /ask   {{\"question\": \"…\", \"top_k\": 8}}"
    )
    uvicorn.run(fa, host="0.0.0.0", port=port, log_level="warning")
    return 0


def probe_action(
    repo_root: Path,
    *,
    out: Path | None = None,
    json_out: bool = False,
    json_file: Path | None = None,
    exclude: list[str] | None = None,
) -> int:
    try:
        import kb_probe  # noqa: PLC0415
    except ImportError as exc:
        render.console.print(f"[red]无法加载 kb_probe: {exc}[/]")
        return 1

    try:
        report = kb_probe.probe(repo_root, exclude or [])
    except SystemExit as exc:
        render.console.print(f"[red]{exc}[/]")
        return 1
    except Exception as exc:
        render.console.print(f"[red]probe failed: {exc}[/]")
        return 1

    kb_probe.write_outputs(report, out.resolve() if out else None,
                           json_file.resolve() if json_file else None)
    if json_out:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        kb_probe.render_terminal(report)
        if out:
            render.console.print(f"[green]report ->[/] {out.resolve()}")
        if json_file:
            render.console.print(f"[green]json ->[/] {json_file.resolve()}")
    return 0
