---
title: "Add Profile Feature Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-31-add-profile-cli-feature-design.md"
created: "2026-05-31T12:05:00Z"
status: "approved"
total_phases: 4
estimated_files: 5
task_complexity: "medium"
---

# Add Profile Feature Implementation Plan

## Plan Overview

- **Total phases**: 4
- **Agents involved**: coder, tester
- **Estimated effort**: Implementation of a dynamic profile registry and CLI UI updates.

## Dependency Graph

```
Phase 1: Foundation
      |
Phase 2: Service Logic
      |
Phase 3: UI Integration
      |
Phase 4: Verification
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Registry & Migration |
| 2     | Phase 2 | Sequential | 1 | Add Profile Logic |
| 3     | Phase 3 | Sequential | 1 | CLI Menu Update |
| 4     | Phase 4 | Sequential | 1 | Testing |

## Phase 1: Foundation: Registry & Migration

### Objective
Replace hardcoded profile list with a dynamic `profiles.json` registry and migrate existing profiles.

### Agent: coder
### Parallel: No

### Files to Create
- `apps/cli/profiles.json` — Initial registry containing `["personal", "business"]`.

### Files to Modify
- `packages/core/application/profile_service.py` — Update `__init__` and `get_available_profiles` to use `profiles.json`.

### Implementation Details
- `ProfileService` should check if `apps/cli/profiles.json` exists.
- If not, create it with default profiles.
- Load profiles from JSON during initialization.

### Validation
- Verify `profiles.json` exists after initialization.
- Verify `get_available_profiles()` returns the registered profiles.

---

## Phase 2: Service Logic: Add Profile Feature

### Objective
Implement the logic for adding new profiles, including validation and directory scaffolding.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/core/application/profile_service.py` — Add `add_profile(name)` method.

### Implementation Details
- `add_profile(name)`:
  - Normalize name to lowercase.
  - Validate: `^[a-zA-Z0-9_]+$`.
  - Check for duplicates in registry.
  - Check if directory `apps/cli/profiles/{name}/` already exists.
  - Add to registry list and save `profiles.json`.
  - Create directory `apps/cli/profiles/{name}/`.

### Validation
- Call `add_profile("test_profile")` in a script.
- Verify directory exists and `profiles.json` is updated.

---

## Phase 3: UI Integration: Profile Management Menu

### Objective
Update the CLI menu to provide an "Add Profile" option.

### Agent: coder
### Parallel: No

### Files to Modify
- `apps/cli/main.py` — Refactor profile switching into a management sub-menu.

### Implementation Details
- Rename `switch_profile()` to `manage_profiles()`.
- Add a choice menu: `[1] Switch Profile`, `[2] Add New Profile`.
- Implement `[2]` using `console.input()` and `profile_service.add_profile()`.
- Ensure `get_dispatch` maps "8" to `manage_profiles()`.

### Validation
- Launch CLI and navigate to Option 8.
- Verify "Add New Profile" flow works and creates the profile.

---

## Phase 4: Verification: End-to-End Testing

### Objective
Validate the entire profile creation lifecycle and data isolation.

### Agent: tester
### Parallel: No

### Files to Create
- `tests/unit/test_profile_creation.py` — New test suite.

### Implementation Details
- Test successful profile creation.
- Test validation failures (invalid chars, duplicates).
- Test switching to new profile and verifying that it uses the correct data path.

### Validation
- Run `pytest tests/unit/test_profile_creation.py`.

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/profiles.json` | 1 | Profile registry |
| 2 | `packages/core/application/profile_service.py` | 1, 2 | Logic |
| 3 | `apps/cli/main.py` | 3 | UI |
| 4 | `tests/unit/test_profile_creation.py` | 4 | Tests |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | MEDIUM | Critical to maintain compatibility with existing 'personal' and 'business' data. |
| 2     | LOW | Standard logic, low risk of regressions. |
| 3     | LOW | UI update, safe within sub-menu. |
| 4     | LOW | Verification only. |

## Execution Profile

```
Execution Profile:
- Total phases: 4
- Parallelizable phases: 0
- Sequential-only phases: 4
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~4 turns

Note: Sequential execution is chosen for strict foundational stability.
```
