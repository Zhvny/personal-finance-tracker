
import logging
import math
import os
import time
from pathlib import Path

from textual import work
from textual.app import App
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import DataTable, Footer, Header, Input, ProgressBar, RichLog, Static, TabbedContent, TabPane

logger = logging.getLogger(__name__)

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.models import TradingSignal
from apps.cli.stock_analyzer.domain.portfolio_manager import PortfolioManager
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.infrastructure.macro_repository import MacroRepository
from apps.cli.stock_analyzer.infrastructure.repository import StockRepository
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer


# Set up simple logging capture for the TUI
class LogHandler(logging.Handler):
    def __init__(self, target):
        super().__init__()
        self.target = target
    def emit(self, record):
        try:
            msg = self.format(record)
            self.target.write(f"[dim]{msg}[/]\n")
        except Exception:
            # Fallback to prevent recursive logging failures
            pass

def _sig_color(s):
    return {
        TradingSignal.STRONG_BUY: "bold bright_green",
        TradingSignal.BUY: "bold green",
        TradingSignal.ACCUMULATE: "bold cyan",
        TradingSignal.WAIT: "bold yellow",
        TradingSignal.AVOID: "bold red",
        TradingSignal.SELL: "bold magenta",
        TradingSignal.STRONG_SELL: "bold white on red"
    }.get(s, "white")
def _tier_color(t): return {"HIGH":"bold bright_green", "MEDIUM":"bold green", "LOW":"bold yellow", "NO_TRADE":"bold red"}.get(t, "white")
def _pct_color(v): return "green" if v > 0 else ("red" if v < 0 else "white")

def _ticker_cat(t):
    f = DataFetcher()
    n = f.normalize(t)
    if n.endswith(".JK"): return "idx"
    if n.endswith("-USD"): return "crypto"
    if n.endswith("=F"): return "commodities"
    if n.endswith("=X"): return "currencies"
    return "us"

class DetailScreen(ModalScreen):
    def __init__(self, res): super().__init__(); self.r = res
    def compose(self):
        # DCDS Robust Formatting for DetailScreen
        if self.r.dcds is None:
            dcds_val = "SYNCING"
        elif self.r.dcds == 0.0 and not self.r.is_commodity:
            dcds_val = "N/A"
        else:
            dcds_val = f"{self.r.dcds:+.2f}"

        yield Vertical(
            Static(f"Detail: {self.r.ticker}"),
            Static(f"CSS Score: {self.r.css} ({self.r.css_tier})"),
            Static(f"Confluence Score: {self.r.score}/10.0"),
            Static(f"DXY Divergence (DCDS): {dcds_val}"),
            Static("--- ML Sniper (Honest XGBoost) ---"),
            Static(f"ML Signal: {self.r.ml_signal}"),
            Static(f"ML Prob: {self.r.ml_prob:.4f} | Sniper: {'[bold green]YES[/]' if self.r.is_selective else '[dim]NO[/]'}"),
            Static("--- Strategy ---"),
            Static(f"Support: {self.r.support} | Resistance: {self.r.resistance}"),
            Static(f"Stop Loss: {self.r.stop_loss} | Take Profit: {self.r.take_profit}"),
            Static("--- Risk & Performance ---"),
            Static(f"Expectancy: {self.r.expectancy}"),
            Static(f"Win Rate: {self.r.win_rate*100:.1f}% | RR: {self.r.risk_reward_ratio}"),
            Static(f"Kelly %: {self.r.kelly_fraction*100:.1f}%"),
            Static(f"Position Size: {self.r.position_size} units"),
            Static("--- Macro ---"),
            Static(f"Vol Regime: {self.r.vol_regime}"),
            Static(f"Macro Regime: {self.r.macro_regime}"),
            Static(f"Consumer Sentiment: {self.r.csi}"),
            Static(f"1W Forecast: {self.r.forecast_1w}"),
            Static(f"1M Forecast: {self.r.forecast_1m}"),
            Static("--- Advanced Strategies ---"),
            Static(f"AMT State: {self.r.amt_state} | Structure: {self.r.market_structure}"),
            Static(f"POC: {self.r.poc:.2f} | VAH: {self.r.vah:.2f} | VAL: {self.r.val:.2f}"),
            Static(f"VWAP: {self.r.vwap:.2f} | Cum Delta: {self.r.cumulative_delta:,.0f}"),
            Static(f"FVG: {'[bold red]DETECTED[/]' if self.r.fvg_present else '[dim]NONE[/]'}"),
            Static(self._render_vp_ascii(), id="vp_chart"),
            Static(self._render_of_summary(), id="of_summary"),
            id="detail_outer"
        )

    def _render_vp_ascii(self):
        if not self.r.profile_summary: return "[dim]No Profile Data[/]"
        max_vol = max(v for p, v in self.r.profile_summary) if self.r.profile_summary else 1
        width = 20
        lines = ["[bold underline]Volume Profile (Intraday)[/]"]
        for price, vol in reversed(self.r.profile_summary):
            bar_len = int((vol / max_vol) * width)
            bar = "█" * bar_len

            # 1. Base color (blue) or POC color (magenta)
            is_poc = abs(price - self.r.poc) < (self.r.poc * 0.002)
            color = "magenta" if is_poc else "blue"

            # 2. Check for Absorption (Yellow overlay)
            # Absorption is identified by high volume nodes with minimal price movement
            is_absorbed = any(abs(price - az) < (price * 0.001) for az in self.r.absorption_zones)
            if is_absorbed:
                color = "yellow"
                bar = "▓" * bar_len # Different character for absorption

            label = ""
            if is_poc: label = " [bold magenta]POC[/]"
            elif abs(price - self.r.vah) < (self.r.vah * 0.002): label = " [cyan]VAH[/]"
            elif abs(price - self.r.val) < (self.r.val * 0.002): label = " [cyan]VAL[/]"

            if is_absorbed: label += " [bold yellow]ABS[/]"

            lines.append(f"{price:8.2f} | [bold {color}]{bar:<{width}}[/] {label}")
        return "\n".join(lines)

    def _render_of_summary(self):
        if not self.r.footprint_data: return "[dim]No Footprint Data[/]"
        try:
            latest_ts = sorted(self.r.footprint_data.keys())[-1]
            bins = self.r.footprint_data[latest_ts]
            lines = [f"[bold underline]Order Flow ({latest_ts[-8:]})[/]"]
            sorted_prices = sorted(bins.keys(), reverse=True)
            # Show top 8 bins around highest volume or mid
            for price in sorted_prices[:10]:
                data = bins[price]
                b, s = data['buy_vol'], data['sell_vol']
                imb = ""
                if b > s * 3 and b > 100: imb = "[bold green]B-IMB[/]"
                elif s > b * 3 and s > 100: imb = "[bold red]S-IMB[/]"
                lines.append(f"{price:8.2f} | {b:6.0f} x {s:6.0f} {imb}")
            return "\n".join(lines)
        except: return "[dim]Footprint error[/]"

    def on_key(self, event):
        if event.key == "escape": self.app.pop_screen()

class MarketAnalyzerApp(App):
    CSS = """
    Screen { background: #0c0d10; } 
    DataTable { height: 1fr; border: none; } 
    #ticker_input { margin: 1 1; border: tall #333333; }
    TabbedContent { height: 1fr; }
    #detail_outer { padding: 2 4; background: #1a1b1e; border: tall #555; }
    
    #status_panel { 
        height: 5; 
        background: #1a1b1e; 
        color: #eee; 
        padding: 1 2; 
        border-top: double #333333;
    }
    #status_text { text-style: bold; height: 2; color: #5fafff; }
    ProgressBar { width: 100%; height: 1; margin-top: 1; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("slash", "search", "Search"),
        ("o", "open", "Detail"),
        ("f", "toggle_favorite", "Fav")
    ]

    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.portfolio_mgr = PortfolioManager()
        self.stock_repo = StockRepository()
        # Shared fetcher and analyzer — reused across all tickers to share cache + SPY data
        self._shared_fetcher = DataFetcher()
        self._shared_analyzer = None  # Built after macro init
        self.macro_repo = MacroRepository(FREDFetcher(self.config), self._shared_fetcher)
        self._cache = {}
        self._all_tickers = []
        self._load_all_tickers()
        self.macro_context = {'rrm':0,'ycmo':0,'lpi':0.5,'icm':0,'errf_mult':1.0, 'regime': 'NEUTRAL'}

    def _load_all_tickers(self):
        _BASE = Path(__file__).resolve().parent.parent
        list_path = _BASE / "list.txt"
        if os.path.exists(list_path):
            with open(list_path) as f:
                self._all_tickers = [l.strip().upper() for l in f if l.strip() and not l.startswith("#") and ":" not in l]

    def compose(self):
        yield Header()
        with TabbedContent():
            with TabPane("ALL", id="tab_all"): yield DataTable(id="main_table")
            with TabPane("FAVORITES", id="tab_favorites"): yield DataTable(id="favorites_table")
            with TabPane("PORTFOLIO", id="tab_portfolio"): yield DataTable(id="portfolio_table")
            with TabPane("IDX", id="tab_idx"): yield DataTable(id="idx_table")
            with TabPane("US", id="tab_us"): yield DataTable(id="us_table")
            with TabPane("CRYPTO", id="tab_crypto"): yield DataTable(id="crypto_table")
            with TabPane("COMM", id="tab_commodities"): yield DataTable(id="commodities_table")
            with TabPane("CURR", id="tab_currencies"): yield DataTable(id="currencies_table")
            with TabPane("FRED", id="tab_fred"): yield DataTable(id="fred_table")
            with TabPane("SYSTEM", id="tab_system"): yield RichLog(id="system_log", markup=True)
        yield Input(placeholder="Search ticker (e.g. BBCA, BTC, EURIDR=X) / to focus", id="ticker_input", suggester=SuggestFromList(self._all_tickers))
        with Vertical(id="status_panel"):
            yield Static("SYSTEM READY", id="status_text", markup=True)
            yield ProgressBar(id="progress", show_percentage=True)
        yield Footer()

    def on_mount(self):
        # Explicit keys for columns to avoid sort-by-label crashes
        # format: (label, key)
        main_cols = [
            ("Sig", "col_sig"),
            ("CSS", "col_css"),
            ("ML Sniper", "col_ml_sniper"),
            ("Prob", "col_prob"),
            ("Score", "col_score"),
            ("Price", "col_price"),
            ("% Chg", "col_pct_chg"),
            ("Vol", "col_vol"),
            ("DCDS", "col_dcds"),
            ("MRZG", "col_mrzg"),
            ("Ticker", "col_ticker")
        ]

        tids = ("main_table", "favorites_table", "idx_table", "us_table", "crypto_table", "commodities_table", "currencies_table")
        for tid in tids:
            table = self.query_one(f"#{tid}", DataTable)
            for label, key in main_cols:
                table.add_column(label, key=key)

        portfolio_cols = [
            ("Sig", "col_sig"),
            ("CSS", "col_css"),
            ("Ticker", "col_ticker"),
            ("Price", "col_price"),
            ("% Chg", "col_pct_chg"),
            ("ML", "col_ml"),
            ("SL", "col_sl"),
            ("TP", "col_tp"),
            ("DCDS", "col_dcds"),
            ("MRZG", "col_mrzg")
        ]
        p_table = self.query_one("#portfolio_table", DataTable)
        for label, key in portfolio_cols:
            p_table.add_column(label, key=key)

        self.query_one("#fred_table", DataTable).add_columns("Indicator", "Value", "Change", "Macro Influence")

        self.system_log = self.query_one("#system_log", RichLog)
        self.progress = self.query_one("#progress", ProgressBar)
        self.status_text = self.query_one("#status_text", Static)

        # Capture logs
        handler = LogHandler(self.system_log)
        logging.getLogger().addHandler(handler)

        self.system_log.write("[bold blue]System initialized with Machine Learning Engine.[/]\n")

        self._update_fred()
        self._auto_load_all()

    async def on_input_submitted(self, event):
        v = event.value.strip().upper()
        if v:
            self.system_log.write(f"[bold cyan]>[/] Analyzing: {v}\n")
            self.run_analysis(v.split())
            event.input.value = ""

    def action_search(self): self.query_one("#ticker_input").focus()
    def action_refresh(self):
        self.system_log.write("[bold yellow]![/] Refreshing all data...\n")
        self._update_fred()
        self._auto_load_all()

    def action_toggle_favorite(self):
        try:
            active_tab = self.query_one(TabbedContent).active
            if active_tab == "tab_fred" or active_tab == "tab_system": return

            if active_tab == "tab_all": table_id = "main_table"
            else: table_id = active_tab.replace("tab_", "") + "_table"

            table = self.query_one(f"#{table_id}", DataTable)
            if table and table.row_count > 0:
                row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
                ticker = row_key.value if row_key else None
                if ticker:
                    is_fav = self.stock_repo.toggle_favorite(ticker)
                    status = "ADDED TO" if self.stock_repo.is_favorite(ticker) else "REMOVED FROM"
                    self.system_log.write(f"[bold magenta]*[/] {ticker} {status} favorites.\n")
                    if ticker in self._cache:
                        self._add_row(self._cache[ticker])
        except Exception as e:
            self.system_log.write(f"[bold red]ERR[/] toggle_favorite: {e}\n")

    def action_open(self):
        try:
            active_tab = self.query_one(TabbedContent).active
            self.system_log.write(f"[dim]Opening detail for tab: {active_tab}[/]\n")

            if active_tab == "tab_all": table_id = "main_table"
            elif active_tab == "tab_fred" or active_tab == "tab_system":
                self.system_log.write("[yellow]WARN[/] No detail for this tab.\n")
                return
            else: table_id = active_tab.replace("tab_", "") + "_table"

            table = self.query_one(f"#{table_id}", DataTable)
            if table and table.row_count > 0:
                row_index = table.cursor_row
                # Textual DataTable row key retrieval
                row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
                ticker = row_key.value if row_key else None

                if ticker and ticker in self._cache:
                    self.system_log.write(f"[dim]Pushing DetailScreen for {ticker}[/]\n")
                    self.push_screen(DetailScreen(self._cache[ticker]))
                else:
                    self.system_log.write(f"[yellow]WARN[/] Ticker {ticker} not in cache.\n")
            else:
                self.system_log.write("[yellow]WARN[/] Table empty or not found.\n")
        except Exception as e:
            self.system_log.write(f"[bold red]ERR[/] action_open: {e}\n")
            logging.error(f"action_open error: {e}", exc_info=True)

    def _auto_load_all(self):
        """Batch load tickers from list, portfolio, and favorites."""
        self._load_all_tickers()
        self.system_log.write("[dim]Scanning list.txt, Portfolio, and Favorites...[/]\n")
        positions = self.portfolio_mgr.load_positions()
        p_tickers = [p['ticker'] for p in positions]
        f_tickers = self.stock_repo.get_favorites()
        all_to_run = list(dict.fromkeys(self._all_tickers + p_tickers + f_tickers))

        if all_to_run:
            self.system_log.write(f"[bold magenta]*[/] Batch loading {len(all_to_run)} tickers ({len(f_tickers)} favorites)...\n")
            self.run_analysis(all_to_run)
        else:
            self.system_log.write("[yellow]WARN[/] No tickers found.\n")

    @work(exclusive=False, thread=True)
    def analyze_single_ticker(self, ticker, macro_context, dxy_df=None):
        try:
            self.call_from_thread(self.status_text.update, f"PROCESSING: [bold white]{ticker}[/]")

            # Reuse shared analyzer — preserves SPY cache and DataFetcher cache across all tickers
            analyzer = self._shared_analyzer
            if analyzer is None:
                analyzer = StockAnalyzer(
                    self._shared_fetcher, DataCleaner(), IndicatorEngine(), ScoringEngine(),
                    self.config, macro_context, macro_repo=self.macro_repo
                )
            res = analyzer.analyze_ticker(ticker, dxy_df=dxy_df)
            if res:
                self.call_from_thread(self._add_row, res)
                self.call_from_thread(self.system_log.write, f"[bold green]OK[/] {ticker} (CSS: {res.css:.1f} | ML: {res.ml_signal})\n")
            else:
                self.call_from_thread(self.system_log.write, f"[bold yellow]WARN[/] No data for {ticker}\n")
        except Exception as e:
            self.call_from_thread(self.system_log.write, f"[bold red]ERR[/] {ticker}: {e}\n")
        finally:
            self.call_from_thread(self.progress.advance, 1)
            if self.progress.progress >= self.progress.total:
                self.call_from_thread(self.status_text.update, "[bold green]BATCH COMPLETE[/]")

    @work(exclusive=True, thread=True)
    def run_analysis(self, tickers):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            # 1. Fetch Macro Context & DXY (only if not already initialized)
            self.call_from_thread(self.status_text.update, "FETCHING MACRO REGIME...")
            self.call_from_thread(lambda: setattr(self.progress, 'total', len(tickers)))
            self.call_from_thread(lambda: setattr(self.progress, 'progress', 0))

            if not self.macro_repo.is_initialized:
                self.macro_repo.initialize()

            self.macro_context = self.macro_repo.get_fred_context()
            dxy_df = self.macro_repo.get_dxy()

            stale_msg = " [bold red](STALE)[/]" if self.macro_context.get('is_stale') else ""
            self.call_from_thread(self.system_log.write, f"Macro Regime: [bold cyan]{self.macro_context.get('regime', 'NEUTRAL')}[/]{stale_msg}\n")

            # 2. Build shared analyzer once (preserves SPY cache across all tickers)
            self._shared_analyzer = StockAnalyzer(
                self._shared_fetcher, DataCleaner(), IndicatorEngine(), ScoringEngine(),
                self.config, self.macro_context, macro_repo=self.macro_repo
            )

            # 3. Pre-warm SPY cache once in the main worker before parallelism
            self.call_from_thread(self.system_log.write, "[dim]Pre-warming SPY cache...[/]\n")
            try:
                self._shared_analyzer._get_spy()
            except Exception:
                pass

            # 4. Process tickers in parallel batches (max 4 concurrent to avoid Yahoo rate-limiting)
            BATCH_SIZE = 4
            self.call_from_thread(self.system_log.write, f"[dim]Running {len(tickers)} tickers in parallel batches of {BATCH_SIZE}[/]\n")
            for i in range(0, len(tickers), BATCH_SIZE):
                batch = tickers[i:i + BATCH_SIZE]
                with ThreadPoolExecutor(max_workers=BATCH_SIZE) as ex:
                    futs = {ex.submit(self.analyze_single_ticker, t, self.macro_context, dxy_df): t for t in batch}
                    for fut in as_completed(futs):
                        try: fut.result()
                        except Exception as e:
                            t = futs[fut]
                            self.call_from_thread(self.system_log.write, f"[red]ERR batch {t}: {e}[/]\n")
                # Small delay between batches only
                if i + BATCH_SIZE < len(tickers):
                    time.sleep(0.3)
        except Exception as e:
            self.call_from_thread(self.system_log.write, f"[bold red]FATAL worker error: {e}[/]\n")
            self.call_from_thread(self.status_text.update, "[bold red]WORKER CRASHED[/]")

    def _add_row(self, r):
        # Runs in main thread
        pct = ((r.current_price - r.prev_close)/r.prev_close)*100 if r.prev_close else 0
        mrzg_style = "bold cyan" if "LONG" in r.mrzg else ("bold red" if "SHORT" in r.mrzg else "dim")
        ml_style = "bold green" if "BUY" in r.ml_signal else ("bold red" if "SELL" in r.ml_signal else "dim")

        is_fav = self.stock_repo.is_favorite(r.ticker)
        fav_marker = "[bold yellow]★[/] " if is_fav else ""

        # DCDS Robust Formatting
        if r.dcds is None or (isinstance(r.dcds, float) and math.isnan(r.dcds)):
            dcds_fmt = "[dim]SYNCING[/]"
        elif r.dcds == 0.0 and not r.is_commodity:
            dcds_fmt = "[dim]N/A[/]"
        else:
            dcds_fmt = f"{r.dcds:+.2f}"

        row = (
            f"[{_sig_color(r.signal)}]{r.signal.value[:1]}[/]",
            f"{r.css:.1f}",
            f"[{ml_style}]{r.ml_signal}[/]",
            f"{r.ml_prob:.3f}",
            f"{r.score:.1f}",
            f"{r.current_price:,.2f}",
            f"[{_pct_color(pct)}]{pct:+.2f}%[/]",
            r.vol_regime[:1],
            dcds_fmt,
            f"[{mrzg_style}]{r.mrzg}[/]",
            f"{fav_marker}[dim]{r.ticker}[/]"
        )

        cat = _ticker_cat(r.ticker)
        target_tables = ["main_table", f"{cat}_table"]
        if is_fav: target_tables.append("favorites_table")
        else:
            try: self.query_one("#favorites_table", DataTable).remove_row(r.ticker)
            except Exception:
                logger.debug(f"Ticker {r.ticker} not in favorites table to remove")

        for tid in target_tables:
            try:
                table = self.query_one(f"#{tid}", DataTable)
                try: table.remove_row(r.ticker)
                except Exception:
                    pass # Expected if ticker is new
                table.add_row(*row, key=r.ticker)
                table.sort("col_css", reverse=True)
            except Exception:
                logger.exception(f"Error updating table {tid} for {r.ticker}")

        self._cache[r.ticker] = r
        self._check_and_update_portfolio_row(r)

    def _check_and_update_portfolio_row(self, r):
        # Runs in main thread
        positions = self.portfolio_mgr.load_positions()
        pos = next((p for p in positions if p["ticker"].upper() == r.ticker.upper()), None)
        if pos:
            pct = ((r.current_price - r.prev_close)/r.prev_close)*100 if r.prev_close else 0
            mrzg_style = "bold cyan" if "LONG" in r.mrzg else ("bold red" if "SHORT" in r.mrzg else "dim")
            ml_style = "bold green" if "BUY" in r.ml_signal else ("bold red" if "SELL" in r.ml_signal else "dim")

            # DCDS Robust Formatting
            if r.dcds is None or (isinstance(r.dcds, float) and math.isnan(r.dcds)):
                dcds_fmt = "[dim]SYNCING[/]"
            elif r.dcds == 0.0 and not r.is_commodity:
                dcds_fmt = "[dim]N/A[/]"
            else:
                dcds_fmt = f"{r.dcds:+.2f}"

            row = (
                f"[{_sig_color(r.signal)}]{r.signal.value[:1]}[/]",
                f"{r.css:.1f}",
                r.ticker,
                f"{r.current_price:,.2f}",
                f"[{_pct_color(pct)}]{pct:+.2f}%[/]",
                f"[{ml_style}]{r.ml_signal[:3]}[/]",
                f"{pos['sl']:,.2f}",
                f"{pos['tp']:,.2f}",
                dcds_fmt,
                f"[{mrzg_style}]{r.mrzg}[/]"
            )
            try:
                t = self.query_one("#portfolio_table", DataTable)
                try: t.remove_row(r.ticker)
                except Exception:
                    pass # Expected if ticker is new to portfolio table
                t.add_row(*row, key=r.ticker)
            except Exception:
                logger.exception(f"Error updating portfolio table for {r.ticker}")

    @work(exclusive=True, thread=True)
    def _update_fred(self):
        if not self.macro_repo.is_initialized:
            self.macro_repo.initialize()

        data = self.macro_repo.fred.fetch_all()
        table = self.query_one("#fred_table", DataTable)
        self.call_from_thread(table.clear)

        if not data:
            self.call_from_thread(table.add_row, "FRED", "No Key / Error", "0", "Check config.yaml")
        else:
            for d in data:
                self.call_from_thread(table.add_row, d['name'], f"{d['value']:.2f}", f"{d['change']:+.2f}", d['influence'])
            self.call_from_thread(table.add_row, "[bold magenta]────────────────[/]", "──────", "──────", "────────────────")
            ctx = self.macro_repo.get_fred_context()
            self.call_from_thread(table.add_row, "[bold cyan]CURRENT REGIME[/]", f"[bold]{ctx['regime']}[/]", "", "Overall market context")
            regdesc = {"rrm": "Real Rate Momentum", "ycmo": "Yield Curve", "lpi": "Liquidity Pulse", "icm": "Inflation Momentum", "csi": "Consumer Sentiment"}
            for k, v in ctx['signals'].items():
                self.call_from_thread(table.add_row, f"Layer 1: {k.upper()}", v, "", regdesc.get(k, ""))


if __name__ == "__main__": MarketAnalyzerApp().run()
