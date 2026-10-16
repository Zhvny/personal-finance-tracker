---
title: "Investment Tracker Import Fix"
created: "2026-05-31"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Investment Tracker Import Fix Design Document

## Problem Statement
The Investment Tracker module fails to start with "attempted relative import beyond top-level package". This occurs because `apps/cli/main.py` manipulates `sys.path` to load modules, effectively promoting sub-directories to top-level packages. Relative imports (`..core`) in these promoted packages fail because they lose their parent context.

## Requirements
1. **Restore Functionality**: Investment Tracker must launch from the main CLI.
2. **Preserve Portability**: Changes should maintain the module's relative structure where possible.
3. **Monorepo Standard**: Align with root-based package resolution.
4. **No Side Effects**: Ensure no impact on other CLI modules.

## Approach
### Selected: Standardized Absolute Imports
Convert all relative imports in `apps/cli/investment_tracker/services/` to absolute imports starting from the project root (`apps.cli.investment_tracker`).

### Decision Matrix
| Criterion | Weight | Absolute Imports | Launcher Refactor |
|-----------|--------|------------------|-------------------|
| Reliability | 40% | 5: Explicit paths | 3: High risk |
| Portability | 20% | 3: Tied to root | 5: Portability+ |
| Risk | 30% | 5: Surgical | 2: System-wide |
| Consistency| 10% | 4: Monorepo standard| 4: Launcher fix |
| **Weighted Total** | | **4.7** | **3.0** |

## Agent Team
| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Fixed imports in services/ |
| 2     | tester   | No       | Verification results |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Import Drift | LOW | MEDIUM | Use consistent `apps.cli.investment_tracker` prefix. |
| Launcher Conflict | LOW | LOW | Verify manual launch from CLI menu. |

## Success Criteria
1. Investment Tracker launches from `run-cli.bat` successfully.
2. Unit tests for Investment Tracker services pass.
3. No regressions in Portfolio or Sync modules.
