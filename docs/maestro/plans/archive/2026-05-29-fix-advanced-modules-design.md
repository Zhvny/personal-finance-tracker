---
title: "Advanced Module Fixes"
created: "2026-05-29T01:30:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "complex"
---

# Advanced Module Fixes Design Document

## Problem Statement

The "Advanced" modules of the `finance-tracker` project currently suffer from technical debt and implementation gaps that prevent them from delivering their intended value:
- **Monte Carlo Simulator**: The core simulation engine is restricted to synchronous execution because `ProcessPoolExecutor` fails on Windows. This leads to TUI hangs and poor performance during large-scale "Probability of Ruin" calculations.
- **Volume Profiler**: It provides basic histogram data but lacks the sophisticated "absorption" and "accumulation zone" logic required to detect market participant behavior (e.g., "bandar" accumulation). This makes it a "partial" tool rather than a professional trading analyzer.
- **Genetic Optimizer**: The optimizer's credibility is compromised by the use of fabricated (mock) data in the TUI integration. Furthermore, it lacks a true genetic algorithm implementation, currently relying on simple random search for XGBoost parameter optimization.

## Requirements

### Functional Requirements
- **FR-1: Windows Multiprocessing Support**: Fix the `ProcessPoolExecutor` in `RiskService` to support parallel execution on Windows. This includes implementing proper entry-point protection and ensuring object serializability.
- **FR-2: Advanced Absorption Logic**: Update `VolumeProfile` to detect "absorption" (price stalling at high volume zones). This must use both OHLCV patterns and Tick data (where available) to identify buy/sell pressure imbalances.
- **FR-3: Integrated Accumulation Overlay**: Visualize accumulation/distribution zones as an overlay on the existing Volume Profile histogram within the TUI/CLI.
- **FR-4: Real Data Pipeline**: Replace all mock data generation (`np.random.normal`) in `tui.py` with a robust historical data loader that pulls real market returns from the project's database.
- **FR-5: Full Genetic Algorithm**: Implement a proper GA (Population, Fitness, Selection, Crossover, Mutation) in `genetic_optimizer.py` for XGBoost parameter tuning.

### Non-Functional Requirements
- **NFR-1: Performance**: Multiprocessing simulation must reduce "Probability of Ruin" calculation time by at least 50% on multi-core systems.
- **NFR-2: Data Integrity**: Ensure that the Genetic Optimizer rejects any input data that is not verified as historical/real-market data.
- **NFR-3: UI Responsiveness**: The TUI must remain responsive while simulations are running in the background processes.

## Approach

### Selected Approach
We will pursue a **Direct Integration & Architecture Fix** strategy:
- **Monte Carlo**: Refactor `RiskService` and `SimulationEngine` to support standard Python multiprocessing idioms (entry-point isolation). We will ensure the TUI controller manages the process pool lifecycle safely.
- **Volume Profiler**: Enhance `VolumeProfile.calculate()` to include a multi-pass analysis. Pass 1: standard histogram. Pass 2: absorption detection. Pass 3: accumulation zone mapping.
- **Genetic Optimizer**: Implement a `DataLoader` service to feed the optimizer with actual historical returns. Rebuild the `GeneticOptimizer` class to include standard GA operators (`select`, `crossover`, `mutate`).

### Decision Matrix (Monte Carlo Fix)

| Criterion | Weight | Fix Local MP (Selected) | Background Worker (Alt) |
|-----------|--------|-------------------------|-------------------------|
| Performance | 30% | **5**: Max use of local cores. | **4**: Overhead of IPC/Service. |
| UI Responsiveness | 30% | **4**: Good if managed correctly. | **5**: Best; fully async. |
| Complexity | 20% | **4**: Moderate (refactor only). | **2**: High (new service/IPC). |
| Maintainability | 20% | **5**: Single codebase/monolith. | **3**: Distributed complexity. |
| **Weighted Total** | | **4.5** | **3.8** |

## Architecture

### Component Diagram
```
[ TUI / CLI ]
      |
      +--- [ RiskService ] ----> [ ProcessPoolExecutor ] ----> [ SimulationEngine ]
      |         (Logic)               (Parallelism)                (Math/Sims)
      |
      +--- [ VolumeProfile ] --> [ AbsorptionDetector ] --> [ Tick/OHLCV Data ]
      |         (Overlay)             (Logic)                 (Sources)
      |
      +--- [ GeneticOptimizer ] --> [ DataLoader ] --------> [ Market DB ]
                (GA Logic)            (Real Data)             (Postgres/JSON)
```

### Key Interfaces
- **`RiskService.run_parallel_monte_carlo(params: Dict) -> SimResult`**: Entry point for parallel sims.
- **`AbsorptionDetector.analyze(volume_nodes: List[Node], tick_data: Optional[DataFrame]) -> List[Zone]`**: Returns identified accumulation/absorption zones.
- **`DataLoader.get_historical_returns(ticker: str, period: str) -> np.ndarray`**: Standardized fetcher for the optimizer.

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | `data_engineer`, `coder` | Yes | Real Data Pipeline (`DataLoader`), Multiprocessing refactor foundation. |
| 2     | `performance_engineer`, `ml_engineer` | Yes | Fixed `ProcessPoolExecutor`, Full GA Implementation. |
| 3     | `coder`, `ux_designer` | Yes | Absorption/Accumulation logic, Integrated Overlay. |
| 4     | `tester` | No | Integration tests, benchmarks, data integrity audit. |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Windows Serialization | HIGH | MEDIUM | Use picklable types; ensure entry-point isolation. |
| Tick Data Scarcity | MEDIUM | HIGH | Robust fallback to OHLCV price action logic. |
| GA Convergence | MEDIUM | MEDIUM | Early stopping and wide initial population. |

## Success Criteria

1. Monte Carlo simulations run in parallel on Windows without hangs.
2. Volume Profiler identifies and overlays "Absorption Zones".
3. Genetic Algorithm outperforms current Random Search in XGBoost tuning.
4. 100% real historical data usage in Optimizer production paths.
