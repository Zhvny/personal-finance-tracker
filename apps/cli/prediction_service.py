import logging
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

# Initialize logger for this module
logger = logging.getLogger("ml_prediction")

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT / "models"
RAW_BASE = ROOT / "apps" / "cli" / "stock_ml" / "data" / "raw"
FEATURE_COLS = ["RET_5", "MA_20_R", "RSI_Z", "ATR_R", "VOL_Z", "RET_1", "MA_50_R"]

class PredictionService:
    @staticmethod
    def _get_audit_db():
        db_dir = ROOT / "data" / "audit"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "ml_audit.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                category TEXT,
                last_close REAL,
                target_price REAL,
                pred_return REAL,
                confidence REAL,
                timestamp TEXT,
                actual_close_h1 REAL,
                is_correct INTEGER
            )
        """)
        return conn

    @staticmethod
    def save_prediction(p: dict):
        if not p or p.get('status') != 'success': return
        data = p.get('data')
        if not data: return
        try:
            with PredictionService._get_audit_db() as conn:
                conn.execute("""
                    INSERT INTO predictions_audit 
                    (ticker, category, last_close, target_price, pred_return, confidence, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (data['ticker'], data.get('category', 'unknown'), data['last_close'], data['target_price'],
                      data['pred_return'], data['confidence'], data['timestamp']))
        except Exception as e:
            logger.error(f"Failed to save prediction to audit log: {e}", exc_info=True)

    @staticmethod
    def calculate_confidence(pred_return: float, volatility: float) -> float:
        """
        Tanh-based confidence calibration.
        Provides a smooth [0, 1] curve.
        """
        score = abs(pred_return) / (volatility + 1e-8)
        conf = np.tanh(0.35 * score)
        return float(conf)

    @staticmethod
    def get_prediction(ticker: str, cat: str):
        try:
            model_path = MODELS_DIR / "prod" / f"{ticker}_sniper.json"
            if not model_path.exists():
                return {"status": "insufficient_data", "ticker": ticker, "data": None}

            raw_fpath = RAW_BASE / cat / f"{ticker}.csv"
            if not raw_fpath.exists():
                return {"status": "insufficient_data", "ticker": ticker, "data": None}

            df = pd.read_csv(raw_fpath, index_col=0, parse_dates=True)
            if len(df) < 60:
                return {"status": "insufficient_data", "ticker": ticker, "data": None}

            # Feature Engineering (Latest only)
            df.columns = [c.capitalize() for c in df.columns]
            close = df["Close"].squeeze()
            high, low, vol = df["High"].squeeze(), df["Low"].squeeze(), df["Volume"].squeeze()

            df["MA_20_R"] = close / (close.rolling(20).mean() + 1e-8)
            df["RET_5"] = close.pct_change(5)

            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / (loss + 1e-8))))
            df["RSI_Z"] = (rsi - rsi.rolling(20).mean()) / (rsi.rolling(20).std() + 1e-8)
            df["ATR_R"] = (high - low).rolling(14).mean() / (close + 1e-8)
            df["VOL_Z"] = (vol - vol.rolling(20).mean()) / (vol.rolling(20).std() + 1e-8)
            df["RET_1"] = close.pct_change(1)
            df["MA_50_R"] = close / (close.rolling(50).mean() + 1e-8)

            feats_df = df[FEATURE_COLS].dropna()
            if feats_df.empty:
                return {"status": "insufficient_data", "ticker": ticker, "data": None}
            last_idx = feats_df.index[-1]

            vals = feats_df.values
            v_min, v_max = vals.min(axis=0), vals.max(axis=0)
            last_feat = (vals[-1] - v_min) / (v_max - v_min + 1e-8)

            model = xgb.XGBRegressor()
            model.load_model(str(model_path))

            pred_return = float(model.predict(last_feat.reshape(1, -1))[0])
            last_close = float(close.iloc[-1])
            target_price = last_close * (1 + pred_return)

            vol_std = float(df["RET_1"].tail(20).std())
            confidence = PredictionService.calculate_confidence(pred_return, vol_std)

            prediction_dict = {
                "ticker": ticker,
                "category": cat,
                "last_close": last_close,
                "pred_return": pred_return,
                "target_price": target_price,
                "confidence": confidence,
                "volatility": float(df["ATR_R"].iloc[-1]), # Added for Dr. Strange Simulator
                "timestamp": last_idx.strftime("%Y-%m-%d")
            }
            res = {"status": "success", "ticker": ticker, "data": prediction_dict}
            PredictionService.save_prediction(res)
            return res
        except Exception as e:
            logger.exception(f"Prediction failed for {ticker} ({cat}): {e}")
            return {"status": "error", "ticker": ticker, "data": None}

    @staticmethod
    def get_top_prediction():
        all_preds = []
        model_files = list(MODELS_DIR.rglob("*_sniper.json"))
        # Prioritize some categories or just take first 30 for speed
        for m_path in model_files[:30]:
            ticker = m_path.stem.replace("_sniper", "")
            cat = m_path.parent.name
            p = PredictionService.get_prediction(ticker, cat)
            if p and p.get('status') == 'success':
                all_preds.append(p['data'])

        if not all_preds: return None
        return max(all_preds, key=lambda x: abs(x["pred_return"]) * x["confidence"])

if __name__ == "__main__":
    p = PredictionService.get_prediction("AAPL", "us")
    print(p)
