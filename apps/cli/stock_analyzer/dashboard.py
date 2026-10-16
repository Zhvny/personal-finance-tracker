import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# Find the directory that contains 'stock_analyzer'
_P = _HERE.parent
while _P.name != "stock_analyzer" and _P.parent != _P:
    _P = _P.parent
_PROJECT_ROOT = str(_P.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from __future__ import annotations

import logging
import threading

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Label, Static

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer


class StockDashboard(App):
    TITLE = "ZHVNY_STOCK_CORE"

    CSS = """
    Screen { background: #000; color: #fff; }
    #main { padding: 1; }
    .header { height: 3; border-bottom: solid #222; content-align: center middle; text-style: bold; }
    DataTable { background: #000; color: #fff; border: none; height: 1fr; margin: 1 0; }
    DataTable > .datatable--header { background: #111; color: #fff; text-style: bold; }
    DataTable > .datatable--cursor { background: #222; color: #fff; }
    Input { background: #000; border: none; border-bottom: solid #222; color: #fff; }
    Input:focus { border-bottom: solid #fff; }
    #status { height: 1; background: #111; color: #444; text-align: center; }
    """

    BINDINGS = [Binding("q", "quit", "Quit"), Binding("r", "refresh", "Refresh")]

    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.macro_context = {'rrm':0,'ycmo':0,'lpi':0.5,'icm':0,'errf_mult':1.0, 'regime': 'NEUTRAL'}
        self.dxy_df = None
        self.fetcher = DataFetcher()
        self.analyzer = StockAnalyzer(self.fetcher, DataCleaner(), IndicatorEngine(), ScoringEngine(), self.config, self.macro_context)
        self.results = {}
        self.favorites = []
        self.macro_ready = threading.Event() # Ensure macro fetch completes at least once

    def compose(self) -> ComposeResult:
        yield Label("STOCK_ANALYZER", classes="header")
        with Vertical(id="main"):
            yield Static("WAITING_FOR_MACRO...", id="macro-status")
            yield DataTable(id="stock-table")
            yield Input(placeholder="ADD_TICKER_TO_SCAN...")
        yield Static("SYSTEM_STABLE", id="status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("TICKER", "PRICE", "CSS", "SIGNAL", "1W_FC", "1M_FC")
        table.cursor_type = "row"
        self.update_all()
        # AC #3: Auto-refresh every 5 minutes
        self.set_interval(300, self.update_all)

    @work(thread=True)
    def update_all(self):
        # 1. Fetch Macro Context
        self.call_from_thread(self.query_one("#macro-status", Static).update, "FETCHING_MACRO_DATA...")
        fred = FREDFetcher(self.config)
        try:
            brent = self.fetcher.fetch("CL=F", period="1y")
            self.dxy_df = self.fetcher.fetch("DX-Y.NYB", period="1y")
            self.macro_context = fred.get_macro_context(brent)
        except Exception as e:
            logging.error(f"Macro fetch error: {e}")

        stale_msg = " [STALE]" if self.macro_context.get('is_stale') else ""
        self.call_from_thread(self.query_one("#macro-status", Static).update, f"REGIME: {self.macro_context['regime']}{stale_msg}")

        # Update analyzer with real macro context
        self.analyzer.macro_context = self.macro_context
        self.macro_ready.set() # Allow ticker analysis to proceed

        watchlist = ["NVDA", "BTC-USD", "BBCA.JK", "GC=F", "TSLA", "META", "TLKM.JK", "ADRO.JK"]
        self.favorites = []

        list_path = ROOT / "list.txt"
        if list_path.exists():
            with open(list_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.endswith(":"):
                        continue

                    is_fav = False
                    if line.startswith("*"):
                        is_fav = True
                        line = line[1:].strip()

                    t_upper = line.upper()
                    if t_upper not in watchlist:
                        watchlist.append(t_upper)
                    if is_fav and t_upper not in self.favorites:
                        self.favorites.append(t_upper)

        for t in watchlist:
            try:
                res = self.analyzer.analyze_ticker(t, dxy_df=self.dxy_df)
                if res:
                    res.is_favorite = (t in self.favorites)
                    self.results[t] = res
                    self.call_from_thread(self.refresh_table)
            except Exception:
                logging.exception(f"Error analyzing ticker {t}")

    def refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        # AC #4: Sort by is_favorite DESC, then CSS Score DESC
        sorted_res = sorted(self.results.values(), key=lambda x: (x.is_favorite, x.css), reverse=True)
        for r in sorted_res:
            ticker_display = f"⭐ {r.ticker}" if r.is_favorite else r.ticker
            table.add_row(
                ticker_display,
                f"{r.current_price:,.0f}",
                f"{r.css:.1f}",
                r.signal.value,
                f"{r.forecast_1w:,.0f}",
                f"{r.forecast_1m:,.0f}",
                key=r.ticker
            )

    @on(Input.Submitted)
    def handle_search(self, event: Input.Submitted):
        t = event.value.strip().upper()
        if t:
            self.run_worker(self.analyze_one(t))
            event.input.value = ""

    async def analyze_one(self, t: str):
        # Ensure macro data is loaded before manual analysis
        if not self.macro_ready.is_set():
            self.query_one("#status", Static).update("WAITING_FOR_MACRO_TO_INITIALIZE...")
            await self.run_thread(self.macro_ready.wait)
            self.query_one("#status", Static).update("SYSTEM_STABLE")

        res = await self.run_thread(lambda: self.analyzer.analyze_ticker(t, dxy_df=self.dxy_df))
        if res:
            res.is_favorite = (t in self.favorites)
            self.results[t] = res
            self.refresh_table()

    def run_thread(self, func):
        import asyncio
        return asyncio.get_event_loop().run_in_executor(None, func)

if __name__ == "__main__":
    StockDashboard().run()
