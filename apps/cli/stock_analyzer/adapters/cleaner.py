
import numpy as np
import pandas as pd

from packages.core.utils.symbol_utils import SymbolFormatter


class DataCleaner:
    """Adapter for cleaning and validating raw OHLCV data with repair strategies."""

    def clean(self, df: pd.DataFrame, ticker: str, min_rows: int = 50) -> pd.DataFrame | None:
        if df is None or df.empty:
            return None

        ticker = ticker.upper()
        market = SymbolFormatter.get_market(ticker)

        # 0. Robust Column Extraction & Standardization
        # Force standardization to a new DF to avoid duplicate/fragmented columns
        clean_df = pd.DataFrame(index=df.index)
        col_map = {c.lower(): c for c in df.columns}

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            source = col_map.get(col.lower())
            if source:
                series = df[source]
                if isinstance(series, pd.DataFrame):
                    # Handle MultiIndex or duplicate columns by picking first
                    series = series.iloc[:, 0]
                clean_df[col] = series
            else:
                # Essential Fallback: Use Adj Close for Close if missing
                if col == 'Close' and 'adj close' in col_map:
                    clean_df['Close'] = df[col_map['adj close']]
                elif col == 'Volume':
                    clean_df['Volume'] = 0.0
                else:
                    # Mark as missing to be filled or rejected later
                    clean_df[col] = np.nan

        df = clean_df

        # 0b. Drop duplicate indices
        if df.index.duplicated().any():
            df = df.loc[~df.index.duplicated(keep='last')]

        # 1. DATA REPAIR: Forward-fill / Interpolate based on market
        # ... rest of method ...
        ffill_limit = 10 if market in ["FOREX", "IDX"] else 5
        df = df.ffill(limit=ffill_limit)

        # 2. OHLC SANITY & REPAIR
        # If essential price data is completely missing, abort
        if df['Close'].isna().all(): return None

        # Filter out rows where Close is NaN (can't repair without anchor)
        df = df.dropna(subset=['Close'])

        # Repair Strategy: If High/Low/Open are invalid or NaN, use Close as proxy
        df['Open'] = df['Open'].fillna(df['Close'])
        df['High'] = df['High'].fillna(df[['Open', 'Close']].max(axis=1))
        df['Low'] = df['Low'].fillna(df[['Open', 'Close']].min(axis=1))

        # Cross-validate bounds and fix instead of drop
        df['High'] = df[['High', 'Open', 'Close']].max(axis=1)
        df['Low']  = df[['Low', 'Open', 'Close']].min(axis=1)

        # 3. Volume handling
        if market == "US":
            df = df.loc[df['Volume'] > 0]
        else:
            df['Volume'] = df['Volume'].fillna(0)

        # 4. Final Verification
        # Drop only truly broken rows (where High < Low even after repair)
        valid = (df['High'] >= df['Low']) & (df['Close'] > 0)
        df = df[valid]

        # 5. Minimum history gate
        if len(df) < min_rows:
            return None

        return df

