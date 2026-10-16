# Failure State Simulation & Resilience Report
**Date**: 14-05-2026 (16:15)
**Status**: COMPLETED
**Target**: Stock Analyzer, Investment Tracker & Core Infrastructure

## 1. Executive Summary
This document records the simulation of various failure states for the Finance Tracker ecosystem. The goal was to verify that the system handles API outages, malformed data, and connection issues gracefully without crashing (degraded states).

## 2. Simulated Failure States

### 2.1 API Outage (Connection Error)
*   **Method**: Patched `yfinance.download` and `yfinance.Ticker.history` to raise `ConnectionError`.
*   **Result**: 
    *   **Stock Analyzer**: Successfully fell back to **Stale Cache** data. If no cache existed, it returned `None` gracefully and logged the error.
    *   **Investment Tracker**: Successfully fell back to the **Last Known Price** stored in the database.
*   **Status**: PASS (Graceful Degradation)

### 2.2 Response Malformed (Missing Columns)
*   **Method**: Injected a DataFrame containing only `Close` prices, missing `Open`, `High`, `Low`, and `Volume`.
*   **Result**:
    *   **DataCleaner**: Successfully detected missing columns and used `Close` as a proxy for `Open`/`High`/`Low` and `0.0` for `Volume`.
    *   **IndicatorEngine**: Successfully computed indicators using the repaired data.
*   **Status**: PASS (Robust Repair)

### 2.3 Rate Limit Hit
*   **Method**: Patched `yfinance` to raise "Too Many Requests" exceptions.
*   **Result**:
    *   **DataFetcher**: Triggered `tenacity` retry logic (3 attempts with exponential backoff). After exhaustion, it successfully fell back to **Stale Cache**.
*   **Status**: PASS (Retry + Fallback)

### 2.4 No Internet / Offline Mode
*   **Method**: Patched all network-bound services (`requests`, `yfinance`) to raise exceptions and mocked Cache to be empty.
*   **Result**:
    *   **System**: TUI displayed "—" for missing prices and "Data Unavailable" messages. No crashes observed.
*   **Status**: PASS (Graceful Silence)

### 2.5 Empty Dataframe
*   **Method**: Injected `pd.DataFrame()` into the fetch pipeline.
*   **Result**:
    *   **Stock Analyzer**: Discarded analysis early and returned `None`.
    *   **TUI**: Handled `None` results by skipping the row or showing a placeholder.
*   **Status**: PASS (Graceful Skip)

## 3. Implemented Improvements (Task 16 Fixes)

### 3.1 Robust Data Cleaning (`DataCleaner.clean`)
*   Refactored column extraction to use a fresh DataFrame, preventing `ValueError: The truth value ...` when encountering duplicate or MultiIndex columns.
*   Implemented "Essential Price Fallback": If `Close` is missing, try `Adj Close`.
*   Standardized column names (Capitalized) and types (Series, not DataFrames).

### 3.2 Resilience Gates
*   Added `if df['Close'].isna().all(): return None` to prevent downstream indicator math on empty/garbage data.
*   Enforced `min_rows` gate (50 rows) to ensure statistical significance of technical indicators.

## 4. Verification Metrics
| Failure Mode | Recovery Strategy | User Impact |
| :--- | :--- | :--- |
| Network Down | Stale Cache / DB Fallback | Minimal (Yellow "!" alert) |
| API Error | Tenacity Retry (3x) | Slight Delay, then Success |
| Malformed Data | Logic-Based Repair | Full Functionality |
| Zero History | Early Discard | Graceful Skip |

## 5. Maintenance Notes
- **Stale Data Alert**: The TUI now consistently shows a yellow `!` next to tickers when displaying stale data from cache.
- **DXY Degraded State**: Commodities analysis correctly reports `dcds=NaN` when DXY data is missing, rather than computing false signals.
