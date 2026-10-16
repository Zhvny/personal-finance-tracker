import logging

import numpy as np
import pandas as pd


class VolumeProfile:
    """
    Implements Volume Profile and Auction Market Theory (AMT) core logic.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate(self, df: pd.DataFrame, bins: int = None) -> dict:
        """
        Calculate Volume Profile, POC, and Value Area.
        
        Args:
            df: DataFrame with 'High', 'Low', 'Close' and 'Volume' columns.
            bins: Number of price bins to use. If None, auto-calculated.
            
        Returns:
            dict containing POC, VAH, VAL, and profile data.
        """
        if df is None or df.empty or 'Volume' not in df.columns:
            return {}

        try:
            # 1. Handle price range
            price_min = df['Low'].min()
            price_max = df['High'].max()

            if price_min == price_max:
                return self._create_empty_profile(price_min)

            # Auto-binning if not provided
            if bins is None:
                # Heuristic: aim for a balance between detail and speed
                price_range_pct = (price_max - price_min) / price_min if price_min > 0 else 0
                bins = int(max(30, min(100, price_range_pct * 200)))

            bin_width = (price_max - price_min) / bins

            # 2. Distribute volume across bins
            profile_raw = np.zeros(bins)
            price_edges = np.linspace(price_min, price_max, bins + 1)

            # Distribute volume for each bar across the bins it touches
            for _, row in df.iterrows():
                low, high, vol = row['Low'], row['High'], row['Volume']
                if high == low:
                    idx = int(min(bins - 1, max(0, (high - price_min) / bin_width)))
                    profile_raw[idx] += vol
                else:
                    start_bin = int(max(0, (low - price_min) / bin_width))
                    end_bin = int(min(bins - 1, (high - price_min) / bin_width))

                    num_bins = end_bin - start_bin + 1
                    vol_per_bin = vol / num_bins
                    profile_raw[start_bin:end_bin+1] += vol_per_bin

            price_centers = (price_edges[:-1] + price_edges[1:]) / 2
            profile = pd.Series(profile_raw, index=price_centers)

            # 3. Identify POC (Point of Control)
            poc = float(profile.idxmax())
            poc_idx = profile.index.get_loc(poc)

            # 4. Calculate Value Area (70% of total volume)
            total_volume = float(profile.sum())
            target_va_volume = total_volume * 0.70

            vah, val = self._calculate_value_area(profile, poc_idx, target_va_volume)

            # 5. Nodes (HVN / LVN)
            hvn, lvn = self.identify_nodes(profile)

            # 6. AMT State
            current_price = df['Close'].iloc[-1]
            amt_state = self.get_amt_state(current_price, vah, val, poc)

            # 7. Profile Shape
            profile_shape = self.detect_shape(profile, poc, vah, val)

            # 8. Market Structure (Simplified)
            market_structure = self._determine_market_structure(df)

            # 9. Absorption Detection (New)
            absorption_zones = self.detect_absorption(df, profile)

            return {
                'poc': float(poc),
                'vah': float(vah),
                'val': float(val),
                'hvn': [float(h) for h in hvn],
                'lvn': [float(l) for l in lvn],
                'amt_state': amt_state,
                'profile_shape': profile_shape,
                'is_balanced': amt_state == 'BALANCED',
                'market_structure': market_structure,
                'absorption_zones': absorption_zones,
                'profile': profile,
                'total_volume': total_volume
            }

        except Exception as e:
            self.logger.error(f"Error calculating Volume Profile: {e}")
            return {}

    def _create_empty_profile(self, price):
        return {
            'poc': float(price),
            'vah': float(price),
            'val': float(price),
            'hvn': [],
            'lvn': [],
            'amt_state': 'BALANCED',
            'profile_shape': 'D-shape',
            'is_balanced': True,
            'market_structure': 'NEUTRAL',
            'profile': pd.Series({price: 0.0}),
            'total_volume': 0.0
        }

    def _calculate_value_area(self, profile, poc_idx, target_vol):
        """Standard expansion algorithm from POC to identify 70% volume range."""
        va_vol = profile.iloc[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx

        while va_vol < target_vol:
            vol_below = 0
            # Compare two rows below vs two rows above
            if low_idx >= 2:
                vol_below = profile.iloc[low_idx-1] + profile.iloc[low_idx-2]
            elif low_idx == 1:
                vol_below = profile.iloc[0]

            vol_above = 0
            if high_idx <= len(profile) - 3:
                vol_above = profile.iloc[high_idx+1] + profile.iloc[high_idx+2]
            elif high_idx == len(profile) - 2:
                vol_above = profile.iloc[-1]

            if vol_below == 0 and vol_above == 0:
                break

            if vol_below >= vol_above and low_idx > 0:
                va_vol += profile.iloc[low_idx-1]
                low_idx -= 1
                if low_idx > 0 and va_vol < target_vol:
                     va_vol += profile.iloc[low_idx-1]
                     low_idx -= 1
            elif high_idx < len(profile) - 1:
                va_vol += profile.iloc[high_idx+1]
                high_idx += 1
                if high_idx < len(profile) - 1 and va_vol < target_vol:
                    va_vol += profile.iloc[high_idx+1]
                    high_idx += 1
            else:
                break

        return float(profile.index[high_idx]), float(profile.index[low_idx])

    def detect_shape(self, profile: pd.Series, poc: float, vah: float, val: float) -> str:
        """
        Identify the shape of the volume profile (D, P, or b).
        
        D-shape: POC near center of VA. Suggests Balance.
        P-shape: POC in upper half, lower half low volume. Bullish/Short Covering.
        b-shape: POC in lower half, upper half low volume. Bearish/Long Liquidation.
        """
        if profile is None or profile.empty:
            return "D-shape"

        prices = profile.index
        min_p, max_p = prices.min(), prices.max()
        p_range = max_p - min_p

        if p_range == 0:
            return "D-shape"

        # 1. P-shape and b-shape checks
        poc_rel = (poc - min_p) / p_range
        mid_p = (min_p + max_p) / 2

        lower_vol = profile[profile.index < mid_p].sum()
        upper_vol = profile[profile.index >= mid_p].sum()

        # P-shape: POC in upper half AND upper volume significantly higher
        if poc_rel > 0.6 and upper_vol > lower_vol * 1.5:
            return "P-shape"

        # b-shape: POC in lower half AND lower volume significantly higher
        if poc_rel < 0.4 and lower_vol > upper_vol * 1.5:
            return "b-shape"

        # 2. D-shape check: POC near center of Value Area
        va_center = (vah + val) / 2
        va_range = vah - val
        if va_range > 0 and abs(poc - va_center) / va_range < 0.2:
            return "D-shape"

        return "D-shape" # Default to D-shape (Balanced)

    def identify_nodes(self, profile: pd.Series) -> tuple:
        """Find High Volume Nodes (peaks) and Low Volume Nodes (valleys)."""
        data = profile.values
        hvn_indices = []
        lvn_indices = []

        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                hvn_indices.append(i)
            elif data[i] < data[i-1] and data[i] < data[i+1]:
                lvn_indices.append(i)

        return profile.index[hvn_indices].tolist(), profile.index[lvn_indices].tolist()

    def get_amt_state(self, price: float, vah: float, val: float, poc: float) -> str:
        """Categorize market state based on price relation to Value Area."""
        if price > vah:
            return 'IMBALANCED_UP'
        elif price < val:
            return 'IMBALANCED_DOWN'
        else:
            return 'BALANCED'

    def detect_absorption(self, df: pd.DataFrame, profile: pd.Series) -> list:
        """
        Detect price levels where high volume occurs with minimal price movement.
        Returns a list of price levels (centers of bins) flagged as absorption zones.
        """
        if df is None or df.empty or profile is None or profile.empty:
            return []

        try:
            # 1. Calculate baselines
            avg_vol = df['Volume'].mean()
            avg_range = (df['High'] - df['Low']).mean()
            if avg_range == 0: avg_range = 1e-9

            # 2. Identify "Absorption Bars" (High Vol, Low Range)
            # Thresholds: Vol > 1.5x Avg, Range < 0.8x Avg
            absorption_mask = (df['Volume'] > avg_vol * 1.5) & ((df['High'] - df['Low']) < avg_range * 0.8)
            abs_bars = df[absorption_mask]

            if abs_bars.empty:
                return []

            # 3. Map these bars to the profile bins
            absorption_zones = []
            bin_centers = profile.index.values
            bin_width = bin_centers[1] - bin_centers[0] if len(bin_centers) > 1 else 0

            for _, bar in abs_bars.iterrows():
                # Find which bins this bar's range touches
                # For simplicity, we flag the bin containing the close price of the absorption bar
                close = bar['Close']
                # Find nearest bin center
                distances = np.abs(bin_centers - close)
                nearest_idx = np.argmin(distances)

                # Check if this bin is also a High Volume Node (HVN)
                # An absorption zone is more significant if it's an HVN
                if profile.iloc[nearest_idx] > profile.mean():
                    absorption_zones.append(float(bin_centers[nearest_idx]))

            # Remove duplicates and sort
            return sorted(list(set(absorption_zones)))

        except Exception as e:
            self.logger.error(f"Error detecting absorption in Volume Profile: {e}")
            return []

    def _determine_market_structure(self, df: pd.DataFrame) -> str:
        """Identify if market is in Trending or Ranging state."""
        if len(df) < 20:
            return 'NEUTRAL'

        close = df['Close']
        sma = close.rolling(window=20).mean()

        # Check if price is consistently above/below SMA
        above_sma = (close.tail(5) > sma.tail(5)).all()
        below_sma = (close.tail(5) < sma.tail(5)).all()

        if above_sma:
            return 'TRENDING_UP'
        elif below_sma:
            return 'TRENDING_DOWN'
        else:
            return 'RANGING'

    def get_amt_signals(self, df: pd.DataFrame, vp_data: dict) -> dict:
        """Identify signals based on Auction Market Theory (AMT)."""
        if not vp_data or 'amt_state' not in vp_data:
            return {}

        current_price = df['Close'].iloc[-1]
        amt_state = vp_data['amt_state']
        vah = vp_data['vah']
        val = vp_data['val']
        poc = vp_data['poc']
        profile_shape = vp_data.get('profile_shape', 'D-shape')

        signals = {
            'type': 'NEUTRAL',
            'confidence': 0.0,
            'target': None,
            'description': ''
        }

        prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price

        # 1. Mean Reversion (The 80% Rule)
        if prev_price > vah and current_price <= vah:
            signals = {
                'type': 'MEAN_REVERSION_SHORT',
                'confidence': 0.7,
                'target': poc,
                'description': f'Accepted back into VA from above ({profile_shape}). Target POC.'
            }
        elif prev_price < val and current_price >= val:
            signals = {
                'type': 'MEAN_REVERSION_LONG',
                'confidence': 0.7,
                'target': poc,
                'description': f'Accepted back into VA from below ({profile_shape}). Target POC.'
            }

        # 2. Breakout / Extension
        elif amt_state == 'IMBALANCED_UP' and prev_price <= vah:
            confidence = 0.8 if profile_shape == 'P-shape' else 0.6
            desc = 'Broke above VAH with bullish P-shape.' if profile_shape == 'P-shape' else 'Broke above VAH.'
            signals = {
                'type': 'BREAKOUT_UP',
                'confidence': confidence,
                'target': current_price * 1.01,
                'description': desc
            }
        elif amt_state == 'IMBALANCED_DOWN' and prev_price >= val:
            confidence = 0.8 if profile_shape == 'b-shape' else 0.6
            desc = 'Broke below VAL with bearish b-shape.' if profile_shape == 'b-shape' else 'Broke below VAL.'
            signals = {
                'type': 'BREAKOUT_DOWN',
                'confidence': confidence,
                'target': current_price * 0.99,
                'description': desc
            }

        return signals
