Last Updated: 29-05-2026 (14:30)

---
title: "System Remediation and Stabilization Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-system-remediation-stabilization-design.md"
created: "2026-05-29T01:05:00.000Z"
status: "approved"
total_phases: 3
estimated_files: 100
task_complexity: "medium"
---

# System Remediation and Stabilization Implementation Plan

## Plan Overview
- **Total phases**: 3
- **Agents involved**: coder, refactor, tester
- **Estimated effort**: Medium. Focuses on targeted repository fixes, cross-cutting documentation updates, and final system validation.

## Dependency Graph
```
Phase 1: Core Implementation & Profile Cleanup
    |
Phase 2: Metadata & Path Stabilization
    |
Phase 3: Final Verification
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Repo fixes and cleanup |
| 2     | Phase 2 | Sequential | 1 | Paths and timestamps |
| 3     | Phase 3 | Sequential | 1 | Full verification |

## Phase 1: Core Implementation & Profile Cleanup
### Objective
Implement missing repository methods to prevent crashes and remove residual QA profile data.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/core/infrastructure/investment_tracker/sqlite_repository.py`: Implement `get_all_lots_by_ticker` and `get_all_sell_transactions_by_ticker`. Use standard SQLite query patterns and `_map_row_to_investment` / `_map_row_to_sell_transaction` helpers.

### Files to Delete
- `apps/cli/profiles/qa_financial/`: Recursively delete this entire directory.

### Implementation Details
- `get_all_lots_by_ticker`: `SELECT * FROM investments WHERE ticker = ? ORDER BY buy_date ASC`.
- `get_all_sell_transactions_by_ticker`: `SELECT s.*, i.ticker FROM sell_transactions s JOIN investments i ON s.investment_id = i.id WHERE i.ticker = ? ORDER BY s.sell_date DESC`.

### Validation
- Verify `qa_financial` is gone via `ls`.
- Signature check for implemented methods.

### Dependencies
- Blocked by: None
- Blocks: Phase 2, Phase 3

---

## Phase 2: Metadata & Path Stabilization
### Objective
Resolve health check failures related to hardcoded absolute paths and missing documentation timestamps.

### Agent: refactor
### Parallel: No

### Files to Modify
- `docs/planning/INFRA_AUDIT_LOG.md`: Refactor absolute paths to placeholders or relative paths.
- `docs/superpowers/plans/2026-05-29-vwap-signals.md`: Refactor absolute paths.
- `tests/automation/probe_income.py`: Refactor absolute paths.
- `tests/automation/probe_profiles.py`: Refactor absolute paths.
- **Documentation Batch**: Inject `dd-mm-yyyy (hh:mm)` timestamps into 93 MD files identified by `health_check.py`.

### Implementation Details
- Use regex to identify missing headers and inject current timestamp.
- Use relative paths (e.g., `./` or `../`) where absolute paths were used.

### Validation
- `scripts/health_check.py` should show 0 failures for paths and timestamps.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Final Verification
### Objective
Ensure system stability and 100% test pass rate after remediation.

### Agent: tester
### Parallel: No

### Validation
- `pytest tests/unit`: 100% pass rate.
- `run-cli.bat`: Verify application launches to main menu without crash.
- `scripts/health_check.py`: Final pass for all categories.

### Dependencies
- Blocked by: Phase 2
- Blocks: None

---

## File Inventory
| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `sqlite_repository.py` | 1 | Implement missing logic |
| 2 | `qa_financial/` | 1 | Delete polluted data |
| 3 | `INFRA_AUDIT_LOG.md` | 2 | Path refactoring |
| 4 | `... (93 MD files)` | 2 | Timestamp injection |

## Risk Classification
| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Standard SQL implementation, targeted cleanup. |
| 2 | MEDIUM | High number of file modifications (93+); needs precise regex to avoid corruption. |
| 3 | LOW | Verification only. |

## Execution Profile
```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 3 turns
```
