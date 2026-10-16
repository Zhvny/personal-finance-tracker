import sys
from pathlib import Path

import pandas as pd

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "apps" / "cli"))

from apps.cli.genetic_optimizer import PortfolioOptimizer


def verify_universe():
    print("--- Optimizer Universe Integrity Audit ---")

    # Mock some returns data to trigger filtering
    # In a real scenario, we'd load this from the DB or features
    # But for a standalone verification script, we can simulate the 'full' universe

    # 1. Detect feature files to get the 'potential' universe
    potential_tickers = []
    features_dir = ROOT / "data" / "features"
    if features_dir.exists():
        for csv_file in features_dir.rglob("*.csv"):
            ticker = csv_file.stem.replace("_features", "")
            potential_tickers.append(ticker)

    potential_count = len(set(potential_tickers))
    print(f"Detected potential universe (from features): {potential_count}")

    # 2. Simulate returns_df
    # We create a dummy DF with all detected tickers
    # Some with data, some with NaNs, some with Infs to test logging
    dummy_data = {}
    for i, ticker in enumerate(list(set(potential_tickers))[:550]): # Cap for speed
        if i % 100 == 0:
            # Ticker with all NaNs
            dummy_data[ticker] = [float('nan')] * 10
        elif i % 100 == 1:
            # Ticker with some Infs
            dummy_data[ticker] = [1.0, float('inf'), 0.5, 0.2] + [0.1]*6
        else:
            # Healthy ticker
            dummy_data[ticker] = [0.01, -0.02, 0.005, 0.01] + [0.0]*6

    returns_df = pd.DataFrame(dummy_data)

    optimizer = PortfolioOptimizer()
    audit = optimizer.get_universe_audit(returns_df)

    print(f"Total Tickers Analyzed: {audit['total']}")
    print(f"Eligible Tickers: {audit['eligible']}")
    print(f"Excluded Tickers: {len(audit['excluded'])}")

    if audit['excluded']:
        print("\nSample Exclusions:")
        for entry in audit['excluded'][:10]:
            print(f"  - {entry['ticker']}: {entry['reason']}")

    # Trigger a dummy optimization to verify file logging
    print("\nTriggering test optimization to verify log file...")
    # Reduce iterations for speed
    optimizer.generations = 2
    optimizer.pop_size = 5
    optimizer.optimize(returns_df, target="sharpe")

    log_file = ROOT / "logs" / "optimizer_exclusions.log"
    if log_file.exists():
        print(f"\nSUCCESS: Log file created at {log_file}")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            print(f"Log entries count: {len(lines)}")
            print("Last 3 log entries:")
            for line in lines[-3:]:
                print(f"  {line.strip()}")
    else:
        print(f"\nFAILURE: Log file NOT found at {log_file}")

if __name__ == "__main__":
    verify_universe()
