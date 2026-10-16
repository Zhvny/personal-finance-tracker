---
title: "Fix Stocks CLI Sorting Bug Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-31-fix-stocks-cli-sort-bug-design.md"
created: "2026-05-31T22:55:00Z"
status: "draft"
total_phases: 2
estimated_files: 1
task_complexity: "medium"
---

# Fix Stocks CLI Sorting Bug Implementation Plan

## Plan Overview

- **Total phases**: 2
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Small; targeted fix in one file with verification.

## Dependency Graph

```
Phase 1: Fix sorting logic (coder)
   |
Phase 2: Verify TUI stability (tester)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Code implementation |
| 2     | Phase 2 | Sequential | 1 | Verification |

## Phase 1: Fix Sorting Logic

### Objective
Update `tui.py` to use explicit column keys for sorting to prevent the DataTable crash.

### Agent: `coder`
### Parallel: No

### Files to Modify

- `apps/cli/stock_analyzer/infrastructure/tui.py`
    - Update `on_mount` to define keys for columns (specifically "CSS").
    - Update `_add_row` to use the new column key in `table.sort()`.

### Implementation Details

1. In `on_mount`, change `self.query_one(f"#{tid}", DataTable).add_columns(*cols)` to use `add_column` calls or find a way to assign keys. Note: Textual's `add_columns` (plural) might not support per-column keys easily. Switching to individual `add_column` calls for the CSS column is more reliable.
2. Specifically, define a constant or local variable for the CSS column key (e.g., `"col_css"`).
3. In `_add_row`, replace `table.sort("CSS", reverse=True)` with `table.sort("col_css", reverse=True)`.

### Validation

- Check for syntax errors.
- Run the CLI (if possible in this environment) or verify via unit test mocks.
- `python -m py_compile apps/cli/stock_analyzer/infrastructure/tui.py`

### Dependencies

- Blocked by: None
- Blocks: Phase 2

## Phase 2: Verify TUI Stability

### Objective
Verify that the CLI 'Stocks' view no longer crashes and sorts correctly.

### Agent: `tester`
### Parallel: No

### Implementation Details

1. Create a reproduction script or unit test that mocks the `DataTable` and simulates the row addition/sorting process.
2. Verify that `table.sort` is called with the correct key and no exception is raised.

### Validation

- Run the verification script.
- Check logs for any remaining "WORKER CRASHED" errors related to sorting.

### Dependencies

- Blocked by: Phase 1
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/stock_analyzer/infrastructure/tui.py` | 1 | Fix the sorting bug |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | LOW | Targeted fix in a well-identified location. |
| 2     | LOW | Verification is straightforward. |

## Execution Profile

```
Execution Profile:
- Total phases: 2
- Parallelizable phases: 0
- Sequential-only phases: 2
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~10 minutes

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
