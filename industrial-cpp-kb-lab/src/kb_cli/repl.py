from __future__ import annotations

import shlex

from rich.panel import Panel

from . import actions, render
from .runtime import REPL_HISTORY, index_stats, model_label, search_module

COMMANDS = [
    "/ask",
    "/search",
    "/sources",
    "/symbol",
    "/context",
    "/history",
    "/export",
    "/eval",
    "/demo",
    "/paste",
    "/clear",
    "/help",
    "/quit",
    "/exit",
]

HELP = """[bold]Commands[/]
/ask <question>       ask LLM with retrieved context
/search <query>       search with preview
/sources <query>      search bundle + context panels
/symbol <name>        inspect exact symbol
/history              show session history
/export [file.md]     export last answer/search
/eval                 recall dashboard
/demo                 run eval questions in search-only mode
/paste                multiline question, finish with a single '.'
/quit                 exit

[bold]Hotkeys[/]
F1 help   F2 /search   F3 /ask   F4 /sources   F5 /eval   F8 /export
"""


def _prompt_session():
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.styles import Style
    except ImportError:
        return None

    bindings = KeyBindings()

    def set_text(event, text: str) -> None:
        event.current_buffer.text = text
        event.current_buffer.cursor_position = len(text)

    @bindings.add("f1")
    def _(event) -> None:
        set_text(event, "/help")

    @bindings.add("f2")
    def _(event) -> None:
        set_text(event, "/search ")

    @bindings.add("f3")
    def _(event) -> None:
        set_text(event, "/ask ")

    @bindings.add("f4")
    def _(event) -> None:
        set_text(event, "/sources ")

    @bindings.add("f5")
    def _(event) -> None:
        set_text(event, "/eval")

    @bindings.add("f8")
    def _(event) -> None:
        set_text(event, "/export answer.md")

    style = Style.from_dict({
        "bottom-toolbar": "bg:#1f2937 #d1d5db",
        "prompt": "ansicyan bold",
    })
    REPL_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    return PromptSession(
        history=FileHistory(str(REPL_HISTORY)),
        completer=WordCompleter(COMMANDS, ignore_case=True, match_middle=True),
        key_bindings=bindings,
        bottom_toolbar=_bottom_toolbar,
        style=style,
    )


def _bottom_toolbar() -> str:
    stats = index_stats(search_module())
    return (
        f" F1 help  F2 search  F3 ask  F4 sources  F5 eval  F8 export "
        f"| repo {stats['repo']} | chunks {stats['chunks']} | model {model_label()} "
    )


def _simple_repl(top_k: int) -> None:
    render.console.print(Panel("prompt_toolkit 未安装，使用简易 REPL", border_style="yellow"))
    while True:
        try:
            line = input("kb> ").strip()
        except (EOFError, KeyboardInterrupt):
            render.console.print()
            return
        if not _handle_line(line, top_k):
            return


def _read_paste(session) -> str:
    render.console.print("[cyan]Paste multiline question. End with a single '.' line.[/]")
    lines = []
    while True:
        line = session.prompt("... ")
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _handle_line(line: str, top_k: int, session=None) -> bool:
    if not line:
        return True
    if not line.startswith("/"):
        actions.ask_action(line, top_k=top_k)
        return True

    try:
        parts = shlex.split(line)
    except ValueError as exc:
        render.console.print(f"[red]{exc}[/]")
        return True
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("/quit", "/exit"):
        return False
    if cmd == "/help":
        render.console.print(Panel(HELP, title="Help", border_style="cyan"))
    elif cmd == "/search":
        actions.search_action(" ".join(args), top_k=top_k, preview=True, explain=True)
    elif cmd == "/ask":
        actions.ask_action(" ".join(args), top_k=top_k)
    elif cmd == "/sources":
        actions.sources_action(" ".join(args), top_k=top_k)
    elif cmd == "/symbol":
        actions.inspect_symbol_action(" ".join(args))
    elif cmd == "/history":
        actions.history_action()
    elif cmd == "/export":
        actions.export_action(args[0] if args else "answer.md")
    elif cmd == "/eval":
        actions.eval_action()
    elif cmd == "/demo":
        actions.demo_action(top_k=top_k, search_only=True)
    elif cmd == "/paste":
        if session is None:
            render.console.print("[yellow]/paste 需要 prompt_toolkit REPL[/]")
        else:
            question = _read_paste(session)
            if question:
                actions.ask_action(question, top_k=top_k)
    elif cmd == "/clear":
        render.console.clear()
    else:
        render.console.print(f"[red]未知命令[/] {cmd}  （/help 查看帮助）")
    return True


def run_repl(top_k: int = 8) -> None:
    search_module()
    stats = index_stats()
    render.console.print(
        Panel(
            f"repo: {stats['repo']} | chunks: {stats['chunks']} | "
            f"symbols: {stats['symbols']} | model: {model_label()}\n"
            "F1 help, F2 search, F3 ask, F4 sources, F5 eval, F8 export",
            title="Smoothieware Code KB",
            border_style="cyan",
        )
    )
    session = _prompt_session()
    if session is None:
        _simple_repl(top_k)
        return

    while True:
        try:
            line = session.prompt([("class:prompt", "kb> ")]).strip()
        except (EOFError, KeyboardInterrupt):
            render.console.print()
            return
        if not _handle_line(line, top_k, session=session):
            return

