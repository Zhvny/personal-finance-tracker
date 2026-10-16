Last Updated: 29-05-2026 (14:30)

# ⚡ ELITE SYSTEM AUDIT & STABILITY EXECUTION PLAN

## 1. Executive Summary
This plan details the end-to-end audit of the Finance Tracker monorepo following its massive structural reorganization. The goal is to verify that the split into `@core`, `@api`, `@web`, and `@cli` has not introduced regressions, security holes, or performance bottlenecks. We will execute the 50-vector Elite Execution Matrix and perform deep stack validation.

## 2. Phase 1: Structural Reconciliation & Baseline (Refactor Agent)
- **Objective**: Finalize the monorepo structure and ensure all imports/aliases are correct.
- **Tasks**:
    - **Import Purge**: Remove all erroneous `.src.` path segments from imports in `packages/api` (e.g., in `deps.py`, `accounts.py`).
    - **Service Consolidation**: Complete the migration of flat service files in `packages/core/application` to their domain subfolders (`income_tracker`, `expense_tracker`, etc.) and delete the redundant root files.
    - **Sankey Alignment**: Audit `packages/web/src/finance/SankeyChart.jsx` and `useApi.js` to ensure they correctly consume the `VirtualAccount` data structure.
    - **Infrastructure Cleanup**: Purge stale files in `packages/core/infrastructure/shared` and align with the `postgres`/`sqlite` persistence split.
- **Verification**:
    - Run `python scripts/health_check.py` (Must yield 0 errors).
    - Manual verification of `apps/cli/main.py` and `packages/api/api_server.py` startup.

## 3. Phase 2: Core Stability Matrix (Batches A, B, C) (Tester / Security Agent)
- **Infrastructure (A)**:
    - [ ] 1.1 - 1.10: Root detection, thread-safety, PID management, circular imports.
- **Finance (B)**:
    - [ ] 2.1 - 2.10: Decimal precision, lot tracking (FIFO), ACID transactions, tax math.
- **Security (C)**:
    - [ ] 3.1 - 3.10: SQL injection, HMAC integrity, path traversal, privilege drop.

## 4. Phase 3: AI & Performance Integrity (Batches D, E) (ML / Performance Agent)
- **AI/ML Chaos (D)**:
    - [ ] 4.1 - 4.10: OCR consensus, regime hysteresis, sentiment satire, prompt injection.
- **Performance (E)**:
    - [ ] 5.1 - 5.10: N+1 queries, React hook leaks, handle leaks, TUI thread decoupling.

## 5. Phase 4: Full-Stack UX & Integration Audit (UX / Coder Agent)
- **GUI Audit (Web)**:
    - **Routing**: Test all dynamic routes and unauthorized access redirects.
    - **Hydration**: Detect and fix Next.js hydration mismatches in the dashboard.
    - **State**: Verify Redux/Zustand state persistence across page refreshes.
    - **UX/UI**: Audit layout consistency, responsive breakpoints, and theme (Light/Dark) toggle stability.
- **CLI Audit**:
    - Full menu walkthrough (Options 1-10) in both Personal and Business profiles.
    - Verify TUI (Rich) rendering doesn't crash on long tables or wide terminal windows.
    - Profile switching (Personal <-> Business) must not leave stale database handles.
- **API & Integration**:
    - **Websockets**: Audit `butterfly_service` websocket broadcast stability under load.
    - **Scheduler**: Verify async background jobs in `apps/cli/scheduler.py` resume correctly after crash.
    - **Caching**: Enforce 48h TTL on market data cache in `Config`.

## 6. Phase 5: Root-Cause & Remediation Report (Orchestrator)
- Consolidate all failure logs.
- Perform root-cause analysis for each "Failed" vector.
- Generate `docs/planning/AUDIT_FINDINGS_20260525.md`.
- Final Stability Sign-off.

## 7. DoD (Definition of Done)
- 50/50 Vectors Green or explicitly mitigated with Root-Cause Analysis.
- No console errors in GUI.
- CLI menu 100% functional.
- Zero handle/memory leaks detected in 1000-cycle stress tests.
