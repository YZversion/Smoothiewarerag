from __future__ import annotations

import sys
from typing import Optional

import typer

from . import actions, repl, tui
from .runtime import configure_console_encoding

configure_console_encoding()

app = typer.Typer(
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
    help="Smoothieware code knowledge-base CLI.",
)

COMMANDS = {
    "ask", "search", "sources", "symbol", "repl", "eval", "demo",
    "history", "export", "tui",
}


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    top_k: int = typer.Option(8, "--top-k", "-k", help="检索返回数量"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    repl.run_repl(top_k=top_k)


@app.command("ask")
def ask(
    question: str = typer.Argument(..., help="要问代码库的问题"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    json_out: bool = typer.Option(False, "--json", help="JSON 输出"),
    show_context: bool = typer.Option(False, "--show-context", help="显示上下文 chunk"),
    no_stream: bool = typer.Option(False, "--no-stream", help="关闭 streaming dashboard"),
) -> None:
    actions.ask_action(question, top_k=top_k, json_out=json_out,
                       show_context=show_context, stream=not no_stream)


@app.command("search")
def search(
    query: str = typer.Argument(..., help="关键词 / 函数 / 模块名"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    preview: bool = typer.Option(True, "--preview/--no-preview",
                                 help="显示 top hit 源码预览"),
    explain: bool = typer.Option(True, "--explain/--no-explain",
                                 help="显示 rank 解释"),
    show_context: bool = typer.Option(False, "--show-context", help="展开 context chunk"),
    json_out: bool = typer.Option(False, "--json", help="JSON 输出"),
) -> None:
    actions.search_action(query, top_k=top_k, preview=preview, explain=explain,
                          show_context=show_context, json_out=json_out)


@app.command("sources")
def sources(
    query: str = typer.Argument(..., help="问题或关键词"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    preview: bool = typer.Option(True, "--preview/--no-preview"),
) -> None:
    actions.sources_action(query, top_k=top_k, preview=preview)


@app.command("symbol")
def symbol(
    name: str = typer.Argument(..., help="例如 Planner::append_block"),
    preview: bool = typer.Option(True, "--preview/--no-preview"),
) -> None:
    actions.inspect_symbol_action(name, preview=preview)


@app.command("repl")
def repl_cmd(top_k: int = typer.Option(8, "--top-k", "-k")) -> None:
    repl.run_repl(top_k=top_k)


@app.command("eval")
def eval_cmd(live: bool = typer.Option(True, "--live/--no-live")) -> None:
    raise typer.Exit(actions.eval_action(live=live))


@app.command("demo")
def demo(
    top_k: int = typer.Option(8, "--top-k", "-k"),
    search_only: bool = typer.Option(True, "--search-only/--ask",
                                     help="默认只跑检索 demo，避免误调 LLM"),
) -> None:
    actions.demo_action(top_k=top_k, search_only=search_only)


@app.command("history")
def history(limit: int = typer.Option(12, "--limit", "-n")) -> None:
    actions.history_action(limit)


@app.command("export")
def export(output: str = typer.Argument("answer.md", help="导出路径")) -> None:
    actions.export_action(output)


@app.command("tui")
def tui_cmd() -> None:
    tui.run_tui()


def _option_consumes_value(arg: str) -> bool:
    return arg in {"--top-k", "-k", "--limit", "-n"}


def _legacy_question(argv: list[str]) -> str | None:
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if _option_consumes_value(arg):
            skip = True
            continue
        if not arg.startswith("-"):
            return arg
    return None


def _without(argv: list[str], *remove: str) -> list[str]:
    return [a for a in argv if a not in remove]


def _rewrite_legacy_args(argv: list[str]) -> list[str] | None:
    if not argv or argv[0] in COMMANDS or argv[0] in {"--help", "-h"}:
        return None
    if "--test" in argv:
        return ["eval"]
    if "--demo" in argv:
        rest = _without(argv, "--demo")
        rest = _without(rest, "--search-only")
        return ["demo", "--search-only", *rest]

    question = _legacy_question(argv)
    if not question:
        return None

    search_only = "--search-only" in argv
    rest = []
    removed_question = False
    for arg in argv:
        if arg == "--search-only":
            continue
        if arg == question and not removed_question:
            removed_question = True
            continue
        rest.append(arg)
    command = "search" if search_only else "ask"
    return [command, question, *rest]


def main() -> None:
    rewritten = _rewrite_legacy_args(sys.argv[1:])
    if rewritten is not None:
        sys.argv = [sys.argv[0], *rewritten]
    app()


if __name__ == "__main__":
    main()
