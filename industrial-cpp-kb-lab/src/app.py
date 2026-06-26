"""
Phase 5 — 知识库一体化 CLI（REPL + Streaming + Rich）

用法：
    python src/app.py                         # 交互 REPL
    python src/app.py "G-code 从哪里进入系统？"  # 一次性 streaming 回答
    python src/app.py --search-only "关键词"
    python src/app.py --demo
    python src/app.py --test
    python src/app.py "问题" --json           # plain JSON（管道用）
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

LAB_ROOT = Path(__file__).parent.parent
console = Console()


def load_module(filename: str):
    path = Path(__file__).parent / filename
    spec = importlib.util.spec_from_file_location(f"_kb_{filename}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def model_label(answer_mod) -> str:
    answer_mod.load_dotenv(answer_mod.ENV_PATH)
    provider = os.environ.get("LLM_PROVIDER", "zhipu").lower().strip()
    model = os.environ.get(
        "LLM_MODEL", answer_mod.DEFAULT_MODEL.get(provider, "glm-4-flash")
    )
    return f"{provider} / {model}"


def render_search_hits(query: str, hits: list[dict]) -> None:
    console.print(f"[bold]query:[/] {query!r}  ({len(hits)} hits)\n")
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", width=3)
    table.add_column("file:line")
    table.add_column("type")
    table.add_column("symbol")
    table.add_column("score", justify="right", width=7)
    table.add_column("snippet")
    for i, h in enumerate(hits, 1):
        snippet = (h.get("snippet") or "").splitlines()
        first = snippet[0][:80] if snippet else ""
        table.add_row(
            str(i),
            f"{h['file']}:{h['line_start']}",
            h.get("type", ""),
            h.get("symbol") or "",
            f"{h['score']:.1f}",
            first,
        )
    console.print(table)


def render_citations_panel(hits: list[dict]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", width=3)
    table.add_column("file:line")
    table.add_column("symbol")
    for i, h in enumerate(hits, 1):
        table.add_row(str(i), f"{h['file']}:{h['line_start']}", h.get("symbol") or "")
    console.print(Panel(table, title="Sources", border_style="dim"))


def stream_tokens(token_iter) -> str:
    full_text = ""
    with Live(Spinner("dots", text="Thinking..."), console=console,
              refresh_per_second=12):
        for token in token_iter:
            if token:
                full_text = token
                break
    with Live(Markdown(full_text), console=console, refresh_per_second=12) as live:
        live.update(Markdown(full_text))
        for token in token_iter:
            if token:
                full_text += token
                live.update(Markdown(full_text))
    console.print()
    return full_text


def render_answer(question: str, top_k: int, search_mod, answer_mod) -> None:
    with Live(Spinner("dots", text="Searching..."), console=console,
              refresh_per_second=12):
        hits = search_mod.search(question, top_k=top_k, bundle=True)

    template = answer_mod.load_prompt_template()
    prompt = answer_mod.build_prompt(template, question, hits)
    provider, api_key, model, base_url = answer_mod.llm_config()
    token_iter = answer_mod.call_llm_stream(prompt, provider, api_key, model, base_url)
    stream_tokens(token_iter)
    render_citations_panel(hits)


def print_answer_json(result: dict) -> None:
    out = {k: v for k, v in result.items() if k != "hits"}
    out["citations"] = [
        {"file": h["file"], "line_start": h["line_start"],
         "symbol": h.get("symbol", ""), "score": h["score"]}
        for h in result["hits"]
    ]
    print(json.dumps(out, ensure_ascii=False, indent=2))


def show_banner(answer_mod) -> None:
    body = (
        "Smoothieware Code KB  |  Ctrl+C 中断回答，/quit 退出\n"
        f"model: {model_label(answer_mod)}"
    )
    console.print(Panel(body, title="Code KB", border_style="cyan"))
    console.print()


def show_help() -> None:
    console.print(
        "[bold]/quit, /exit[/]  退出\n"
        "[bold]/search[/] <词>  仅检索\n"
        "[bold]/demo[/]         依次跑 Q1–Q5（streaming）\n"
        "[bold]/eval[/]         检索 Recall 评估（不调 LLM）\n"
        "[bold]/help[/]         显示本帮助"
    )


def run_repl(search_mod, answer_mod, top_k: int) -> None:
    show_banner(answer_mod)
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not line:
            continue
        cmd = line.lower()
        if cmd in ("/quit", "/exit"):
            sys.exit(0)
        if cmd == "/help":
            show_help()
            continue
        if cmd == "/eval":
            search_mod.run_eval()
            continue
        if cmd == "/demo":
            data = json.loads(answer_mod.EVAL_PATH.read_text(encoding="utf-8"))
            for q in data["questions"]:
                console.rule(q["id"])
                try:
                    render_answer(q["question"], top_k, search_mod, answer_mod)
                except KeyboardInterrupt:
                    console.print("[yellow]已中断[/]")
            continue
        if cmd.startswith("/search "):
            query = line[8:].strip()
            if not query:
                console.print("[red]用法: /search <关键词>[/]")
                continue
            hits = search_mod.search(query, top_k=top_k)
            render_search_hits(query, hits)
            continue
        try:
            render_answer(line, top_k, search_mod, answer_mod)
        except KeyboardInterrupt:
            console.print("[yellow]已中断[/]")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Smoothieware 代码知识库 — REPL + 检索 + 问答")
    p.add_argument("question", nargs="?", help="问题或关键词")
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--search-only", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--test", action="store_true")
    p.add_argument("--json", action="store_true", help="plain JSON（不用 Rich）")
    p.add_argument("--show-context", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.test:
        reg = load_module("run_regression.py")
        sys.exit(reg.main(skip_llm=True))

    search = load_module("03_search.py")
    answer_mod = load_module("04_answer.py")
    search.load_index()

    if args.demo:
        data = json.loads(answer_mod.EVAL_PATH.read_text(encoding="utf-8"))
        for q in data["questions"]:
            if args.search_only:
                hits = search.search(q["question"], top_k=args.top_k)
                if args.json:
                    print(json.dumps({"question": q["question"], "hits": hits},
                                     ensure_ascii=False, indent=2))
                else:
                    console.rule(q["id"])
                    render_search_hits(q["question"], hits)
            elif args.json:
                print_answer_json(answer_mod.answer(q["question"], top_k=args.top_k,
                                                    search_mod=search))
            else:
                console.rule(q["id"])
                try:
                    render_answer(q["question"], args.top_k, search, answer_mod)
                except KeyboardInterrupt:
                    console.print("[yellow]已中断[/]")
        return

    if not args.question:
        run_repl(search, answer_mod, args.top_k)
        return

    if args.search_only:
        hits = search.search(args.question, top_k=args.top_k)
        if args.json:
            print(json.dumps({"question": args.question, "hits": hits},
                             ensure_ascii=False, indent=2))
        else:
            render_search_hits(args.question, hits)
        return

    if args.json:
        print_answer_json(answer_mod.answer(args.question, top_k=args.top_k,
                                            search_mod=search))
        return

    try:
        render_answer(args.question, args.top_k, search, answer_mod)
    except KeyboardInterrupt:
        console.print("[yellow]已中断[/]")


if __name__ == "__main__":
    main()
