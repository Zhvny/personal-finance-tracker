---
title: \"Fix CLI: INVEST Module Issues\"
created: \"2026-05-29T11:15:00Z\"
status: \"approved\"
authors: [\"TechLead\", \"User\"]
type: \"design\"
design_depth: \"standard\"
task_complexity: \"complex\"
---

# Fix CLI: INVEST Module Issues Design Document

## Problem Statement
The `INVEST` module of the `finance-tracker` CLI experiences multiple critical failures across data visibility, user experience, and analytical accuracy:
1. **Data Isolation Breach**: `VIEW_FORTOFOLIO` fails to display existing data due to incorrect path resolution in the repository layer.
2. **UI/UX Modal Confusion**: `QUICK_CHECK` behaves like `QUICK_ADD` due to hardcoded save prompts.
3. **Currency & Region Fragility**: Hardcoded USD assumptions break support for IDX (Indonesian) assets.
4. **Path Resolution Errors**: ML models and raw data CSVs cannot be loaded due to incorrect directory mapping in the monorepo.
5. **Analytical Stagnation**: `BUTTERFLY_MAP` is limited to static drivers and lacks visibility for high-impact correlations.

## Requirements
- **FR-1: Dynamic Profile Path Resolution**: Initialize `InvestmentRepository` with profile-specific data directory.
- **FR-2: Modal UI Input**: Add `confirm_save` parameter to `get_investment_input` to support read-only checks.
- **FR-3: Multi-Currency Normalization**: Detect ticker regions (e.g., `.JK`) and adapt currency symbols/logic.
- **FR-4: Path Mapping Correction**: Update `PredictionService` and data loaders to canonical monorepo paths.
- **FR-5: High-Impact Driver Expansion**: Expand `ButterflyService` drivers and highlight correlations > 0.7 in the UI.

## Approach
### Selected Approach: Architectural Normalization
- **Repository Layer**: Inject profile-specific DB path into `PortfolioApp`.
- **UI Layer**: Modify `CLIView.get_investment_input` to accept a `mode` parameter.
- **Service Layer**: 
  - Add currency detection in `HistoricalDataService`.
  - Fix relative paths in `PredictionService`.
  - Expand driver set in `ButterflyService`.

### Decision Matrix
| Criterion | Weight | Architectural Normalization | Quick-Patching |
|-----------|--------|-----------------------------|----------------|
| **Multi-Profile Safety** | 30% | 5 | 1 |
| **Maintainability** | 30% | 5 | 2 |
| **Accuracy** | 20% | 5 | 3 |
| **Risk of Regression** | 20% | 4 | 5 |
| **Weighted Total** | | **4.8** | **2.5** |

## Agent Team
| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Path fixes, UI refactoring, Service logic updates |
| 2     | tester   | No       | Verification across profiles, ML model validation |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Path Incompatibility | MEDIUM | LOW | Use `os.path.join` based on project root. |
| Breaking UI Signatures | LOW | MEDIUM | Use keyword arguments with defaults. |
| ML Model Loading Latency | LOW | LOW | Resolve paths during initialization. |
| Currency Mis-normalization | MEDIUM | LOW | Fallback to generic labels. |

## Success Criteria
1. `VIEW_FORTOFOLIO` correctly lists active holdings in both Personal and Business profiles.
2. `QUICK_CHECK` displays calculations without prompting to save.
3. IDX stocks show correct currency/labels in P/L charts.
4. `SNIPER_ADVICE` and `AGENT_SENATE` successfully load models/data and return results.
5. `BUTTERFLY_MAP` displays >10 drivers and highlights HIGH impact ones.
