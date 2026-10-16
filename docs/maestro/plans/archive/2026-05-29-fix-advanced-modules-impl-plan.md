---
title: "Advanced Module Fixes Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-fix-advanced-modules-design.md"
created: "2026-05-29T02:00:00Z"
status: "approved"
total_phases: 4
estimated_files: 8
task_complexity: "complex"
---

# Advanced Module Fixes Implementation Plan

## Plan Overview

- **Total phases**: 4
- **Agents involved**: data_engineer, performance_engineer, coder, tester
- **Estimated effort**: High complexity due to Windows multiprocessing nuances and advanced financial math implementation.

## Dependency Graph

```
Phase 1: Foundation (Data & MP)
    |
Phase 2: Core Enhancements (GA & MP Fix)
    |
Phase 3: Analysis Features (Absorption)
    |
Phase 4: Quality & Validation
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Data Fetcher & Simulation Refactor |
| 2     | Phase 2 | Sequential | 2 | Multiprocessing & GA Logic |
| 3     | Phase 3 | Sequential | 1 | Volume Profile & TUI Integration |
| 4     | Phase 4 | Sequential | 1 | Benchmarking & Testing |

## Phase 1: Real Data Pipeline & MP Foundation

### Objective
Establish a robust data source for the Genetic Optimizer and refactor the Simulation Engine for picklability.

### Agent: data_engineer
### Parallel: No

### Files to Create
- `apps/cli/investment_tracker/services/data_loader.py` — New service to fetch historical returns from Market DB or `DataFetcher`.

### Files to Modify
- `apps/cli/stock_analyzer/adapters/fetcher.py` — Add methods for structured return retrieval.
- `apps/cli/investment_tracker/services/simulation_engine.py` — Ensure `run_monte_carlo` is top-level and all arguments are serializable.

### Implementation Details
- `DataLoader.get_returns(ticker: str, timeframe: str)`: Returns normalized NumPy array of returns.
- Refactor `SimulationEngine` to avoid closure-based lookups which break `pickle`.

### Validation
- Verify `SimulationEngine` functions can be pickled: `python -c "import pickle; from apps.cli.investment_tracker.services.simulation_engine import run_monte_carlo; pickle.dumps(run_monte_carlo)"`
- Run `DataLoader` smoke test against existing market data.

### Dependencies
- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Multiprocessing Fix & Full GA

### Objective
Implement working Windows parallelism for Monte Carlo and a true Genetic Algorithm for XGBoost optimization.

### Agent: performance_engineer
### Parallel: Yes

### Files to Modify
- `apps/cli/investment_tracker/services/risk_service.py` — Implement Windows-safe `ProcessPoolExecutor` with entry-point checks.
- `apps/cli/genetic_optimizer.py` — Replace `_get_random_params` with full GA (Population, Selection, Crossover, Mutation).

### Implementation Details
- `RiskService`: Move executor to a context manager or protected method. Ensure `if __name__ == "__main__":` is respected in entry points like `main.py`.
- `GeneticOptimizer`: Implement `Tournament Selection`, `One-point Crossover`, and `Gaussian Mutation` for continuous parameters.

### Validation
- Benchmark MC simulation time (Sequential vs Parallel).
- Run Genetic Optimizer with a small population and verify fitness improvement over generations.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Absorption Logic & Overlay

### Objective
Enhance the Volume Profiler with absorption detection and integrate into the TUI.

### Agent: coder
### Parallel: Yes

### Files to Modify
- `apps/cli/stock_analyzer/domain/strategies/volume_profile.py` — Add `detect_absorption()` logic.
- `apps/cli/tui_components.py` — Update chart rendering to include Accumulation/Distribution overlays.

### Implementation Details
- Absorption detection: Identify price levels where volume is high but price movement (delta) is low over N periods.
- Overlay: Use distinct colors or intensity in the TUI histogram to mark these zones.

### Validation
- Visual verification in TUI with historical ticker data (e.g., AAPL).
- Unit test `detect_absorption()` with synthetic data.

### Dependencies
- Blocked by: Phase 2
- Blocks: Phase 4

---

## Phase 4: Integration & Audit

### Objective
Finalize integration, verify data integrity, and perform performance benchmarks.

### Agent: tester
### Parallel: No

### Files to Create
- `tests/integration/test_advanced_modules_flow.py` — End-to-end flow from real data to GA optimization.

### Implementation Details
- Performance audit: Compare latency of new modules against baseline.
- Integrity audit: Ensure 100% of optimizer data is sourced from real returns.

### Validation
- `pytest tests/integration/test_advanced_modules_flow.py`
- `pytest tests/unit/test_volume_profile.py`

### Dependencies
- Blocked by: Phase 3
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/investment_tracker/services/data_loader.py` | 1 | Historical data retrieval for Optimizer |
| 2 | `apps/cli/investment_tracker/services/simulation_engine.py` | 1 | Monte Carlo Math (Refactor) |
| 3 | `apps/cli/investment_tracker/services/risk_service.py` | 2 | Parallel execution logic |
| 4 | `apps/cli/genetic_optimizer.py` | 2 | XGBoost GA implementation |
| 5 | `apps/cli/stock_analyzer/domain/strategies/volume_profile.py` | 3 | Absorption detection logic |
| 6 | `apps/cli/tui_components.py` | 3 | UI Visualization of zones |
| 7 | `tests/integration/test_advanced_modules_flow.py` | 4 | E2E Validation |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | LOW | Pure refactor and new service creation. |
| 2     | HIGH | Windows `multiprocessing` is notoriously fragile. GA hyperparameter tuning requires careful range mapping. |
| 3     | MEDIUM | UI rendering complexity in TUI; logic for absorption can be subjective. |
| 4     | LOW | Standard integration testing and benchmarking. |

## Execution Profile

```
Execution Profile:
- Total phases: 4
- Parallelizable phases: 2 (Phase 2, Phase 3)
- Sequential-only phases: 2 (Phase 1, Phase 4)
- Estimated parallel wall time: 2 days
- Estimated sequential wall time: 4 days

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
