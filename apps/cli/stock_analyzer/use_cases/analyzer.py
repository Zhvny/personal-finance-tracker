import logging

import numpy as np
import pandas as pd

from apps.cli.stock_analyzer.adapters.advanced_indicators import AdvancedIndicatorEngine
from apps.cli.stock_analyzer.adapters.ml_engine import MLEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.models import StockResult
from apps.cli.stock_analyzer.domain.risk import RiskManager


class StockAnalyzer:
    def __init__(self, fetcher, cleaner, indicators, scoring, config=None, macro_context=None, ml_engine=None, macro_repo=None, advanced_indicators=None):
        self.fetcher, self.cleaner, self.indicators, self.scoring = fetcher, cleaner, indicators, scoring
        self.config = config or AppConfig()
        self.macro_repo = macro_repo
        self.macro_context = macro_context or {'rrm':0,'ycmo':0,'lpi':0.5,'icm':0,'errf_mult':1.0, 'regime': 'NEUTRAL'}

        # Sync with Repo if available
        if self.macro_repo and self.macro_repo.is_initialized:
            self.macro_context = self.macro_repo.get_fred_context()

        self.risk_manager = RiskManager()
        self.ml_engine = ml_engine or MLEngine()
        self.advanced_indicators = advanced_indicators or AdvancedIndicatorEngine()
        self._spy_cache = None

    def _get_spy(self, force_cache: bool = False):
        if self._spy_cache is None:
            try:
                spy = self.fetcher.fetch('SPY', period='2y', force_cache=force_cache)
                if spy.empty: return None
                self._spy_cache = self.cleaner.clean(spy, 'SPY')
            except: return None
        return self._spy_cache

    def analyze_ticker(self, ticker, dxy_df=None, category=None, force_cache: bool = False):
        def _to_naive(df):
            if df is not None and not df.empty and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df

        ticker = ticker.upper()

        # If repo exists, prioritize its data
        if self.macro_repo and self.macro_repo.is_initialized:
            self.macro_context = self.macro_repo.get_fred_context()
            if dxy_df is None:
                dxy_df = self.macro_repo.get_dxy()

        # Defensive check: Ensure macro context has been fetched
        # Change: NEUTRAL is a valid regime. Only skip if status is SYNCING or regime is missing.
        if self.macro_context.get('regime') == 'SYNCING':
            logging.warning(f'[Analyzer] Skipping {ticker}: Macro context still syncing.')
            return None

        try:
            from concurrent.futures import ThreadPoolExecutor

            # ── Parallel fetching: ticker + SPY + intraday ──────────────────
            df_raw = None
            spy_df_raw = None
            intraday_raw = None

            def _fetch_ticker():
                return self.fetcher.fetch(ticker, period='2y', category=category, force_cache=force_cache)

            def _fetch_spy():
                try:
                    spy = self.fetcher.fetch('SPY', period='2y', force_cache=force_cache)
                    return self.cleaner.clean(spy, 'SPY') if not spy.empty else None
                except Exception:
                    return None

            def _fetch_intraday():
                try:
                    return self.fetcher.fetch_intraday(ticker, period='5d', interval='5m')
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=3) as ex:
                ft  = ex.submit(_fetch_ticker)
                fsp = ex.submit(_fetch_spy)
                fid = ex.submit(_fetch_intraday)
                try:
                    df_raw = ft.result()
                except Exception as e:
                    logging.error(f'[Analyzer] Fetch error for {ticker}: {e}')
                    return None
                spy_df_raw   = fsp.result()
                intraday_raw = fid.result()

            if df_raw is None or df_raw.empty:
                return None

            if self._spy_cache is None and spy_df_raw is not None:
                self._spy_cache = spy_df_raw

            df = self.cleaner.clean(df_raw, ticker)
            if df is None or len(df) < 100: return None
            df      = _to_naive(df)
            spy_df  = _to_naive(self._get_spy() if spy_df_raw is None else spy_df_raw)
            dxy_df  = _to_naive(dxy_df)
            df = self.indicators.compute(df, ticker=ticker, spy_df=spy_df)
            df = self.indicators.compute_mrc(df, self.macro_context)

            is_commodity = any(c in ticker for c in self.config.commodity_tickers) or any(c in ticker for c in ['GOLD', 'GC=F', 'CL=F', 'SI=F', 'BTC', 'ETH'])
            if is_commodity:
                if dxy_df is not None:
                    df = self.indicators.compute_dcds(df, dxy_df)
                else:
                    logging.warning(f'[DXY] degraded state triggered: missing data for {ticker}')
                    df['dcds'] = np.nan # Degraded: missing required DXY data
            else:
                df['dcds'] = 0.0 # Standard: not a commodity, divergence N/A

            df = df.ffill()
            valid_df = df.dropna(subset=['rsi', 'macd_hist', 'atr'])
            if valid_df.empty:
                df = df.bfill().ffill()
                valid_df = df.dropna(subset=['rsi'])
                if valid_df.empty: return None

            last = valid_df.iloc[-1]
            prev = valid_df.iloc[-2] if len(valid_df) > 1 else last
            indicators_row = last.copy()
            if pd.isna(indicators_row.get('ema200')):
                indicators_row['ema200'] = indicators_row.get('ema50', indicators_row['Close'])

            pred_ret, target_price, ml_sig, is_sel = self.ml_engine.predict(ticker, valid_df, self.macro_context)
            tech_score, scores = self.scoring.calculate_composite_score(indicators_row, ticker=ticker, config=self.config)

            # 4. Composite Scoring & Macro Alignment
            dcds_raw = indicators_row.get('dcds', 0.0)
            dcds_val = float(dcds_raw) if not pd.isna(dcds_raw) else 0.0
            css, tier = self.scoring.calculate_css(tech_score, self.macro_context, is_commodity=is_commodity, dcds=dcds_val)

            mrzg = self.scoring.mrzg_signal(indicators_row, self.macro_context.get('ycmo',0), self.macro_context.get('rrm',0))
            signal = self.scoring.generate_signal(tech_score, indicators_row, self.config, ml_sig, abs(pred_ret), css_tier=tier)

            ml_stats = self.ml_engine.get_ticker_stats(ticker)
            win_rate_base, rr_ratio = self.risk_manager.get_strategy_performance(tech_score)
            selective_prec = ml_stats.get('precision_buy', ml_stats.get('precision'))
            if selective_prec is not None and float(selective_prec) > 0.4:
                win_rate_base = (win_rate_base + float(selective_prec)) / 2.0

            f1w = float(np.clip(pred_ret * 5, -0.15, 0.15))
            f1m = float(np.clip(pred_ret * 21, -0.40, 0.40))

            # 5. Advanced Analysis (Intraday) – already fetched in parallel above
            advanced_data = {}
            try:
                if intraday_raw is not None and not intraday_raw.empty:
                    intraday_df = self.cleaner.clean(intraday_raw, ticker)
                    advanced_data = self.advanced_indicators.compute_advanced(ticker, df, intraday_df)
            except Exception as e:
                logging.warning(f'[Analyzer] Advanced analysis skipped for {ticker}: {e}')

            vr = indicators_row.get('vr', 1.0)
            vol_regime = 'HIGH' if vr > 1.3 else ('LOW' if vr < 0.7 else 'NORMAL')
            dynamic_risk_pct = self.risk_manager.calculate_dynamic_risk(tech_score, win_rate_base, rr_ratio)
            sl_mult = self.config.sl_atr_multiplier
            if vol_regime == 'HIGH': sl_mult *= 1.2
            stop_loss = round(indicators_row['Close'] - (sl_mult * indicators_row['atr']), 2)
            take_profit = round(indicators_row['Close'] + (indicators_row['Close'] - stop_loss) * rr_ratio, 2)

            # 4. Final Mapping
            dcds_final = float(round(dcds_raw, 2)) if dcds_raw is not None and np.isfinite(dcds_raw) else None

            res = StockResult(
                ticker=ticker, score=float(tech_score), css=float(css), css_tier=tier,
                vol_regime=vol_regime, macro_regime=self.macro_context.get('regime', 'NEUTRAL'),
                is_commodity=is_commodity,
                trend_score=float(scores.get('trend', 0.0)),
                momentum_score=float(scores.get('momentum', 0.0)),
                volatility_score=float(scores.get('structure', 0.0)),
                liquidity_score=float(scores.get('volume', 0.0)),
                signal=signal, current_price=float(round(indicators_row['Close'], 2)),
                prev_close=float(round(prev['Close'], 2)),
                stop_loss=float(stop_loss), take_profit=float(take_profit),
                support=float(round(indicators_row.get('sr_support', indicators_row['bb_lower']), 2)),
                resistance=float(round(indicators_row.get('sr_resistance', indicators_row['bb_upper']), 2)),
                forecast_1w=float(round(f1w, 4)), forecast_1m=float(round(f1m, 4)),
                target_price=float(round(target_price, 2)),
                dcds=dcds_final,
                mrzg=str(mrzg), csi=float(self.macro_context.get('csi', 0.0)),
                ml_signal=str(ml_sig), ml_prob=float(abs(pred_ret)),
                is_selective=bool(is_sel), n_sniper_buy=int(ml_stats.get('n_sniper_buy', 0)),
                global_acc=float(ml_stats.get('global_acc', 0.0)),
                precision=float(selective_prec if selective_prec else 0.0),
                expectancy=float(round(self.risk_manager.calculate_expectancy(win_rate_base, indicators_row['Close']*0.05*rr_ratio, indicators_row['Close']*0.05), 2)),
                kelly_fraction=float(round(self.risk_manager.calculate_kelly_criterion(win_rate_base, rr_ratio), 3)),
                position_size=float(self.risk_manager.calculate_position_size(100000000, dynamic_risk_pct, indicators_row['Close'], stop_loss, tech_score)),
                win_rate=float(win_rate_base), risk_reward_ratio=float(rr_ratio),
                is_favorite=False,
                sparkline=[float(round(c, 2)) for c in valid_df['Close'].tail(30).tolist()],

                # Advanced Strategy fields
                poc=float(advanced_data.get('poc', 0.0)),
                vah=float(advanced_data.get('vah', 0.0)),
                val=float(advanced_data.get('val', 0.0)),
                amt_state=str(advanced_data.get('amt_state', 'NONE')),
                market_structure=str(advanced_data.get('market_structure', 'NEUTRAL')),
                cumulative_delta=float(advanced_data.get('cumulative_delta', 0.0)),
                fvg_present=bool(advanced_data.get('fvg_present', False)),
                vwap=float(advanced_data.get('vwap', 0.0)),
                footprint_data=advanced_data.get('footprint_data'),
                profile_summary=advanced_data.get('profile_summary', []),
                absorption_zones=advanced_data.get('absorption_zones', [])
            )
            return res
        except Exception as e:
            logging.error(f'Deep Analysis error for {ticker}: {e}')
            return None
