import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to sys.path to access packages
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path: sys.path.insert(0, str(_ROOT))

try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
    HAS_POSTGRES = True
except ImportError: HAS_POSTGRES = False

logger = logging.getLogger(__name__)

class DataLoader:
    REQUIRED_COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
        self.repo = None
        if HAS_POSTGRES:
            try:
                DatabaseManager.initialize()
                self.repo = PostgresOHLCVRepository()
            except Exception as e: logger.warning(f"Failed to initialize PostgreSQL repository: {e}")
    def _validate_df(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        # Standardize MultiIndex if needed (yfinance artifacts)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]

        # 1. Column Integrity Check
        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            logger.warning(f"Ticker {ticker} rejected: Missing required columns {missing}")
            return pd.DataFrame()

        # 2. Minimum History Check
        if len(df) < 50:
            logger.warning(f"Ticker {ticker} rejected: Insufficient data points ({len(df)} < 50)")
            return pd.DataFrame()

        # 3. Data Quality (NaN Ratio) Check
        nan_ratio = df[self.REQUIRED_COLUMNS].isnull().mean().max()
        if nan_ratio > 0.10:
            logger.warning(f"Ticker {ticker} rejected: High NaN ratio ({nan_ratio:.1%})")
            return pd.DataFrame()

        # 4. Zero/Negative Price Check (at least in recent history)
        last_closes = df['Close'].tail(5)
        if (last_closes <= 0).any() or last_closes.isnull().any():
            logger.warning(f"Ticker {ticker} rejected: Recent invalid prices (Zero/NaN/Negative)")
            return pd.DataFrame()

        # 5. Outlier Detection (Nonsensical Price Spikes)
        # Check for daily price changes > 1000% (10x jump) - usually data error
        # pct_change is calculated on 'Close'
        returns = df['Close'].pct_change().abs()
        if returns.max() > 10.0:
            logger.warning(f"Ticker {ticker} rejected: Detected nonsensical price spike ({returns.max():.1%})")
            return pd.DataFrame()

        return df
    def load_ticker_data(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        df = None
        if self.repo:
            try:
                df = self.repo.get(f"{ticker}_{period}_1d", period)
            except Exception:
                logger.exception("Failed to load ticker data from repository: %s", ticker)

        if df is None or df.empty:
            file_path = self.data_dir / f"{ticker}.csv"
            if not file_path.exists():
                for sub in self.data_dir.iterdir():
                    if sub.is_dir():
                        candidate = sub / f"{ticker}.csv"
                        if candidate.exists():
                            file_path = candidate
                            break
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                except Exception:
                    logger.exception("Failed to load ticker data from CSV: %s", file_path)

        return self._validate_df(df, ticker)
    def load_summary(self, summary_path: str = "results_honest/honest_summary.csv") -> pd.DataFrame:
        if not os.path.exists(summary_path): return pd.DataFrame()
        try: return pd.read_csv(summary_path)
        except: return pd.DataFrame()
