from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure root is in sys.path
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import the CLI main module using an explicit absolute path to ensure the
# correct `apps/cli/main.py` is loaded regardless of how sys.path is ordered
# (e.g., when pytest runs from the project root, bare `import main` would
# otherwise resolve to a different module).
import importlib.util as _ilu

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, LoadingIndicator, RichLog, Static

_cli_main_path = Path(__file__).parent / "main.py"
_spec = _ilu.spec_from_file_location("apps.cli.main", str(_cli_main_path))
cli_main = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(cli_main)       # type: ignore[union-attr]
from genetic_optimizer import PortfolioOptimizer

# Database Infrastructure
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError:
    import sys
    ROOT_PATH = str(Path(__file__).resolve().parent.parent.parent)
    if ROOT_PATH not in sys.path:
        sys.path.append(ROOT_PATH)
    try:
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    except ImportError:
        DatabaseManager = None

# ─────────────────────────────────────────────────────────────────────────────
# Shared Widgets
# ─────────────────────────────────────────────────────────────────────────────

class DashboardCard(Static):
    def __init__(self, title: str, value: str, subtitle: str, id: str | None = None):
        super().__init__(id=id)
        self.title_text = title
        self.value_text = value
        self.subtitle_text = subtitle

    def compose(self) -> ComposeResult:
        yield Label(self.title_text, classes="card-title")
        yield Label(self.value_text, classes="card-value")
        yield Label(self.subtitle_text, classes="card-subtitle")

# ─────────────────────────────────────────────────────────────────────────────
# Log Viewer / Live Dashboard Screen
# ─────────────────────────────────────────────────────────────────────────────

import subprocess


def copy_to_clipboard(text: str) -> bool:
    if not text:
        return False
    try:
        subprocess.run(["clip"], input=text, text=True, check=True, encoding="utf-8")
        return True
    except Exception:
        try:
            cmd = f'Set-Clipboard -Value @"{text}"@'
            subprocess.run(["powershell", "-Command", cmd], check=True)
            return True
        except Exception:
            return False


class LogScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("t", "toggle_source", "Toggle CLI/API Source"),
        ("i", "filter_info", "Info Level"),
        ("w", "filter_warning", "Warning Level"),
        ("e", "filter_error", "Error Level"),
        ("a", "filter_all", "Show All"),
        ("c", "copy_logs", "Copy Logs"),
        ("s", "focus_search", "Search Logs"),
    ]

    CSS = """
    #log-screen-layout {
        background: #080808;
    }
    #log-stats-grid {
        layout: grid;
        grid-size: 5;
        height: 6;
        margin: 1 2 0 2;
        grid-gutter: 1;
    }
    .stat-card {
        background: #121212;
        border: solid #222222;
        padding: 1 2;
        content-align: center middle;
    }
    .stat-value {
        text-style: bold;
        color: white;
        font-size: 120%;
    }
    .stat-label {
        color: #666666;
        font-size: 80%;
    }
    #log-main-container {
        layout: horizontal;
        height: 1fr;
        margin: 1 2;
    }
    #log-sidebar {
        width: 35;
        background: #111111;
        border: solid #222222;
        padding: 1;
        margin-right: 1;
    }
    #log-content-wrapper {
        width: 1fr;
        background: #0a0a0a;
        border: solid #222222;
        padding: 0;
    }
    #log-richlog {
        height: 1fr;
        background: transparent;
    }
    #search-input {
        background: #1a1a1a;
        border: solid #333333;
        color: white;
        margin: 1 0;
    }
    .sidebar-title {
        text-style: bold;
        color: #00ffff;
        margin-top: 1;
    }
    .sidebar-desc {
        color: #555555;
        font-size: 85%;
    }
    .active-filter {
        color: #00ff00;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_log_path = "logs/app.log"
        self.active_level = "ALL"
        self.last_output = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="log-screen-layout"):
            with Grid(id="log-stats-grid"):
                with Vertical(classes="stat-card"):
                    yield Label("1000", id="stat-total-val", classes="stat-value")
                    yield Label("TOTAL RECENT", classes="stat-label")
                with Vertical(classes="stat-card"):
                    yield Label("0", id="stat-info-val", classes="stat-value")
                    yield Label("INFO LOGS", classes="stat-label")
                with Vertical(classes="stat-card"):
                    yield Label("0", id="stat-warn-val", classes="stat-value")
                    yield Label("WARNINGS", classes="stat-label")
                with Vertical(classes="stat-card"):
                    yield Label("0", id="stat-error-val", classes="stat-value")
                    yield Label("ERRORS & CRIT", classes="stat-label")
                with Vertical(classes="stat-card"):
                    yield Label("0.00 MB", id="stat-size-val", classes="stat-value")
                    yield Label("LOG FILE SIZE", classes="stat-label")

            with Container(id="log-main-container"):
                with Vertical(id="log-sidebar"):
                    yield Label("LOG COCKPIT", classes="sidebar-title")
                    yield Label("Monitoring & Filter Logs", classes="sidebar-desc")

                    yield Label("Active Source:", classes="sidebar-title")
                    yield Label("CLI & Scheduler", id="log-source-label")

                    yield Label("Search Query:", classes="sidebar-title")
                    yield Input(placeholder="Ketik kata kunci...", id="search-input")

                    yield Label("Filter Level (Hotkey):", classes="sidebar-title")
                    yield Label("• [a] ALL Levels", id="filter-all-label", classes="active-filter")
                    yield Label("• [i] INFO Level", id="filter-info-label")
                    yield Label("• [w] WARNING Level", id="filter-warning-label")
                    yield Label("• [e] ERROR Level", id="filter-error-label")

                    yield Label("• [t] Toggle CLI/API logs", classes="sidebar-desc")

                with Container(id="log-content-wrapper"):
                    yield RichLog(id="log-richlog", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.update_logs(force_refresh=True)
        self.set_interval(1.0, self.update_logs)

    @on(Input.Changed, "#search-input")
    def on_search_changed(self) -> None:
        self.update_logs(force_refresh=True)

    def action_toggle_source(self) -> None:
        if self.current_log_path == "logs/app.log":
            self.current_log_path = "packages/api/api_server.log"
            self.query_one("#log-source-label", Label).update("API Server & Bot")
        else:
            self.current_log_path = "logs/app.log"
            self.query_one("#log-source-label", Label).update("CLI & Scheduler")
        self.notify(f"Switched log source to: {self.current_log_path}")
        self.update_logs(force_refresh=True)

    def _update_filter_highlights(self) -> None:
        for level in ["ALL", "INFO", "WARNING", "ERROR"]:
            lbl = self.query_one(f"#filter-{level.lower()}-label", Label)
            if self.active_level == level:
                lbl.add_class("active-filter")
            else:
                lbl.remove_class("active-filter")

    def action_filter_info(self) -> None:
        self.active_level = "INFO"
        self._update_filter_highlights()
        self.update_logs(force_refresh=True)

    def action_filter_warning(self) -> None:
        self.active_level = "WARNING"
        self._update_filter_highlights()
        self.update_logs(force_refresh=True)

    def action_filter_error(self) -> None:
        self.active_level = "ERROR"
        self._update_filter_highlights()
        self.update_logs(force_refresh=True)

    def action_filter_all(self) -> None:
        self.active_level = "ALL"
        self._update_filter_highlights()
        self.update_logs(force_refresh=True)

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_copy_logs(self) -> None:
        if self.last_output:
            if copy_to_clipboard(self.last_output):
                self.notify("📋 Log disalin ke clipboard! (Ctrl+V)", title="Copied!")
            else:
                self.notify("❌ Gagal menyalin log.", severity="error")
        else:
            self.notify("Tidak ada log untuk disalin.", severity="warning")

    def _format_line(self, line: str) -> Text:
        levels = {
            "DEBUG": "grey50",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }
        text = Text(line)
        for level, style in levels.items():
            if level in line:
                text.stylize(style)
                break
        return text

    def update_logs(self, force_refresh=False) -> None:
        log_path = Path(self.current_log_path)
        if not log_path.exists():
            self.query_one("#log-richlog", RichLog).write(f"[red]Log file {self.current_log_path} not found.[/red]")
            return

        try:
            current_size = log_path.stat().st_size
        except FileNotFoundError:
            return

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                recent_lines = lines[-1000:]
        except Exception as e:
            self.query_one("#log-richlog", RichLog).write(f"[red]Error reading logs: {e}[/red]")
            return

        info_cnt = 0
        warn_cnt = 0
        err_cnt = 0
        crit_cnt = 0

        parsed_lines = []
        for line in recent_lines:
            line_str = line.strip()
            level = "INFO"
            if "WARNING" in line_str:
                level = "WARNING"
                warn_cnt += 1
            elif "ERROR" in line_str:
                level = "ERROR"
                err_cnt += 1
            elif "CRITICAL" in line_str:
                level = "CRITICAL"
                crit_cnt += 1
            else:
                info_cnt += 1

            parsed_lines.append((level, line_str))

        self.query_one("#stat-total-val", Label).update(str(len(recent_lines)))
        self.query_one("#stat-info-val", Label).update(str(info_cnt))
        self.query_one("#stat-warn-val", Label).update(str(warn_cnt))
        self.query_one("#stat-error-val", Label).update(str(err_cnt + crit_cnt))
        self.query_one("#stat-size-val", Label).update(f"{current_size / (1024*1024):.2f} MB")

        search_query = self.query_one("#search-input", Input).value.strip().lower()

        filtered_lines = []
        for level, line_str in parsed_lines:
            if self.active_level != "ALL":
                if self.active_level == "ERROR" and level not in ("ERROR", "CRITICAL"):
                    continue
                elif self.active_level != level:
                    continue

            if search_query and search_query not in line_str.lower():
                continue

            filtered_lines.append(line_str)

        joined_output = "\n".join(filtered_lines)
        if force_refresh or joined_output != self.last_output:
            rich_log = self.query_one("#log-richlog", RichLog)
            rich_log.clear()
            for line_str in filtered_lines:
                rich_log.write(self._format_line(line_str))
            self.last_output = joined_output

# ─────────────────────────────────────────────────────────────────────────────
# Desktop Layout
# ─────────────────────────────────────────────────────────────────────────────

class DesktopTUI(App):
    TITLE = "Alpha Desktop"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "cancel", "Cancel", show=False),
    ]

    current_task_id: str | None = None

    CSS = """
    Screen { background: #0a0a0a; color: #eee; }
    #dashboard { grid-size: 3; grid-gutter: 2; height: 11; margin: 1 2; }
    DashboardCard { background: #151515; border: tall #333333; padding: 1 2; }
    .card-title { color: #888; text-style: bold; }
    .card-value { margin: 1 0; color: white; text-style: bold; }
    .card-subtitle { color: #555; }
    
    #menu-panel { margin: 1 2; border: double #444; background: #111; }
    DataTable { height: auto; background: transparent; }
    
    #loading-indicator { height: 3; margin: 1 2; }
    .hidden { display: none; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            with Grid(id="dashboard"):
                yield DashboardCard("INCOME", "...", "Monthly", id="card-inc")
                yield DashboardCard("EXPENSE", "...", "Monthly", id="card-exp")
                yield DashboardCard("SAVINGS", "...", "Total", id="card-sav")
                yield DashboardCard("SNIPER", "...", "H+1 Prediction", id="card-ml")

            with Vertical(id="menu-panel"):
                yield Label("  MAIN MENU", id="menu-label")
                yield DataTable(id="menu-table")

        yield LoadingIndicator(id="loading-indicator", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("No", "Module", "Description")
        table.cursor_type = "row"
        for num, label, desc in [
            ("1", "INVEST",  "Portfolio Assets"),
            ("2", "EXPENSE", "Spending Tracker"),
            ("3", "INCOME",  "Earning Tracker"),
            ("4", "SCAN",    "Receipt OCR"),
            ("5", "REOPT",   "Portfolio Optimizer"),
            ("6", "LOGS",    "System Logs"),
        ]:
            table.add_row(num, label, desc)
        self.update_data()

    def update_data(self) -> None:
        data = cli_main._get_dashboard_data()
        self.query_one("#card-inc", DashboardCard).value_text = cli_main.fmt(data["inc_this"])
        self.query_one("#card-exp", DashboardCard).value_text = cli_main.fmt(data["exp_this"])
        self.query_one("#card-sav", DashboardCard).value_text = cli_main.fmt(data["bank_savings"])

        ml_card = self.query_one("#card-ml", DashboardCard)
        if data.get("top_pred"):
            p = data["top_pred"]
            ml_card.value_text = p["ticker"]
            ml_card.subtitle_text = f"Target: {p['target_price']:.1f} ({p['pred_return']:+.1f}%)"
        else:
            ml_card.value_text = "N/A"
            ml_card.subtitle_text = "No models active"

        for card in self.query(DashboardCard): card.refresh()

    @on(DataTable.RowSelected)
    def handle_selection(self, event: DataTable.RowSelected) -> None:
        row = self.query_one(DataTable).get_row_at(event.cursor_row)
        key = str(row[0])
        if key == "6":
            self.notify("Jalankan run-log.bat untuk membuka Log Cockpit.", severity="information")
        elif key == "5":
            self.run_worker(self.run_portfolio_optimization())
        elif key in cli_main.DISPATCH:
            self.run_worker(self.launch_module(key))

    def action_cancel(self) -> None:
        """Signals cancellation to the optimizer via Database."""
        if self.current_task_id and DatabaseManager:
            try:
                DatabaseManager.execute(
                    "UPDATE system.optimization_tasks SET status = 'timeout' WHERE task_id = %s",
                    (self.current_task_id,),
                    schema="system"
                )
                self.notify("Cancellation requested...", severity="warning")
                self._toggle_cancel_binding(False)
            except Exception as e:
                self.notify(f"Cancel failed: {e}", severity="error")

    def _toggle_cancel_binding(self, show: bool) -> None:
        """Helper to toggle the visibility of the Cancel binding in the footer."""
        try:
            for binding in self._bindings.binds:
                if binding.key == "c":
                    binding.show = show
            self.query_one(Footer).refresh()
        except Exception:
            pass

    async def run_portfolio_optimization(self) -> None:
        """Async flow for portfolio optimization with persistent loading indicator."""
        indicator = self.query_one("#loading-indicator")
        indicator.remove_class("hidden")
        self._toggle_cancel_binding(True)

        self.current_task_id = str(uuid.uuid4())

        # Register the task in DB so it exists for the optimizer to check
        if DatabaseManager:
            try:
                # Ensure table exists first
                DatabaseManager.execute("""
                    CREATE TABLE IF NOT EXISTS system.optimization_tasks (
                        task_id UUID PRIMARY KEY,
                        profile_id TEXT,
                        status TEXT,
                        progress INTEGER DEFAULT 0,
                        input_params JSONB,
                        result JSONB,
                        error TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                DatabaseManager.execute(
                    "INSERT INTO system.optimization_tasks (task_id, status) VALUES (%s, 'running')",
                    (self.current_task_id,),
                    schema="system"
                )
            except Exception:
                pass # Already exists or managed elsewhere

        try:
            # For Phase 1, we use a controlled optimization run
            # Generate minimal mock data to trigger the optimizer flow
            n_assets = 5
            tickers = [f"ASSET_{i}" for i in range(n_assets)]
            data = np.random.normal(0.0005, 0.01, (100, n_assets))
            returns_df = pd.DataFrame(data, columns=tickers)

            optimizer = PortfolioOptimizer(generations=15) # Fast run for TUI integration
            result = await optimizer.optimize_async(returns_df, task_id=self.current_task_id)

            if result is None:
                self.notify("No assets available for optimization.", severity="error")
            else:
                self.notify("Optimization complete.")

        except asyncio.TimeoutError:
            self.notify("Optimization timed out.", severity="warning")
        except ValueError as e:
            self.notify(f"Invalid data: {e}", severity="error")
        except RuntimeError as e:
            self.notify(f"Critical Error: {e}", severity="error")
        except Exception as e:
            self.notify(f"Optimization failed: {e}", severity="error")
        finally:
            self.current_task_id = None
            indicator.add_class("hidden")
            self._toggle_cancel_binding(False)
            self.update_data()

    async def launch_module(self, key: str) -> None:
        self.app.suspend_stdio()
        print("\033[2J\033[H", end="")
        cli_main.DISPATCH[key]()
        input("\nPress Enter...")
        self.app.resume_stdio()
        self.update_data()

# ─────────────────────────────────────────────────────────────────────────────
# Mobile Layout (Narrow & Vertical)
# ─────────────────────────────────────────────────────────────────────────────

class MobileTUI(DesktopTUI):
    TITLE = "Finance Mobile"

    CSS = """
    Screen { background: black; }
    #dashboard { grid-size: 1; height: auto; margin: 0 1; }
    DashboardCard { height: 7; margin-bottom: 1; border: panel #222; }
    #menu-panel { margin: 1 1; border: none; }
    """

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mobile", action="store_true")
    args = parser.parse_args()

    if args.mobile:
        app = MobileTUI()
    else:
        app = DesktopTUI()
    app.run()
