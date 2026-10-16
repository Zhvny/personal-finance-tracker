Last Updated: 29-05-2026 (14:30)

---
title: "Finance-Tracker Independence"
created: "2026-05-25T20:25:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Finance-Tracker Independence Design Document

## Problem Statement
The `Finance-Tracker` project is currently "managed" by `Gemini-Manager`, creating tight couplings through implicit management (syncing markers), environment dependencies (`PROJECT_PATH`), and fragmented operational logic. This prevents the tracker from being a truly autonomous, portable application.

## Requirements

### Functional Requirements
1. **Local Profile Management**: Move all `ProfileService` logic to be fully contained within `finance-tracker`. `data/active_profile.txt` must be the local source of truth.
2. **Internal Maintenance CLI**: Implement a `maintain` command in `main.py` that handles SQL WAL-mode optimization, Postgres schema updates, and redundant script cleanup.
3. **Dynamic Path Resolution**: Refactor `Config` to resolve all paths relative to the current file's location.
4. **Isolated Data/Cache**: Ensure all logs, caches, and databases remain strictly within the project root.

### Non-Functional Requirements
1. **Path Agnostic**: No requirement for `PROJECT_PATH` or `MANAGER_ROOT` env vars.
2. **Zero-Manager Dependency**: Functionality persists even if `Gemini-Manager` is deleted.

### Constraints
1. **Preserve Data**: No destructive changes to existing databases.
2. **Monorepo Compatibility**: Maintain existing internal `packages/` structure.

## Approach

### Selected Approach: Self-Contained Architecture
- **Config**: Update `packages/core/infrastructure/config.py` for relative resolution.
- **Maintenance**: Port and enhance `MaintenanceService` in `packages/core/application/`.
- **Profiles**: Finalize `ProfileService` as the local authority.

### Decision Matrix (Standard Mode)
| Criterion | Weight | Current | Proposed |
|-----------|--------|---------|----------|
| Autonomy | 40% | 1 | 5 |
| Portability | 30% | 2 | 5 |
| Simplicity | 20% | 3 | 5 |
| Safety | 10% | 4 | 4 |
| **Weighted Total** | | **2.1** | **4.9** |

## Architecture

### Component Diagram
```
[Main Entry (main.py)]
      |
      +--> [Config (Dynamic Pathing)]
      |
      +--> [ProfileService (Local Marker)]
      |
      +--> [MaintenanceService (SQL & Cleanup)]
```

### Data Flow
1. **Startup**: `Config.initialize()` calculates `BASE_DIR` dynamically -> Loads local `.env`.
2. **Profile**: `ProfileService` reads `data/active_profile.txt` directly.
3. **Storage**: All paths derived from `Config.BASE_DIR`.

## Agent Team
| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Config refactor & logic porting |
| 2     | tester   | No       | Verification of independence |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Path Resolution Error | HIGH | LOW | Use `Path.resolve()` relative to `__file__`. |
| Missing Logic Port | MEDIUM | MEDIUM | Source comparison with `MaintenanceManager`. |

## Success Criteria
1. Functional independence from `Gemini-Manager`.
2. Working `maintain` CLI command.
3. Correct local profile switching.
