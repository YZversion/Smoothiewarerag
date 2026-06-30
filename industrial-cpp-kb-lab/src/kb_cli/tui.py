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


# ── help text ─────────────────────────────────────────────────────────────────

_HELP = """\
[bold]Search[/bold]
  [cyan]<query>[/cyan]         search the index
  [cyan]/ask <query>[/cyan]    LLM answer  (requires LLM_API_KEY)
  [cyan]/clear[/cyan]  Ctrl+L  clear the screen
  [cyan]Escape  Ctrl+C[/cyan]  quit

[bold]Copy code[/bold]
  [cyan]1 – 9[/cyan]  (input empty) open result in full-screen code view
             mouse-select any text, then [bold]Ctrl+C[/bold] to copy
             [bold]Escape / q[/bold] to close code view

[bold]Quick clipboard[/bold]
  [cyan]/copy N[/cyan]         copy result N's file:line to clipboard

[bold]History[/bold]
  [cyan]↑ / ↓[/cyan]           cycle previous queries
"""


# ── TUI ───────────────────────────────────────────────────────────────────────

def run_tui() -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.screen import ModalScreen
        from textual.widgets import Footer, Input, Label, RichLog, TextArea
    except ImportError:
        render.console.print(
            "[yellow]Textual not installed.[/]\n"
            "Run `pip install -r requirements.txt` to enable tui."
        )
        return

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
            sym  = self._hit.get("symbol", "")
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

    # ── main app ──────────────────────────────────────────────────────────────

    class KBCLI(App):
        CSS = """
        Screen {
            background: $background;
        }
        RichLog {
            height: 1fr;
            padding: 1 3;
            border: none;
            scrollbar-gutter: stable;
            scrollbar-color: $primary-darken-3 $background;
        }
        #input-row {
            height: 3;
            border-top: solid $primary-darken-3;
            padding: 0 3;
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
        ]

        def __init__(self) -> None:
            super().__init__()
            self._mod: ModuleType | None = None
            self._history: list[str] = []
            self._hist_pos: int = -1
            self._last_hits: list[dict] = []
            self._search_gen: int = 0

        def compose(self) -> ComposeResult:
            yield RichLog(id="log", highlight=True, markup=True, wrap=True)
            with Horizontal(id="input-row"):
                yield Label("❯", id="prompt")
                yield Input(
                    placeholder="search…   1-9 open code view   /ask <q>   /help   Escape quit",
                    id="query",
                )
            yield Footer()

        def on_mount(self) -> None:
            log = self.query_one(RichLog)
            log.write(
                "[bold]Smoothieware Code KB[/bold]  "
                "[dim]rg + BM25 + ctags · /help for commands[/dim]\n"
            )
            self._load_history()
            self.query_one(Input).focus()
            try:
                self._mod = search_module()
                log.write("[dim green]✓ index loaded[/dim green]\n")
            except Exception as exc:
                log.write(f"[red]✗ index load failed: {exc}[/red]\n")

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
                self.query_one(RichLog).write(
                    f"[dim]⚠ history unavailable: {exc}[/dim]\n"
                )

        def _record_history(self, raw: str) -> None:
            if self._history and self._history[-1] == raw:
                return
            self._history.append(raw)
            try:
                REPL_HISTORY.parent.mkdir(parents=True, exist_ok=True)
                with REPL_HISTORY.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(raw + "\n")
            except Exception as exc:
                self.query_one(RichLog).write(
                    f"[dim]⚠ history write failed: {exc}[/dim]\n"
                )

        def _set_input_busy(self, busy: bool) -> None:
            self.query_one(Input).disabled = busy

        def _finish_input(self) -> None:
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()

        def _set_last_hits(self, hits: list[dict]) -> None:
            self._last_hits = hits

        def _ask_log_write(self, line: str) -> None:
            self.query_one(RichLog).write(line)

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
                self.query_one(RichLog).write(_HELP)
            elif raw.startswith("/ask "):
                self._do_ask(raw[5:].strip())
            elif raw.startswith("/copy "):
                self._do_copy_cmd(raw[6:].strip())
            else:
                self._do_search(raw)

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

            # digit 1-9 (empty input) → open code view
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
            self.query_one(RichLog).clear()

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
            log = self.query_one(RichLog)
            try:
                n = int(arg)
            except ValueError:
                log.write("[red]✗ /copy needs a number, e.g. /copy 2[/red]\n")
                return
            if not self._last_hits:
                log.write("[dim]  no results to copy[/dim]\n")
                return
            if not (1 <= n <= len(self._last_hits)):
                log.write(f"[red]✗ result {n} out of range (1–{len(self._last_hits)})[/red]\n")
                return
            hit = self._last_hits[n - 1]
            text = f"{hit['file']}:{hit.get('line_start', '')}"
            if self._clipboard_write(text):
                self.notify(f"Copied  {text}", timeout=2)
            else:
                self.notify("Clipboard unavailable — install pyperclip", severity="warning", timeout=3)

        # ── search ────────────────────────────────────────────────────────────

        def _do_search(self, query: str) -> None:
            log = self.query_one(RichLog)
            if not self._mod:
                log.write("[red]✗ index not loaded[/red]\n")
                return

            self._search_gen += 1
            gen = self._search_gen

            log.write(f"\n[bold cyan]> {_safe(query)}[/bold cyan]")
            log.write("[dim]  ▸ searching…[/dim]")
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
            hits: list[tuple[dict, list[tuple[int, str, bool]]]] | None,
            ms: float,
            error: Exception | None,
        ) -> None:
            if gen != self._search_gen:
                return

            log = self.query_one(RichLog)
            try:
                if error is not None:
                    log.write(f"[red]✗ search error: {error}[/red]\n")
                    return

                if not hits:
                    self._last_hits = []
                    log.write("[dim]  no results[/dim]\n")
                    return

                self._last_hits = [hit for hit, _ in hits]
                for i, (hit, snippets) in enumerate(hits, 1):
                    self._render_hit(log, i, hit, snippets)

                log.write(
                    f"\n[dim]── {len(hits)} result{'s' if len(hits) != 1 else ''}"
                    f" · {ms:.0f} ms"
                    f"  ·  press [bold]1–9[/bold] to open code view ──[/dim]\n"
                )
            finally:
                if gen == self._search_gen:
                    self._finish_input()

        def _render_hit(
            self,
            log,
            idx: int,
            hit: dict,
            snippets: list[tuple[int, str, bool]],
        ) -> None:
            file_short = _short_path(hit.get("file", ""))
            line   = hit.get("line_start", "")
            symbol = hit.get("symbol", "")
            source = hit.get("source", "")
            score  = float(hit.get("score", 0))

            src_tag  = f" [dim]\\[{source}][/dim]" if source else ""
            sym_part = f"  [green]{_safe(symbol)}[/green]" if symbol else ""

            log.write(
                f"\n [dim]{idx:>2}[/dim]  "
                f"[cyan]{_safe(file_short)}[/cyan]:[yellow]{line}[/yellow]"
                f"{sym_part}{src_tag}  [dim]{score:.1f}[/dim]"
            )

            full = hit.get("file", "")
            if full and full != file_short:
                log.write(f"      [dim]{_safe(full)}[/dim]")

            for lineno, text, focused in snippets:
                marker = "[bold green]▶[/bold green]" if focused else " "
                style  = "bold white" if focused else "dim"
                log.write(
                    f"      {marker} [dim]{lineno:>4}[/dim] [dim]│[/dim]"
                    f" [{style}]{_safe(text)}[/{style}]"
                )

        # ── /ask ─────────────────────────────────────────────────────────────

        def _do_ask(self, query: str) -> None:
            log = self.query_one(RichLog)
            if not self._mod:
                log.write("[red]✗ index not loaded[/red]\n")
                return
            log.write(f"\n[bold magenta]? {_safe(query)}[/bold magenta]")
            log.write("[dim]  ▸ searching context…[/dim]")
            self._set_input_busy(True)
            self.run_worker(lambda: self._ask_thread(query), thread=True, name="ask")

        def _ask_thread(self, query: str) -> None:
            """Background thread: buffers tokens into lines before writing."""

            def w(line: str) -> None:
                self.call_from_thread(self._ask_log_write, line)

            try:
                answer = answer_module()
                answer.load_dotenv(answer.ENV_PATH)

                import os
                if not os.environ.get("LLM_API_KEY"):
                    w("[yellow]  LLM_API_KEY not set; use plain search instead.[/yellow]")
                    return

                hits = self._mod.search(query, top_k=8, bundle=True)
                w(f"[dim]  ▸ {len(hits)} chunks · building prompt…[/dim]")

                template = answer.load_prompt_template()
                prompt = answer.build_prompt(template, query, hits)
                provider, api_key, model, base_url = answer.llm_config()
                w(f"[dim]  ▸ {provider} / {model}[/dim]")
                w("")  # blank line before answer

                # Buffer tokens into complete lines before writing.
                # RichLog.write() creates a new visual row per call — writing
                # each token separately stacks them vertically.
                line_buf: list[str] = []
                for token in answer.call_llm_stream(prompt, provider, api_key, model, base_url):
                    parts = token.split("\n")
                    for i, part in enumerate(parts):
                        line_buf.append(part)
                        if i < len(parts) - 1:          # newline in this token
                            w(_safe("".join(line_buf)))
                            line_buf = []
                if line_buf:                              # flush last partial line
                    w(_safe("".join(line_buf)))

                w("")  # blank line after answer

                # Store hits so digit keys open CodeViewScreen
                self.call_from_thread(self._set_last_hits, hits[:9])
                n = min(len(hits), 9)
                w(f"[dim]── sources  ·  press 1–{n} to view code ──[/dim]")
                for i, h in enumerate(hits[:9], 1):
                    fs  = _short_path(h.get("file", ""))
                    ln  = h.get("line_start", "")
                    sy  = h.get("symbol", "")
                    sym = f"  [green]{_safe(sy)}[/green]" if sy else ""
                    w(f" [dim]{i:>2}[/dim]  [cyan]{_safe(fs)}[/cyan]:[yellow]{ln}[/yellow]{sym}")
                w("")

            except Exception as exc:
                w(f"[red]✗ {exc}[/red]")
            finally:
                self.call_from_thread(self._finish_input)

    KBCLI().run()
