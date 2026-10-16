---
title: "Fix Stocks CLI Sorting Bug"
created: "2026-05-31T22:50:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Fix Stocks CLI Sorting Bug Design Document

## Problem Statement

The 'Stocks' view in the CLI crashes when updating ticker rows because it attempts to sort using the column label "CSS" (`table.sort("CSS", reverse=True)`). The Textual library's `DataTable.sort` method requires a column key or an integer index, not a display label. This results in a "WORKER CRASHED" error and fatal logs in the TUI.

## Requirements

### Functional Requirements

1. **REQ-1**: Fix the sorting logic to use column keys instead of labels.
2. **REQ-2**: Ensure all tables (`main_table`, category tables, `favorites_table`) sort correctly by the CSS value in descending order.
3. **REQ-3**: Maintain existing UI appearance and column ordering.

### Non-Functional Requirements

1. **REQ-N1**: Robustness: The fix should prevent future regressions if column names change.

### Constraints

- Must stay within the `apps/cli/stock_analyzer/infrastructure/tui.py` implementation.
- Must use Textual's `DataTable` API correctly.

## Approach

### Selected Approach

**Define Column Keys**

Instead of relying on column indices (which are fragile) or labels (which are unsupported), we will explicitly define a key for the "CSS" column when adding columns to the tables. We will then use this key in all `sort()` calls.

### Alternatives Considered

#### Use Column Index

- **Description**: Hardcode the index `1` for the CSS column.
- **Pros**: Very small code change.
- **Cons**: Fragile; if a column is added before "CSS", the sort will target the wrong data.
- **Rejected Because**: The user preferred the more robust "Define Column Keys" approach.

### Decision Matrix

| Criterion | Weight | Use Column Index | Define Column Keys |
|-----------|--------|------------------|--------------------|
| Robustness | 50% | 2: Fails if columns shift | 5: Independent of column order |
| Simplicity | 30% | 5: Single character change | 4: Requires updating add_columns |
| Maintainability | 20% | 2: Needs manual index tracking | 5: Explicit and clear |
| **Weighted Total** | | **3.2** | **4.7** |

## Architecture

### Key Interfaces

`DataTable.add_columns(*labels, **kwargs)` will be used to define the key for the CSS column.
`DataTable.sort(column_key, reverse=True)` will be used with the defined key.

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Fixed `tui.py` sorting logic |
| 2     | tester   | No       | Verification of TUI stability |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Column misalignment | MEDIUM | LOW | Use descriptive keys and verify column order during implementation |

## Success Criteria

1. CLI 'Stocks' view no longer crashes during ticker updates.
2. Tables are correctly sorted by CSS score (descending).
3. System log shows successful initialization and no fatal sorting errors.
