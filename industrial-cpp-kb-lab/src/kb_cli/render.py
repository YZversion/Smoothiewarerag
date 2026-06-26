from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rich import box
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .runtime import repo_file

console = Console()


def badge(text: str, style: str) -> Text:
    return Text(f" {text} ", style=f"bold {style} on grey15")


def source_badges(source: str) -> Text:
    labels = {"symbol": "S", "bm25": "B", "rg": "R", "bundle": "ctx"}
    colors = {"symbol": "cyan", "bm25": "magenta", "rg": "green", "bundle": "yellow"}
    out = Text()
    for part in (source or "unknown").split("+"):
        out.append(labels.get(part, part), style=f"bold {colors.get(part, 'white')}")
        out.append("/")
    if out.plain.endswith("/"):
        out = out[:-1]
    return out


def short_path(file: str, line: int, max_len: int = 42) -> str:
    value = f"{file}:{line}"
    if len(value) <= max_len:
        return value
    return "..." + value[-(max_len - 3):]


def score_bar(score: float, best: float) -> Text:
    style = "bold cyan" if best and score >= best * 0.95 else "cyan"
    return Text(f"{score:.1f}", style=style)


def sources_table(hits: list[dict], compact: bool = False) -> Table:
    table = Table(box=box.SIMPLE_HEAVY, show_lines=False, expand=False)
    table.add_column("#", width=3, justify="right")
    table.add_column("score", width=7, no_wrap=True, justify="right")
    table.add_column("src", width=8 if not compact else 6, no_wrap=True)
    table.add_column("location", width=32 if not compact else 24,
                     overflow="ellipsis", no_wrap=True)
    table.add_column("symbol", width=20 if not compact else 18,
                     overflow="ellipsis", no_wrap=True)
    best = max((float(h.get("score", 0)) for h in hits), default=0)
    for i, h in enumerate(hits, 1):
        symbol = h.get("symbol") or ""
        cls = h.get("class") or ""
        if cls and symbol and not symbol.startswith(f"{cls}::"):
            symbol = f"{cls}::{symbol}"
        table.add_row(
            str(i),
            score_bar(float(h.get("score", 0)), best),
            source_badges(h.get("source", "")),
            short_path(h["file"], h["line_start"], 32 if not compact else 24),
            symbol,
        )
    return table


def rank_explanation(hits: list[dict]) -> Panel:
    lines = []
    for i, h in enumerate(hits, 1):
        role = h.get("bundle_role", "primary")
        lines.append(
            f"[bold]{i:>2}[/]. {h['file']}:{h['line_start']}  "
            f"score={h['score']:.1f}  source={h.get('source', '')}  role={role}"
        )
    return Panel("\n".join(lines), title="Rank Explain", border_style="dim")


def preview_source(hit: dict, context: int = 8) -> RenderableType:
    path = repo_file(hit["file"])
    focus = int(hit.get("line_start") or 1)
    suffix = Path(hit["file"]).suffix.lower()
    lexer = "cpp" if suffix in {".cpp", ".h", ".hpp", ".c", ".cc"} else "text"
    if path.is_file():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, focus - context)
        end = min(len(lines), focus + context)
        code = "\n".join(lines[start - 1:end])
        return Syntax(
            code,
            lexer,
            line_numbers=True,
            start_line=start,
            highlight_lines={focus},
            word_wrap=False,
            theme="monokai",
        )
    return Syntax(hit.get("snippet", ""), lexer, line_numbers=True, theme="monokai")


def render_search_results(
    query: str,
    hits: list[dict],
    *,
    preview: bool = False,
    explain: bool = False,
    show_context: bool = False,
) -> None:
    if not hits:
        console.print(Panel(f"query: {query}", title="No Hits", border_style="yellow"))
        return
    console.print(
        Panel(
            f"[bold]query[/]: {query}\n[bold]hits[/]: {len(hits)}",
            title="Search",
            border_style="cyan",
        )
    )
    console.print(sources_table(hits))
    if preview:
        console.print(
            Panel(
                preview_source(hits[0]),
                title=f"Preview  {hits[0]['file']}:{hits[0]['line_start']}",
                border_style="green",
            )
        )
    if explain:
        console.print(rank_explanation(hits))
    if show_context:
        render_context(hits)


def render_context(hits: list[dict], limit: int = 8) -> None:
    for i, h in enumerate(hits[:limit], 1):
        title = (
            f"[{i}] {h['file']}:{h['line_start']}  "
            f"{h.get('class') or ''}::{h.get('symbol') or ''}"
        )
        console.print(
            Panel(
                Syntax(h.get("snippet", ""), "cpp", line_numbers=True,
                       start_line=int(h.get("chunk_line_start") or h["line_start"]),
                       theme="monokai", word_wrap=True),
                title=title,
                border_style="dim",
            )
        )


def citation_panel(cites: dict | None) -> Panel:
    if not cites:
        return Panel("citation check pending", title="Citation Check", border_style="dim")
    status = "OK" if cites.get("ok") else "WARN"
    style = "green" if cites.get("ok") else "yellow"
    lines = [
        f"valid: {len(cites.get('valid', []))}",
        f"invalid: {len(cites.get('invalid', []))}",
    ]
    if cites.get("invalid"):
        lines.append("invalid refs: " + ", ".join(cites["invalid"][:5]))
    if not cites.get("has_citations"):
        lines.append("no file:line citations found")
    return Panel("\n".join(lines), title=f"Citation Check: {status}", border_style=style)


def answer_layout(
    question: str,
    answer: str,
    hits: list[dict],
    *,
    status: str,
    model: str,
    cites: dict | None = None,
) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="body"),
        Layout(name="footer", size=5),
    )
    layout["body"].split_row(Layout(name="answer", ratio=3), Layout(name="sources", ratio=2))
    layout["header"].update(
        Panel(
            f"[bold]Q[/]: {question}\n[bold]model[/]: {model}   [bold]status[/]: {status}",
            title="Smoothieware Code KB",
            border_style="cyan",
        )
    )
    body: RenderableType = Markdown(answer or "_waiting for tokens..._")
    layout["answer"].update(Panel(body, title="Answer", border_style="green"))
    layout["sources"].update(Panel(sources_table(hits, compact=True), title="Sources",
                                   border_style="magenta"))
    layout["footer"].update(citation_panel(cites))
    return layout


def stream_answer_dashboard(
    question: str,
    hits: list[dict],
    token_iter: Iterable[str],
    *,
    model: str,
) -> str:
    full_text = ""
    with Live(
        answer_layout(question, full_text, hits, status="streaming", model=model),
        console=console,
        refresh_per_second=12,
        screen=False,
    ) as live:
        for token in token_iter:
            if token:
                full_text += token
                live.update(answer_layout(question, full_text, hits,
                                          status="streaming", model=model))
        live.update(answer_layout(question, full_text, hits, status="done", model=model))
    console.print()
    return full_text


def render_history(rows: list[dict]) -> None:
    table = Table(title="Session History", box=box.SIMPLE_HEAVY)
    table.add_column("#", width=3, justify="right")
    table.add_column("time", width=19)
    table.add_column("kind", width=8)
    table.add_column("question / query", overflow="fold")
    for i, row in enumerate(rows, 1):
        table.add_row(str(i), row.get("ts", ""), row.get("kind", ""),
                      row.get("question") or row.get("query") or "")
    console.print(table)


def render_eval(summary: dict) -> None:
    table = Table(title="Recall Dashboard", box=box.SIMPLE_HEAVY)
    table.add_column("split")
    table.add_column("Recall@5", justify="right")
    table.add_column("mean cov@5", justify="right")
    for name in ("tune", "holdout"):
        part = summary[name]
        table.add_row(name, f"{part['pass5']}/{part['count']}",
                      f"{part['mean_cov5']:.0%}")
    status = "PASS" if summary["gate_ok"] else "FAIL"
    table.add_row("all", f"{summary['pass5']}/{summary['total']}",
                  f"{summary['mean_cov5']:.0%} {status}")
    console.print(table)

    fail = [d for d in summary["details"] if not d["ok5"]]
    if fail:
        ftab = Table(title="Failures @5", box=box.SIMPLE)
        ftab.add_column("id", width=8)
        ftab.add_column("cov@5", width=10)
        ftab.add_column("miss")
        for d in fail:
            ftab.add_row(d["id"], f"{d['cov5']:.0%}", ", ".join(d["miss5"]))
        console.print(ftab)


def pipeline_progress(label: str = "Searching...") -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        transient=True,
        console=console,
    )
