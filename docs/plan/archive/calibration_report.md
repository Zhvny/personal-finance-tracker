Last Updated: 29-05-2026 (14:30)

# ML Confidence Calibration Report
**Date**: 2026-05-20
**Task**: ML Confidence Calibration (Task 27)

## Overview
Audit and tuning of ML confidence distribution to prevent clustering and ensure healthy spread across the [0, 1] range.

## Initial State (Baseline)
- **Calibration Method**: Tanh
- **Scaling Factor (k)**: 0.25
- **Clustering (5-15% Range)**: 12.00%
- **Mean Confidence**: 42.98%
- **Max Confidence**: 98.66%
- **Min Confidence**: 2.63%

### Bin Distribution (k=0.25)
- Bin 0.0-0.1: 12.00%
- Bin 0.1-0.2: 11.50%
- Bin 0.2-0.3: 11.50%
- Bin 0.3-0.4: 13.50%
- Bin 0.4-0.5: 14.00%
- Bin 0.5-0.6: 11.50%
- Bin 0.6-0.7: 8.00%
- Bin 0.7-0.8: 7.00%
- Bin 0.8-0.9: 6.00%
- Bin 0.9-1.0: 5.00%

## Tuning Process
Detected slight clustering in lower-mid ranges. Updated `calculate_confidence` scaling factor to improve spread.

**Change**: `k = 0.25` -> `k = 0.35`

## Final State (Post-Tuning)
- **Calibration Method**: Tanh
- **Scaling Factor (k)**: 0.35
- **Clustering (5-15% Range)**: 9.00%
- **Mean Confidence**: 53.09%
- **Max Confidence**: 99.82%
- **Min Confidence**: 3.68%

### Bin Distribution (k=0.35)
- Bin 0.0-0.1: 8.00%
- Bin 0.1-0.2: 9.00%
- Bin 0.2-0.3: 8.00%
- Bin 0.3-0.4: 10.00%
- Bin 0.4-0.5: 9.50%
- Bin 0.5-0.6: 11.50%
- Bin 0.6-0.7: 12.00%
- Bin 0.7-0.8: 10.50%
- Bin 0.8-0.9: 9.50%
- Bin 0.9-1.0: 12.00%

## Validation Result
**PASS**: No single 0.1-width band exceeds 20% clustering (Max observed: 12.00%). Confidence distribution shows a healthier spread across the entire range.
