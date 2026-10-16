import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger('api.ml_engine')

class MLEngine:
    _model_cache = {}
    _summary_cache = None

    def __init__(self, model_dir=None):
        curr = Path(__file__).resolve()
        root = curr.parent
        while root.name != 'finance-tracker' and root.parent != root:
            root = root.parent
        self.root = root
        if model_dir is None:
            self.model_dir = root / 'models'
        else:
            self.model_dir = Path(model_dir)

        if MLEngine._summary_cache is None:
            MLEngine._summary_cache = self._load_summary()
        self.summary = MLEngine._summary_cache

    def _load_summary(self):
        paths = [
            self.root / 'data' / 'results_honest' / 'backtest_results.csv',
            self.root / 'apps' / 'cli' / 'stock_ml' / 'results_honest' / 'backtest_results.csv',
            self.root / 'data' / 'results_honest' / 'honest_summary.csv'
        ]
        for summary_path in paths:
            try:
                if summary_path.exists():
                    df = pd.read_csv(summary_path)
                    df['ticker'] = df['ticker'].str.upper()
                    logger.info(f'[MLEngine] Loaded performance summary from {summary_path}')
                    return df
            except Exception as e:
                logger.error(f'[MLEngine] Error loading summary {summary_path}: {e}')
        return None

    def get_ticker_stats(self, ticker):
        if self.summary is not None:
            row = self.summary[self.summary['ticker'] == ticker.upper()]
            if not row.empty:
                return row.iloc[0].to_dict()
        return {}

    def predict(self, ticker, df, macro_context=None):
        try:
            if df is None or len(df) < 100:
                return 0.0, 0.0, 'NEUTRAL', False
            df = df.copy()
            df.columns = [c.capitalize() for c in df.columns]
            EPS = 1e-8
            close = df['Close'].squeeze()
            high, low, vol = df['High'].squeeze(), df['Low'].squeeze(), df['Volume'].squeeze()
            df['MA_20_R'] = close / (close.rolling(20).mean() + EPS)
            df['RET_5'] = close.pct_change(5)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / (loss + EPS))))
            df['RSI_Z'] = (rsi - rsi.rolling(20).mean()) / (rsi.rolling(20).std() + EPS)
            df['ATR_R'] = (high - low).rolling(14).mean() / (close + EPS)
            df['VOL_Z'] = (vol - vol.rolling(20).mean()) / (vol.rolling(20).std() + EPS)
            df['RET_1'] = close.pct_change(1)
            df['MA_50_R'] = close / (close.rolling(50).mean() + EPS)
            feature_cols = ['RET_5', 'MA_20_R', 'RSI_Z', 'ATR_R', 'VOL_Z', 'RET_1', 'MA_50_R']
            feat_df = df[feature_cols].dropna()
            if feat_df.empty: return 0.0, 0.0, 'NEUTRAL', False
            from sklearn.preprocessing import MinMaxScaler
            scaler = MinMaxScaler()
            X_scaled = scaler.fit_transform(feat_df)
            X_latest = X_scaled[-1:].astype(np.float32)
            model_file = f'{ticker.upper()}_sniper.json'
            if model_file in self._model_cache:
                model = self._model_cache[model_file]
            else:
                model_path = None
                for p in self.model_dir.rglob(model_file):
                    model_path = p
                    break
                if not model_path or not model_path.exists():
                    return 0.0, 0.0, 'NEUTRAL', False
                model = xgb.XGBRegressor()
                model.load_model(str(model_path))
                self._model_cache[model_file] = model
            pred_return = float(model.predict(X_latest)[0])
            current_price = float(close.iloc[-1])
            target_price = current_price * (1.0 + pred_return)
            regime = (macro_context or {}).get('regime', 'NEUTRAL')
            sig = 'NEUTRAL'
            is_sniper = False
            raw_ma20r = float(feat_df['MA_20_R'].iloc[-1])
            raw_ret5 = float(feat_df['RET_5'].iloc[-1])
            is_overextended_buy = raw_ma20r > 1.06 or raw_ret5 > 0.10
            if pred_return > 0.015:
                sig = 'BULLISH'
                if pred_return > 0.03 and not is_overextended_buy: is_sniper = True
            elif pred_return < -0.015:
                sig = 'BEARISH'
            return pred_return, target_price, sig, is_sniper
        except Exception as e:
            logger.error(f'[MLEngine] {ticker} error: {e}')
            return 0.0, 0.0, 'NEUTRAL', False
