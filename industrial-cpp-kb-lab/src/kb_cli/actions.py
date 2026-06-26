from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.panel import Panel

from . import render
from .runtime import answer_module, model_label, search_module
from .session import SessionStore

store = SessionStore()


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
    with render.pipeline_progress() as progress:
        task = progress.add_task("Load index -> BM25 -> symbol fusion -> rg", total=3)
        progress.advance(task)
        hits = search.search(query, top_k=top_k, bundle=bundle)
        progress.advance(task, 2)
    if json_out:
        print(json.dumps({"query": query, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        render.render_search_results(query, hits, preview=preview,
                                     explain=explain, show_context=show_context)
    store.append({"kind": "search", "query": query, "top_k": top_k, "hits": hits})
    return hits


def ask_action(
    question: str,
    *,
    top_k: int = 8,
    json_out: bool = False,
    show_context: bool = False,
    stream: bool = True,
) -> dict | None:
    search = search_module()
    answer = answer_module()
    if json_out or not stream:
        result = answer.answer(question, top_k=top_k, search_mod=search)
        if json_out:
            answer_json(result)
        else:
            render.console.print(Panel(result["answer"], title="Answer",
                                       border_style="green"))
            render.console.print(render.citation_panel(result.get("citations")))
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
            "hits": result["hits"],
        })
        return result

    with render.pipeline_progress() as progress:
        task = progress.add_task("Search -> bundle context -> build prompt", total=3)
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
    render.console.print(render.citation_panel(cites))
    store.append({
        "kind": "ask",
        "question": question,
        "top_k": top_k,
        "answer": text,
        "model": f"{provider} / {model}",
        "citations": cites,
        "hits": hits,
    })
    return {
        "question": question,
        "top_k": top_k,
        "answer": text,
        "provider": provider,
        "model": model,
        "citations": cites,
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

