Last Updated: 29-05-2026 (14:30)

# Implementation Plan: Automated QA Resumption (Flow D, H, K)

**Session ID:** resume-qa-testing-v1
**Task Complexity:** complex
**Design Depth:** standard

## Phase 1: Test Infrastructure Setup
Setup the foundational components for automated CLI interaction and reporting.

- **Task 1.1:** Create `tests/automation/cli_driver.py` - A utility to drive `apps/cli/main.py` via subprocess.
- **Task 1.2:** Create `tests/automation/test_reporter.py` - A unified reporting class.
- **Task 1.3:** Setup `tests/automation/conftest.py` for test profile creation and cleanup.

## Phase 2: Flow D (OCR) Automation
Automate the receipt scanning and expense integration flow.

- **Task 2.1:** Implement `tests/automation/test_flow_d_ocr.py`.
- **Task 2.2:** Add test assets (mock receipt images or data) if not already present.
- **Task 2.3:** Verify database insertion in `expenses.db`.

## Phase 3: Flow H (Reporting) Automation
Automate behavioral and business P&L reports.

- **Task 3.1:** Implement `tests/automation/test_flow_h1_behavioral.py` for Personal profile.
- **Task 3.2:** Implement `tests/automation/test_flow_h2_business.py` for Business profile.
- **Task 3.3:** Verify report generation and content accuracy.

## Phase 4: Flow K (Exit & Integrity) Automation
Automate the safe exit and database integrity checks.

- **Task 4.1:** Implement `tests/automation/test_flow_k_integrity.py`.
- **Task 4.2:** Integrate `PRAGMA integrity_check` for all database files.

## Phase 5: Unified Execution & Reporting
Run the complete suite and produce the final report.

- **Task 5.1:** Execute the full automation suite via a runner script.
- **Task 5.2:** Generate `docs/maestro/qa_report_final.md`.
- **Task 5.3:** Perform final validation of the project state.

## Resource Requirements
- Agents: `tester`, `coder`, `code_reviewer`.
- Tools: `run_shell_command`, `read_file`, `write_file`, `replace`.
- Environment: Python 3.x, `pytest`.
