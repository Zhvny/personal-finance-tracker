Last Updated: 29-05-2026 (14:30)

# Design Document: Automated QA Resumption (Flow D, H, K)

**Date:** 28-05-2026
**Status:** DRAFT
**Scope:** Automated testing of Flow D (OCR), Flow H (Reporting), and Flow K (Integrity).

## 1. Objective
Automate the validation of the Finance Tracker CLI's critical behavioral and reporting paths, ensuring data integrity and correct business/behavioral logic without using Prisma.

## 2. Technical Approach

### 2.1 Test Harness
- **Framework:** `pytest`
- **Mechanism:** `subprocess.Popen` with `stdin=subprocess.PIPE` to simulate user interaction in the interactive CLI.
- **Profile Isolation:** Tests will use dedicated test profiles to avoid polluting user data.
- **Mocking:** Mock external APIs (FX, OCR) where necessary to ensure deterministic results, or use static test images for OCR.

### 2.2 Flow D (OCR & Integration)
- **Input:** Provide a path to a pre-defined test receipt image.
- **Action:** Select menu `4` -> `1`, enter path, confirm/edit data.
- **Validation:** 
    - Check if the receipt data is correctly extracted (Merchant, Date, Total).
    - Verify that exporting to Expense results in a new entry in `expenses.db` for the active profile.

### 2.3 Flow H (Behavioral & Business Reporting)
- **H1 (Personal):** 
    - Populate `expenses.db` with specific patterns (e.g., impulsive spending).
    - Run option `7` in Personal profile.
    - Capture and analyze output for expected behavioral insights.
- **H2 (Business):**
    - Populate `income.db` and `expenses.db` in Business profile.
    - Run option `7` in Business profile.
    - Verify that a quarterly P&L report (PDF/CSV/Text) is generated and its contents match the input data.

### 2.4 Flow K (Exit & Integrity)
- **Action:** Select menu `0`.
- **Validation:**
    - Verify the process exits with code 0.
    - Perform a `PRAGMA integrity_check` on all `.db` files in the profile.
    - Verify that no temporary files or lock files are left behind.

## 3. Unified Reporting
- A custom `TestReporter` class will aggregate results from all `pytest` runs.
- Output: `docs/maestro/qa_report_[timestamp].md` containing:
    - Summary of Pass/Fail.
    - Detailed logs for failures.
    - Performance metrics (execution time).
    - Data integrity confirmation.

## 4. Constraints Alignment
- **No Prisma:** All database operations use `sqlite3` or the existing `SQLiteRepository` classes.
- **Full Automation:** No manual steps required; the script handles interaction.
- **Standard Depth:** Focus on core behavioral paths and integration points.

## 5. Architectural Mitigations
- Use a `conftest.py` to handle setup/teardown of test environments (profiles, databases).
- Implement a `CLIDriver` utility to manage the interaction sequence (menu navigation).
