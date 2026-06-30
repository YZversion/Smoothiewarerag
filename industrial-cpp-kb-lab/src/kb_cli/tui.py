from __future__ import annotations

import re
import time
from pathlib import Path
from types import ModuleType

from . import render
from .runtime import REPL_HISTORY, answer_module, read_lines, search_module

# ── helpers ───────────────────────────────────────────────────────────────────

def _short_path(file: str) -> str:
    parts = Path(file).parts
    return "/".join(parts[-2:]) if len(parts) >= 2 else file


def _snippet_lines(hit: dict, context: int = 4) -> list[tuple[int, str, bool]]:
    focus = int(hit.get("line_start") or 1)
    try:
        raw = read_lines(hit["file"])
    except (FileNotFoundError, OSError):
        return []
    start = max(1, focus - context)
    end = min(len(raw), focus + context)
    return [(n, raw[n - 1], n == focus) for n in range(start, end + 1)]


def _read_chunk(hit: dict) -> str:
    try:
        lines = read_lines(hit["file"])
    except FileNotFoundError:
        return f"# file not found: {hit['file']}"
    except OSError as exc:
        return str(exc)
    m = re.search(r"::(\d+)-(\d+)$", hit.get("chunk_id", ""))
    if m:
        start = max(0, int(m.group(1)) - 1)
        end = min(len(lines), int(m.group(2)))
    else:
        focus = int(hit.get("line_start") or 1)
        start = max(0, focus - 5)
        end = min(len(lines), focus + 80)
    return "\n".join(lines[start:end])


def _safe(text: str) -> str:
    return text.expandtabs(4).replace("[", "\\[")


def _format_result_label(idx: int, hit: dict) -> str:
    file_short = _short_path(hit.get("file", ""))
    line = hit.get("line_start", "")
    symbol = hit.get("symbol", "")
    source = hit.get("source", "")
    score = float(hit.get("score", 0))
    sym = f" {_safe(symbol)}" if symbol else ""
    src = f" [{source}]" if source else ""
    return (
        f"{idx:>2}  {_safe(file_short)}:{line}{sym}{src}  {score:.1f}"
    )


# ── help text ─────────────────────────────────────────────────────────────────

_HELP = """\
[bold]Search[/bold]
  [cyan]<query>[/cyan]         search the index
  [cyan]/smart <query>[/cyan] LLM plan + search + answer
  [cyan]/ask <query>[/cyan]    LLM answer  (requires LLM_API_KEY)
  [cyan]/clear[/cyan]  Ctrl+L  clear results
  [cyan]Escape  Ctrl+C[/cyan]  quit

[bold]Results[/bold]
  click            preview code on the right
  double-click     open full-screen code view
  [cyan]1 – 9[/cyan]  (input empty) open code view by number
  [cyan]Enter[/cyan]  (results focused) open selected code view

[bold]Clipboard[/bold]
  [cyan]/copy N[/cyan]         copy result N's file:line

[bold]History[/bold]
  [cyan]↑ / ↓[/cyan]           cycle previous queries
"""

_EMPTY_PREVIEW = """\
[bold]Smoothieware Code KB[/bold]
[dim]rg + BM25 + ctags[/dim]

[dim]Type a query to search[/dim]
[dim]Click a result to preview[/dim]
[dim]Press 1–9 to open code view[/dim]
[dim]/ask <q> for LLM answer[/dim]
[dim]/smart <q> plan + search + LLM answer[/dim]
[dim]/help for commands[/dim]
"""


def _format_plan_preview(plan_dict: dict, ms: float | None = None) -> str:
    lines = [
        "[bold magenta]Smart Search Plan[/bold magenta]",
        f"intent: [cyan]{_safe(str(plan_dict.get('intent', 'unknown')))}[/cyan]",
    ]
    if plan_dict.get("normalized_question"):
        lines.append(f"question: {_safe(str(plan_dict['normalized_question']))}")
    if plan_dict.get("planner_fallback"):
        lines.append(f"[yellow]{_safe(str(plan_dict.get('notes', 'planner fallback')))}[/yellow]")
    sq = plan_dict.get("search_queries") or []
    if sq:
        lines.append("[bold]search_queries[/bold]")
        for q in sq:
            lines.append(f"  · {_safe(str(q))}")
    syms = plan_dict.get("symbols") or []
    if syms:
        lines.append("[bold]symbols[/bold] " + ", ".join(_safe(str(s)) for s in syms))
    if ms is not None:
        lines.append(f"[dim]{ms:.0f} ms[/dim]")
    return "\n".join(lines)


# ── TUI ───────────────────────────────────────────────────────────────────────

def run_tui() -> None:
    try:
        from textual import events
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.screen import ModalScreen
        from textual.widgets import (
            Footer,
            Header,
            Input,
            Label,
            ListItem,
            ListView,
            RichLog,
            Static,
            TextArea,
        )
    except ImportError:
        render.console.print(
            "[yellow]Textual not installed.[/]\n"
            "Run `pip install -r requirements.txt` to enable tui."
        )
        return

    SnippetLines = list[tuple[int, str, bool]]

    # ── code viewer modal ─────────────────────────────────────────────────────

    class CodeViewScreen(ModalScreen):
        BINDINGS = [
            Binding("escape", "dismiss", "Close"),
            Binding("q", "dismiss", "Close"),
        ]
        CSS = """
        CodeViewScreen {
            align: center middle;
        }
        #cv-panel {
            width: 92%;
            height: 88%;
            border: double $primary;
            background: $surface;
        }
        #cv-title {
            height: 2;
            padding: 0 2;
            background: $primary-darken-3;
            color: $text-muted;
        }
        #cv-hint {
            height: 1;
            padding: 0 2;
            background: $primary-darken-3;
            color: $text-disabled;
            text-style: dim;
        }
        TextArea {
            height: 1fr;
        }
        """

        def __init__(self, hit: dict) -> None:
            super().__init__()
            self._hit = hit

        def compose(self) -> ComposeResult:
            file = self._hit.get("file", "")
            line = self._hit.get("line_start", "")
            sym = self._hit.get("symbol", "")
            code = _read_chunk(self._hit)

            with Vertical(id="cv-panel"):
                yield Label(
                    f" {file}:{line}  {sym}",
                    id="cv-title",
                )
                yield Label(
                    " mouse-select + Ctrl+C to copy  │  Ctrl+A select all  │  Escape / q to close",
                    id="cv-hint",
                )
                try:
                    yield TextArea(code, read_only=True, language="cpp", id="cv-code")
                except Exception:
                    yield TextArea(code, read_only=True, id="cv-code")

        def on_mount(self) -> None:
            self.query_one("#cv-code").focus()

    # ── result list item ──────────────────────────────────────────────────────

    class HitListItem(ListItem):
        def __init__(self, idx: int, hit: dict, snippets: SnippetLines) -> None:
            self.idx = idx
            self.hit = hit
            self.snippets = snippets
            super().__init__(Label(_format_result_label(idx, hit)))

        def on_click(self, event: events.Click) -> None:
            app = self.app
            if not isinstance(app, KBCLI):
                return
            if event.chain >= 2:
                app.push_screen(CodeViewScreen(self.hit))
            else:
                app._show_hit_preview(self.hit, self.snippets)

    # ── main app ──────────────────────────────────────────────────────────────

    class KBCLI(App):
        TITLE = "Smoothieware Code KB"
        CSS = """
        Screen {
            background: $background;
        }
        #status-bar {
            height: 1;
            padding: 0 2;
            background: $primary-darken-3;
            color: $text-muted;
        }
        #main {
            height: 1fr;
        }
        #results-panel {
            width: 42%;
            border-right: solid $primary-darken-3;
        }
        #results-header {
            height: 1;
            padding: 0 1;
            background: $surface;
            color: $text-muted;
            text-style: bold;
        }
        ListView {
            height: 1fr;
            background: $background;
            scrollbar-gutter: stable;
        }
        ListView > ListItem {
            padding: 0 1;
        }
        ListView > ListItem.--highlight {
            background: $primary-darken-2;
        }
        #preview-panel {
            width: 58%;
        }
        #preview-header {
            height: 1;
            padding: 0 1;
            background: $surface;
            color: $text-muted;
            text-style: bold;
        }
        #preview {
            height: 1fr;
            padding: 0 1;
            border: none;
            scrollbar-gutter: stable;
        }
        #input-row {
            height: 3;
            border-top: solid $primary-darken-3;
            padding: 0 2;
            align: left middle;
        }
        #prompt {
            width: 2;
            color: $success;
            text-style: bold;
        }
        Input {
            width: 1fr;
            border: none;
            background: transparent;
            padding: 0 1;
            color: $text;
        }
        Input:focus {
            border: none;
        }
        Footer {
            height: 1;
            background: $primary-darken-3;
        }
        """

        BINDINGS = [
            Binding("ctrl+c", "quit", "Quit"),
            Binding("ctrl+l", "clear_log", "Clear"),
            Binding("escape", "quit", "Quit", show=False),
            Binding("enter", "open_selected_code", "Open", show=False),
        ]

        def __init__(self) -> None:
            super().__init__()
            self._mod: ModuleType | None = None
            self._history: list[str] = []
            self._hist_pos: int = -1
            self._last_hits: list[dict] = []
            self._search_gen: int = 0
            self._index_ok: bool = False
            self._suppress_result_preview: bool = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Ready", id="status-bar")
            with Horizontal(id="main"):
                with Vertical(id="results-panel"):
                    yield Static("Results", id="results-header")
                    yield ListView(id="results")
                with Vertical(id="preview-panel"):
                    yield Static("Preview", id="preview-header")
                    yield RichLog(id="preview", highlight=True, markup=True, wrap=True)
            with Horizontal(id="input-row"):
                yield Label("❯", id="prompt")
                yield Input(
                    placeholder="search…  click result  1-9 code view  /ask <q>  /help",
                    id="query",
                )
            yield Footer()

        def on_mount(self) -> None:
            self._load_history()
            self._show_empty_preview()
            self.query_one(Input).focus()
            try:
                self._mod = search_module()
                self._index_ok = True
                self._set_status("[green]✓ index loaded[/green] — type a query to search")
            except Exception as exc:
                self._index_ok = False
                self._set_status(f"[red]✗ index load failed: {exc}[/red]")
                self._show_message_preview(f"[red]✗ index load failed: {exc}[/red]")

        def _set_status(self, text: str) -> None:
            self.query_one("#status-bar", Static).update(text)

        def _show_empty_preview(self) -> None:
            preview = self.query_one("#preview", RichLog)
            preview.clear()
            preview.write(_EMPTY_PREVIEW)

        def _show_message_preview(self, text: str) -> None:
            preview = self.query_one("#preview", RichLog)
            preview.clear()
            preview.write(text)

        def _show_hit_preview(self, hit: dict, snippets: SnippetLines) -> None:
            preview = self.query_one("#preview", RichLog)
            preview.clear()
            file = hit.get("file", "")
            line = hit.get("line_start", "")
            symbol = hit.get("symbol", "")
            source = hit.get("source", "")
            score = float(hit.get("score", 0))

            preview.write(f"[bold cyan]{_safe(file)}[/bold cyan]:[yellow]{line}[/yellow]")
            if symbol:
                preview.write(f"[green]{_safe(symbol)}[/green]")
            if source:
                preview.write(f"[dim]source: {_safe(source)}  score: {score:.1f}[/dim]")
            else:
                preview.write(f"[dim]score: {score:.1f}[/dim]")

            if not snippets:
                preview.write("[dim yellow]  (source file unavailable)[/dim yellow]")
                return

            preview.write("")
            for lineno, text, focused in snippets:
                marker = "[bold green]▶[/bold green]" if focused else " "
                style = "bold white" if focused else "dim"
                preview.write(
                    f"{marker} [dim]{lineno:>4}[/dim] [dim]│[/dim]"
                    f" [{style}]{_safe(text)}[/{style}]"
                )

        def _clear_results(self) -> None:
            self.query_one("#results", ListView).clear()
            self._last_hits = []

        def _populate_results(
            self,
            rendered: list[tuple[dict, SnippetLines]],
            *,
            focus_preview: bool = True,
        ) -> None:
            self._last_hits = [hit for hit, _ in rendered]
            list_view = self.query_one("#results", ListView)
            list_view.clear()
            for i, (hit, snippets) in enumerate(rendered, 1):
                list_view.append(HitListItem(i, hit, snippets))
            if rendered:
                if focus_preview:
                    list_view.index = 0
                    self._show_hit_preview(rendered[0][0], rendered[0][1])
                else:
                    self._suppress_result_preview = True
                    try:
                        list_view.index = 0
                    finally:
                        self._suppress_result_preview = False
            rh = self.query_one("#results-header", Static)
            rh.update(f"Results ({len(rendered)})")

        def _load_history(self) -> None:
            try:
                REPL_HISTORY.parent.mkdir(parents=True, exist_ok=True)
                if not REPL_HISTORY.is_file():
                    return
                self._history = [
                    line
                    for line in REPL_HISTORY.read_text(encoding="utf-8").splitlines()
                    if line
                ]
            except Exception as exc:
                self.notify(f"History unavailable: {exc}", severity="warning", timeout=3)

        def _record_history(self, raw: str) -> None:
            if self._history and self._history[-1] == raw:
                return
            self._history.append(raw)
            try:
                REPL_HISTORY.parent.mkdir(parents=True, exist_ok=True)
                with REPL_HISTORY.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(raw + "\n")
            except Exception as exc:
                self.notify(f"History write failed: {exc}", severity="warning", timeout=3)

        def _set_input_busy(self, busy: bool) -> None:
            self.query_one(Input).disabled = busy

        def _finish_input(self) -> None:
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()

        def _ask_preview_write(self, line: str) -> None:
            self.query_one("#preview", RichLog).write(line)

        def _ask_preview_clear(self) -> None:
            self.query_one("#preview", RichLog).clear()

        def _ask_set_sources(
            self,
            rendered: list[tuple[dict, SnippetLines]],
        ) -> None:
            self._populate_results(rendered, focus_preview=False)
            self.query_one("#results-header", Static).update(f"Sources ({len(rendered)})")

        # ── input ─────────────────────────────────────────────────────────────

        def on_input_submitted(self, event: Input.Submitted) -> None:
            raw = event.value.strip()
            if not raw:
                return
            self._record_history(raw)
            self._hist_pos = -1
            event.input.clear()

            if raw in ("/clear", "/c"):
                self.action_clear_log()
            elif raw in ("/help", "/h", "?"):
                self._show_message_preview(_HELP)
                self._set_status("Help")
            elif raw.startswith("/ask "):
                self._do_ask(raw[5:].strip())
            elif raw.startswith("/smart "):
                self._do_smart_search(raw[7:].strip())
            elif raw.startswith("/copy "):
                self._do_copy_cmd(raw[6:].strip())
            else:
                self._do_search(raw)

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            if self._suppress_result_preview:
                return
            item = event.item
            if isinstance(item, HitListItem):
                self._show_hit_preview(item.hit, item.snippets)

        def on_key(self, event) -> None:
            inp = self.query_one(Input)
            if not inp.has_focus:
                return

            if event.key == "up" and self._history:
                self._hist_pos = min(self._hist_pos + 1, len(self._history) - 1)
                inp.value = self._history[-(self._hist_pos + 1)]
                inp.cursor_position = len(inp.value)
                event.stop()
                return

            if event.key == "down":
                if self._hist_pos > 0:
                    self._hist_pos -= 1
                    inp.value = self._history[-(self._hist_pos + 1)]
                    inp.cursor_position = len(inp.value)
                elif self._hist_pos == 0:
                    self._hist_pos = -1
                    inp.value = ""
                event.stop()
                return

            if (
                not inp.value
                and event.character
                and event.character.isdigit()
                and event.character != "0"
            ):
                n = int(event.character)
                if n <= len(self._last_hits):
                    self.push_screen(CodeViewScreen(self._last_hits[n - 1]))
                    event.stop()

        def action_clear_log(self) -> None:
            self._clear_results()
            self._show_empty_preview()
            self.query_one("#results-header", Static).update("Results")
            self._set_status(
                "[green]✓ index loaded[/green] — ready"
                if self._index_ok
                else "[red]✗ index not loaded[/red]"
            )

        def action_open_selected_code(self) -> None:
            list_view = self.query_one("#results", ListView)
            if list_view.has_focus and list_view.highlighted_child is not None:
                item = list_view.highlighted_child
                if isinstance(item, HitListItem):
                    self.push_screen(CodeViewScreen(item.hit))

        # ── clipboard ─────────────────────────────────────────────────────────

        def _clipboard_write(self, text: str) -> bool:
            try:
                self.copy_to_clipboard(text)
                return True
            except Exception:
                pass
            try:
                import pyperclip
                pyperclip.copy(text)
                return True
            except Exception:
                return False

        def _do_copy_cmd(self, arg: str) -> None:
            try:
                n = int(arg)
            except ValueError:
                self.notify("/copy needs a number, e.g. /copy 2", severity="error", timeout=3)
                return
            if not self._last_hits:
                self.notify("No results to copy", severity="warning", timeout=2)
                return
            if not (1 <= n <= len(self._last_hits)):
                self.notify(
                    f"Result {n} out of range (1–{len(self._last_hits)})",
                    severity="error",
                    timeout=3,
                )
                return
            hit = self._last_hits[n - 1]
            text = f"{hit['file']}:{hit.get('line_start', '')}"
            if self._clipboard_write(text):
                self.notify(f"Copied  {text}", timeout=2)
            else:
                self.notify("Clipboard unavailable — install pyperclip", severity="warning", timeout=3)

        # ── search ────────────────────────────────────────────────────────────

        def _do_search(self, query: str) -> None:
            if not self._mod:
                self._set_status("[red]✗ index not loaded[/red]")
                self._show_message_preview("[red]✗ index not loaded[/red]")
                return

            self._search_gen += 1
            gen = self._search_gen

            self._set_status(f"[cyan]Searching[/cyan]: {_safe(query)}")
            self._show_message_preview("[dim]▸ searching…[/dim]")
            self._set_input_busy(True)
            self.run_worker(
                lambda: self._search_thread(query, gen), thread=True, name="search"
            )

        def _search_thread(self, query: str, gen: int) -> None:
            try:
                t0 = time.perf_counter()
                hits = self._mod.search(query, top_k=10, bundle=False)
                ms = (time.perf_counter() - t0) * 1000
                rendered = [(hit, _snippet_lines(hit)) for hit in hits]
            except Exception as exc:
                self.call_from_thread(self._search_done, gen, None, 0.0, exc)
                return
            self.call_from_thread(self._search_done, gen, rendered, ms, None)

        def _search_done(
            self,
            gen: int,
            hits: list[tuple[dict, SnippetLines]] | None,
            ms: float,
            error: Exception | None,
        ) -> None:
            if gen != self._search_gen:
                return

            try:
                if error is not None:
                    self._clear_results()
                    self._set_status(f"[red]✗ search error: {error}[/red]")
                    self._show_message_preview(f"[red]✗ search error: {error}[/red]")
                    return

                if not hits:
                    self._clear_results()
                    self.query_one("#results-header", Static).update("Results")
                    self._set_status("[dim]No results[/dim]")
                    self._show_message_preview("[dim]no results[/dim]")
                    return

                self._populate_results(hits)
                n = len(hits)
                self._set_status(
                    f"[cyan]{n} result{'s' if n != 1 else ''}[/cyan]"
                    f" · {ms:.0f} ms"
                    f" · click to preview · 1–9 open code view"
                )
            finally:
                if gen == self._search_gen:
                    self._finish_input()

        # ── /smart ───────────────────────────────────────────────────────────

        def _do_smart_search(self, query: str) -> None:
            if not self._mod:
                self._set_status("[red]✗ index not loaded[/red]")
                self._show_message_preview("[red]✗ index not loaded[/red]")
                return

            import os
            from query_planner import load_dotenv

            load_dotenv()
            if not os.environ.get("LLM_API_KEY", "").strip():
                self.notify(
                    "LLM_API_KEY not set — using plain search",
                    severity="warning",
                    timeout=3,
                )
                self._do_search(query)
                return

            self._search_gen += 1
            gen = self._search_gen
            self._set_status(f"[magenta]Smart[/magenta]: {_safe(query)}")
            self._show_message_preview("[dim]▸ planning queries…[/dim]")
            self._set_input_busy(True)
            self.run_worker(
                lambda: self._smart_search_thread(query, gen), thread=True, name="smart"
            )

        def _smart_search_thread(self, query: str, gen: int) -> None:
            from search.smart_search import smart_search

            try:
                t0 = time.perf_counter()
                plan, hits = smart_search(self._mod, query, top_k=10)
                ms = (time.perf_counter() - t0) * 1000
                rendered = [(hit, _snippet_lines(hit)) for hit in hits]
                self.call_from_thread(
                    self._smart_search_done, gen, query, plan.to_dict(), rendered, ms, None
                )
            except Exception as exc:
                self.call_from_thread(
                    self._smart_search_done, gen, query, None, None, 0.0, exc
                )

        def _smart_search_done(
            self,
            gen: int,
            query: str,
            plan_dict: dict | None,
            hits: list[tuple[dict, SnippetLines]] | None,
            ms: float,
            error: Exception | None,
        ) -> None:
            if gen != self._search_gen:
                return

            chain_ask = False
            try:
                if error is not None:
                    self._clear_results()
                    self._set_status(f"[red]✗ smart search error: {error}[/red]")
                    self._show_message_preview(f"[red]✗ smart search error: {error}[/red]")
                    return

                plan_dict = plan_dict or {}
                intent = plan_dict.get("intent", "unknown")
                sq = plan_dict.get("search_queries") or []
                status = f"[magenta]smart/{intent}[/magenta]"
                if plan_dict.get("planner_fallback"):
                    status += " [yellow](fallback)[/yellow]"
                if sq:
                    short = "; ".join(_safe(str(q)) for q in sq[:3])
                    if len(sq) > 3:
                        short += "…"
                    status += f" · {short}"

                if not hits:
                    self._clear_results()
                    self.query_one("#results-header", Static).update("Results")
                    self._set_status(f"{status} · [dim]no results[/dim]")
                    self._show_message_preview(_format_plan_preview(plan_dict, ms))
                    return

                self._populate_results(hits)
                n = len(hits)
                ask_question = (plan_dict.get("normalized_question") or query).strip()
                hit_dicts = [hit for hit, _ in hits]
                chain_ask = True
                self._set_status(
                    f"{status} · {n} result{'s' if n != 1 else ''} · {ms:.0f} ms"
                    f" · answering…"
                )
                self._ask_preview_clear()
                self._ask_preview_write("[dim]▸ generating answer from smart results…[/dim]")
                self.run_worker(
                    lambda: self._ask_thread(ask_question, hit_dicts),
                    thread=True,
                    name="ask",
                )
            finally:
                if gen == self._search_gen and not chain_ask:
                    self._finish_input()

        # ── /ask ─────────────────────────────────────────────────────────────

        def _do_ask(self, query: str) -> None:
            if not self._mod:
                self._set_status("[red]✗ index not loaded[/red]")
                self._show_message_preview("[red]✗ index not loaded[/red]")
                return
            self._set_status(f"[magenta]Asking[/magenta]: {_safe(query)}")
            self._ask_preview_clear()
            self._ask_preview_write("[dim]▸ searching context…[/dim]")
            self._set_input_busy(True)
            self.run_worker(lambda: self._ask_thread(query), thread=True, name="ask")

        def _ask_thread(self, query: str, hits: list[dict] | None = None) -> None:
            def w(line: str) -> None:
                self.call_from_thread(self._ask_preview_write, line)

            keep_results = hits is not None
            source_count = len(hits) if hits else 0

            try:
                answer = answer_module()
                answer.load_dotenv(answer.ENV_PATH)

                import os
                if not os.environ.get("LLM_API_KEY"):
                    self.call_from_thread(self._ask_preview_clear)
                    w("[yellow]LLM_API_KEY not set; use plain search instead.[/yellow]")
                    self.call_from_thread(
                        self._set_status,
                        "[yellow]LLM_API_KEY not set[/yellow] — use plain search",
                    )
                    return

                if hits is None:
                    hits = self._mod.search(query, top_k=8, bundle=True)
                else:
                    hits = self._mod.expand_bundle(hits[:8]) if hits else []

                self.call_from_thread(self._ask_preview_clear)
                w(f"[dim]▸ {len(hits)} chunks · {answer.llm_config()[2]}[/dim]")
                w("")

                template = answer.load_prompt_template()
                prompt = answer.build_prompt(template, query, hits)
                provider, api_key, model, base_url = answer.llm_config()

                line_buf: list[str] = []
                for token in answer.call_llm_stream(prompt, provider, api_key, model, base_url):
                    parts = token.split("\n")
                    for i, part in enumerate(parts):
                        line_buf.append(part)
                        if i < len(parts) - 1:
                            w(_safe("".join(line_buf)))
                            line_buf = []
                if line_buf:
                    w(_safe("".join(line_buf)))

                w("")
                if keep_results:
                    self.call_from_thread(
                        self._set_status,
                        f"[magenta]Answer complete[/magenta]"
                        f" · {source_count} source{'s' if source_count != 1 else ''}"
                        f" · answer in preview · click result for code",
                    )
                else:
                    primaries = [
                        h for h in hits if h.get("bundle_role", "primary") == "primary"
                    ][:9]
                    source_hits = primaries or hits[:9]
                    rendered = [(h, _snippet_lines(h)) for h in source_hits]
                    self.call_from_thread(self._ask_set_sources, rendered)
                    n = len(rendered)
                    self.call_from_thread(
                        self._set_status,
                        f"[magenta]Answer complete[/magenta]"
                        f" · {n} source{'s' if n != 1 else ''}"
                        f" · answer in preview · click result for code",
                    )

            except Exception as exc:
                self.call_from_thread(self._ask_preview_clear)
                w(f"[red]✗ {exc}[/red]")
                self.call_from_thread(self._set_status, f"[red]✗ {exc}[/red]")
            finally:
                self.call_from_thread(self._finish_input)

    KBCLI().run()
