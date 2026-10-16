# Design Document: Phase 3 QA Automation (Intelligence & Analytics)

**Session ID**: 2026-05-27-phase-3-qa-resume-v2
**Status**: Draft
**Date**: 2026-05-27

## 1. Objective
Resume and automate the QA process for Phase 3 of the Finance Tracker CLI, specifically focusing on the Intelligence & Analytics modules:
- **Flow E**: ML Sniper, Agent Senate, Butterfly Map.
- **Flow F**: Stock Analyzer.
- **Flow G**: Predictive ML Forecasting.
- **Flow I**: Whale Profiler.

## 2. Requirements
- **Automation**: Full automation using Python scripts.
- **Environment**: Must run within the `PERSONAL` profile (Intelligence features are disabled in `BUSINESS`).
- **No Prisma**: Strictly use SQLite repositories (already the case in the codebase).
- **Validation**: Verify that each flow returns expected technical analysis, predictions, or risk maps.
- **Robustness**: Handle network failures or missing data gracefully without crashing the runner.

## 3. Architecture
The automation will consist of a `CLIDriver` utility and specific test cases for each flow.

### 3.1 CLIDriver Utility
- **Implementation**: Uses `subprocess.Popen` with `stdin=PIPE` and `stdout=PIPE`.
- **Functionality**:
    - `send_input(keys: List[str])`: Sends a sequence of keys/inputs to the CLI.
    - `capture_output()`: Reads stdout to verify presence of keywords (e.g., "ML SNIPER", "AGENT SENATE", "Correlation").
    - `cleanup()`: Ensures the process is killed after testing.

### 3.2 Test Flow Mapping
Based on `QA_EXHAUSTIVE_TEST_PLAN.md`:

| Flow | Menu Sequence | Verification Keywords |
| :--- | :--- | :--- |
| **E.1 (Sniper)** | `1` -> `5` -> `BTCUSD` -> `crypto` | "TARGET", "CONFIDENCE" |
| **E.2 (Senate)** | `1` -> `10` -> `AAPL` -> `us` | "VOTING", "BUY/HOLD/SELL" |
| **E.3 (Butterfly)** | `1` -> `11` -> `TSLA` -> `us` | "CORRELATION", "RISK MAP" |
| **F.1 (Analyzer)** | `5` -> `MSFT` | "EXPECTANCY", "KELLY CRITERION" |
| **G.2 (Predict)** | `6` -> `NVDA` | "PREDICTION", "CLOSING PRICE" |
| **I.1 (Whale)** | `9` -> `ETHUSD` -> `crypto` | "WHALE", "VOLUME PATTERNS" |

## 4. Implementation Plan (High Level)
1. **Scaffold**: Create `tests/automation/cli_driver.py` and `tests/automation/test_phase3_intelligence.py`.
2. **Helper**: Implement `CLIDriver` to handle the interactive nature of `main.py` (which uses `console.input`).
3. **Tests**: Write the test functions for Flows E, F, G, and I.
4. **Validation**: Run the tests and capture output logs in `tests/logs/qa_phase3_results.log`.

## 5. Security & Safety
- Use dummy data or test tickers where possible to avoid excessive API usage.
- Ensure `data/` directory is backed up before running tests if necessary (though these are read-only flows for the most part).

## 6. Constraints Check
- No Prisma? Yes (using `SQLiteInvestmentRepository`).
- Standard Design Depth? Yes.
- Full Automation? Yes.
- Profile Isolation? Yes, the script will ensure `PERSONAL` profile is active.
