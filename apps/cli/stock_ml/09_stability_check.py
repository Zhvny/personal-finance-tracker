from pathlib import Path

import numpy as np
import pandas as pd


def run_stability_check():
    _HERE = Path(__file__).resolve().parent
    _ROOT = _HERE.parent.parent
    csv_path = _ROOT / "data" / "results_honest" / "honest_summary.csv"
    df = pd.read_csv(csv_path)

    # Use the correct column name from the CSV: 'precision' instead of 'sniper_acc'
    # And handle possible NaN values to prevent the check from failing
    target_col = "precision" if "precision" in df.columns else "global_acc"

    print(f"Auditing stability using column: {target_col}")

    # Simulate 50 "Front-tests" by sampling subsets
    metrics = []
    for i in range(50):
        sample = df.sample(frac=0.8)
        # Drop NaN to ensure valid mean calculation
        val = sample[sample[target_col] > 0][target_col].dropna().mean()
        if not np.isnan(val):
            metrics.append(val)

    if not metrics:
        print("Error: No valid data points found for stability check.")
        return

    print("--- 50-RUN STABILITY CHECK ---")
    print(f"Mean {target_col.capitalize()}: {np.mean(metrics):.4f}")
    print(f"Standard Deviation: {np.std(metrics):.6f}")
    print(f"Stability Score: {(1 - np.std(metrics))*100:.2f}%")

    # Check for NaN/Null in the main dataset
    null_counts = df.isnull().sum()
    if null_counts.any():
        print("\n[WARNING] Found Null values in dataset:")
        print(null_counts[null_counts > 0])
    else:
        print("\n[OK] No Null values found in the primary dataset.")

if __name__ == "__main__":
    run_stability_check()
