import json
import logging
import os
import threading
import time

import pandas as pd

logger = logging.getLogger(__name__)

class FREDFetcher:
    def __init__(self, config):
        self.api_key = config.fred_api_key
        self.base_url = 'https://api.stlouisfed.org/fred/series/observations'
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_file = os.path.join(base_dir, 'fred_cache.json')
        raw_refresh = getattr(config, 'macro_refresh_hours', 24)
        try:
            self.refresh_hours = float(raw_refresh)
        except (TypeError, ValueError):
            self.refresh_hours = 24.0
        self.stale_data = False
        self._lock = threading.Lock()

    def _get_cache(self, series_id):
        if not os.path.exists(self.cache_file): return None
        try:
            with self._lock:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    if series_id in cache:
                        entry = cache[series_id]
                        fetched_at = entry.get('fetched_at', 0)
                        if time.time() - fetched_at < self.refresh_hours * 3600:
                            return pd.Series(entry['data'], index=pd.to_datetime(entry['index']))
        except Exception as e:
            logger.warning(f"[FRED] Cache read error for {series_id}: {e}")
        return None

    def _set_cache(self, series_id, series):
        try:
            with self._lock:
                cache = {}
                if os.path.exists(self.cache_file):
                    try:
                        with open(self.cache_file, 'r') as f:
                            cache = json.load(f)
                    except Exception:
                        cache = {}
                cache[series_id] = {'fetched_at': time.time(), 'index': [str(d.date()) for d in series.index], 'data': series.tolist()}
                with open(self.cache_file, 'w') as f:
                    json.dump(cache, f)
        except Exception as e:
            logger.error(f"[FRED] Cache write error for {series_id}: {e}")

    def fetch_series(self, series_id, limit=60, force_refresh=False):
        if not self.api_key:
            logger.error("[FRED] API Key missing")
            return pd.Series()

        if not force_refresh:
            cached = self._get_cache(series_id)
            if cached is not None: return cached

        try:
            from packages.core.utils.api_resilience import safe_requests_get
            p = {'series_id': series_id, 'api_key': self.api_key, 'file_type': 'json', 'sort_order': 'desc', 'limit': limit}
            success, data = safe_requests_get(self.base_url, params=p, timeout=5, max_retries=2)
            if success and data:
                obs = data.get('observations', [])
                if not obs: return pd.Series()
                df = pd.DataFrame(obs)
                df['date'] = pd.to_datetime(df['date'])
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df = df.dropna().set_index('date').sort_index()
                series = df['value']
                self._set_cache(series_id, series)
                return series
            else:
                logger.error(f"[FRED] API Fetch failed for {series_id}")
                self.stale_data = True
        except Exception as e:
            logger.error(f"[FRED] Request failed for {series_id}: {e}")
            self.stale_data = True

        if os.path.exists(self.cache_file):
            try:
                with self._lock:
                    with open(self.cache_file, 'r') as f:
                        cache = json.load(f)
                        if series_id in cache:
                            entry = cache[series_id]
                            logger.info(f"[FRED] Using stale cache for {series_id}")
                            self.stale_data = True
                            return pd.Series(entry['data'], index=pd.to_datetime(entry['index']))
            except Exception as e:
                logger.error(f"[FRED] Fallback cache read failed: {e}")

        return pd.Series()

    def fetch_all(self):
        if not self.api_key:
            return []

        indicators = [
            ('DGS10', '10Y Treasury Yield'),
            ('FEDFUNDS', 'Fed Funds Rate'),
            ('CPIAUCSL', 'CPI Inflation YoY'),
            ('UMCSENT', 'Consumer Sentiment'),
            ('WALCL', 'Fed Balance Sheet YoY'),
            ('M2SL', 'M2 Money Supply YoY')
        ]

        results = []
        for series_id, name in indicators:
            series = self.fetch_series(series_id, limit=24)
            if not series.empty:
                if series_id in ['CPIAUCSL', 'M2SL', 'WALCL']:
                    series_yoy = series.pct_change(12) * 100
                    val = series_yoy.iloc[-1]
                    change = series_yoy.iloc[-1] - series_yoy.iloc[-2] if len(series_yoy) > 1 else 0
                else:
                    val = series.iloc[-1]
                    change = series.iloc[-1] - series.iloc[-2] if len(series) > 1 else 0

                influence = "Neutral"
                if series_id == 'DGS10': influence = "Tightening" if change > 0 else "Easing"
                elif series_id == 'FEDFUNDS': influence = "Hawkish" if change > 0 else "Dovish"
                elif series_id == 'CPIAUCSL': influence = "Inflationary" if val > 2.5 else "Stable"
                elif series_id == 'UMCSENT': influence = "Optimistic" if val > 75 else "Pessimistic"

                results.append({'name': name, 'value': val, 'change': change, 'influence': influence})

        # Add Yield Spread (10Y-2Y)
        dgs10 = self.fetch_series('DGS10', 2)
        dgs2 = self.fetch_series('DGS2', 2)
        if not dgs10.empty and not dgs2.empty:
            val = dgs10.iloc[-1] - dgs2.iloc[-1]
            prev = dgs10.iloc[-2] - dgs2.iloc[-2] if len(dgs10) > 1 and len(dgs2) > 1 else val
            results.append({
                'name': 'Yield Spread (10Y-2Y)',
                'value': val,
                'change': val - prev,
                'influence': 'Recession Risk' if val < 0 else 'Normal'
            })

        return results

    def get_macro_context(self, brent_df=None, force_refresh=False):
        self.stale_data = False
        context = {'rrm': 0.0, 'ycmo': 0.0, 'lpi': 0.5, 'icm': 0.0, 'csi': 70.0, 'errf_mult': 1.0, 'regime': 'NEUTRAL', 'is_stale': False}
        context['signals'] = {} # Initialize signals dict for TUI

        if not self.api_key:
            context['signals'] = {k: "N/A" for k in ['rrm', 'ycmo', 'lpi', 'icm', 'csi']}
            return context

        from concurrent.futures import ThreadPoolExecutor

        reqs = [
            ('FEDFUNDS', 12), ('CPIAUCSL', 24), ('DGS10', 24), ('DGS2', 24),
            ('M2SL', 24), ('WALCL', 24), ('PPIACO', 12), ('UMCSENT', 12)
        ]
        series_data = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self.fetch_series, s_id, limit, force_refresh): s_id
                for s_id, limit in reqs
            }
            for fut in futures:
                s_id = futures[fut]
                try:
                    series_data[s_id] = fut.result()
                except Exception:
                    series_data[s_id] = pd.Series()

        fedfunds = series_data.get('FEDFUNDS', pd.Series())
        cpi = series_data.get('CPIAUCSL', pd.Series())
        if not fedfunds.empty and not cpi.empty:
            cpi_yoy = cpi.pct_change(12) * 100
            real_rate = fedfunds - cpi_yoy.reindex(fedfunds.index, method='ffill')
            rrm = real_rate.diff(3).iloc[-1] if len(real_rate) > 3 else 0
            context['rrm'] = rrm
            context['errf_mult'] = 1.3 if rrm < -0.3 else (0.7 if rrm > 0.3 else 1.0)

        dgs10 = series_data.get('DGS10', pd.Series())
        dgs2 = series_data.get('DGS2', pd.Series())
        if not dgs10.empty and not dgs2.empty:
            context['ycmo'] = (dgs10 - dgs2).ewm(span=6).mean().iloc[-1] - (dgs10 - dgs2).ewm(span=12).mean().iloc[-1]

        m2 = series_data.get('M2SL', pd.Series())
        fed_bal = series_data.get('WALCL', pd.Series())
        if not m2.empty and not fed_bal.empty:
            m2_g = m2.pct_change(12).iloc[-1]
            fed_90d = fed_bal.diff().rolling(13).sum().iloc[-1]
            def norm(v, lo, hi): return max(0.0, min(1.0, (v - lo) / (hi - lo)))
            context['lpi'] = 0.5 * norm(m2_g, -0.05, 0.15) + 0.5 * norm(fed_90d, -500e9, 500e9)

        ppi = series_data.get('PPIACO', pd.Series())
        if not ppi.empty and not cpi.empty:
            cpi_acc = cpi.pct_change(12).diff(3).iloc[-1]
            brent_3m = brent_df['Close'].pct_change(63).iloc[-1] if brent_df is not None and not brent_df.empty else 0
            context['icm'] = 0.4 * (1 if cpi_acc > 0 else -1) + 0.4 * (1 if ppi.pct_change(12).iloc[-1] > 0 else -1) + 0.2 * (1 if brent_3m > 0 else -1)

        um = series_data.get('UMCSENT', pd.Series())
        if not um.empty:
            context['csi'] = um.iloc[-1]
            if um.diff(3).iloc[-1] > 5: context['errf_mult'] *= 1.1
            elif um.diff(3).iloc[-1] < -5: context['errf_mult'] *= 0.9

        if context['errf_mult'] > 1.0 and context['ycmo'] > 0: context['regime'] = 'GOLDILOCKS'
        elif context['icm'] > 0.4: context['regime'] = 'INFLATIONARY_GROWTH'
        elif context['lpi'] < 0.35: context['regime'] = 'LIQUIDITY_DROUGHT'
        elif context['csi'] < 60: context['regime'] = 'BEARISH_SENTIMENT'

        # Format signals for TUI
        context['signals'] = {
            'rrm': f"{context['rrm']:+.2f}",
            'ycmo': f"{context['ycmo']:+.2f}",
            'lpi': f"{context['lpi']:.2f}",
            'icm': f"{context['icm']:+.2f}",
            'csi': f"{context['csi']:.1f}"
        }

        context['is_stale'] = self.stale_data
        return context
