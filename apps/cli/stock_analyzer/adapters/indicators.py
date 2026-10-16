import pandas as pd

try:
    import pandas_ta as ta
    _PANDAS_TA_AVAILABLE = True
except ImportError:
    import logging as _log
    _log.getLogger(__name__).warning(
        "pandas_ta not installed — stock technical indicators will be unavailable. "
        "Install with: pip install pandas-ta"
    )
    ta = None
    _PANDAS_TA_AVAILABLE = False
import logging

import numpy as np

from apps.cli.stock_analyzer.adapters.cache import TTL_TECHNICALS, ticker_cache


class IndicatorEngine:
    """Adapter for computing technical indicators using pandas-ta."""

    @ticker_cache(ttl=TTL_TECHNICALS, cache_type="technicals")
    def compute(self, df: pd.DataFrame, ticker: str = None, spy_df: pd.DataFrame = None) -> pd.DataFrame:
        # --- ROBUST COLUMN NORMALIZATION ---
        # yfinance/pandas-ta can be inconsistent with casing. Force standardization.
        # Handle MultiIndex: use the first level for column mapping
        def get_col_name(c):
            return c[0] if isinstance(c, tuple) else c

        col_map = {get_col_name(c).lower(): c for c in df.columns}
        clean_df = pd.DataFrame(index=df.index)

        target_cols = ['open', 'high', 'low', 'close', 'volume']
        for target in target_cols:
            source = col_map.get(target)
            if source:
                series = df[source]
                # If multi-index (Ticker, Field), flatten it
                if isinstance(series, pd.DataFrame):
                    series = series.iloc[:, 0]
                clean_df[target.capitalize()] = series
            else:
                # Critical fallback: If Close is missing, try Adj Close
                if target == 'close' and 'adj close' in col_map:
                    clean_df['Close'] = df[col_map['adj close']]
                else:
                    clean_df[target.capitalize()] = np.nan

        df = clean_df.ffill().bfill() # Immediate gap fill
        EPS = 1e-8

        # Guard: pandas_ta unavailable — populate all indicator columns with defaults
        if ta is None:
            logging.debug('[IndicatorEngine] pandas_ta not available; returning degraded indicators (all zeros).')
            zero_cols = [
                'RET', 'MA_DIST', 'ADX', 'ALPHA', 'CORR',
                'ema50', 'ema200', 'ma20', 'ma50', 'rsi',
                'macd_line', 'macd_signal', 'macd_hist', 'atr',
                'bb_lower', 'bb_mid', 'bb_upper', 'stoch_k', 'stoch_d',
                'ema50_slope', 'vol_ma20', 'obv', 'obv_ma20', 'obv_slope',
                'atr7', 'atr28', 'vr', 'range_pos', 'vol_spike',
                'smfd_daily', 'smfd_5d', 'smfd_10d', 'z_price', 'z_rsi',
                'rsi_divergence', 'sr_support', 'sr_resistance', 'dcds',
            ]
            for col in zero_cols:
                df[col] = 0.0
            df['stoch_k'] = 50.0
            df['stoch_d'] = 50.0
            df['bb_lower'] = df['bb_mid'] = df['bb_upper'] = df.get('Close', pd.Series(0.0, index=df.index))
            return df

        # --- ML FEATURES ---
        df['RET'] = df['Close'].pct_change().fillna(0)

        # MA_DIST (Z-score style)
        ma20 = df['Close'].rolling(20, min_periods=1).mean()
        std20 = df['Close'].rolling(20, min_periods=1).std().fillna(0)
        df['MA_DIST'] = (df['Close'] - ma20) / (std20 + EPS)

        # ADX
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx is not None:
            df['ADX'] = adx.iloc[:, 0].fillna(0.0)
        else:
            df['ADX'] = 0.0

        # ALPHA & CORR (Market Relative)
        if spy_df is not None:
            # Force TZ naive for market baseline
            spy_c = spy_df['Close'].squeeze()
            if spy_c.index.tz is not None:
                spy_c.index = spy_c.index.tz_localize(None)

            spy_c = spy_c.reindex(df.index).ffill()
            spy_ret = spy_c.pct_change().fillna(0)
            df['ALPHA'] = df['RET'] - spy_ret
            df['CORR'] = df['RET'].rolling(20, min_periods=1).corr(spy_ret).fillna(0)
        else:
            df['ALPHA'] = 0.0
            df['CORR'] = 0.0

        # --- ORIGINAL INDICATORS ---
        # Moving Averages (EMA for faster trend response)
        df['ema50'] = ta.ema(df['Close'], length=50)
        df['ema200'] = ta.ema(df['Close'], length=200)

        # Keep old ones for backward compatibility if needed, or focus on new strategy
        df['ma20'] = ta.sma(df['Close'], length=20)
        df['ma50'] = ta.sma(df['Close'], length=50)

        # RSI
        df['rsi']  = ta.rsi(df['Close'], length=14)

        # MACD
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df['macd_line']   = macd.iloc[:, 0].fillna(0)
            df['macd_signal'] = macd.iloc[:, 1].fillna(0)
            df['macd_hist']   = macd.iloc[:, 2].fillna(0)
        else:
            df['macd_line'] = df['macd_signal'] = df['macd_hist'] = 0

        # ATR
        atr = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        if atr is not None:
            df['atr'] = atr.fillna(0)
        else:
            df['atr'] = 0.0

        # Bollinger Bands (20, 2)
        bbands = ta.bbands(df['Close'], length=20, std=2)
        if bbands is not None and not bbands.empty:
            df['bb_lower'] = bbands.filter(like='BBL').iloc[:, 0].fillna(df['Close'])
            df['bb_mid']   = bbands.filter(like='BBM').iloc[:, 0].fillna(df['Close'])
            df['bb_upper'] = bbands.filter(like='BBU').iloc[:, 0].fillna(df['Close'])
        else:
            df['bb_lower'] = df['bb_mid'] = df['bb_upper'] = df['Close']

        # Stochastic Oscillator (14, 3, 3)
        stoch = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        if stoch is not None and not stoch.empty:
            df['stoch_k'] = stoch.filter(like='STOCHk').iloc[:, 0].fillna(50)
            df['stoch_d'] = stoch.filter(like='STOCHd').iloc[:, 0].fillna(50)
        else:
            df['stoch_k'] = df['stoch_d'] = 50

        # Slope EMA50 (Trend Direction) - Using percentage change for better scaling
        df['ema50_slope'] = df['ema50'].pct_change(3).fillna(0)

        # Volume Indicators
        df['vol_ma20'] = ta.sma(df['Volume'], length=20)

        # OBV (On-Balance Volume)
        df['obv'] = ta.obv(df['Close'], df['Volume'])
        if df['obv'] is not None:
            df['obv'] = df['obv'].fillna(0)
        else:
            df['obv'] = 0.0

        df['obv_ma20'] = ta.sma(df['obv'], length=20)
        df['obv_slope'] = df['obv'].diff(3).fillna(0)

        # --- NEW QUANT INDICATORS ---

        # Indicator 8: Adaptive ATR Volatility Regime (AAVR)
        atr7 = ta.atr(df['High'], df['Low'], df['Close'], length=7)
        df['atr7'] = atr7.fillna(0) if atr7 is not None else 0.0

        atr28 = ta.atr(df['High'], df['Low'], df['Close'], length=28)
        df['atr28'] = atr28.fillna(0) if atr28 is not None else 0.0

        df['vr']    = df['atr7'] / (df['atr28'] + 1e-9)

        # Indicator 9: Smart Money Flow Divergence (SMFD)
        df['range_pos'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'] + 1e-9)
        df['vol_spike'] = df['Volume'] / (df['vol_ma20'] + 1e-9)

        def daily_smfd(row):
            if pd.isna(row['vol_spike']) or pd.isna(row['range_pos']): return 0
            if row['vol_spike'] > 1.5 and row['range_pos'] > 0.80:  return  1
            if row['vol_spike'] > 1.5 and row['range_pos'] < 0.20:  return -1
            return 0

        df['smfd_daily'] = df.apply(daily_smfd, axis=1)
        df['smfd_5d']    = df['smfd_daily'].rolling(5).sum().fillna(0)
        df['smfd_10d']   = df['smfd_daily'].rolling(10).sum().fillna(0)

        # Indicator 10: Mean Reversion Z-Score (MRZG)
        window_z = 20
        df['z_price'] = (df['Close'] - df['Close'].rolling(window_z).mean()) / (df['Close'].rolling(window_z).std().fillna(0) + 1e-9)
        df['z_rsi']   = (df['rsi'] - df['rsi'].rolling(window_z).mean()) / (df['rsi'].rolling(window_z).std().fillna(0) + 1e-9)

        # RSI Divergence
        df['rsi_divergence'] = self._detect_rsi_divergence(df)

        # Support and Resistance
        df['sr_support'], df['sr_resistance'] = self._detect_sr(df)

        return df

    def _detect_sr(self, df: pd.DataFrame, window: int = 60) -> tuple[pd.Series, pd.Series]:
        """Detect static Support and Resistance levels using local minima and maxima."""
        # Rolling min/max to find levels - Using center=False for real-time relevance
        supports = df['Low'].rolling(window=window, center=False).min()
        resistances = df['High'].rolling(window=window, center=False).max()

        return supports.ffill(), resistances.ffill()

    def compute_mrc(self, df: pd.DataFrame, macro_context: dict) -> pd.DataFrame:
        """Indicator 7: Macro-RSI Composite (MRC)"""
        rrm_s    = macro_context.get('rrm', 0)
        ycmo_s   = macro_context.get('ycmo', 0)
        dxy_chg  = macro_context.get('dxy_20d_chg', 0)

        macro_score = (
            -(1 if rrm_s > 0 else (-1 if rrm_s < 0 else 0))  * 0.40 +
             (1 if ycmo_s > 0 else (-1 if ycmo_s < 0 else 0)) * 0.30 +
            -(1 if dxy_chg > 0 else (-1 if dxy_chg < 0 else 0)) * 0.30
        )

        df['macro_score_mrc'] = macro_score
        df['mrc'] = df['rsi'] * (1 + 0.5 * macro_score)
        return df

    def compute_dcds(self, df: pd.DataFrame, dxy_df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """Indicator 5: DXY-Commodity Divergence Score (DCDS)"""
        logging.info(f'[DXY] correlation window: {window}')
        if dxy_df is None or dxy_df.empty:
            # Degraded state: dcds is not applicable/available
            df['dcds'] = np.nan
            return df

        # Robust Column Extraction (handles MultiIndex)
        def get_close(target_df):
            if 'Close' in target_df.columns:
                series = target_df['Close']
                if isinstance(series, pd.DataFrame):
                    return series.iloc[:, 0]
                return series
            return None

        dxy_s = get_close(dxy_df)
        comm_s = get_close(df)

        if dxy_s is None or comm_s is None:
            df['dcds'] = np.nan
            return df

        dxy = dxy_s.copy()
        comm = comm_s.copy()

        if comm.index.tz is not None:
            comm.index = comm.index.tz_localize(None)

        if dxy.index.tz is not None:
            dxy.index = dxy.index.tz_localize(None)

        # Align on dates
        comm = comm.reindex(dxy.index, method='ffill')

        # Robust Z-Score calculation
        comm_std = comm.rolling(window).std().fillna(0)
        dxy_std  = dxy.rolling(window).std().fillna(0)

        comm_z = (comm - comm.rolling(window).mean()) / (comm_std + 1e-9)
        dxy_z  = (dxy  - dxy.rolling(window).mean())  / (dxy_std + 1e-9)

        logging.info(f'[DXY] normalization result | comm_z_last: {comm_z.iloc[-1]:.4f} | dxy_z_last: {dxy_z.iloc[-1]:.4f}')

        df['dcds'] = comm_z + dxy_z # > 0 -> commodity stronger than USD predicts
        logging.info(f'[DXY] divergence calculated | dcds_last: {df["dcds"].iloc[-1]:.4f}')
        return df

    def _detect_rsi_divergence(self, df: pd.DataFrame, window: int = 14) -> pd.Series:
        """Return +1 = bullish div, -1 = bearish div, 0 = no divergence."""
        # Simple implementation: compare current low/high with previous window's low/high
        price_lows = df['Close'].rolling(window).min()
        rsi_lows   = df['rsi'].rolling(window).min()

        # Bullish: Price lower low, RSI higher low
        bullish_div = (df['Close'] < price_lows.shift(1)) & \
                      (df['rsi'] > rsi_lows.shift(1)) & \
                      (df['rsi'] < 40) # Typical oversold area

        # Bearish: Price higher high, RSI lower high
        price_highs = df['Close'].rolling(window).max()
        rsi_highs   = df['rsi'].rolling(window).max()

        bearish_div = (df['Close'] > price_highs.shift(1)) & \
                      (df['rsi'] < rsi_highs.shift(1)) & \
                      (df['rsi'] > 60) # Typical overbought area

        result = pd.Series(0, index=df.index)
        result[bullish_div] = 1
        result[bearish_div] = -1
        return result
