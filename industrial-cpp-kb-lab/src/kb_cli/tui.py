from __future__ import annotations

from pathlib import Path
from types import ModuleType

from . import render
from .runtime import repo_file, search_module

_HELP_TEXT = """\
[bold]Smoothieware Code KB — Search Cockpit[/]

[bold cyan]Navigation[/]
  j / ↓      下一条 hit（table 获焦时）
  k / ↑      上一条 hit（table 获焦时）
  Enter      提交 query

[bold cyan]Actions[/]
  /          跳到 query 输入框
  s          重跑检索
  ?          打开 / 关闭本帮助
  q          退出

[bold cyan]Workflow[/]
  1. 在顶部输入框输入 query，按 Enter
  2. j / k 浏览命中行，右侧 preview 实时更新
  3. 按 / 再次搜索

Esc / q / ?  关闭此帮助\
"""


def _source_preview(hit: dict | None, context: int = 10):
    try:
        from rich.panel import Panel
        from rich.syntax import Syntax
    except ImportError:
        return "Rich is required for source preview."

    if not hit:
        return Panel(
            "Run a search to preview the top source hit.",
            title="Source Preview",
            border_style="dim",
        )

    path = repo_file(hit["file"])
    focus = int(hit.get("line_start") or 1)
    lexer = "cpp" if Path(hit["file"]).suffix.lower() in {
        ".cpp", ".h", ".hpp", ".c", ".cc"
    } else "text"

    if not path.is_file():
        return Panel(
            f"File not found: {path}",
            title="Source Preview",
            border_style="red",
        )

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return Panel(str(exc), title="Source Preview", border_style="red")

    start = max(1, focus - context)
    end = min(len(lines), focus + context)
    code = "\n".join(lines[start - 1:end])
    return Panel(
        Syntax(
            code,
            lexer,
            line_numbers=True,
            start_line=start,
            highlight_lines={focus},
            theme="monokai",
            word_wrap=False,
        ),
        title=f"Source Preview  {hit['file']}:{focus}",
        border_style="green",
    )


def run_tui() -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.screen import ModalScreen
        from textual.widgets import DataTable, Footer, Header, Input, Label, ListItem, ListView, Static
    except ImportError:
        render.console.print(
            "[yellow]Textual 当前未安装。[/]\n"
            "运行 `pip install -r requirements.txt` 后可启用 `tui`。\n"
            "现在可先使用 `repl` 的 F1/F2/F3/F4/F5/F8 快捷键工作台。"
        )
        return

    class HelpScreen(ModalScreen):
        BINDINGS = [
            Binding("escape", "dismiss", "Close"),
            Binding("q", "dismiss", "Close"),
            Binding("?", "dismiss", "Close"),
        ]
        CSS = """
        HelpScreen {
            align: center middle;
        }
        #help_panel {
            width: 64;
            height: auto;
            padding: 2 4;
            border: double $primary;
            background: $surface;
        }
        """

        def compose(self) -> ComposeResult:
            yield Static(_HELP_TEXT, id="help_panel")

    class SearchCockpit(App):
        CSS = """
        Screen {
            layout: vertical;
        }

        #query {
            height: 3;
            dock: top;
        }

        #main {
            height: 1fr;
        }

        #left {
            width: 24;
            border: solid $accent;
        }

        #results {
            width: 44%;
            border: solid $primary;
        }

        #preview {
            width: 1fr;
            border: solid $success;
            overflow: auto;
        }

        #status {
            height: 1;
            color: $text-muted;
        }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("/", "focus_query", "Query"),
            Binding("s", "run_search", "Search"),
            Binding("?", "show_help", "Help"),
            Binding("j", "table_down", "↓", show=False),
            Binding("k", "table_up", "↑", show=False),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.search_mod: ModuleType | None = None
            self.last_query = ""
            self.hits: list[dict] = []

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Input(
                placeholder="Search Smoothieware code: G-code entry, Planner, halt...",
                id="query",
            )
            with Horizontal(id="main"):
                with Vertical(id="left"):
                    yield Label("History / Commands", id="status")
                    yield ListView(
                        ListItem(Label("/ search current query")),
                        ListItem(Label("s run search")),
                        ListItem(Label("/ focus query")),
                        ListItem(Label("? help")),
                        ListItem(Label("q quit")),
                        id="history",
                    )
                table = DataTable(id="results", zebra_stripes=True)
                table.add_columns(
                    "#",
                    "file",
                    "line",
                    "type",
                    "class",
                    "symbol",
                    "score",
                    "source",
                    "chunk_id",
                )
                yield table
                yield Static(_source_preview(None), id="preview")
            yield Footer()

        def on_mount(self) -> None:
            self.title = "Smoothieware Code KB"
            self.sub_title = "Search Cockpit v1"
            self.query_one("#query", Input).focus()
            self._set_status("Loading index...")
            try:
                self.search_mod = search_module()
            except SystemExit as exc:
                self._set_status(str(exc), error=True)
            except Exception as exc:
                self._set_status(f"Index load failed: {exc}", error=True)
            else:
                self._set_status("Ready. Type a query and press Enter.")

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == "query":
                self.last_query = event.value.strip()
                self.run_search()

        def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
            idx = event.cursor_row
            if 0 <= idx < len(self.hits):
                self.query_one("#preview", Static).update(_source_preview(self.hits[idx]))

        def action_focus_query(self) -> None:
            self.query_one("#query", Input).focus()

        def action_run_search(self) -> None:
            self.last_query = self.query_one("#query", Input).value.strip()
            self.run_search()

        def action_show_help(self) -> None:
            self.push_screen(HelpScreen())

        def action_table_down(self) -> None:
            table = self.query_one("#results", DataTable)
            if table.row_count:
                table.move_cursor(row=min(table.cursor_row + 1, table.row_count - 1))
                table.focus()

        def action_table_up(self) -> None:
            table = self.query_one("#results", DataTable)
            if table.row_count:
                table.move_cursor(row=max(0, table.cursor_row - 1))
                table.focus()

        def run_search(self) -> None:
            table = self.query_one("#results", DataTable)
            if not self.search_mod:
                self._set_status("Search index is not loaded.", error=True)
                return
            if not self.last_query:
                self._set_status("Type a query first.", error=True)
                return

            self._set_status(f"Searching: {self.last_query}")
            try:
                self.hits = self.search_mod.search(
                    self.last_query,
                    top_k=20,
                    bundle=False,
                )
            except Exception as exc:
                self.hits = []
                table.clear()
                self.query_one("#preview", Static).update(_source_preview(None))
                self._set_status(f"Search failed: {exc}", error=True)
                return

            table.clear()
            if not self.hits:
                self.query_one("#preview", Static).update(_source_preview(None))
                self._set_status("No hits.")
                return

            for index, hit in enumerate(self.hits, 1):
                table.add_row(
                    str(index),
                    str(hit.get("file", "")),
                    str(hit.get("line_start", "")),
                    str(hit.get("type", "")),
                    str(hit.get("class", "")),
                    str(hit.get("symbol", "")),
                    f"{float(hit.get('score', 0)):.2f}",
                    str(hit.get("source", "")),
                    str(hit.get("chunk_id", "")),
                )

            self.query_one("#preview", Static).update(_source_preview(self.hits[0]))
            self._set_status(f"{len(self.hits)} hits for: {self.last_query}")

        def _set_status(self, message: str, *, error: bool = False) -> None:
            style = "red" if error else "green"
            self.query_one("#status", Label).update(f"[{style}]{message}[/{style}]")

    SearchCockpit().run()
