---
title: "Exhaustive QA & Testing Design"
created: "2026-05-26T14:30:00Z"
status: "approved"
authors: ["TechLead"]
type: "design"
design_depth: "standard"
task_complexity: "complex"
---

# Exhaustive QA & Testing Design Document

## Problem Statement

The `finance-tracker` project requires a comprehensive verification of its CLI application to ensure functional correctness, data integrity, and strict isolation between profiles. The `QA_EXHAUSTIVE_TEST_PLAN.md` provides a roadmap, but its execution must be systematic, reproducible, and robust.

## Requirements

### Functional Requirements

1. **REQ-A (Profile Isolation)**: Ensure data in "Personal" profile does not leak into "Business" profile.
2. **REQ-B (Investment Integrity)**: Validate FIFO logic, realized P/L calculations, and real-time portfolio tracking.
3. **REQ-C (Financial Management)**: Verify expense tracking, category-based budgeting, and income management.
4. **REQ-D (OCR Service)**: Test image-based receipt scanning, manual correction, and module integration.
5. **REQ-E (Intelligence Modules)**: Validate ML-driven advice, Agent Senate voting, and Butterfly Map correlations.
6. **REQ-F (Stock Analysis)**: Ensure technical analysis (Kelly Criterion, Expectancy) and quantitative scoring are accurate.
7. **REQ-G (Predictive ML)**: Verify price forecasting and sniper picks integration.
8. **REQ-H (Specialized Reporting)**: Test Behavioral Finance (Personal) and P&L (Business) reports.
9. **REQ-I (Whale Tracking)**: Validate volume-based movement detection for crypto/stocks.
10. **REQ-K (System Integrity)**: Ensure safe exit and database health after operations.

### Non-Functional Requirements

1. **Robustness**: Application must not crash on invalid inputs (type mismatches, empty inputs).
2. **Offline Resilience**: Essential features must fail gracefully without internet connection.
3. **Reproducibility**: Tests should be scriptable to allow for regression testing.

### Constraints

- **Input Mode**: Interactive integer-based menu system.
- **Persistence**: SQLite databases in `apps/cli/profiles/`.
- **Environment**: Must run via `run-cli.bat` or `python apps/cli/main.py`.

## Approach

### Selected Approach: Scripted CLI Interaction & Parallel Verification

I will employ a **Phase-based Scripted Execution** strategy. 
1. **Tooling**: We will use Python's `subprocess` and `pexpect` (or simple `communicate`) to simulate user input sequences defined in the test plan.
2. **Orchestration**: Maestro will delegate specific "Flows" to parallel subagents to maximize throughput.
3. **Validation**: Each agent will not only run the flow but also verify the resulting state in the database using the `repository` layer or direct SQL checks.

### Alternatives Considered

- **Manual Interactive Testing**: Too slow and error-prone for an "exhaustive" requirement.
- **Full Pytest Integration**: Ideal, but requires significant refactoring of the CLI to be fully testable without a TTY. Scripted interaction is a better "black-box" fit for the current state.

## Architecture

### Component Diagram

```
[Test Orchestrator] -> [Subagent: Flow A] -> [CLI App] -> [SQLite DB]
                    -> [Subagent: Flow B] -> [CLI App] -> [SQLite DB]
                    ...
                    -> [Verification Engine] -> [DB Integrity Checks]
```

### Data Flow

1. Input Sequences (Integers/Strings) are injected into `stdin`.
2. CLI App processes logic and writes to profile-specific databases.
3. Subagents read `.db` files after execution to verify state changes (e.g., balance increase, lot creation).

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1: Research | `tester` | Yes | Validation of paths and dummy data setup |
| 2: Core Flows | `tester`, `data_engineer` | Yes | Execution of Flows A, B, C, J |
| 3: Intel Flows| `tester`, `ml_engineer` | Yes | Execution of Flows E, F, G, I |
| 4: Integration| `tester`, `security_engineer`| Yes | Execution of Flows D, H, K |
| 5: Resilience | `debugger`, `performance_engineer`| Yes | Negative testing results |
| 6: Completion | `technical_writer` | No | Final QA Summary Report |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Database corruption during stress test | HIGH | LOW | Always use `dummy_test.db` and backup existing profiles before testing. |
| Network latency causing flow timeouts | MEDIUM | MEDIUM | Implement wait times and retry logic for API-dependent menus. |
| Inconsistent CLI output formats | MEDIUM | LOW | Use regex for pattern matching in CLI responses. |

## Success Criteria

1. All 11 Flows (A-K) executed with 100% pass rate on expected outcomes.
2. Zero crashes during Negative Testing.
3. Verified profile isolation between Personal and Business data.
4. Comprehensive `QA_SUMMARY_REPORT.md` generated.
