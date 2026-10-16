---
title: "Investment Tracker Import Fix Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-31-investment-import-fix-design.md"
created: "2026-05-31"
status: "draft"
total_phases: 2
estimated_files: 8
task_complexity: "medium"
---

# Investment Tracker Import Fix Implementation Plan

## Plan Overview

- **Total phases**: 2
- **Agents involved**: coder, tester
- **Estimated effort**: Medium complexity, targeted import refactor.

## Dependency Graph

```
Phase 1: Standardize Imports (coder)
    |
    v
Phase 2: Verification (tester)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Foundation/Implementation |
| 2     | Phase 2 | Sequential | 1 | Verification |

## Phase 1: Standardize Imports

### Objective
Convert all relative imports in `apps/cli/investment_tracker/` (specifically services and core) to absolute imports starting from `apps.cli.investment_tracker`.

### Agent: coder
### Parallel: No

### Files to Modify

- `apps/cli/investment_tracker/core/__init__.py` — Change `.calculator` and `.interfaces` to absolute.
- `apps/cli/investment_tracker/services/__init__.py` — Change `.fx_service`, `.stock_service`, etc. to absolute.
- `apps/cli/investment_tracker/services/base_price_service.py` — Change `..core.interfaces` to absolute.
- `apps/cli/investment_tracker/services/crypto_service.py` — Change `.base_price_service` and `..core.interfaces` to absolute.
- `apps/cli/investment_tracker/services/fx_service.py` — Change `..core.interfaces` to absolute.
- `apps/cli/investment_tracker/services/gold_service.py` — Change `.base_price_service` and `..core.interfaces` to absolute.
- `apps/cli/investment_tracker/services/risk_service.py` — Change `.simulation_engine` to absolute.
- `apps/cli/investment_tracker/services/stock_service.py` — Change `.base_price_service` and `..core.interfaces` to absolute.

### Implementation Details

- All imports starting with `from .` or `from ..` within `apps/cli/investment_tracker/` should be updated.
- Use the prefix `apps.cli.investment_tracker`.
- Example: `from .fx_service import FXService` -> `from apps.cli.investment_tracker.services.fx_service import FXService`.
- Example: `from ..core.interfaces import IFXService` -> `from apps.cli.investment_tracker.core.interfaces import IFXService`.

### Validation

- Run `python apps/cli/main.py` and attempt to enter the Investment Tracker module (Choice 1).
- Ensure no `ImportError` or `ValueError: attempted relative import beyond top-level package` occurs.

### Dependencies

- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Verification

### Objective
Verify that the import changes did not break existing functionality and that unit tests pass.

### Agent: tester
### Parallel: No

### Validation

- Run unit tests: `pytest tests/unit/test_investment_logic.py`
- Verify main dashboard still functions (Choice 1 in `main.py`).
- Check `FXService` integration in `main.py` (which currently has a try/except block that might be swallowing errors).

### Dependencies

- Blocked by: Phase 1
- Blocks: None

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/investment_tracker/core/__init__.py` | 1 | Export core logic |
| 2 | `apps/cli/investment_tracker/services/__init__.py` | 1 | Export services |
| 3 | `apps/cli/investment_tracker/services/base_price_service.py` | 1 | Base class for price services |
| 4 | `apps/cli/investment_tracker/services/crypto_service.py` | 1 | Crypto pricing |
| 5 | `apps/cli/investment_tracker/services/fx_service.py` | 1 | Currency conversion |
| 6 | `apps/cli/investment_tracker/services/gold_service.py` | 1 | Gold pricing |
| 7 | `apps/cli/investment_tracker/services/risk_service.py` | 1 | Risk simulation |
| 8 | `apps/cli/investment_tracker/services/stock_service.py` | 1 | Stock pricing |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | LOW | Targeted import changes are low risk but frequent source of bugs. |
| 2     | LOW | Verification phase ensures stability. |

## Execution Profile

```
Execution Profile:
- Total phases: 2
- Parallelizable phases: 0
- Sequential-only phases: 2
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 10-15 minutes

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
