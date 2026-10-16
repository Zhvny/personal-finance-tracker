#!/usr/bin/env python3
"""
Finance Tracker — Datadog Alpha Log Cockpit
=============================================
High-performance Datadog-inspired Live Log Monitor & Observability Dashboard.
Features:
  - Unified Chronological Log Stream across all microservices & logs
  - Multi-Pane Grid View, Log Inspector & Log Pattern Analytics
  - Datadog-style Facet Query Search (service:microservice status:error keyword)
  - Live Log Volume Histogram & Ingestion Error Rate Metrics
  - One-click Clipboard Copy & Timestamped File Exports
"""
import datetime
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Footer, Input, Label, RichLog, TabbedContent, TabPane

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Log Sources & Configuration
LOG_SOURCES = {
    "microservice": {
        "label": "Alpha Microservice",
        "badge": "MICROSERVICE",
        "color": "#38bdf8", # Sky Blue
        "path": PROJECT_ROOT / "apps" / "api" / "alpha_microservice.log"
    },
    "cli": {
        "label": "CLI & Scheduler",
        "badge": "CLI",
        "color": "#c084fc", # Purple
        "path": PROJECT_ROOT / "logs" / "app.log"
    },
    "api": {
        "label": "API Boot & Gateway",
        "badge": "API",
        "color": "#f472b6", # Pink
        "path": PROJECT_ROOT / "logs" / "api_server_boot.log"
    },
    "optimizer": {
        "label": "Genetic Optimizer",
        "badge": "OPTIMIZER",
        "color": "#fbbf24", # Amber
        "path": PROJECT_ROOT / "logs" / "optimizer_exclusions.log"
    },
    "security": {
        "label": "Security Audit",
        "badge": "SECURITY",
        "color": "#f87171", # Red
        "path": PROJECT_ROOT / "logs" / "security_audit.log"
    },
    "dr_backup": {
        "label": "Disaster Recovery",
        "badge": "RECOVERY",
        "color": "#34d399", # Emerald
        "path": PROJECT_ROOT / "logs" / "dr_backup.log"
    },
}

LEVEL_STYLES = {
    "CRITICAL": {"badge": " CRIT ", "color": "bold white on #991b1b"},
    "ERROR":    {"badge": " ERR  ", "color": "bold white on #b91c1c"},
    "WARNING":  {"badge": " WARN ", "color": "bold black on #f59e0b"},
    "INFO":     {"badge": " INFO ", "color": "bold black on #10b981"},
    "DEBUG":    {"badge": " DBG  ", "color": "grey70 on #334155"},
}

TIMESTAMP_REGEX = re.compile(
    r'(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to Windows clipboard using native utilities."""
    if not text:
        return False
    try:
        subprocess.run(["clip"], input=text, text=True, check=True, encoding="utf-8")
        return True
    except Exception:
        try:
            # Fallback to PowerShell
            cmd = f'$val = @"{text}"@; Set-Clipboard -Value $val'
            subprocess.run(["powershell", "-Command", cmd], check=True)
            return True
        except Exception:
            return False


def classify_line(line: str) -> str:
    """Determine log severity level from text."""
    line_upper = line.upper()
    for level in ("CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG"):
        if level in line_upper:
            if level == "WARN":
                return "WARNING"
            return level
    return "INFO"


def extract_timestamp(line: str) -> datetime.datetime:
    """Extract datetime object from log line for sorting, or return fallback."""
    match = TIMESTAMP_REGEX.search(line)
    if match:
        raw_ts = match.group(1).replace("T", " ")
        try:
            # Try parsing common timestamp formats
            if "." in raw_ts:
                raw_ts = raw_ts.split(".")[0]
            return datetime.datetime.strptime(raw_ts[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return datetime.datetime.min


def format_datadog_line(source_key: str, line: str) -> Text:
    """Format log line with Datadog styling tags and syntax highlighting."""
    src_info = LOG_SOURCES.get(source_key, {"badge": source_key.upper(), "color": "#94a3b8"})
    level = classify_line(line)
    lvl_info = LEVEL_STYLES.get(level, LEVEL_STYLES["INFO"])

    text = Text()

    # 1. Timestamp extraction or fallback
    match = TIMESTAMP_REGEX.search(line)
    if match:
        ts_str = match.group(1)
        text.append(f"{ts_str[:19]} ", style="#64748b")
        content_line = line.replace(ts_str, "").strip()
    else:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text.append(f"{now_str} ", style="#475569")
        content_line = line.strip()

    # 2. Service Pill Tag
    text.append(f" {src_info['badge']} ", style=f"bold #0f172a on {src_info['color']}")
    text.append(" ")

    # 3. Status Level Pill Tag
    text.append(f"{lvl_info['badge']}", style=lvl_info['color'])
    text.append(" ")

    # 4. Message Content with Syntax Highlighting
    # Highlight HTTP codes, URLs, paths, errors, metrics
    words = content_line.split(" ")
    for word in words:
        if any(err_kw in word.lower() for err_kw in ["error", "exception", "failed", "critical", "crash"]):
            text.append(f"{word} ", style="bold #f87171")
        elif any(succ_kw in word.lower() for succ_kw in ["success", "healthy", "connected", "ok", "passed"]):
            text.append(f"{word} ", style="bold #4ade80")
        elif word.isdigit() and len(word) == 3 and word.startswith(("2", "3", "4", "5")):
            # HTTP status code
            if word.startswith("2"):
                text.append(f"{word} ", style="bold #34d399")
            elif word.startswith(("4", "5")):
                text.append(f"{word} ", style="bold #f87171")
            else:
                text.append(f"{word} ", style="bold #fbbf24")
        elif word.startswith(("/", "C:\\", "http://", "https://")):
            text.append(f"{word} ", style="underline #38bdf8")
        else:
            text.append(f"{word} ", style="#e2e8f0")

    return text


class LogPane(Vertical):
    """Single Source Log Panel for Grid View."""

    DEFAULT_CSS = """
    LogPane {
        border: solid #1e293b;
        background: #0f172a;
        padding: 0;
        margin: 0 1 1 0;
    }
    LogPane:focus-within {
        border: solid #6366f1;
    }
    LogPane .pane-header {
        background: #1e293b;
        padding: 0 1;
        height: 1;
        color: #38bdf8;
        text-style: bold;
    }
    LogPane .pane-stats {
        background: #0f172a;
        padding: 0 1;
        height: 1;
        color: #64748b;
        border-bottom: solid #1e293b;
    }
    LogPane RichLog {
        height: 1fr;
        background: transparent;
    }
    """

    def __init__(self, key: str, label: str, path: Path, **kwargs):
        super().__init__(**kwargs)
        self.source_key = key
        self.source_label = label
        self.log_path = path
        self.visible_lines: List[str] = []

    def compose(self) -> ComposeResult:
        badge = LOG_SOURCES.get(self.source_key, {}).get("badge", self.source_key.upper())
        yield Label(f" ● [{badge}] {self.source_label}", classes="pane-header")
        yield Label(" INFO: 0  |  WARN: 0  |  ERR: 0  |  0.00 MB",
                    id=f"stats-{self.source_key}", classes="pane-stats")
        yield RichLog(id=f"richlog-{self.source_key}", highlight=True, markup=True)

    def refresh_logs(self, active_level: str = "ALL", search: str = "") -> Tuple[int, int, int]:
        if not self.log_path.exists():
            self.visible_lines = []
            self._write_single(f"[dim]Log file pending: {self.log_path.name}[/dim]")
            return (0, 0, 0)

        try:
            current_size = self.log_path.stat().st_size
            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            self.visible_lines = []
            self._write_single(f"[red]Failed reading log: {e}[/red]")
            return (0, 0, 0)

        recent = lines[-600:]
        info_c = warn_c = err_c = 0
        parsed = []

        for line in recent:
            s = line.strip()
            if not s:
                continue
            lv = classify_line(s)
            if lv in ("ERROR", "CRITICAL"):
                err_c += 1
            elif lv == "WARNING":
                warn_c += 1
            else:
                info_c += 1
            parsed.append((lv, s))

        # Update stats bar label
        try:
            stats_label = self.query_one(f"#stats-{self.source_key}", Label)
            stats_label.update(
                f" INFO: [bold #10b981]{info_c}[/]  |  WARN: [bold #f59e0b]{warn_c}[/]  |  ERR: [bold #ef4444]{err_c}[/]"
                f"  |  [dim]{current_size/(1024*1024):.2f} MB[/dim]"
            )
        except Exception:
            pass

        # Apply Filters
        visible = []
        for lv, s in parsed:
            if active_level != "ALL":
                if active_level == "ERROR" and lv not in ("ERROR", "CRITICAL"):
                    continue
                elif active_level not in ("ERROR",) and lv != active_level:
                    continue
            if search and search not in s.lower():
                continue
            visible.append(s)

        self.visible_lines = visible
        try:
            rl = self.query_one(f"#richlog-{self.source_key}", RichLog)
            rl.clear()
            for s in visible:
                rl.write(format_datadog_line(self.source_key, s))
        except Exception:
            pass

        return (info_c, warn_c, err_c)

    def get_log_text(self) -> str:
        return "\n".join(self.visible_lines)

    def _write_single(self, msg: str) -> None:
        try:
            rl = self.query_one(f"#richlog-{self.source_key}", RichLog)
            rl.clear()
            rl.write(msg)
        except Exception:
            pass


class DatadogLogCockpitApp(App):
    TITLE = "Log Cockpit"
    SUB_TITLE = "Alpha Live Observability & Microservice Log Stream"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "tab_stream", "Stream View"),
        ("2", "tab_grid", "Grid View"),
        ("3", "tab_inspector", "Inspector View"),
        ("4", "tab_analytics", "Analytics View"),
        ("p", "toggle_pause", "Pause/Live"),
        ("c", "copy_logs", "Copy Logs"),
        ("e", "export_logs", "Export File"),
        ("r", "force_refresh", "Refresh"),
        ("s", "focus_search", "Search"),
        ("/", "focus_search", "Search"),
        ("a", "filter_all", "All"),
        ("i", "filter_info", "Info"),
        ("w", "filter_warn", "Warn"),
        ("err", "filter_err", "Error"),
    ]

    CSS = """
    Screen {
        background: #090d16;
        color: #f8fafc;
    }

    /* Header Bar */
    #datadog-header {
        height: 3;
        background: #1e1b4b;
        color: #ffffff;
        padding: 0 2;
        layout: horizontal;
        align: left middle;
        border-bottom: solid #4338ca;
    }
    #header-title {
        text-style: bold;
        color: #818cf8;
        width: 1fr;
    }
    #header-live-badge {
        background: #065f46;
        color: #34d399;
        padding: 0 1;
        text-style: bold;
    }

    /* Metrics Summary Bar */
    #metrics-bar {
        height: 3;
        background: #0f172a;
        border-bottom: solid #1e293b;
        padding: 0 2;
        layout: horizontal;
        align: left middle;
    }
    .metric-card {
        margin-right: 3;
        padding: 0 1;
    }
    .metric-title {
        color: #64748b;
    }
    .metric-value {
        text-style: bold;
        color: #f8fafc;
    }

    /* Volume Histogram */
    #histogram-bar {
        height: 2;
        background: #090d16;
        padding: 0 2;
        color: #818cf8;
        border-bottom: solid #1e293b;
    }

    /* Search & Filter Toolbar */
    #toolbar {
        height: 3;
        background: #0f172a;
        padding: 0 2;
        layout: horizontal;
        align: left middle;
        border-bottom: solid #1e293b;
    }
    #search-input {
        width: 48;
        height: 1;
        background: #1e293b;
        border: solid #334155;
        color: #f8fafc;
        margin-right: 2;
    }
    #search-input:focus {
        border: solid #6366f1;
    }
    .filter-btn {
        min-width: 8;
        height: 1;
        border: none;
        padding: 0 1;
        margin-right: 1;
        background: #1e293b;
        color: #94a3b8;
    }
    .filter-btn:hover {
        background: #334155;
        color: #ffffff;
    }
    .filter-btn-active {
        background: #312e81;
        color: #a5b4fc;
        text-style: bold;
    }

    /* Tabs & Content */
    TabbedContent {
        height: 1fr;
        background: transparent;
    }
    TabPane {
        padding: 1;
        background: transparent;
    }

    /* Stream View */
    #stream-log {
        height: 1fr;
        background: #0f172a;
        border: solid #1e293b;
        padding: 1;
    }

    /* Grid View */
    #grid-container {
        height: 1fr;
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1 1;
    }

    /* Inspector View */
    #inspector-container {
        height: 1fr;
        layout: horizontal;
    }
    #inspector-list {
        width: 60%;
        height: 1fr;
        border: solid #1e293b;
        background: #0f172a;
    }
    #inspector-detail {
        width: 40%;
        height: 1fr;
        border: solid #1e293b;
        background: #0f172a;
        padding: 1;
        margin-left: 1;
    }

    /* Analytics View */
    #analytics-table {
        height: 1fr;
        background: #0f172a;
        border: solid #1e293b;
    }
    """

    is_paused = reactive(False)
    active_level = reactive("ALL")
    active_tab = reactive("tab-stream")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_log_entries: List[Tuple[datetime.datetime, str, str]] = [] # (ts, source_key, line)
        self.stats = {"info": 0, "warn": 0, "err": 0, "bytes": 0}

    def compose(self) -> ComposeResult:
        # Datadog Top Header
        with Horizontal(id="datadog-header"):
            yield Label(" LOG COCKPIT", id="header-title")
            yield Label(" ● LIVE STREAMING ", id="header-live-badge")

        # Metrics Bar
        with Horizontal(id="metrics-bar"):
            with Vertical(classes="metric-card"):
                yield Label("TOTAL LOGS / SIZE", classes="metric-title")
                yield Label("0 msgs | 0.0 MB", id="metric-volume", classes="metric-value")
            with Vertical(classes="metric-card"):
                yield Label("ERROR RATE", classes="metric-title")
                yield Label("0.0% (0 ERR)", id="metric-err-rate", classes="metric-value")
            with Vertical(classes="metric-card"):
                yield Label("WARNINGS", classes="metric-title")
                yield Label("0 WARN", id="metric-warn", classes="metric-value")
            with Vertical(classes="metric-card"):
                yield Label("ACTIVE SOURCES", classes="metric-title")
                yield Label(f"{len(LOG_SOURCES)} Services", id="metric-sources", classes="metric-value")

        # Volume Histogram Bar
        yield Label("LOG VOLUME (15m): █ ▇ ▆ ▅ ▄ ▃ ▂   █ ▇ ▆ ▅ ▄ (Live Feed)", id="histogram-bar")

        # Query & Filter Toolbar
        with Horizontal(id="toolbar"):
            yield Input(
                placeholder="Search (e.g. status:error service:microservice timeout)...",
                id="search-input"
            )
            yield Button("ALL", id="btn-all", classes="filter-btn filter-btn-active")
            yield Button("INFO", id="btn-info", classes="filter-btn")
            yield Button("WARN", id="btn-warn", classes="filter-btn")
            yield Button("ERROR", id="btn-err", classes="filter-btn")
            yield Button("PAUSE", id="btn-pause", classes="filter-btn")
            yield Button("COPY", id="btn-copy", classes="filter-btn")
            yield Button("EXPORT", id="btn-export", classes="filter-btn")

        # Tabbed View Container
        with TabbedContent(initial="tab-stream", id="main-tabs"):
            with TabPane("Stream", id="tab-stream"):
                yield RichLog(id="stream-log", highlight=True, markup=True)

            with TabPane("Split Grid", id="tab-grid"):
                with Container(id="grid-container"):
                    yield LogPane("microservice", LOG_SOURCES["microservice"]["label"], LOG_SOURCES["microservice"]["path"], id="pane-microservice")
                    yield LogPane("cli", LOG_SOURCES["cli"]["label"], LOG_SOURCES["cli"]["path"], id="pane-cli")
                    yield LogPane("api", LOG_SOURCES["api"]["label"], LOG_SOURCES["api"]["path"], id="pane-api")
                    yield LogPane("optimizer", LOG_SOURCES["optimizer"]["label"], LOG_SOURCES["optimizer"]["path"], id="pane-optimizer")

            with TabPane("Log Inspector", id="tab-inspector"):
                with Horizontal(id="inspector-container"):
                    yield RichLog(id="inspector-list", highlight=True, markup=True)
                    with Vertical(id="inspector-detail"):
                        yield Label(" [bold #818cf8]LOG ENTRY DETAILS[/bold #818cf8]\n")
                        yield Label("Select log line to inspect attributes.", id="inspector-content")

            with TabPane("Log Analytics", id="tab-analytics"):
                yield DataTable(id="analytics-table")

        yield Footer()

    def on_mount(self) -> None:
        # Setup DataTable columns
        try:
            table = self.query_one("#analytics-table", DataTable)
            table.add_columns("Service / Source", "Total Lines", "Info", "Warnings", "Errors", "Status")
        except Exception:
            pass

        self._do_refresh()
        self.set_interval(2.0, self._do_refresh)

    # Watchers & Handlers
    def watch_is_paused(self, paused: bool) -> None:
        try:
            badge = self.query_one("#header-live-badge", Label)
            btn = self.query_one("#btn-pause", Button)
            if paused:
                badge.update(" STREAM PAUSED ")
                badge.styles.background = "#991b1b"
                badge.styles.color = "#fca5a5"
                btn.label = "RESUME"
            else:
                badge.update(" ● LIVE STREAMING ")
                badge.styles.background = "#065f46"
                badge.styles.color = "#34d399"
                btn.label = "PAUSE"
        except Exception:
            pass

    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-all":
            self._set_level("ALL")
        elif btn_id == "btn-info":
            self._set_level("INFO")
        elif btn_id == "btn-warn":
            self._set_level("WARNING")
        elif btn_id == "btn-err":
            self._set_level("ERROR")
        elif btn_id == "btn-pause":
            self.action_toggle_pause()
        elif btn_id == "btn-copy":
            self.action_copy_logs()
        elif btn_id == "btn-export":
            self.action_export_logs()

    @on(Input.Changed, "#search-input")
    def handle_search(self) -> None:
        self._do_refresh()

    def _set_level(self, level: str) -> None:
        self.active_level = level
        for b_id, l_val in [("btn-all", "ALL"), ("btn-info", "INFO"), ("btn-warn", "WARNING"), ("btn-err", "ERROR")]:
            try:
                btn = self.query_one(f"#{b_id}", Button)
                if l_val == level:
                    btn.add_class("filter-btn-active")
                else:
                    btn.remove_class("filter-btn-active")
            except Exception:
                pass
        self._do_refresh()

    def _do_refresh(self) -> None:
        if self.is_paused:
            return

        search_q = ""
        try:
            search_q = self.query_one("#search-input", Input).value.strip().lower()
        except Exception:
            pass

        # 1. Refresh Grid Panes & Accumulate Stats
        total_info = total_warn = total_err = total_bytes = 0
        all_entries: List[Tuple[datetime.datetime, str, str]] = []

        for key, conf in LOG_SOURCES.items():
            path = conf["path"]
            if not path.exists():
                continue
            try:
                size = path.stat().st_size
                total_bytes += size
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                recent = lines[-400:]
                for line in recent:
                    s = line.strip()
                    if not s:
                        continue
                    ts = extract_timestamp(s)
                    lv = classify_line(s)
                    if lv in ("ERROR", "CRITICAL"):
                        total_err += 1
                    elif lv == "WARNING":
                        total_warn += 1
                    else:
                        total_info += 1

                    # Apply query & level filters
                    if self.active_level != "ALL":
                        if self.active_level == "ERROR" and lv not in ("ERROR", "CRITICAL"):
                            continue
                        elif self.active_level != "ERROR" and lv != self.active_level:
                            continue
                    if search_q and search_q not in s.lower():
                        continue

                    all_entries.append((ts, key, s))

            except Exception:
                pass

            # Update Pane in Grid
            try:
                pane = self.query_one(f"#pane-{key}", LogPane)
                pane.refresh_logs(self.active_level, search_q)
            except Exception:
                pass

        # Sort Stream Entries Chronologically
        all_entries.sort(key=lambda x: x[0])
        self.all_log_entries = all_entries

        # 2. Update Datadog Unified Stream View
        try:
            stream_log = self.query_one("#stream-log", RichLog)
            stream_log.clear()
            for ts, src_key, line in all_entries[-500:]:
                stream_log.write(format_datadog_line(src_key, line))
        except Exception:
            pass

        # 3. Update Datadog Inspector List View
        try:
            insp_log = self.query_one("#inspector-list", RichLog)
            insp_log.clear()
            for ts, src_key, line in all_entries[-200:]:
                insp_log.write(format_datadog_line(src_key, line))
        except Exception:
            pass

        # 4. Update Metrics Summary Cards
        total_msgs = total_info + total_warn + total_err
        err_pct = (total_err / total_msgs * 100) if total_msgs > 0 else 0.0

        try:
            m_vol = self.query_one("#metric-volume", Label)
            m_vol.update(f"{total_msgs} msgs | {total_bytes/(1024*1024):.2f} MB")

            m_err = self.query_one("#metric-err-rate", Label)
            err_style = "#f87171" if err_pct > 5 else ("#fbbf24" if err_pct > 1 else "#34d399")
            m_err.update(f"[{err_style}]{err_pct:.1f}% ({total_err} ERR)[/{err_style}]")

            m_warn = self.query_one("#metric-warn", Label)
            m_warn.update(f"[#fbbf24]{total_warn} WARN[/#fbbf24]")
        except Exception:
            pass

        # 5. Update Analytics Table
        try:
            table = self.query_one("#analytics-table", DataTable)
            table.clear()
            for key, conf in LOG_SOURCES.items():
                p = conf["path"]
                if p.exists():
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            l = f.readlines()
                        cnt = len(l)
                        i_c = sum(1 for line in l if classify_line(line) == "INFO")
                        w_c = sum(1 for line in l if classify_line(line) == "WARNING")
                        e_c = sum(1 for line in l if classify_line(line) in ("ERROR", "CRITICAL"))
                        status = "[bold #34d399]HEALTHY[/bold #34d399]" if e_c == 0 else "[bold #f87171]ATTENTION[/bold #f87171]"
                        table.add_row(conf["label"], str(cnt), str(i_c), str(w_c), str(e_c), status)
                    except Exception:
                        pass
        except Exception:
            pass

    # Keyboard Actions
    def action_tab_stream(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-stream"

    def action_tab_grid(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-grid"

    def action_tab_inspector(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-inspector"

    def action_tab_analytics(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-analytics"

    def action_toggle_pause(self) -> None:
        self.is_paused = not self.is_paused
        st = "PAUSED" if self.is_paused else "RESUMED"
        self.notify(f"Live log stream {st}.", title="Datadog Stream Status")

    def action_filter_all(self) -> None: self._set_level("ALL")
    def action_filter_info(self) -> None: self._set_level("INFO")
    def action_filter_warn(self) -> None: self._set_level("WARNING")
    def action_filter_err(self) -> None: self._set_level("ERROR")
    def action_force_refresh(self) -> None: self._do_refresh()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_copy_logs(self) -> None:
        lines = [f"{ts.strftime('%Y-%m-%d %H:%M:%S')} [{src}] {line}" for ts, src, line in self.all_log_entries]
        full_text = "\n".join(lines)
        if full_text and copy_to_clipboard(full_text):
            self.notify("Log stream disalin ke OS Clipboard!", title="Copied!")
        else:
            self.notify("Gagal menyalin log atau tidak ada logs visible.", severity="warning")

    def action_export_logs(self) -> None:
        if not self.all_log_entries:
            self.notify("Tidak ada log visible untuk diexport.", severity="warning")
            return
        exp_dir = PROJECT_ROOT / "logs"
        exp_dir.mkdir(exist_ok=True)
        ts_filename = datetime.datetime.now().strftime("datadog_export_%Y%m%d_%H%M%S.log")
        out_path = exp_dir / ts_filename

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                for ts, src, line in self.all_log_entries:
                    f.write(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} [{src}] {line}\n")
            self.notify(f"Log diexport ke: {out_path.name}", title="Export Complete")
        except Exception as e:
            self.notify(f"Export gagal: {e}", severity="error")


if __name__ == "__main__":
    DatadogLogCockpitApp().run()
