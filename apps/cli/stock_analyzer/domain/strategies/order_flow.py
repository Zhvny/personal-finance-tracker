import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd


class OrderFlowEngine:
    """
    Synthetic Order Flow Engine.
    Proxies tick-level order flow using 1m intraday data.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_synthetic_delta(self, intraday_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates synthetic delta from 1m bars.
        Approximation: 
        - If Close > Open: Volume is assigned to Buy Volume.
        - If Close < Open: Volume is assigned to Sell Volume.
        - If Close == Open: Volume split 50/50.
        """
        if intraday_df is None or intraday_df.empty:
            return intraday_df

        df = intraday_df.copy()

        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Initialize columns
        df['buy_vol'] = 0.0
        df['sell_vol'] = 0.0

        # Close > Open -> Aggressive buying
        df.loc[df['Close'] > df['Open'], 'buy_vol'] = df['Volume']

        # Close < Open -> Aggressive selling
        df.loc[df['Close'] < df['Open'], 'sell_vol'] = df['Volume']

        # Close == Open -> Split
        df.loc[df['Close'] == df['Open'], 'buy_vol'] = df['Volume'] / 2
        df.loc[df['Close'] == df['Open'], 'sell_vol'] = df['Volume'] / 2

        df['delta'] = df['buy_vol'] - df['sell_vol']

        # Cumulative Delta reset per session (day)
        df['cum_delta'] = df.groupby(df.index.date)['delta'].cumsum()

        return df

    def detect_divergence(self, df: pd.DataFrame, window: int = 5) -> List[Dict[str, Any]]:
        """
        Identify Price-Delta Divergence.
        - Bullish Divergence: Price Lower Low (LL) vs Delta Higher Low (HL)
        - Bearish Divergence: Price Higher High (HH) vs Delta Lower High (LH)
        """
        divergences = []
        if df is None or df.empty or 'cum_delta' not in df.columns or len(df) < window * 4:
            return divergences

        try:
            # Find local peaks and troughs in Price
            # Use a rolling window to find local extrema
            df = df.copy()
            df['is_peak'] = (df['High'] == df['High'].rolling(window=window*2+1, center=True).max())
            df['is_trough'] = (df['Low'] == df['Low'].rolling(window=window*2+1, center=True).min())

            # Extract timestamps of peaks and troughs
            peak_indices = df[df['is_peak']].index.tolist()
            trough_indices = df[df['is_trough']].index.tolist()

            # Divergence check on Troughs (Bullish)
            # We look at all significant troughs
            if len(trough_indices) >= 2:
                for i in range(len(trough_indices) - 1):
                    p1, p2 = trough_indices[i], trough_indices[i+1]

                    price_ll = df.at[p2, 'Low'] < df.at[p1, 'Low']
                    delta_hl = df.at[p2, 'cum_delta'] > df.at[p1, 'cum_delta']

                    if price_ll and delta_hl:
                        divergences.append({
                            'type': 'Bullish Divergence',
                            'timestamp': p2,
                            'price_level': float(df.at[p2, 'Low']),
                            'delta_level': float(df.at[p2, 'cum_delta']),
                            'prev_price': float(df.at[p1, 'Low']),
                            'prev_delta': float(df.at[p1, 'cum_delta'])
                        })

            # Divergence check on Peaks (Bearish)
            if len(peak_indices) >= 2:
                for i in range(len(peak_indices) - 1):
                    p1, p2 = peak_indices[i], peak_indices[i+1]

                    price_hh = df.at[p2, 'High'] > df.at[p1, 'High']
                    delta_lh = df.at[p2, 'cum_delta'] < df.at[p1, 'cum_delta']

                    if price_hh and delta_lh:
                        divergences.append({
                            'type': 'Bearish Divergence',
                            'timestamp': p2,
                            'price_level': float(df.at[p2, 'High']),
                            'delta_level': float(df.at[p2, 'cum_delta']),
                            'prev_price': float(df.at[p1, 'High']),
                            'prev_delta': float(df.at[p1, 'cum_delta'])
                        })

            return divergences

        except Exception as e:
            self.logger.error(f"Error detecting order flow divergence: {e}")
            return divergences

    def detect_absorption(self, df: pd.DataFrame, vol_window: int = 20, range_window: int = 20) -> List[Dict[str, Any]]:
        """
        Detects absorption: High volume with narrow price range.
        Suggests a large participant is absorbing aggressive orders.
        """
        absorptions = []
        if df is None or df.empty or len(df) < vol_window:
            return absorptions

        try:
            df = df.copy()
            df['range'] = df['High'] - df['Low']
            df['vol_ma'] = df['Volume'].rolling(window=vol_window).mean()
            df['range_ma'] = df['range'].rolling(window=range_window).mean()

            # Logic: Vol > 1.5 * MA and Range < 0.5 * MA
            mask = (df['Volume'] > df['vol_ma'] * 1.5) & (df['range'] < df['range_ma'] * 0.5)

            for timestamp, row in df[mask].iterrows():
                mid = (row['High'] + row['Low']) / 2
                side = "Bullish (Sellers Absorbed)" if row['Close'] >= mid else "Bearish (Buyers Absorbed)"

                absorptions.append({
                    'timestamp': timestamp,
                    'price_level': float(row['Close']),
                    'type': 'Absorption',
                    'side': side,
                    'volume': float(row['Volume']),
                    'vol_relative': float(row['Volume'] / row['vol_ma']),
                    'range_relative': float(row['range'] / row['range_ma'])
                })

            return absorptions
        except Exception as e:
            self.logger.error(f"Error detecting absorption: {e}")
            return absorptions

    def detect_exhaustion(self, df: pd.DataFrame, window: int = 10) -> List[Dict[str, Any]]:
        """
        Detects exhaustion: New price extreme with weakening delta/volume.
        """
        exhaustions = []
        if df is None or df.empty or 'delta' not in df.columns or len(df) < window:
            return exhaustions

        try:
            df = df.copy()
            df['local_high'] = df['High'].rolling(window=window).max()
            df['local_low'] = df['Low'].rolling(window=window).min()
            df['delta_ma'] = df['delta'].rolling(window=window).mean()

            for timestamp, row in df.iterrows():
                # Bearish Exhaustion: Price at high with negative/weak delta
                if row['High'] >= row['local_high']:
                    if row['delta'] <= 0 or (row['delta'] > 0 and row['delta'] < row['delta_ma'] * 0.3):
                        exhaustions.append({
                            'timestamp': timestamp,
                            'price_level': float(row['High']),
                            'type': 'Bearish Exhaustion',
                            'delta': float(row['delta']),
                            'avg_delta': float(row['delta_ma']),
                            'reason': 'Weak/negative delta at local high'
                        })

                # Bullish Exhaustion: Price at low with positive/weak delta
                if row['Low'] <= row['local_low']:
                    if row['delta'] >= 0 or (row['delta'] < 0 and abs(row['delta']) < abs(row['delta_ma']) * 0.3):
                        exhaustions.append({
                            'timestamp': timestamp,
                            'price_level': float(row['Low']),
                            'type': 'Bullish Exhaustion',
                            'delta': float(row['delta']),
                            'avg_delta': float(row['delta_ma']),
                            'reason': 'Weak/positive delta at local low'
                        })

            return exhaustions
        except Exception as e:
            self.logger.error(f"Error detecting exhaustion: {e}")
            return exhaustions

    def calculate_footprint(self, intraday_df: pd.DataFrame, bin_size: float = 0.10, window_minutes: int = 15) -> Dict[str, Any]:
        """
        Group volume by price bins within a specific time window.
        Distributes bar volume across High-Low range to approximate a footprint.
        """
        if intraday_df is None or intraday_df.empty:
            return {}

        df = intraday_df.copy()

        # Ensure we have buy/sell vol
        if 'buy_vol' not in df.columns or 'sell_vol' not in df.columns:
            df = self.calculate_synthetic_delta(df)

        footprint = {}

        try:
            # Resample to the desired window
            time_groups = df.groupby(pd.Grouper(freq=f'{window_minutes}min'))

            for timestamp, group in time_groups:
                if group.empty:
                    continue

                aggregated_bins = {}

                for _, row in group.iterrows():
                    # Calculate how many bins this bar covers
                    low = float(row['Low'])
                    high = float(row['High'])

                    # Start bin (floor to nearest bin_size)
                    start_bin = np.floor(low / bin_size) * bin_size
                    # End bin (floor of high)
                    end_bin = np.floor(high / bin_size) * bin_size

                    # List of price bins covered by the bar
                    bins = np.arange(start_bin, end_bin + bin_size/2, bin_size)
                    num_bins = len(bins)

                    if num_bins > 0:
                        # Distribute volume across bins
                        b_vol_share = float(row['buy_vol']) / num_bins
                        s_vol_share = float(row['sell_vol']) / num_bins

                        for b in bins:
                            b_rounded = round(float(b), 4)
                            if b_rounded not in aggregated_bins:
                                aggregated_bins[b_rounded] = {'buy_vol': 0.0, 'sell_vol': 0.0}
                            aggregated_bins[b_rounded]['buy_vol'] += b_vol_share
                            aggregated_bins[b_rounded]['sell_vol'] += s_vol_share

                # Convert price keys to strings for JSON compatibility if needed,
                # but for now keep as floats for downstream logic
                footprint[timestamp.isoformat()] = aggregated_bins

            return footprint

        except Exception as e:
            self.logger.error(f"Error calculating order flow footprint: {e}")
            return {}

    def detect_imbalances(self, footprint: Dict[str, Any], ratio: float = 3.0) -> List[Dict[str, Any]]:
        """
        Detects horizontal volume imbalances in footprint data.
        An imbalance occurs when Buy Vol is significantly greater than Sell Vol (or vice versa)
        at the same price level.
        For standard diagonal imbalances, use detect_diagonal_imbalances.
        """
        imbalances = []

        for timestamp_str, bins in footprint.items():
            for price, data in bins.items():
                buy = data['buy_vol']
                sell = data['sell_vol']

                if buy > sell * ratio and buy > 0:
                    imbalances.append({
                        'timestamp': timestamp_str,
                        'price': price,
                        'type': 'Buy Imbalance',
                        'ratio': buy/sell if sell > 0 else float('inf'),
                        'volume': buy
                    })
                elif sell > buy * ratio and sell > 0:
                    imbalances.append({
                        'timestamp': timestamp_str,
                        'price': price,
                        'type': 'Sell Imbalance',
                        'ratio': sell/buy if buy > 0 else float('inf'),
                        'volume': sell
                    })

        return imbalances

    def detect_diagonal_imbalances(self, footprint: Dict[str, Any], ratio: float = 3.0, min_vol: float = 10.0) -> List[Dict[str, Any]]:
        """
        Detects diagonal volume imbalances.
        Standard Order Flow logic: compares Buy Volume at Price X with Sell Volume at Price X - TickSize.
        """
        imbalances = []

        for timestamp_str, bins in footprint.items():
            # Sort prices ascending
            prices = sorted(bins.keys())
            if len(prices) < 2:
                continue

            for i in range(len(prices)):
                current_p = prices[i]

                # Check Buy Imbalance (current_p vs price below)
                if i > 0:
                    p_below = prices[i-1]
                    buy_at_p = bins[current_p]['buy_vol']
                    sell_at_below = bins[p_below]['sell_vol']

                    if buy_at_p > sell_at_below * ratio and buy_at_p >= min_vol:
                        imbalances.append({
                            'timestamp': timestamp_str,
                            'price': current_p,
                            'type': 'Diagonal Buy Imbalance',
                            'ratio': float(buy_at_p / sell_at_below) if sell_at_below > 0 else float('inf'),
                            'volume': float(buy_at_p),
                            'compared_to_price': p_below
                        })

                # Check Sell Imbalance (current_p vs price above)
                if i < len(prices) - 1:
                    p_above = prices[i+1]
                    sell_at_p = bins[current_p]['sell_vol']
                    buy_at_above = bins[p_above]['buy_vol']

                    if sell_at_p > buy_at_above * ratio and sell_at_p >= min_vol:
                        imbalances.append({
                            'timestamp': timestamp_str,
                            'price': current_p,
                            'type': 'Diagonal Sell Imbalance',
                            'ratio': float(sell_at_p / buy_at_above) if buy_at_above > 0 else float('inf'),
                            'volume': float(sell_at_p),
                            'compared_to_price': p_above
                        })

        return imbalances
