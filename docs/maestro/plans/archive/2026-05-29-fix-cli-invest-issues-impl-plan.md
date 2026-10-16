---
title: \"Fix CLI: INVEST Module Issues Implementation Plan\"
design_ref: \"docs/maestro/plans/2026-05-29-fix-cli-invest-issues-design.md\"
created: \"2026-05-29T11:20:00Z\"
status: \"draft\"
total_phases: 4
estimated_files: 6
task_complexity: \"complex\"
---

# Fix CLI: INVEST Module Issues Implementation Plan

## Plan Overview
- **Total phases**: 4
- **Agents involved**: coder, tester
- **Estimated effort**: Medium-Complex (path resolution, UI modal logic, and analytics expansion)

## Dependency Graph
```
Phase 1: Foundation & ML Restoral
      |
Phase 2: UI & Feature Logic
      |
Phase 3: Analytics Enhancement
      |
Phase 4: Verification & Integration
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Restores data/model visibility |
| 2     | Phase 2 | Sequential | 1 | Fixes UX and currency logic |
| 3     | Phase 3 | Sequential | 1 | Enhances analytical drivers |
| 4     | Phase 4 | Sequential | 1 | Final validation |

## Phase 1: Foundation & ML Restoral
### Objective
Restore data visibility for portfolios and connectivity for ML/Data services by fixing incorrect hardcoded paths.

### Agent: coder
### Parallel: No

### Files to Modify
- `apps/cli/investment_tracker/main.py`: Update `PortfolioApp` initialization to use `Config` for DB path; fix `_load_ticker_df` CSV path.
- `apps/cli/prediction_service.py`: Update `PredictionService.get_prediction` to look in `models/prod/`.

### Validation
- Verify `VIEW_FORTOFOLIO` successfully initializes (no more "no data" error if DB exists).
- Verify `SNIPER_ADVICE` and `AGENT_SENATE` can find their respective files.

## Phase 2: UI & Feature Logic
### Objective
Decouple the save prompt from informational checks and fix USD-centric charting for IDX stocks.

### Agent: coder
### Parallel: No

### Files to Modify
- `apps/cli/investment_tracker/ui/cli_view.py`: Add `mode` parameter to `get_investment_input` (default 'ADD'). Skip save prompt if mode is 'CHECK'.
- `apps/cli/investment_tracker/main.py`: Update `quick_check` call to pass `mode='CHECK'`.
- `apps/cli/investment_tracker/services/historical_service.py`: Implement ticker-suffix detection for currency symbols and price normalization.

### Validation
- Run `INVEST > QUICK_CHECK` and confirm it does NOT ask to save.
- View P/L chart for an IDX ticker (e.g., `BBCA.JK`) and verify IDR/generic labels.

## Phase 3: Analytics Enhancement
### Objective
Expand the macro driver set in the Butterfly Map and enhance UI highlighting for high-impact correlations.

### Agent: coder
### Parallel: No

### Files to Modify
- `apps/cli/investment_tracker/services/butterfly_service.py`: Expand driver dictionary with additional indicators (e.g., Bond Yields, Commodity Indices).
- `apps/cli/investment_tracker/ui/cli_view.py`: Update `show_butterfly_map` to prominently highlight drivers with correlation > 0.7.

### Validation
- Run `INVEST > BUTTERFLY_MAP` and verify > 10 drivers are listed.
- Confirm "HIGH" impact drivers are visually distinct.

## Phase 4: Verification & Integration
### Objective
Perform end-to-end verification across different profiles and asset classes.

### Agent: tester
### Parallel: No

### Validation
- Switch profiles and verify portfolio visibility follows the profile.
- Smoke test all fixed menus: `VIEW_FORTOFOLIO`, `QUICK_CHECK`, `SNIPER_ADVICE`, `AGENT_SENATE`, `BUTTERFLY_MAP`.
