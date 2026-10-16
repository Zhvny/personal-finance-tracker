import sys
from pathlib import Path

# Setup paths
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path: sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path: sys.path.insert(0, str(_ROOT))

import warnings

import numpy as np
import pandas as pd
import xgboost as xgb
from infrastructure.data_loader import DataLoader
from tqdm import tqdm

warnings.filterwarnings("ignore")

ROOT = _ROOT
FEATURE_BASE = ROOT / "data" / "features"
RESULTS_DIR = ROOT / "apps" / "cli" / "stock_ml" / "results_honest"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = ["RET_5", "MA_20_R", "RSI_Z", "ATR_R", "VOL_Z", "RET_1", "MA_50_R"]

MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

def train_elite_sniper(ticker, cat, feature_fpath, loader: DataLoader):
    try:
        df_feat = pd.read_csv(feature_fpath, index_col=0, parse_dates=True)
        if len(df_feat) < 250: return None

        df_raw = loader.load_ticker_data(ticker, period="2y")
        if df_raw.empty: return None

        close_raw = df_raw["Close"].loc[df_feat.index]
        target_raw = df_raw["Close"].shift(-1).loc[df_feat.index].dropna()

        df_feat = df_feat.loc[target_raw.index]
        close_raw = close_raw.loc[target_raw.index]

        X = df_feat[FEATURE_COLS].values
        y = df_feat["TARGET"].values

        test_size = 60
        val_size = 60

        X_train_full, X_test = X[:-test_size], X[-test_size:]
        y_train_full, y_test = y[:-test_size], y[-test_size:]

        X_train, X_val = X_train_full[:-val_size], X_train_full[-val_size:]
        y_train, y_val = y_train_full[:-val_size], y_train_full[-val_size:]

        close_test = close_raw.values[-test_size:]
        y_test_raw = target_raw.values[-test_size:]

        model = xgb.XGBRegressor(
            n_estimators=1000,
            max_depth=4,
            learning_rate=0.01,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            tree_method='hist',
            early_stopping_rounds=50
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        cat_dir = MODELS_DIR / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        model.save_model(str(cat_dir / f"{ticker}_sniper.json"))

        pred_returns = model.predict(X_test)
        preds_price = close_test * (1 + pred_returns)

        abs_error = np.abs(preds_price - y_test_raw)
        mae_price = np.mean(abs_error)
        mae_pct = np.mean(abs_error / y_test_raw) * 100

        return {
            "ticker": ticker,
            "category": cat,
            "mae_price": round(mae_price, 4),
            "mae_pct": round(mae_pct, 4),
            "last_close": round(float(y_test_raw[-1]), 4),
            "timestamp": df_feat.index[-1].strftime('%Y-%m-%d')
        }
    except Exception:
        return None

def main():
    results = []
    print("--- SHPIS SNIPER ENGINE v5.0 (PROFESSIONAL MODE) ---")
    print("Goal: MAE < 1.5% | Early Stopping | Return-Based Target")

    loader = DataLoader()
    files = list(FEATURE_BASE.rglob("*.csv"))
    for f in tqdm(files, desc="Sniper Training"):
        res = train_elite_sniper(f.stem.replace("_features", ""), f.parent.name, f, loader)
        if res: results.append(res)

    if results:
        df_res = pd.DataFrame(results)
        df_res.to_csv(RESULTS_DIR / "backtest_results.csv", index=False)

        success_rate = (df_res['mae_pct'] < 1.5).mean() * 100
        print("\n--- SPRINT 2 RESULTS ---")
        print(f"Active Models      : {len(df_res)}")
        print(f"Avg. MAE (%)       : {df_res['mae_pct'].mean():.4f}%")
        print(f"Goal Achievement   : {success_rate:.1f}% of models meet < 1.5% error")
        print(f"Top Performer      : {df_res.loc[df_res['mae_pct'].idxmin(), 'ticker']} ({df_res['mae_pct'].min():.4f}%)")

if __name__ == "__main__":
    main()
