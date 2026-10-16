import asyncio
import logging
import math
import time
from typing import Any, Dict, List, Optional

import numpy as np
from stock_analyzer.adapters.cleaner import DataCleaner
from stock_analyzer.adapters.fetcher import DataFetcher
from stock_analyzer.adapters.indicators import IndicatorEngine
from stock_analyzer.adapters.ml_engine import MLEngine
from stock_analyzer.domain.config import AppConfig
from stock_analyzer.domain.scoring import ScoringEngine
from stock_analyzer.use_cases.analyzer import StockAnalyzer

from packages.api.backend.repositories.stock_repository import StockRepository

logger = logging.getLogger("api.service.stock")

class StockAnalysisService:
    def __init__(self, repo: StockRepository, config: AppConfig):
        self.repo = repo
        self.config = config
        self.cleaner = DataCleaner()
        self.indicators = IndicatorEngine()
        self.scoring = ScoringEngine()
        self.ml_engine = MLEngine()
        self.fetcher = DataFetcher()
        self._semaphore = asyncio.Semaphore(15) # Limit to 15 concurrent analyses

    async def analyze_ticker(self, ticker: str, category: str = None) -> Optional[Dict[str, Any]]:
        """Perform full analysis for a single ticker."""
        async with self._semaphore:
            start_time = time.time()

            try:
                # Centralized Normalization
                norm_ticker = self.fetcher.normalize(ticker, category)
                if not category:
                    category = self.fetcher.get_category(norm_ticker)

                logger.info(f"Starting analysis for {norm_ticker} (Input: {ticker}, Cat: {category})")

                # 2. Get Macro Context (Cached)
                macro = await self.repo.get_macro_context()
                dxy_df = await self.repo.get_dxy_data()

                # 3. Perform Analysis
                analyzer = StockAnalyzer(
                    self.fetcher,
                    self.cleaner,
                    self.indicators,
                    self.scoring,
                    self.config,
                    macro,
                    self.ml_engine
                )

                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, analyzer.analyze_ticker, norm_ticker, dxy_df, category, False)

                if not res:
                    return None

                # 4. Map to standardized response
                def safe_f(v):
                    try:
                        if v is None: return None
                        val = float(v)
                        return val if math.isfinite(val) else None
                    except: return None

                raw_signal = str(res.signal.name if hasattr(res.signal, 'name') else res.signal).upper()
                allowed_tech = ["STRONG BUY", "ACCUMULATE", "WAIT", "AVOID", "BUY", "SELL"]
                clean_signal = raw_signal if raw_signal in allowed_tech else "WAIT"

                # Calculate Price Change %
                change_pct = None
                if res.prev_close and res.prev_close > 0:
                    change_pct = (res.current_price - res.prev_close) / res.prev_close * 100

                elapsed = time.time() - start_time
                logger.info(f"Analysis completed for {ticker} in {elapsed:.2f}s (Signal: {clean_signal})")

                # Post-process DXY divergence for async status
                dxy_status = await self.repo.get_dxy_status()
                dcds_raw = getattr(res, 'dcds', None)

                if dcds_raw is None or (isinstance(dcds_raw, (float, np.float64)) and np.isnan(dcds_raw)):
                    if not dxy_status["is_ready"]:
                        dcds_final = { "status": "syncing", "message": "DXY background sync in progress" }
                    else:
                        dcds_final = { "status": "insufficient data", "message": "Correlation window too short" }
                elif dcds_raw == 0.0 and not any(c in ticker for c in ['GOLD', 'GC=F', 'CL=F', 'SI=F', 'BTC', 'ETH']):
                    dcds_final = { "status": "unavailable", "message": "N/A for non-macro assets" }
                else:
                    dcds_final = safe_f(dcds_raw)

            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}", exc_info=True)
                return None
            return {
                "ticker": str(res.ticker),
                "current_price": safe_f(res.current_price),
                "price": safe_f(res.current_price),
                "change": safe_f(change_pct),
                "score": safe_f(res.score),
                "signal": str(clean_signal),
                "css": safe_f(res.css),
                "css_tier": str(res.css_tier.name if hasattr(res.css_tier, 'name') else res.css_tier),
                "vol_regime": str(res.vol_regime.name if hasattr(res.vol_regime, 'name') else res.vol_regime),
                "trend_score": safe_f(res.trend_score),
                "momentum_score": safe_f(res.momentum_score),
                "liquidity_score": safe_f(res.liquidity_score),
                "volatility_score": safe_f(res.volatility_score),
                "expectancy": safe_f(res.expectancy),
                "kelly_fraction": safe_f(res.kelly_fraction),
                "position_size": safe_f(res.position_size),
                "win_rate": safe_f(res.win_rate),
                "risk_reward_ratio": safe_f(res.risk_reward_ratio),
                "support": safe_f(res.support),
                "resistance": safe_f(res.resistance),
                "stop_loss": safe_f(res.stop_loss),
                "take_profit": safe_f(res.take_profit),
                "dcds": dcds_final,
                "mrzg": None if str(res.mrzg) == "NONE" else str(res.mrzg),
                "csi": safe_f(getattr(res, 'csi', None)),
                "ml_signal": str(getattr(res, 'ml_signal', 'NEUTRAL')),
                "ml_prob": safe_f(getattr(res, 'ml_prob', None)),
                "n_sniper_buy": int(getattr(res, 'n_sniper_buy', 0)),
                "global_acc": safe_f(getattr(res, 'global_acc', None)),
                "precision": safe_f(getattr(res, 'precision', None)),
                "forecast_1w": safe_f(getattr(res, 'forecast_1w', None)),
                "forecast_1m": safe_f(getattr(res, 'forecast_1m', None)),
                "sparkline": getattr(res, 'sparkline', [])
            }

    async def analyze_batch(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Analyze multiple tickers in parallel."""
        logger.info(f"Batch analysis started for {len(tickers)} tickers")
        tasks = [self.analyze_ticker(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        # Filter out failed analyses
        valid_results = [r for r in results if r is not None]
        logger.info(f"Batch analysis completed: {len(valid_results)}/{len(tickers)} succeeded")
        return valid_results

    async def get_history(self, ticker: str, period: str = "1y") -> List[Dict[str, Any]]:
        """Get historical price data for charting."""
        df = await self.repo.fetch_ticker_data(ticker, period)
        if df is None or df.empty:
            return []

        try:
            # Clean for frontend
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, self.cleaner.clean, df, ticker)

            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            return [
                {"date": str(idx.date()), "close": float(row["Close"])}
                for idx, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"Error processing history for {ticker}: {e}")
            return []

    async def get_dcds_analysis(self, ticker: str) -> Dict[str, Any]:
        """Lightweight DCDS calculation for async updates."""
        async with self._semaphore:
            try:
                norm_ticker = self.fetcher.normalize(ticker)
                dxy_status = await self.repo.get_dxy_status()

                if not dxy_status["is_ready"]:
                    if dxy_status["is_syncing"]:
                        return {"ticker": norm_ticker, "dcds": {"status": "syncing"}}
                    return {"ticker": norm_ticker, "dcds": {"status": "unavailable"}}

                # Fetch ticker and DXY data
                df_task = self.repo.fetch_ticker_data(norm_ticker, period="1y")
                dxy_task = self.repo.get_dxy_data()
                df, dxy_df = await asyncio.gather(df_task, dxy_task)

                if df is None or dxy_df is None or df.empty or dxy_df.empty:
                    return {"ticker": norm_ticker, "dcds": {"status": "insufficient data"}}

                # Compute DCDS only
                loop = asyncio.get_event_loop()
                df_with_dcds = await loop.run_in_executor(None, self.indicators.compute_dcds, df, dxy_df)

                dcds_val = df_with_dcds['dcds'].iloc[-1]

                if dcds_val is None or (isinstance(dcds_val, (float, np.float64)) and np.isnan(dcds_val)):
                    return {"ticker": norm_ticker, "dcds": {"status": "insufficient data"}}

                return {
                    "ticker": norm_ticker,
                    "dcds": float(dcds_val) if math.isfinite(dcds_val) else None
                }
            except Exception as e:
                logger.error(f"DCDS analysis failed for {ticker}: {e}")
                return {"ticker": ticker, "dcds": {"status": "unavailable"}}
