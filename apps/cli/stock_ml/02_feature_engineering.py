import sys
from pathlib import Path

# Setup paths
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path: sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path: sys.path.insert(0, str(_ROOT))

from infrastructure.data_loader import DataLoader

from packages.core.utils.symbol_utils import SymbolFormatter

ROOT = _ROOT
LIST_PATH    = ROOT / "apps" / "stock_analyzer" / "list.txt"
FEATURE_DIR  = ROOT / "data" / "features"
EPS          = 1e-8

def load_tickers():
    tickers = []
    if LIST_PATH.exists():
        with open(LIST_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.endswith(":"):
                    continue
                tickers.append(SymbolFormatter.normalize(line))
    return list(set(tickers))

def build_elite_features(df):
    df = df.copy()
    df.columns = [c.capitalize() for c in df.columns]
    close = df["Close"].squeeze()
    high, low, vol = df["High"].squeeze(), df["Low"].squeeze(), df["Volume"].squeeze()

    # 1. Stationary Returns & Ratios
    df["MA_20_R"] = close / (close.rolling(20).mean() + EPS)
    df["RET_5"] = close.pct_change(5)

    # 2. RSI Z-Score (Elite Feature: Is RSI high/low relative to its own history?)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + EPS))))
    df["RSI_Z"] = (rsi - rsi.rolling(20).mean()) / (rsi.rolling(20).std() + EPS)

    # 3. Volatility Regime
    df["ATR_R"] = (high - low).rolling(14).mean() / (close + EPS)

    # 4. Volume Momentum
    df["VOL_Z"] = (vol - vol.rolling(20).mean()) / (vol.rolling(20).std() + EPS)

    # 5. Additional Features (to reach 7)
    df["RET_1"] = close.pct_change(1)
    df["MA_50_R"] = close / (close.rolling(50).mean() + EPS)

    # --- REGRESSION TARGET (Next Day Return) ---
    df["TARGET"] = close.shift(-1) / (close + EPS) - 1

    # Standard features for training
    features = ["RET_5", "MA_20_R", "RSI_Z", "ATR_R", "VOL_Z", "RET_1", "MA_50_R"]
    target = ["TARGET"]

    # Cleanup
    df = df[features + target].dropna()

    # --- NORMALIZATION ENGINE ---
    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler()
    # Scale features only
    df[features] = scaler.fit_transform(df[features])

    return df

def main():
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    tickers = load_tickers()
    loader = DataLoader()

    print(f"Baking Elite Features for {len(tickers)} tickers...")
    for ticker in tickers:
        try:
            market = SymbolFormatter.get_market(ticker)
            cat = market.lower()
            out_cat = FEATURE_DIR / cat
            out_cat.mkdir(parents=True, exist_ok=True)

            df = loader.load_ticker_data(ticker, period="2y")
            if df is not None and not df.empty:
                feats = build_elite_features(df)
                feats.to_csv(out_cat / f"{ticker}_features.csv")
                print(f"✓ {ticker}")
            else:
                print(f"✗ {ticker} (No data)")
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

if __name__ == "__main__":
    main()
