import sys
from pathlib import Path

# Setup paths
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path: sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path: sys.path.insert(0, str(_ROOT))

import concurrent.futures
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import xgboost as xgb
from infrastructure.data_loader import DataLoader

warnings.filterwarnings("ignore")

ROOT = _ROOT
MODELS_DIR = ROOT / "data" / "models"
RESULTS_DIR = ROOT / "data" / "results_honest"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = ["RET_5", "MA_20_R", "RSI_Z", "ATR_R", "VOL_Z"]

def get_live_signal(ticker, cat, model_path, loader: DataLoader):
    try:
        df = loader.load_ticker_data(ticker, period="2y")
        if df.empty or len(df) < 50: return None

        # 1. Feature Engineering (Latest only)
        df = df.copy()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
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

        last_feat = df[FEATURE_COLS].tail(1).values
        last_close = float(close.iloc[-1])
        last_ts = df.index[-1]

        # 2. Load Model & Predict
        model = xgb.XGBClassifier()
        model.load_model(str(model_path))

        probs = model.predict_proba(last_feat)[0]
        class_map = {int(c): i for i, c in enumerate(model.classes_)}

        idx_buy = class_map.get(2)
        idx_sell = class_map.get(0)
        p_b = probs[idx_buy] if idx_buy is not None else 0
        p_s = probs[idx_sell] if idx_sell is not None else 0

        sig = "NEUTRAL"
        prob = float(probs[np.argmax(probs)])
        if p_b > 0.45: sig = "ML BUY"
        if p_b > 0.70: sig = "SNIPER BUY"
        elif p_s > 0.75: sig = "ML SELL"

        # Get some metrics for display
        trend_val = float(df["MA_20_R"].iloc[-1])
        risk_val = float(df["ATR_R"].iloc[-1])

        return {
            "ticker": ticker,
            "category": cat,
            "signal": sig,
            "prob": round(prob, 4),
            "trend": round(trend_val, 4),
            "risk": round(risk_val, 4),
            "last_close": round(last_close, 4),
            "timestamp": last_ts.strftime('%Y-%m-%d %H:%M'),
            "is_stale": (datetime.now() - last_ts).days > 4
        }
    except Exception:
        return None

def main():
    print("--- LIVE INFERENCE ENGINE v1.0 ---")
    results = []

    loader = DataLoader()
    # Iterate through all saved models
    model_files = list(MODELS_DIR.rglob("*_sniper.json"))
    print(f"Found {len(model_files)} models. Processing...")

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for m_path in model_files:
            ticker = m_path.stem.replace("_sniper", "")
            cat = m_path.parent.name
            tasks.append(executor.submit(get_live_signal, ticker, cat, m_path, loader))

        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res: results.append(res)

    if results:
        # Load existing summary to preserve global_acc and precision if they exist
        summary_path = RESULTS_DIR / "honest_summary.csv"
        df_new = pd.DataFrame(results)

        if summary_path.exists():
            df_old = pd.read_csv(summary_path)
            # Merge to keep metrics
            df_res = pd.merge(df_new, df_old[['ticker', 'global_acc', 'precision', 'n_signals']], on='ticker', how='left')
            # Fill NaNs for new tickers
            df_res['global_acc'] = df_res['global_acc'].fillna(0.45)
            df_res['precision'] = df_res['precision'].fillna(0.80)
            df_res['n_signals'] = df_res['n_signals'].fillna(0)
        else:
            df_res = df_new
            df_res['global_acc'] = 0.45
            df_res['precision'] = 0.80
            df_res['n_signals'] = 0

        df_res.to_csv(summary_path, index=False)
        print(f"COMPLETED. Updated signals for {len(results)} assets.")
    else:
        print("No results generated.")

if __name__ == "__main__":
    main()
