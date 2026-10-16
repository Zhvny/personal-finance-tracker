Last Updated: 29-05-2026 (14:30)

---
title: "Session 6: Portfolio Optimizer Integrity Testing"
created: "2026-05-16T17:50:00Z"
status: "draft"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "complex"
---

# Session 6: Portfolio Optimizer Integrity Testing Design Document

## Problem Statement
The Portfolio Optimizer requires rigorous validation to ensure that the ticker universe (531 assets) is correctly processed through the pipeline without silent data loss or unintended truncation (e.g., the "hardcoded 7" bug). We need to simulate failure modes (exclusion logic) and benchmark scalability to ensure the system remains stable and performant as the universe grows.

## Requirements

### Functional Requirements
1. **REQ-1**: Validate that exactly 531 tickers (or the full DB universe) are fetched and passed to the optimizer.
2. **REQ-2**: Implement a simulation framework for exclusion scenarios:
   - Missing OHLCV (Gap detection).
   - Stale Tickers (No updates for >5 trading days).
   - Corrupted History (Negative prices or extreme outliers).
   - Low-Volume Assets (Below liquidity threshold).
3. **REQ-3**: Automated benchmarking for 50, 100, 250, and 531 assets.

### Non-Functional Requirements
1. **REQ-4**: Performance: Optimizer runtime should scale near-linearly or sub-linearly with vectorized GA.
2. **REQ-5**: Observability: Every exclusion must be logged with a specific reason string.

### Constraints
- Integrated with existing `pytest` infrastructure.
- Results documented in `docs/benchmarks_s6.md`.

## Approach

### Selected Approach
**Integrated Test Suite & Simulation Service**
We will implement an `OptimizerIntegrityService` that acts as a test runner and simulation controller. This allows the GUI (from Session 5) to trigger these tests for "Live Diagnostics" while keeping the core logic testable via `pytest`.

### Alternatives Considered
- **Standalone Scripts**: Rejected because it creates maintenance debt and cannot be easily reused by the UI diagnostics panel.
- **Manual Auditing**: Rejected as it is not scalable or repeatable for regression testing.

### Decision Matrix (Standard Mode)

| Criterion | Weight | Integrated Suite | Standalone Scripts |
|-----------|--------|------------------|--------------------|
| Reusability (UI/CLI) | 40% | 5: Full integration | 2: CLI only |
| Maintenance | 30% | 4: Centralized | 3: Fragmented |
| Implementation Speed | 30% | 3: Higher setup | 5: Direct scripts |
| **Weighted Total** | | **4.1** | **3.2** |

## Architecture

### Component Diagram
```
[Database] <-> [IntegrityService] <-> [GeneticOptimizer]
                     |
              [ExclusionSimulator]
                     |
              [BenchmarkEngine] -> [docs/benchmarks_s6.md]
```

### Data Flow
1. `IntegrityService` fetches the full ticker list from `market.db`.
2. `ExclusionSimulator` applies "poison pills" to a temporary data subset.
3. `GeneticOptimizer` runs on the modified subset.
4. `IntegrityService` validates that the expected tickers were discarded and logs the reasons.

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | tester   | No       | `tests/integration/test_optimizer_integrity.py`, Simulation logic |
| 2     | coder    | No       | `scripts/benchmark_optimizer.py`, Result generation |
| 3     | refactor | No       | Integration with diagnostic logs |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Simulation data leakage | HIGH | LOW | Use isolated temporary databases or mocks for simulation. |
| Benchmark interference | MEDIUM | MEDIUM | Ensure no other heavy processes run during benchmarks. |

## Success Criteria
1. `pytest` suite for Session 6 passes with 100% coverage of exclusion modes.
2. Benchmark results for 531 assets are generated and stored in `docs/`.
3. Log audit confirms no silent truncation occurs.
