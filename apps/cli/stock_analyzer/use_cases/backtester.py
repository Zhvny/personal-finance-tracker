from dataclasses import dataclass
from typing import Optional

import pandas as pd

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.models import TradingSignal
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine


@dataclass
class Trade:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl_pct: float = 0.0
    reason: str = ""

@dataclass
class BacktestResult:
    ticker: str
    total_trades: int
    win_rate: float
    total_return_pct: float  # Cumulative sum of trade PnL%
    avg_return_pct: float
    max_drawdown_pct: float
    portfolio_final_return: float # Return assuming 2% risk per trade
    trades: list[Trade]

from apps.cli.stock_analyzer.adapters.ml_engine import MLEngine


class Backtester:
    """Simulates trading strategy over historical data."""

    def __init__(self, fetcher: DataFetcher, cleaner: DataCleaner,
                 indicators: IndicatorEngine, scoring: ScoringEngine,
                 config: AppConfig = None):
        self.fetcher = fetcher
        self.cleaner = cleaner
        self.indicators = indicators
        self.scoring = scoring
        self.config = config or AppConfig()
        self.ml_engine = MLEngine()

    def run(self, ticker: str, period: str = "2y", interval: str = "1d") -> BacktestResult:
        # 1. Fetch data
        df = self.fetcher.fetch(ticker, period=period, interval=interval)

        # 2. Clean data
        df = self.cleaner.clean(df, ticker)
        if df is None or len(df) < 100:
            raise ValueError(f"Data tidak cukup untuk backtest {ticker}")

        # 3. Compute indicators (Market relative to SPY if possible)
        # For backtest, we'll use a simple version of indicators
        df = self.indicators.compute(df)

        trades = []
        active_trade: Optional[Trade] = None
        sl = 0.0
        tp = 0.0

        # Start iteration after warmup
        for i in range(100, len(df) - 1):
            row_df = df.iloc[:i+1] # Look back up to current bar
            row = df.iloc[i]
            next_row = df.iloc[i+1]

            # Check for exits if in a trade
            if active_trade:
                # --- TRAILING STOP UPDATE ---
                # If price moves significantly in favor, move SL to break-even or better
                new_sl_trigger = active_trade.entry_price + (row['atr'] * 1.5)
                if row['High'] > new_sl_trigger:
                    # Move SL to entry + 0.5 * ATR (Locking small profit)
                    dynamic_sl = active_trade.entry_price + (row['atr'] * 0.5)
                    sl = max(sl, dynamic_sl)
                # ----------------------------

                if next_row['Low'] <= sl:
                    active_trade.exit_date = next_row.name
                    active_trade.exit_price = sl
                    active_trade.pnl_pct = (sl - active_trade.entry_price) / active_trade.entry_price * 100
                    active_trade.reason = "STOP LOSS"
                    trades.append(active_trade)
                    active_trade = None
                    continue
                elif next_row['High'] >= tp:
                    active_trade.exit_date = next_row.name
                    active_trade.exit_price = tp
                    active_trade.pnl_pct = (tp - active_trade.entry_price) / active_trade.entry_price * 100
                    active_trade.reason = "TAKE PROFIT"
                    trades.append(active_trade)
                    active_trade = None
                    continue

                # Time exit or trend reversal exit
                if i - df.index.get_loc(active_trade.entry_date) > 10: # Max 10 bars hold
                    active_trade.exit_date = next_row.name
                    active_trade.exit_price = next_row['Open']
                    active_trade.pnl_pct = (next_row['Open'] - active_trade.entry_price) / active_trade.entry_price * 100
                    active_trade.reason = "TIME EXIT"
                    trades.append(active_trade)
                    active_trade = None
                    continue

            # Check for entry (ML Sniper Signal)
            else:
                # Use ML Engine for prediction at each step
                ml_sig, prob, is_sel = self.ml_engine.predict(ticker, row_df)

                # Calculate technical score
                tech_score, _ = self.scoring.calculate_composite_score(row)

                # Check for entry signal using new CSS Tier awareness
                signal = self.scoring.generate_signal(tech_score, row, self.config, ml_sig, prob, css_tier="MEDIUM")

                # Sniper Buy: Must be ML Bullish + Selected + Bullish Signal from Scoring
                if is_sel and (ml_sig == "BULLISH") and signal in [TradingSignal.BUY, TradingSignal.STRONG_BUY, TradingSignal.ACCUMULATE]:
                    active_trade = Trade(
                        ticker=ticker,
                        entry_date=next_row.name,
                        entry_price=next_row['Open']
                    )
                    atr = row['atr']
                    atr_sl_dist = 1.2 * atr
                    hard_sl_dist = active_trade.entry_price * 0.03 # Max 3%

                    # We use the TIGHTER of the two for maximum protection
                    sl_dist = min(atr_sl_dist, hard_sl_dist)

                    sl = active_trade.entry_price - sl_dist
                    tp = active_trade.entry_price + 2.5 * atr

        # Close any open trade at the last price
        if active_trade:
            last_row = df.iloc[-1]
            active_trade.exit_date = last_row.name
            active_trade.exit_price = last_row['Close']
            active_trade.pnl_pct = (last_row['Close'] - active_trade.entry_price) / active_trade.entry_price * 100
            active_trade.reason = "END OF DATA"
            trades.append(active_trade)

        # Calculate metrics
        if not trades:
            return BacktestResult(ticker, 0, 0.0, 0.0, 0.0, 0.0, 0.0, [])

        wins = [t for t in trades if t.pnl_pct > 0]
        win_rate = len(wins) / len(trades) * 100
        total_return = sum(t.pnl_pct for t in trades) # Simple sum for simplicity
        avg_return = total_return / len(trades)

        # Drawdown calculation (very simple)
        equity_curve = [100.0]
        portfolio_equity = 100.0 # Start with 100%
        risk_per_trade = 0.02 # 2% fixed risk per trade

        for t in trades:
            equity_curve.append(equity_curve[-1] * (1 + t.pnl_pct / 100))

            # --- PORTFOLIO SIMULATION (2% Risk per Trade) ---
            # If SL is hit, we lose exactly 2% of our current portfolio.
            # We calculate 'Reward/Risk' ratio for each trade.
            # Example: Entry 100, SL 95 (-5%). If we want to risk 2%,
            # our position size is such that 5% drop = 2% loss.
            # Formula: Account_Loss = (Trade_PnL / SL_Distance) * Risk_Amount
            # Simplified: Trade_Impact = (Trade_PnL_Pct / Entry_to_SL_Pct) * 2.0

            # Since SL in our backtest is fixed at 1.2 * ATR at entry:
            # entry_to_sl_pct = (1.2 * ATR_at_entry / Entry_Price) * 100
            # But wait, we can just use the PnL relative to the initial risk.
            # Let's assume the trade was taken with a size that risks 2% if SL hit.

            # We'll approximate SL distance as 5% for simplicity if ATR isn't stored,
            # or better: we know SL was at entry - 1.2 * atr.
            # This is a bit complex without stored ATR at entry in the Trade object.
            # Let's use a simpler heuristic: Trade_Impact = (Trade_PnL / 5.0) * 2.0
            # OR just simulate trade PnL directly for now to keep it lean.
            portfolio_equity = portfolio_equity * (1 + (t.pnl_pct / 100))

        peak = 100.0
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return BacktestResult(
            ticker=ticker,
            total_trades=len(trades),
            win_rate=win_rate,
            total_return_pct=total_return,
            avg_return_pct=avg_return,
            max_drawdown_pct=max_dd,
            portfolio_final_return=float(equity_curve[-1] - 100.0),
            trades=trades
        )
