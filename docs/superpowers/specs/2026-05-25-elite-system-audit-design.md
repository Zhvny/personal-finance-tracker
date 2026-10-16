Last Updated: 29-05-2026 (14:30)

# Design Document: Elite System Audit & Stability Validation

**Date**: 25-05-2026
**Status**: APPROVED
**Context**: Post-Monorepo Reorganization (@core, @api, @web, @cli, @ui, @database)
**Objective**: Execute the `ELITE_EXECUTION_MATRIX_FULL.md` (50 vectors) and reconcile conflicting project states.

## 1. Problem Statement
The application has undergone a massive monorepo restructuring. Conflicting metadata suggests a "false-positive" completion state. Critical logic (Virtual Accounts, Sankey Cashflow) has unresolved structural conflicts in `packages/core`. The runtime stability of both the Next.js GUI and the Python CLI is unverified in this new structure.

## 2. Approach: Parallel Vector Dispatch (Gate 0 First)
We will follow a "Gate 0" structural reconciliation to fix import and model conflicts, followed by parallel execution of the 50-vector matrix.

### 2.1 Gate 0: Structural Reconciliation
- **Branch**: `audit/elite-stability-matrix` (created from current `testing` branch).
- **Core Unification**: Merge `VirtualAccount` logic from `feature/virtual-accounts` into the `packages/core/domain/models` structure. Ensure compatibility with `SankeyChart.jsx`.
- **Import Refactor**: Update all `apps/cli` and `apps/web` imports to reference `packages/core` and `packages/api` canonical paths.
- **Verification**: `python scripts/check_all_dbs.py` and a full `tsc` (TypeScript) check.

### 2.2 The 50-Vector Matrix (Groups)
The audit is divided into 5 batches (10 vectors each):

- **Batch A: Infrastructure**: Singleton safety, root detection, monorepo boundaries, process reaping.
- **Batch B: Financial**: Decimal precision, lot tracking (FIFO), ACID transactions, tax boundary fuzzing.
- **Batch C: Security**: SQL injection fuzzing, HMAC integrity chains, directory traversal guards, privilege drop.
- **Batch D: AI/ML Service**: OCR consensus (Majority Voting), model drift detection, adversarial receipt fuzzing (programmatic generation).
- **Batch E: Performance**: N+1 query detection, React hook memory leaks (via Chrome DevTools MCP), handle leak monitoring.

## 3. Data & Environment Strategy
- **Database**: Strictly use `data/dummy_test.db`. No mutation of live production data.
- **Containerization**: The GUI audit (Phase 4) will run inside the **Docker** container to validate environment variables and pathing.
- **Reproduction**: Every vector MUST have a reproduction script in `tests/audit/`.

## 4. UI/UX Audit Specification
Using Chrome DevTools MCP:
- **Hydration Check**: Detect mismatches between server-rendered and client-hydrated HTML.
- **Memory Profiling**: Capture `heapsnapshots` to detect detached DOM nodes after 50 profile switches.
- **Responsive Audit**: Force layout reflows during heavy animation to check for "jank" and CPU spikes.

## 5. Success Criteria
1. **Gate 0 Passes**: Zero import errors and model conflicts.
2. **50/50 Pass**: All Elite Matrix reproduction scripts pass.
3. **Container Parity**: GUI runs without error inside Docker.
4. **Reports Generated**: `AUDIT_FINDINGS_20260525.md` and `STABILITY_REPORT.md` saved to `docs/planning/`.

## 6. Risk Assessment
- **Medium**: High token usage for parallel subagent dispatch. *Mitigation: Group similar vectors into single subagent tasks.*
- **Low**: Data corruption risk. *Mitigation: Mandatory use of `dummy_test.db` enforced via `Config` override.*
