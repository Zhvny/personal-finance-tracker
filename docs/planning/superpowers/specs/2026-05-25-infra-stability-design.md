Last Updated: 29-05-2026 (14:30)

# 🏗️ Design Document: Part 1 - Infrastructure & Stability Remediation

**Date:** 2026-05-25 (21:15)
**Status:** DRAFT (Awaiting User Review)

## 1. Problem Statement
The finance-tracker project is currently in a "broken" state due to technical debt and failed merges. 
- **Critical Failure:** `packages/core/infrastructure/shared/config.py` contains raw git merge markers.
- **Path Fragility:** `BASE_DIR` calculation uses `parents[n]`, which fails as the project evolves.
- **Mapping Misalignment:** Imports expect `packages.core` but physical layout uses `packages/core/infrastructure`.

## 2. Proposed Architecture: "Resilient Root"
We will transition from relative-parent counting to **Marker-Based Root Detection**.

### 2.1 Marker Logic
The `Config` class will dynamically locate the project root by searching upwards for a `GEMINI.md` or `.setup_done` file. This ensures that even if we refactor directory depths, the system remains stable.

### 2.2 Source of Truth Alignment
We will explicitly map all "Legacy" paths (like `packages/cli`) to the "SSOT" path (`apps/cli`) in the configuration layer to prevent runtime `FileNotFoundError`.

## 3. Implementation Approach

### Approach A: The "Surgical Fix" (Recommended)
1.  **Resolve Conflicts:** Manually merge the `Config` class, preferring the `apps/` layout over the `packages/` layout.
2.  **Implement Marker Detection:** Add a `find_root()` utility method to `Config`.
3.  **Sanitize sys.path:** Update the project's main entry points to include the detected root in `sys.path`.

## 4. Testing & Verification (DoD)
- [ ] **Infrastructure Check:** `python -m packages.core.infrastructure.config` returns the correct paths.
- [ ] **Test Collection:** `pytest --collect-only` completes without `ImportError` or `ModuleNotFoundError`.
- [ ] **Health Check:** `python scripts/health_check.py` returns green status for all core directories.

---
**Next Step:** Once approved, I will create a detailed implementation plan.
