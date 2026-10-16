# Upgrade Roadmap — Stock Analyzer

**Document Type:** Upgrade & Feature Roadmap  
**Date:** April 2026  
**Codebase version:** v3.0 (April 2026 — as inspected)  
**References:** `architechture.md` v3.0

---

## Status: Yang Sudah Selesai di v3.0

Items berikut dari roadmap v2.0 sudah **DONE** di codebase saat ini:

| Item | Status | Notes |
|---|---|---|
| Ganti `liquidity_score = 1.0` | ✅ Done | Volume + OBV scoring (max 2.0 pts) |
| Fix `max_workers=1` | ✅ Done | `AppConfig.max_workers = 5` default |
| Naikkan retry count | ✅ Done | 3 attempts (dari 2), backoff 2–8s |
| IDX `.JK` auto-suffix | ✅ Done | `_normalize()` dengan whitelist crypto/US |
| Config file (`config.yaml`) | ✅ Done | `AppConfig.load()` via pyyaml |
| OBV ke IndicatorEngine | ✅ Done | `obv`, `obv_ma20`, `obv_slope` live |
| RSI divergence detection | ✅ Done | `rsi_divergence` column di indicators |
| SQLite cache | ✅ Done | Market-aware TTL, `cache.db` |
| Backtesting engine | ✅ Done | `use_cases/backtester.py` dengan walk-forward |
| Streamlit dashboard | ⏳ Pending | Masih belum ada |
| Telegram notifikasi | ⏳ Pending | Masih belum ada |
| Unit tests | ⏳ Pending | Masih belum ada |

---

## Prioritas Ringkasan

| Tier | Kriteria | Jumlah item |
|---|---|---|
| 🔴 P1 — Critical | Bug / correctness / observability yang langsung ngaruh ke keputusan | 3 |
| 🟠 P2 — High | Fitur yang langsung ngaruh ke usability dan reliability | 6 |
| 🟡 P3 — Medium | Fitur yang nambah value signifikan | 6 |
| 🟢 P4 — Low | Nice-to-have, polish, future-proofing | 5 |

---

## P1 — Critical (harus selesai sebelum pakai untuk keputusan nyata)

---

### P1-1 · Fix silent exception swallowing di `analyze_ticker()`

**File:** `use_cases/analyzer.py`  
**Masalah:** Sekarang ada bare `except: return None` tanpa logging sama sekali. Kalau fetch gagal, cleaner return None, atau scoring error — semua diam-diam di-skip. Tidak ada cara tau kenapa ticker di-skip.

**Fix:**

```python
def analyze_ticker(self, ticker: str) -> StockResult | None:
    try:
        df = self.fetcher.fetch(ticker, period=self.config.fetch_period)
        df = self.cleaner.clean(df, ticker)
        if df is None:
            logging.warning(f"[Analyzer] {ticker}: discarded by cleaner (insufficient/dirty data)")
            return None
        df = self.indicators.compute(df)
        if len(df) < 2:
            logging.warning(f"[Analyzer] {ticker}: insufficient rows after indicators")
            return None
        last, prev = df.iloc[-1], df.iloc[-2]
        score, scores = self.scoring.calculate_composite_score(last, self.config)
        if "status" in scores:
            logging.warning(f"[Analyzer] {ticker}: scoring returned status flag, skipping")
            return None
        signal = self.scoring.generate_signal(score, last, self.config)
        # ... build StockResult
    except ValueError as e:
        logging.warning(f"[Analyzer] {ticker}: {e}")
        return None
    except Exception as e:
        logging.error(f"[Analyzer] {ticker}: unexpected error — {type(e).__name__}: {e}")
        return None
```

**Dampak:** Setiap skip sekarang punya alasan yang bisa di-trace. Debugging batch 50+ ticker jadi jauh lebih mudah.

---

### P1-2 · Backtester — surface hasil ke TUI

**File:** `infrastructure/tui.py`  
**Masalah:** `use_cases/backtester.py` sudah ada dan fungsional, tapi tidak ada cara run dari TUI. User harus run `backtest_ticker.py` via CLI.

**Implementasi — tambah tab Backtest di TUI:**

```python
# infrastructure/tui.py — tambah TabPane
with TabPane("BACKTEST", id="tab_backtest"):
    yield DataTable(id="backtest_table")

# Tambah binding
BINDINGS = [
    ...,
    ("b", "run_backtest", "Backtest"),
]

def action_run_backtest(self) -> None:
    """Run backtest untuk ticker yang sedang aktif di input."""
    ticker = self.query_one("#ticker_input").value.strip()
    if not ticker:
        return
    self._run_backtest_worker(ticker)

@work(exclusive=False, thread=True)
def _run_backtest_worker(self, ticker: str) -> None:
    from use_cases.backtester import Backtester
    bt = Backtester(self.fetcher, self.cleaner, self.indicators, self.scoring, self.config)
    try:
        result = bt.run(ticker, period="2y")
        self.app.call_from_thread(self._display_backtest_result, result)
    except Exception as e:
        self.app.call_from_thread(
            self.query_one(Log).write_line, f"[BACKTEST ERROR] {ticker}: {e}"
        )

def _display_backtest_result(self, result) -> None:
    table = self.query_one("#backtest_table", DataTable)
    table.add_row(
        result.ticker,
        str(result.total_trades),
        f"{result.win_rate:.1f}%",
        f"{result.total_return_pct:.1f}%",
        f"{result.avg_return_pct:.2f}%",
        f"{result.max_drawdown_pct:.1f}%",
    )
```

**Dampak:** User bisa langsung validasi sinyal historis dari TUI, tanpa keluar ke CLI.

---

### P1-3 · Unit tests untuk scoring dan cleaner

**File baru:** `tests/` folder  
**Masalah:** Tidak ada test coverage sama sekali. Setiap kali refactor scoring engine atau cleaner, tidak ada safety net.

**Struktur:**

```
tests/
├── conftest.py            # fixture: sample OHLCV DataFrame
├── test_scoring.py        # unit test ScoringEngine
├── test_indicators.py     # kolom output IndicatorEngine
├── test_cleaner.py        # edge cases: zero volume, invalid OHLC
└── test_fetcher.py        # normalize() logic
```

**Contoh `tests/conftest.py`:**

```python
import pandas as pd
import numpy as np
import pytest

@pytest.fixture
def sample_ohlcv():
    """250 bars of synthetic OHLCV — enough for EMA200."""
    n = 250
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({
        'Open':   close * 0.999,
        'High':   close * 1.005,
        'Low':    close * 0.995,
        'Close':  close,
        'Volume': np.random.randint(1_000_000, 5_000_000, n),
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
```

**Contoh `tests/test_scoring.py`:**

```python
import pandas as pd
import pytest
from domain.scoring import ScoringEngine
from domain.models import TradingSignal
from adapters.indicators import IndicatorEngine

def make_row(**kwargs) -> pd.Series:
    defaults = dict(
        Close=100.0, ema50=95.0, ema200=90.0,
        macd_hist=0.3, stoch_k=60.0, stoch_d=55.0,
        rsi=55.0, rsi_divergence=0,
        Volume=1_500_000, vol_ma20=1_000_000,
        obv_slope=500_000.0, atr=2.0,
        bb_lower=94.0, bb_upper=106.0
    )
    return pd.Series({**defaults, **kwargs})

def test_buy_signal_near_perfect_row():
    row = make_row()
    score, breakdown = ScoringEngine.calculate_composite_score(row)
    signal = ScoringEngine.generate_signal(score, row)
    assert signal == TradingSignal.BUY
    assert score >= 8.5

def test_bearish_ema200_kills_trend_score():
    row = make_row(Close=85.0)   # Close < ema200=90 → bearish
    score, breakdown = ScoringEngine.calculate_composite_score(row)
    assert breakdown['trend'] == 0.0

def test_high_atr_triggers_avoid():
    row = make_row(atr=12.0)    # atr/price = 0.12 > 0.10 gate
    score, breakdown = ScoringEngine.calculate_composite_score(row)
    # Override score to be high so we test only the gate
    signal = ScoringEngine.generate_signal(5.0, row)
    assert signal == TradingSignal.AVOID

def test_volume_score_varies_with_actual_volume():
    low_vol  = make_row(Volume=100, vol_ma20=1_000_000)
    high_vol = make_row(Volume=2_000_000, vol_ma20=1_000_000)
    _, lo = ScoringEngine.calculate_composite_score(low_vol)
    _, hi = ScoringEngine.calculate_composite_score(high_vol)
    assert hi['liquidity'] > lo['liquidity']

def test_bullish_divergence_adds_score():
    no_div  = make_row(rsi_divergence=0)
    with_div = make_row(rsi_divergence=1, rsi=38.0)  # rsi < 40 untuk bullish
    s_no,  _ = ScoringEngine.calculate_composite_score(no_div)
    s_div, _ = ScoringEngine.calculate_composite_score(with_div)
    assert s_div > s_no
```

**Contoh `tests/test_fetcher.py`:**

```python
from adapters.fetcher import DataFetcher

def test_normalize_idx_auto_suffix():
    f = DataFetcher()
    assert f.normalize("BBCA")   == "BBCA.JK"
    assert f.normalize("TLKM")   == "TLKM.JK"

def test_normalize_crypto():
    f = DataFetcher()
    assert f.normalize("BTC")    == "BTC-USD"
    assert f.normalize("ETH")    == "ETH-USD"

def test_normalize_us_whitelist():
    f = DataFetcher()
    assert f.normalize("NVDA")   == "NVDA"
    assert f.normalize("AAPL")   == "AAPL"

def test_normalize_already_has_suffix():
    f = DataFetcher()
    assert f.normalize("BBCA.JK") == "BBCA.JK"
    assert f.normalize("GC=F")    == "GC=F"
```

---

## P2 — High (ngaruh langsung ke usability)

---

### P2-1 · Naikkan retry dari 3 ke 5 + tambah jitter

**File:** `adapters/fetcher.py`  
**Masalah:** 3 attempts masih borderline untuk batch 100+ ticker. Yahoo Finance rate limiter sering butuh 3–4 hit sebelum sukses, jadi attempt ke-3 sudah final.

```python
from tenacity import wait_random

@retry(
    stop=stop_after_attempt(5),                                     # naik dari 3
    wait=wait_exponential(multiplier=1, min=2, max=15) + wait_random(0, 2),  # tambah jitter
    retry=retry_if_not_exception_type(ValueError),
    reraise=True,
)
def fetch(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    ...
```

Jitter (`wait_random(0, 2)`) penting untuk batch mode — tanpa jitter, semua threads retry bersamaan pada detik yang sama, triggering rate limit lagi.

---

### P2-2 · Export CSV dari TUI

**File:** `infrastructure/tui.py`  
**Masalah:** Tidak ada cara export hasil analisis ke file dari TUI.

```python
BINDINGS = [
    ...,
    ("e", "export_csv", "Export CSV"),
]

def action_export_csv(self) -> None:
    import csv
    from datetime import datetime
    
    # Export dari tab yang sedang aktif
    active_tab = self.query_one(TabbedContent).active
    table_id = active_tab.replace("tab_", "") + "_table"
    try:
        table = self.query_one(f"#{table_id}", DataTable)
    except:
        table = self.query_one("#main_table", DataTable)
    
    filename = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header dari kolom DataTable
        writer.writerow([col.label for col in table.columns.values()])
        for i in range(table.row_count):
            writer.writerow([str(v) for v in table.get_row_at(i)])
    
    self.query_one(Log).write_line(f"[EXPORT] {filename} ({table.row_count} rows)")
```

---

### P2-3 · Validasi SL/TP portfolio saat load

**File:** `domain/portfolio_manager.py`  
**Masalah:** `portfolio.json` bisa punya SL/TP yang sudah obsolete. Tidak ada warning kalau posisi sudah seharusnya di-exit.

```python
def validate_levels(self, position: dict, current_price: float) -> list[str]:
    """Return list warnings untuk posisi ini."""
    warnings = []
    sl = position.get('sl')
    tp = position.get('tp')
    entry = position.get('entry')
    
    if sl and current_price <= sl:
        pnl_pct = (current_price - entry) / entry * 100 if entry else 0
        warnings.append(
            f"⚠️  STOP LOSS BREACH — current {current_price:.2f} ≤ SL {sl:.2f} "
            f"(P/L: {pnl_pct:.1f}%)"
        )
    if tp and current_price >= tp:
        pnl_pct = (current_price - entry) / entry * 100 if entry else 0
        warnings.append(
            f"✅  TAKE PROFIT HIT — current {current_price:.2f} ≥ TP {tp:.2f} "
            f"(P/L: {pnl_pct:.1f}%)"
        )
    return warnings
```

Panggil di TUI saat Portfolio tab di-load — emit warning ke Log panel.

---

### P2-4 · IDX macro series di FRED tab

**File:** `adapters/fred_fetcher.py`  
**Masalah:** Semua FRED series sekarang US-centric. IDX investor perlu konteks makro Indonesia.

yfinance sendiri bisa fetch beberapa proxy IDX macro:

```python
IDX_MACRO_PROXIES = {
    "USDIDR=X":  ("IDR/USD Exchange Rate",  "IDR melemah → tekanan impor, cost naik untuk perusahaan bahan baku asing"),
    "EIDO":      ("iShares MSCI Indonesia ETF", "Proxy untuk foreign fund flow ke IDX"),
    "^JKSE":     ("IHSG Index",             "Benchmark utama pasar saham Indonesia"),
}

# Di FREDFetcher atau fetcher baru IDXMacroFetcher:
def fetch_idx_macro(self) -> list[dict]:
    results = []
    for ticker, (name, influence) in self.IDX_MACRO_PROXIES.items():
        try:
            df = yf.Ticker(ticker).history(period="5d")
            if not df.empty:
                last = df.iloc[-1]['Close']
                prev = df.iloc[-2]['Close'] if len(df) >= 2 else last
                results.append({
                    'name': name, 'value': last,
                    'change': last - prev, 'date': str(df.index[-1].date()),
                    'influence': influence
                })
        except: pass
    return results
```

Tampilkan di FRED tab sebagai section terpisah "IDX Macro".

---

### P2-5 · Detail panel score breakdown saat row diklik

**File:** `infrastructure/tui.py`  
**Masalah:** DataTable hanya menampilkan nilai final. Tidak ada breakdown per sub-score, tidak ada konteks mengapa sinyal BUY/WAIT/AVOID.

```python
class DetailScreen(ModalScreen):
    """Modal screen yang muncul saat row diklik — tampilkan score breakdown."""
    
    DEFAULT_CSS = """
    DetailScreen { align: center middle; }
    #detail_box { 
        width: 60; height: auto; border: double $accent;
        background: $surface; padding: 1 2;
    }
    """
    
    def __init__(self, result: StockResult):
        super().__init__()
        self.r = result
    
    def compose(self) -> ComposeResult:
        r = self.r
        rr = r.take_profit - r.current_price
        risk = r.current_price - r.stop_loss
        rr_ratio = rr / risk if risk > 0 else 0
        
        content = f"""[bold]{r.ticker}[/bold]  [{r.signal.value}]
─────────────────────────────────
Score      : {r.score:.2f} / 10.0
  Trend    : {r.trend_score:.2f} / 3.0
  Momentum : {r.momentum_score:.2f} / 3.0
  RSI/Div  : {r.volatility_score:.2f} / 2.0
  Vol/OBV  : {r.liquidity_score:.2f} / 2.0
─────────────────────────────────
Price      : {r.current_price}
Stop Loss  : {r.stop_loss}  ({((r.stop_loss - r.current_price) / r.current_price * 100):.1f}%)
Take Profit: {r.take_profit}  (+{((r.take_profit - r.current_price) / r.current_price * 100):.1f}%)
Risk/Reward: 1:{rr_ratio:.1f}
─────────────────────────────────
1W Forecast: {r.forecast_1w}
1M Forecast: {r.forecast_1m}
Support    : {r.support}
Resistance : {r.resistance}
─────────────────────────────────
[dim]Press ESC to close[/dim]"""
        
        with Vertical(id="detail_box"):
            yield Static(content)
    
    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()

# Di MarketAnalyzerApp:
def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    # Ambil ticker dari cache result
    row_key = str(event.row_key.value)
    if row_key in self._cache:
        self.push_screen(DetailScreen(self._cache[row_key]))
```

---

### P2-6 · Watchlist persistence — simpan/load dari TUI

**File:** `infrastructure/tui.py` + `watchlist.txt`  
**Masalah:** Setiap session baru, harus input ticker ulang. Tidak ada cara save watchlist dari TUI.

```python
BINDINGS = [
    ...,
    ("ctrl+s", "save_watchlist", "Save Watchlist"),
    ("ctrl+l", "load_watchlist", "Load Watchlist"),
]

def action_save_watchlist(self) -> None:
    tickers = list(self._cache.keys())
    if not tickers:
        self.query_one(Log).write_line("[WARN] No analyzed tickers to save.")
        return
    with open("watchlist.txt", "w") as f:
        f.write("\n".join(tickers))
    self.query_one(Log).write_line(f"[SAVE] Watchlist saved — {len(tickers)} tickers")

def action_load_watchlist(self) -> None:
    try:
        with open("watchlist.txt") as f:
            tickers = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        if tickers:
            self.query_one(Log).write_line(f"[LOAD] {len(tickers)} tickers dari watchlist.txt")
            self._run_batch_analysis(tickers)
    except FileNotFoundError:
        self.query_one(Log).write_line("[WARN] watchlist.txt tidak ditemukan")
```

---

## P3 — Medium (signifikan tapi tidak blocking)

---

### P3-1 · Multi-timeframe scoring — daily + weekly confluence

**File:** `use_cases/analyzer.py` + `domain/scoring.py`  
**Alasan:** Sinyal yang konfirmasi di daily sekaligus weekly jauh lebih reliable.

```python
def analyze_ticker(self, ticker: str) -> StockResult | None:
    # Fetch dua timeframe
    df_daily  = self.fetcher.fetch(ticker, period="1y",  interval="1d")
    df_weekly = self.fetcher.fetch(ticker, period="3y", interval="1wk")
    
    df_daily  = self.cleaner.clean(df_daily, ticker)
    df_weekly = self.cleaner.clean(df_weekly, ticker)
    
    if df_daily is None: return None
    
    df_daily  = self.indicators.compute(df_daily)
    
    daily_score, scores = self.scoring.calculate_composite_score(df_daily.iloc[-1], self.config)
    
    # Weekly scoring (opsional — kalau data cukup)
    weekly_score = daily_score  # fallback
    if df_weekly is not None and len(df_weekly) >= 52:
        df_weekly = self.indicators.compute(df_weekly)
        weekly_score, _ = self.scoring.calculate_composite_score(df_weekly.iloc[-1], self.config)
    
    # Blended: 60% daily + 40% weekly
    blended_score = 0.60 * daily_score + 0.40 * weekly_score
    
    # Weekly trend gate: kalau weekly AVOID, downgrade apapun yang di atas WAIT
    weekly_signal = self.scoring.generate_signal(weekly_score, df_daily.iloc[-1], self.config)
    if weekly_signal == TradingSignal.AVOID and blended_score >= 8.5:
        blended_score = 7.0   # Turunkan ke WAIT
    
    # Build result dengan blended_score
    signal = self.scoring.generate_signal(blended_score, df_daily.iloc[-1], self.config)
    ...
```

---

### P3-2 · Screener mode — scan LQ45 / S&P500 otomatis

**File baru:** `use_cases/screener.py` + `data/watchlists/`  
**Alasan:** Sekarang harus input ticker manual. Screener mode bisa scan semua konstituen indeks dan filter yang layak.

```python
# use_cases/screener.py
import os

WATCHLISTS = {
    "lq45":   "data/watchlists/lq45.txt",
    "idx30":  "data/watchlists/idx30.txt",
    "sp500":  "data/watchlists/sp500.txt",
    "custom": "watchlist.txt",
}

class Screener:
    def __init__(self, analyzer):
        self.analyzer = analyzer
    
    def screen(self, watchlist: str = "lq45", min_score: float = 6.0) -> list:
        path = WATCHLISTS.get(watchlist, watchlist)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Watchlist tidak ditemukan: {path}")
        
        tickers = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
        logging.info(f"[Screener] Scanning {len(tickers)} tickers from {watchlist}")
        
        results = self.analyzer.run_batch(tickers, max_workers=self.analyzer.config.max_workers)
        filtered = [r for r in results if r.score >= min_score]
        logging.info(f"[Screener] {len(filtered)}/{len(results)} passed score filter ≥{min_score}")
        return filtered
```

**Tambah binding di TUI:**

```python
("ctrl+w", "open_screener", "Screener")
```

---

### P3-3 · Telegram notifikasi otomatis

**File baru:** `infrastructure/notifier.py` + `infrastructure/scheduler.py`  
**Alasan:** Supaya tidak harus buka TUI untuk tau ada sinyal baru. Daily scan otomatis jam 17:15 WIB.

```python
# infrastructure/notifier.py
import requests, os, logging

class TelegramNotifier:
    def __init__(self):
        self.token   = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            logging.warning("[Notifier] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set")
            return False
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
            return r.ok
        except Exception as e:
            logging.error(f"[Notifier] Failed to send: {e}")
            return False

# infrastructure/scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
from infrastructure.notifier import TelegramNotifier
from domain.models import TradingSignal
from use_cases.analyzer import StockAnalyzer
from domain.config import AppConfig

def daily_scan():
    config   = AppConfig.load()
    analyzer = StockAnalyzer(...)   # init dengan dependencies
    notifier = TelegramNotifier()
    
    tickers  = [l.strip() for l in open("watchlist.txt") if l.strip() and not l.startswith("#")]
    results  = analyzer.run_batch(tickers, max_workers=config.max_workers)
    
    buys     = [r for r in results if r.signal == TradingSignal.BUY]
    waits    = [r for r in results if r.signal == TradingSignal.WAIT]
    
    if buys or waits:
        date_str = datetime.now().strftime("%d %b %Y %H:%M")
        msg = f"<b>📊 Stock Scan — {date_str}</b>\n\n"
        
        if buys:
            msg += "<b>🟢 BUY Signals</b>\n"
            for r in buys:
                msg += (f"  <b>{r.ticker}</b>  Score: {r.score:.1f}\n"
                        f"  Price: {r.current_price}  SL: {r.stop_loss}  TP: {r.take_profit}\n\n")
        
        if waits:
            msg += "<b>🟡 WATCH List</b>\n"
            for r in waits[:5]:   # Max 5 untuk tidak flood
                msg += f"  <b>{r.ticker}</b>  Score: {r.score:.1f}\n"
        
        notifier.send(msg)
        logging.info(f"[Scheduler] Sent — {len(buys)} BUY, {len(waits)} WAIT")

scheduler = BlockingScheduler(timezone="Asia/Jakarta")
scheduler.add_job(daily_scan, "cron", hour=17, minute=15)
scheduler.start()
```

---

### P3-4 · CLI entry point dengan Typer

**File baru:** `cli.py` di root project  
**Masalah:** `quick_check.py` hardcoded ticker dan `analyze_holdings.py` hardcoded data. Perlu CLI yang proper dan composable.

```python
# cli.py
import typer
app = typer.Typer(help="Stock Analyzer CLI")

@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="Ticker symbol (e.g. BBCA, BTC, NVDA)"),
    period: str = typer.Option("1y", help="Data period (1mo, 3mo, 6mo, 1y, 2y)"),
):
    """Analisis satu ticker dan tampilkan hasilnya."""
    ...

@app.command()
def batch(
    tickers: list[str] = typer.Argument(..., help="Daftar ticker"),
    workers: int = typer.Option(5, help="Max parallel workers"),
    output: str = typer.Option(None, help="CSV output file"),
):
    """Analisis batch beberapa ticker sekaligus."""
    ...

@app.command()
def portfolio():
    """Analisis semua posisi di portfolio.json."""
    ...

@app.command()
def backtest(
    ticker: str = typer.Argument(..., help="Ticker symbol"),
    period: str = typer.Option("2y", help="Backtest period"),
):
    """Backtest sinyal scoring untuk satu ticker."""
    ...

@app.command()
def screen(
    watchlist: str = typer.Option("lq45", help="lq45 / idx30 / sp500 / custom"),
    min_score: float = typer.Option(6.0, help="Minimum score filter"),
):
    """Scan semua ticker di watchlist dan tampilkan yang layak."""
    ...

if __name__ == "__main__":
    app()
```

**Usage:**

```bash
python cli.py analyze BBCA
python cli.py batch BBCA TLKM ASII --workers 3 --output result.csv
python cli.py portfolio
python cli.py backtest NVDA --period 3y
python cli.py screen --watchlist lq45 --min-score 7.0
```

---

### P3-5 · Fundamental data blending (PE, ROE, debt/equity)

**File:** `adapters/fetcher.py` + `domain/scoring.py`  
**Alasan:** Technical-only system akan miss value traps dan overvalued momentum stocks.

```python
# adapters/fetcher.py — tambah method
def fetch_fundamentals(self, symbol: str) -> dict:
    try:
        info = yf.Ticker(symbol).info
        return {
            'pe_ratio':    info.get('trailingPE'),
            'pb_ratio':    info.get('priceToBook'),
            'roe':         info.get('returnOnEquity'),
            'debt_equity': info.get('debtToEquity'),
            'market_cap':  info.get('marketCap'),
        }
    except Exception as e:
        logging.warning(f"[Fetcher] Fundamentals unavailable for {symbol}: {e}")
        return {}
```

**Integrasi ke scoring — opsional, tidak break existing flow:**

```python
# Fundamental overlay (optional, hanya kalau tersedia)
def fundamental_adjustment(score: float, fundamentals: dict) -> float:
    if not fundamentals:
        return score  # Tidak ada data → tidak ubah score
    pe = fundamentals.get('pe_ratio')
    roe = fundamentals.get('roe')
    
    adj = 0.0
    if pe and 5 < pe < 20:   adj += 0.5   # Reasonable valuation bonus
    if pe and pe > 50:        adj -= 0.5   # Expensive penalty
    if roe and roe > 0.15:    adj += 0.5   # Strong profitability
    
    return max(0.0, score + adj)
```

---

### P3-6 · Logging ke file (rotating)

**File:** `main.py` atau `domain/config.py`  
**Alasan:** Sekarang log hanya ke TUI widget. Kalau TUI di-close, semua log hilang. Susah debugging masalah yang terjadi di malam hari saat run scheduled.

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_file: str = "analyzer.log"):
    """Setup dual logging: file + console."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    
    # File handler: rotating 5MB, 3 backup files
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024,
        backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s  %(levelname)-8s  %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root.addHandler(file_handler)
```

Panggil di `main.py` sebelum app start. Log file `analyzer.log` bisa di-inspect setelah session tanpa buka TUI ulang.

---

## P4 — Low (polish & future-proofing)

---

### P4-1 · Streamlit dashboard alternatif TUI

**File baru:** `infrastructure/dashboard.py`  
**Alasan:** TUI tidak support chart visual (candlestick, RSI panel). Streamlit bisa jadi UI alternatif yang lebih kaya secara visual.

```python
# infrastructure/dashboard.py
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def render_chart(ticker: str, df, result):
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=[ticker, "RSI", "MACD"]
    )
    # Row 1: Candlestick + EMA50/200 + BB
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name=ticker
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['ema50'],  name='EMA50',  line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['ema200'], name='EMA200', line=dict(color='red',    dash='dash')), row=1, col=1)
    # Row 2: RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], name='RSI', line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red",   row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    # Row 3: MACD histogram
    fig.add_trace(go.Bar(x=df.index, y=df['macd_hist'], name='MACD Hist'), row=3, col=1)
    fig.update_layout(height=800, showlegend=True, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
```

---

### P4-2 · Docker + GitHub Actions CI

**File baru:** `Dockerfile`, `.github/workflows/test.yml`  
**Alasan:** Supaya bisa deploy ke VPS/cloud untuk scheduled daily scan tanpa setup manual.

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
ENV TELEGRAM_TOKEN=""
ENV TELEGRAM_CHAT_ID=""
CMD ["python", "infrastructure/scheduler.py"]
```

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/ -v --tb=short
```

---

### P4-3 · `StockResult` tambah metadata field

**File:** `domain/models.py`  
**Alasan:** Saat ini tidak ada context tentang data yang digunakan untuk analisis — berapa bar, tanggal candle terakhir, timeframe mana.

```python
@dataclass
class StockResult:
    # ... existing fields ...
    timestamp: datetime = field(default_factory=datetime.now)
    
    # New metadata fields:
    analysis_period: str = "1y"
    data_rows_used: int = 0
    last_candle_date: str = ""       # tanggal bar terakhir yang dipakai
    weekly_score: float = 0.0        # kalau multi-timeframe aktif
    is_multi_timeframe: bool = False  # flag untuk UI display
```

---

### P4-4 · Portfolio CRUD dari TUI tanpa edit JSON manual

**File:** `infrastructure/tui.py` + `domain/portfolio_manager.py`  
**Masalah:** Tambah/hapus posisi harus edit `portfolio.json` manual. Error-prone dan tidak nyaman.

```python
BINDINGS = [
    ...,
    ("a", "add_position", "Add Position"),
    ("d", "delete_position", "Delete Position"),
]

def action_add_position(self) -> None:
    """Aktifkan input mode untuk tambah posisi baru."""
    ticker_input = self.query_one("#ticker_input", Input)
    ticker_input.placeholder = "ADD: TICKER ENTRY_PRICE (e.g. BBCA 8500)"
    self._input_mode = "add_position"

def on_input_submitted(self, event: Input.Submitted) -> None:
    if self._input_mode == "add_position":
        self._handle_add_position(event.value)
        self._input_mode = "search"
        event.input.placeholder = "Search ticker..."
    else:
        self._handle_ticker_search(event.value)

def _handle_add_position(self, value: str) -> None:
    parts = value.strip().split()
    if len(parts) >= 2:
        ticker, entry = parts[0], float(parts[1])
        self.portfolio_mgr.add_position(ticker=ticker, entry=entry)
        self.query_one(Log).write_line(f"[PORTFOLIO] Added {ticker} @ {entry}")
```

---

### P4-5 · Cache inspector dari TUI

**File:** `infrastructure/tui.py`  
**Alasan:** Sekarang `inspect_cache.py` ada tapi harus run dari CLI. Perlu cara lihat cache stats dari TUI.

```python
BINDINGS = [
    ...,
    ("ctrl+i", "inspect_cache", "Cache Stats"),
]

def action_inspect_cache(self) -> None:
    from adapters.cache import DataCache
    stats = DataCache().stats()
    self.query_one(Log).write_line(
        f"[CACHE] {stats['entries']} entries, oldest: {stats['oldest']}"
    )
```

---

## Urutan Implementasi yang Disarankan

```
Minggu 1 — Stability & Observability
  P1-1  Fix silent exceptions di analyze_ticker
  P1-3  Unit tests (conftest + test_scoring + test_fetcher)
  P2-1  Naikkan retry ke 5 + jitter
  P3-6  Rotating log file

Minggu 2 — UX & Validation
  P1-2  Surface backtest ke TUI
  P2-2  Export CSV dari TUI
  P2-5  Detail panel saat row diklik
  P2-3  Validasi SL/TP portfolio saat load

Minggu 3 — Features
  P2-4  IDX macro series di FRED tab
  P2-6  Watchlist save/load dari TUI
  P3-4  CLI entry point dengan Typer
  P4-3  Metadata fields di StockResult

Minggu 4 — Automation & Analytics
  P3-3  Telegram notifier + scheduler
  P3-1  Multi-timeframe scoring (daily + weekly)
  P3-2  Screener mode (LQ45/SP500)
  P3-5  Fundamental data blending

Milestone — Scale & Polish
  P4-1  Streamlit dashboard alternatif
  P4-2  Docker + GitHub Actions CI
  P4-4  Portfolio CRUD dari TUI
  P4-5  Cache inspector dari TUI
```

---

## Dependency Baru yang Dibutuhkan

| Package | Untuk | Priority |
|---|---|---|
| `pytest` | Unit tests | P1-3 |
| `apscheduler` | Scheduled daily scan | P3-3 |
| `typer` | CLI entry point | P3-4 |
| `plotly` + `streamlit` | Dashboard alternatif | P4-1 |

Semua bisa di-install via `pip install <package>`. Tambahkan ke `requirements.txt` setelah install.

---

*Upgrade Roadmap — April 2026 · v3.0 · stock_analyzer*
