Last Updated: 29-05-2026 (14:30)

# Design Document: Exhaustive QA & Testing Resumption

## 1. Objective
Resume and complete the exhaustive QA process for the Finance Tracker CLI as specified in `docs/planning/QA_EXHAUSTIVE_TEST_PLAN.md`. Ensure full coverage of all 11 flows (A-K) and negative testing, while adhering to the "No Prisma" constraint.

## 2. Problem Statement
The previous QA attempt failed due to a `UnicodeEncodeError` in the test harness and only covered a subset of the required flows. The current `tests/run_test_flow.py` needs to be enhanced to handle all test scenarios and robustly capture/report results.

## 3. Technical Strategy
- **Test Harness Refinement**: Update `tests/run_test_flow.py` to:
    - Handle encoding issues (UTF-8 enforcement).
    - Support all 11 flows (A-K).
    - Provide better success verification patterns.
    - Log results per flow in separate files under `tests/logs/`.
- **Environment Isolation**: Ensure tests run against a dedicated `test_qa_profile` to avoid messing with user data.
- **Verification Logic**: Implement regex-based verification for each flow's expected output.
- **Reporting**: Generate a final summary report `tests/QA_FINAL_REPORT.md`.

## 4. Test Flows (A-K)
- **Flow A**: Profiling & Isolation (Verify Personal vs Business data).
- **Flow B**: Investment (FIFO Buy/Sell logic).
- **Flow C**: Expenses & Budgeting.
- **Flow D**: OCR & Integration (Mocking image paths or using valid test images).
- **Flow E**: Intelligence (ML Sniper, Senate, Butterfly).
- **Flow F**: Stock Analyzer (Technical Analysis).
- **Flow G**: Predictive ML (Forecasting).
- **Flow H**: Behavioral & Business Reporting.
- **Flow I**: Whale Profiler.
- **Flow J**: Income Management.
- **Flow K**: Exit & Integrity (DB check).

## 5. Negative Testing
- Input validation (alphabet in numeric fields).
- Empty inputs.
- Invalid file paths for OCR.
- Offline behavior (mocking network failures if possible, or verifying graceful degradation).

## 6. Constraints
- **NO PRISMA**: All database interactions must use the existing SQLite/Repository pattern.
- **Environment**: Windows 11, Python 3.13.
- **Isolation**: Use `apps/cli/profiles/test_qa_profile`.
