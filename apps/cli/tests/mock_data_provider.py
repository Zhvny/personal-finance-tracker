
import numpy as np
import pandas as pd


def generate_mock_returns(n_assets=10, n_days=252, start_date="2024-01-01"):
    """
    Generates a synthetic returns DataFrame.
    """
    dates = pd.date_range(start=start_date, periods=n_days, freq='B')
    tickers = [f"TKR_{i:03d}" for i in range(n_assets)]

    # Generate random normal returns
    data = np.random.normal(0.0005, 0.01, size=(n_days, n_assets))
    df = pd.DataFrame(data, index=dates, columns=tickers)
    return df

def inject_failure_modes(df, failure_map):
    """
    Injects specific failure modes into the DataFrame.
    
    failure_map = {
        'all_nan': ['TKR_001'],
        'partial_nan': {'TKR_002': 10}, # 10 random NaNs
        'stale': ['TKR_003'],           # Zero variance
        'inf': ['TKR_004']              # Infinity values
    }
    """
    df_fail = df.copy()

    if 'all_nan' in failure_map:
        for t in failure_map['all_nan']:
            if t in df_fail.columns:
                df_fail[t] = np.nan

    if 'partial_nan' in failure_map:
        for t, count in failure_map['partial_nan'].items():
            if t in df_fail.columns:
                indices = np.random.choice(df_fail.index, count, replace=False)
                df_fail.loc[indices, t] = np.nan

    if 'stale' in failure_map:
        for t in failure_map['stale']:
            if t in df_fail.columns:
                df_fail[t] = 0.0001 # Constant return

    if 'inf' in failure_map:
        for t in failure_map['inf']:
            if t in df_fail.columns:
                df_fail.loc[df_fail.index[0], t] = np.inf

    return df_fail
