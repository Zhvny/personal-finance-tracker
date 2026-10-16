import logging

import numpy as np
import pandas as pd

from apps.cli.stock_analyzer.domain.strategies.order_flow import OrderFlowEngine
from apps.cli.stock_analyzer.domain.strategies.price_action import PriceActionDetector
from apps.cli.stock_analyzer.domain.strategies.volume_profile import VolumeProfile
from apps.cli.stock_analyzer.domain.strategies.vwap import VWAPEngine


class AdvancedIndicatorEngine:
    """
    Orchestrates Volume Profile, Price Action, VWAP, and Order Flow analysis.
    """
    def __init__(self):
        self.vp = VolumeProfile()
        self.pa = PriceActionDetector()
        self.vwap = VWAPEngine()
        self.of = OrderFlowEngine()
        self.logger = logging.getLogger(__name__)

    def compute_advanced(self, symbol: str, daily_df: pd.DataFrame, intraday_df: pd.DataFrame) -> dict:
        """
        Runs the advanced analysis pipeline.
        
        Args:
            symbol: Stock ticker.
            daily_df: Cleaned daily historical data.
            intraday_df: Cleaned intraday data (typically 1m or 5m).
            
        Returns:
            dict containing advanced indicator results.
        """
        results = {
            'poc': 0.0,
            'vah': 0.0,
            'val': 0.0,
            'amt_state': 'NONE',
            'profile_shape': 'D-shape',
            'market_structure': 'NEUTRAL',
            'cumulative_delta': 0.0,
            'fvg_present': False,
            'vwap': 0.0,
            'vwap_signals': {},
            'order_flow_signals': {
                'absorption': [],
                'exhaustion': []
            },
            'footprint_data': None
        }

        if intraday_df is None or intraday_df.empty:
            return results

        try:
            # 1. Volume Profile (AMT)
            # Volume Profile usually works best on intraday for the current session profile
            vp_data = self.vp.calculate(intraday_df)
            results['poc'] = float(vp_data.get('poc', 0.0))
            results['vah'] = float(vp_data.get('vah', 0.0))
            results['val'] = float(vp_data.get('val', 0.0))
            results['amt_state'] = vp_data.get('amt_state', 'NONE')
            results['profile_shape'] = vp_data.get('profile_shape', 'D-shape')
            results['absorption_zones'] = vp_data.get('absorption_zones', [])

            # Simplified profile for TUI: (price, volume) tuples
            if 'profile' in vp_data and isinstance(vp_data['profile'], pd.Series):
                # Sample 20 points for ASCII chart
                prof = vp_data['profile']
                if len(prof) > 20:
                    indices = np.linspace(0, len(prof)-1, 20).astype(int)
                    prof = prof.iloc[indices]
                results['profile_summary'] = [(float(p), float(v)) for p, v in prof.items()]
            else:
                results['profile_summary'] = []

            # 2. Price Action / Market Structure
            # We use intraday for precise structure detection
            pa_df = self.pa.detect_structure(intraday_df.copy())
            pa_df = self.pa.detect_fvg(pa_df)

            # Get latest structure tag
            struct_series = pa_df['Structure'].replace('', np.nan).dropna()
            if not struct_series.empty:
                results['market_structure'] = str(struct_series.iloc[-1])
            else:
                results['market_structure'] = vp_data.get('market_structure', 'NEUTRAL')

            try:
                results['fvg_present'] = bool((pa_df['FVG'].tail(5) != "").any())
            except Exception as fvg_err:
                self.logger.error(f"FVG check error: {fvg_err}")
                results['fvg_present'] = False

            # 3. VWAP
            vwap_series = self.vwap.calculate_standard(intraday_df)
            if vwap_series is not None and not vwap_series.empty:
                val = vwap_series.iloc[-1]
                # If val is still a series/array, take first element
                if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
                    val = val[0]
                results['vwap'] = float(val)
                # New: VWAP Signals
                results['vwap_signals'] = self.vwap.get_signals(intraday_df, vwap_series)

            # 4. Order Flow (Synthetic)
            of_df = self.of.calculate_synthetic_delta(intraday_df)
            if not of_df.empty:
                val = of_df['cum_delta'].iloc[-1]
                if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
                    val = val[0]
                results['cumulative_delta'] = float(val)

                # New: Absorption and Exhaustion
                results['order_flow_signals']['absorption'] = self.of.detect_absorption(of_df)
                results['order_flow_signals']['exhaustion'] = self.of.detect_exhaustion(of_df)

                # Provide recent footprint data (last 30 rows/bins)
                results['footprint_data'] = self.of.calculate_footprint(of_df.tail(30))

            return results

        except Exception as e:
            self.logger.error(f"Error in AdvancedIndicatorEngine for {symbol}: {e}")
            return results
