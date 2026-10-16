Last Updated: 29-05-2026 (14:30)

---
title: "Portfolio Optimizer Session 2 Implementation Plan"
design_ref: "docs\maestro\plans\2026-05-15-portfolio-optimizer-s2-design.md"
created: "2026-05-15T05:55:00Z"
status: "approved"
total_phases: 4
estimated_files: 4
task_complexity: "medium"
---

# Portfolio Optimizer Session 2 Implementation Plan

## Plan Overview

- **Total phases**: 4
- **Agents involved**: coder, tester
- **Estimated effort**: Surgical refactor of the optimization pipeline to support 531+ assets and provide full exclusion traceability.

## Dependency Graph

```
Phase 1 (Config)
      │
      v
Phase 2 (Preprocessing)
      │
      v
Phase 3 (Logic)
      │
      v
Phase 4 (Validation)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1| Sequential| 1           | Config Foundation |
| 2     | Phase 2| Sequential| 1           | Preprocessing Audit |
| 3     | Phase 3| Sequential| 1           | Logic Refactor |
| 4     | Phase 4| Sequential| 1           | End-to-End Validation |

## Phase 1: Foundation: Config Externalization

### Objective
Remove hardcoded asset limits (7) and ensure constraints are configurable.

### Agent: coder
### Parallel: No

### Files to Modify

- `apps/stock_analyzer/domain/config.py` — Remove hardcoded defaults, ensure YAML loading handles new fields.
- `Gemini-Manager/apps/cli/manager/config.py` — Align manager-level constants with Stock Analyzer.

### Validation

- Run `python apps/stock_analyzer/main.py --check-config` (if exists) or manual verification of `AppConfig.load()`.

### Dependencies

- Blocked by: None
- Blocks: Phase 2

## Phase 2: Preprocessing: Traceable Exclusion Loop

### Objective
Provide granular feedback on why specific assets are dropped before optimization.

### Agent: coder
### Parallel: No

### Files to Modify

- `Gemini-Manager/apps/cli/portfolio_lab.py` — Refactor `excluded_stats` and `load_returns` to track tickers per failure reason.

### Validation

- Run Portfolio Lab with a mix of good and corrupted data; verify the "Quality Filter & Exclusion Report" shows ticker names.

### Dependencies

- Blocked by: Phase 1
- Blocks: Phase 3

## Phase 3: Logic: Scalable Genetic Optimizer

### Objective
Refactor the GA to handle large universes without assumption of size.

### Agent: coder
### Parallel: No

### Files to Modify

- `apps/cli/genetic_optimizer.py` — Dynamic chromosome sizing, tournament candidate scaling, and covariance stability fixes.

### Validation

- Unit test `PortfolioOptimizer.optimize` with 50+ synthetic assets.

### Dependencies

- Blocked by: Phase 2
- Blocks: Phase 4

## Phase 4: Validation: Scaling & Integrity Test

### Objective
Empirical verification of 531-asset support.

### Agent: tester
### Parallel: No

### Files to Create

- `tests/test_optimizer_scaling.py` — Script to generate synthetic returns for 531 tickers and run the full pipeline.

### Validation

- `pytest tests/test_optimizer_scaling.py`

### Dependencies

- Blocked by: Phase 3
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/stock_analyzer/domain/config.py` | 1 | AppConfig definitions |
| 2 | `Gemini-Manager/apps/cli/manager/config.py` | 1 | Global constants |
| 3 | `Gemini-Manager/apps/cli/portfolio_lab.py` | 2 | Preprocessing orchestrator |
| 4 | `apps/cli/genetic_optimizer.py" | 3 | GA implementation |
| 5 | `tests/test_optimizer_scaling.py` | 4 | Integration test |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Simple config change. |
| 2 | MEDIUM | Changes core loop; risk of breaking data loading. |
| 3 | HIGH | Large matrix math risk; convergence reliability. |
| 4 | LOW | Read-only validation. |

## Execution Profile

```
Execution Profile:
- Total phases: 4
- Parallelizable phases: 0
- Sequential-only phases: 4
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~15 mins

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
