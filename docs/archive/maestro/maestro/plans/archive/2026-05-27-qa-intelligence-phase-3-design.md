# 🎨 Design Document: QA Intelligence & Analytics (Phase 3)

**Date**: 2026-05-27  
**Status**: Approved  
**Design Depth**: Standard  
**Task Complexity**: Medium  

## 1. Problem Statement
The `finance-tracker` project requires a robust, automated QA and testing suite for its Intelligence and Analytics modules (Flows E, F, G, I). Manual testing is insufficient for verifying the complex integration between the CLI, ML models, and live market APIs. We need a runner that strictly validates visual and data output to ensure reliability and data integrity.

## 2. Requirements
- **Full Automation**: Execute Flows E, F, G, and I via a Python subprocess runner (stdin piping).
- **Strict Live Mode**: Tests must use real-time data; failure to fetch constitutes a test failure. — *Ensures the app is functional in production conditions.*
- **UI/Regex Validation**: Strictly match CLI table headers and labels (e.g., "Confidence Score", "Kelly Criterion"). — *Prevents visual regressions and data mismatches.*
- **Data Strategy**: Strictly **SQLite only**; no Prisma.
- **Profile Isolation**: Use a dedicated `QA_INTELLIGENCE` profile for testing.

## 3. Approach
### 3.1 Runner Architecture
The existing `tests/run_exhaustive_qa.py` will be extended with specialized regex patterns for Phase 3. 
- **Input Simulation**: `subprocess.Popen` with `stdin.write` for integer-based navigation.
- **Normalization**: Strip ANSI color codes and normalize whitespace before matching.

### 3.2 Verification Engine
A configuration map will define expected regex patterns for each flow:
- **Flow E (ML Sniper)**: `r"Target Price"`, `r"Confidence Score"`.
- **Flow F (Stock Analyzer)**: `r"Kelly Criterion"`, `r"Expectancy"`.
- **Flow G (Forecasting)**: `r"Forecasting Result"`.
- **Flow I (Whale Profiler)**: `r"Whale Movement Detected"`.

### 3.3 Data Isolation
Target `apps/cli/profiles/QA_INTELLIGENCE/` to prevent interference with Personal/Business data.

## 4. Architecture
- **Control Flow**: `ExhaustiveQARunner` -> `subprocess` -> `apps/cli/main.py`.
- **Persistence**: `sqlite3` for audit trail verification.
- **External**: `yfinance`, `crypto-api` (Strict Live).

## 5. Agent Team
- **Tester**: Lead implementation of regex patterns and runner logic.
- **Coder**: Ensure `main.py` entry points remain compatible with piping.
- **Debugger**: Root cause analysis if "Strict Live" fails due to API changes.

## 6. Risk Assessment
- **API Rate Limits**: Strict Live Mode may trigger rate limits. *Mitigation*: Log specific API error codes to distinguish from app bugs.
- **Regex Fragility**: UI changes break tests. *Mitigation*: Focus regex on stable headers rather than dynamic values where possible.

## 7. Success Criteria
- [ ] 100% of Flow E, F, G, and I tests pass in a clean environment.
- [ ] All tests fail gracefully with descriptive errors if internet is disconnected.
- [ ] No data leakage between `QA_INTELLIGENCE` and other profiles.
- [ ] Zero Prisma imports in the test suite.
