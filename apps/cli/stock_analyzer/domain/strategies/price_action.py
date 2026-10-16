import logging

import pandas as pd


class PriceActionDetector:
    """
    Detects price action patterns, market structure, and Fair Value Gaps (FVG).
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_structure(self, df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        """
        Identify HH (Higher High), HL (Higher Low), LH (Lower High), LL (Lower Low).
        Adds 'Structure' and 'TrendState' columns to the DataFrame.
        """
        if df is None or df.empty or len(df) < window * 2:
            return df

        try:
            # Find local peaks and troughs
            df['is_peak'] = (df['High'] == df['High'].rolling(window=window*2+1, center=True).max())
            df['is_trough'] = (df['Low'] == df['Low'].rolling(window=window*2+1, center=True).min())

            df['Structure'] = ""
            df['TrendState'] = "Ranging"

            # Identify structural points
            last_peak_high = None
            last_trough_low = None

            peaks = df[df['is_peak']]
            troughs = df[df['is_trough']]

            for idx in df.index:
                if df.at[idx, 'is_peak']:
                    curr_high = df.at[idx, 'High']
                    if last_peak_high is not None:
                        df.at[idx, 'Structure'] = "HH" if curr_high > last_peak_high else "LH"
                    last_peak_high = curr_high

                if df.at[idx, 'is_trough']:
                    curr_low = df.at[idx, 'Low']
                    if last_trough_low is not None:
                        df.at[idx, 'Structure'] = "HL" if curr_low > last_trough_low else "LL"
                    last_trough_low = curr_low

            # Determine Trend State by propagating structural signals
            current_trend = "Ranging"
            for idx in df.index:
                struct = df.at[idx, 'Structure']
                if struct in ["HH", "HL"]:
                    current_trend = "Bullish"
                elif struct in ["LL", "LH"]:
                    current_trend = "Bearish"
                df.at[idx, 'TrendState'] = current_trend

            # Clean up temporary columns
            df.drop(columns=['is_peak', 'is_trough'], inplace=True)
            return df

        except Exception as e:
            self.logger.error(f"Error detecting market structure: {e}")
            return df

    def detect_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect Doji, Hammer, Pin Bar, Bullish/Bearish Engulfing, Inside Bar.
        Adds 'Pattern' column.
        """
        if df is None or df.empty or len(df) < 2:
            return df

        try:
            df['Pattern'] = ""

            # Vectorized calculations for speed
            body = (df['Close'] - df['Open']).abs()
            candle_range = df['High'] - df['Low']
            upper_wick = df['High'] - df[['Open', 'Close']].max(axis=1)
            lower_wick = df[['Open', 'Close']].min(axis=1) - df['Low']

            for i in range(len(df)):
                idx = df.index[i]

                curr_body = body.iloc[i]
                curr_range = candle_range.iloc[i]
                if curr_range == 0: continue

                # 1. Hammer / Pin Bar (Small body, long wick on one side)
                # Hammer: Small body at top of range, long lower wick
                if lower_wick.iloc[i] > curr_body * 2 and upper_wick.iloc[i] <= curr_body:
                    df.at[idx, 'Pattern'] = "Hammer"
                # Shooting Star / Inverted Hammer: Small body at bottom, long upper wick
                elif upper_wick.iloc[i] > curr_body * 2 and lower_wick.iloc[i] <= curr_body:
                    df.at[idx, 'Pattern'] = "Shooting Star"


                # 2. Doji (Body is very small relative to range)
                elif curr_body <= (curr_range * 0.05):
                    df.at[idx, 'Pattern'] = "Doji"


                # Multi-bar patterns need i > 0
                if i > 0:
                    # 3. Engulfing
                    curr_open = df['Open'].iloc[i]
                    curr_close = df['Close'].iloc[i]
                    prev_open = df['Open'].iloc[i-1]
                    prev_close = df['Close'].iloc[i-1]

                    # Bullish Engulfing
                    if curr_close > curr_open and prev_close < prev_open:
                        if curr_open <= prev_close and curr_close >= prev_open:
                            df.at[idx, 'Pattern'] = "Bullish Engulfing"

                    # Bearish Engulfing
                    elif curr_close < curr_open and prev_close > prev_open:
                        if curr_open >= prev_close and curr_close <= prev_open:
                            df.at[idx, 'Pattern'] = "Bearish Engulfing"

                    # 4. Inside Bar
                    if df['High'].iloc[i] < df['High'].iloc[i-1] and df['Low'].iloc[i] > df['Low'].iloc[i-1]:
                        if df.at[idx, 'Pattern'] == "": # Don't overwrite if already a stronger pattern
                            df.at[idx, 'Pattern'] = "Inside Bar"

            return df

        except Exception as e:
            self.logger.error(f"Error detecting patterns: {e}")
            return df

    def detect_fvg(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify Fair Value Gaps (FVG).
        A gap exists if:
        Bullish: Low(i) > High(i-2)
        Bearish: High(i) < Low(i-2)
        Adds 'FVG' column.
        """
        if df is None or df.empty or len(df) < 3:
            return df

        try:
            df['FVG'] = ""

            for i in range(2, len(df)):
                idx = df.index[i]
                prev_idx = df.index[i-1]
                prev2_idx = df.index[i-2]

                high_prev2 = df['High'].iloc[i-2]
                low_prev2 = df['Low'].iloc[i-2]
                high_curr = df['High'].iloc[i]
                low_curr = df['Low'].iloc[i]

                # Bullish FVG (Gap Up)
                if low_curr > high_prev2:
                    df.at[prev_idx, 'FVG'] = f"Bullish FVG ({high_prev2:.2f}-{low_curr:.2f})"

                # Bearish FVG (Gap Down)
                elif high_curr < low_prev2:
                    df.at[prev_idx, 'FVG'] = f"Bearish FVG ({high_curr:.2f}-{low_prev2:.2f})"

            return df

        except Exception as e:
            self.logger.error(f"Error detecting FVG: {e}")
            return df
