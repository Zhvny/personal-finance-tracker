Last Updated: 29-05-2026 (14:30)

---
title: "Portfolio Optimizer Session 3 - Scalability & Configuration"
created: "2026-05-15T06:45:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Portfolio Optimizer Session 3 Design Document

## Problem Statement
The Portfolio Optimizer currently relies on fragmented configuration sources and legacy hardcoded constraints (notably a bias towards 7 assets), which limits its flexibility for different investor profiles. As the ticker universe grows (targeting 531+ tickers), repeated covariance calculations and linear fitness evaluation introduce significant latency.

## Requirements

### Functional Requirements
1. **REQ-1 (Configurable Size)**: Externalize `min_assets`, `max_assets`, `concentration_tolerance`, `diversification_mode`, and `risk_mode` to `AppConfig`.
2. **REQ-2 (Zero Hardcode)**: Completely remove the hardcoded "7" from `genetic_optimizer.py` and `portfolio_lab.py`.
3. **REQ-3 (Covariance Caching)**: Implement a disk-based cache for covariance matrices, keyed by the hash of the ticker universe and date range.
4. **REQ-4 (Vectorization)**: Refactor GA fitness evaluation to use batch NumPy operations.

### Non-Functional Requirements
1. **Scalability**: Handle a universe of 500+ assets with sub-5s optimization time (post-caching).
2. **Transparency**: Maintain surgical logging for exclusion reasons.

## Approach

### Selected Approach: Config-Driven Vectorized Evolution
Unify configuration in `AppConfig`. Implement `CovarianceManager` for caching. Refactor GA `_calculate_metrics` for population-wide batch processing.

### Decision Matrix
| Criterion | Weight | Batch Vectorization | Async Workers | Linear Search |
|-----------|--------|---------------------|---------------|---------------|
| CPU Efficiency | 40% | 5: Pure NumPy | 4: Multi-proc overhead | 1: O(N*G) loop |
| Complexity | 30% | 4: Medium refactor | 2: High concurrency risk | 5: Simple |
| Latency | 30% | 5: Minimal overhead | 4: Faster than serial | 2: Slow on large pop |
| **Weighted Total** | | **4.7** | **3.4** | **2.5** |

## Architecture

### Key Components
- **AppConfig (domain/config.py)**: Central store for `OptimizerSettings`.
- **PortfolioOptimizer (cli/genetic_optimizer.py)**: The core GA engine.
- **CovarianceCache (infrastructure/cache.py)**: Persistent storage for pre-calculated matrices.

### Component Diagram
```
[AppConfig] <---> [PortfolioLab]
                     |
              [Returns Loader]
                     |
              [CovarianceCache] <---> [Disk/cache.db]
                     |
              [PortfolioOptimizer] (Vectorized)
```

## Agent Team
| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Config expansion, refactored optimizer logic |
| 2     | coder    | No       | Covariance caching implementation |
| 3     | tester   | No       | Scalability benchmarks, regression tests |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Numerical Instability | High | Low | Use standard NumPy covariance with stability checks. |
| Cache Invalidation | Medium | Medium | Hash universe + dates for cache keys. |

## Success Criteria
1. Portfolio size (min/max) is fully controllable via `AppConfig`.
2. Covariance calculation time for 500 assets reduced by >80% on repeat runs.
3. No hardcoded asset limits remain in the backend.
