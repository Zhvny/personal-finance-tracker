import logging

import numpy as np
import pandas as pd


class VWAPEngine:
    """
    Calculates standard session-based and anchored Volume Weighted Average Price (VWAP).
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_standard(self, df: pd.DataFrame) -> pd.Series:
        """
        Standard session-based VWAP. Resets daily if DataFrame contains multiple days.
        VWAP = sum(Typical Price * Volume) / sum(Volume)
        """
        if df is None or df.empty:
            return pd.Series(dtype='float64')

        try:
            # Ensure index is datetime-like
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            typical_price = (df['High'] + df['Low'] + df['Close']) / 3
            df_temp = df.copy()
            df_temp['tp_vol'] = typical_price * df['Volume']

            # Use index date to group by session (day)
            df_temp['date'] = df.index.date

            def group_vwap(group):
                return group['tp_vol'].cumsum() / group['Volume'].cumsum()

            # Using transform ensures the result has the same index as the original df
            vwap = df_temp.groupby('date', group_keys=False)['tp_vol'].transform(lambda x: x.cumsum()) / \
                   df_temp.groupby('date', group_keys=False)['Volume'].transform(lambda x: x.cumsum())

            return vwap

        except Exception as e:
            self.logger.error(f"Error calculating standard VWAP: {e}")
            return pd.Series(index=df.index, dtype='float64')

    def calculate_anchored(self, df: pd.DataFrame, anchor_date: str) -> pd.Series:
        """
        Anchored VWAP starting from a specific timestamp.
        """
        if df is None or df.empty:
            return pd.Series(dtype='float64')

        try:
            # Ensure index is datetime-like
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Convert anchor_date to datetime
            anchor_dt = pd.to_datetime(anchor_date)

            # Mask data before anchor date
            mask = df.index >= anchor_dt
            if not mask.any():
                self.logger.warning(f"Anchor date {anchor_date} not found in data or is after data end.")
                return pd.Series(index=df.index, dtype='float64')

            df_anchored = df[mask].copy()

            typical_price = (df_anchored['High'] + df_anchored['Low'] + df_anchored['Close']) / 3
            pv = typical_price * df_anchored['Volume']

            cumulative_pv = pv.cumsum()
            cumulative_volume = df_anchored['Volume'].cumsum()

            anchored_vwap = cumulative_pv / cumulative_volume

            # Reindex to match original df length, filling with NaN before anchor
            return anchored_vwap.reindex(df.index)

        except Exception as e:
            self.logger.error(f"Error calculating anchored VWAP: {e}")
            return pd.Series(index=df.index, dtype='float64')

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range (ATR)."""
        if len(df) < 2:
            return 0.0

        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) else 0.0

    def get_signals(self, df: pd.DataFrame, vwap_series: pd.Series) -> dict:
        """
        Generate signals based on Price vs VWAP relationship.
        """
        if df.empty or vwap_series.empty:
            return {"trend_signal": "NEUTRAL", "mean_reversion_signal": "NEUTRAL"}

        last_price = df['Close'].iloc[-1]
        last_vwap = vwap_series.iloc[-1]

        # 1. Trend Following
        # Pullback range: within 0.5% of VWAP
        dist_pct = (last_price - last_vwap) / last_vwap
        trend_signal = "NEUTRAL"

        if last_price > last_vwap and 0 <= dist_pct <= 0.005:
            trend_signal = "BULLISH_PULLBACK"
        elif last_price < last_vwap and -0.005 <= dist_pct <= 0:
            trend_signal = "BEARISH_PULLBACK"

        # 2. Mean Reversion
        atr = self._calculate_atr(df)
        threshold = 2.5 * atr if atr > 0 else 0.05 * last_vwap # Fallback to 5% if no ATR

        dist_abs = abs(last_price - last_vwap)
        mr_signal = "NEUTRAL"

        if dist_abs > threshold:
            if last_price > last_vwap:
                mr_signal = "EXTENDED_UP"
            else:
                mr_signal = "EXTENDED_DOWN"

        return {
            "trend_signal": trend_signal,
            "mean_reversion_signal": mr_signal,
            "last_price": last_price,
            "last_vwap": last_vwap,
            "dist_pct": dist_pct,
            "threshold": threshold
        }
