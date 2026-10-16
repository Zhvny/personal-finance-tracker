Last Updated: 29-05-2026 (14:30)

---
title: "Elite System Audit Implementation Plan"
design_ref: "conductor/2026-05-25-elite-system-audit-design.md"
created: "2026-05-25T23:00:00Z"
status: "draft"
total_phases: 9
estimated_files: 50
task_complexity: "complex"
---

# Elite System Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a full 50-vector system audit post-monorepo refactor to ensure structural, financial, security, AI, and performance integrity across GUI and CLI.

**Architecture:** Systematic audit grouping the 50 Elite Matrix vectors into batches, followed by end-to-end runtime validation and report consolidation.

**Tech Stack:** Python (pytest, cProfile), Next.js (Playwright), Chrome DevTools MCP.

---

## Phase 1: Structural Reconciliation & Infrastructure Audit (Batch A)

### Objective
Resolve monorepo structural conflicts and validate infrastructure vectors (1.1 - 1.10).

### Agent: refactor
### Parallel: No

### Files to Modify
- `.ai/CURRENT_STATE.md` — Update to reflect real progress.
- `.ai/TASKS.md` — Sync with audit findings.
- `packages/core/infrastructure/config.py` — Ensure singleton safety and root detection.

- [ ] **Step 1: Reconcile Virtual Accounts & Sankey in Core**
  Verify that the `VirtualAccount` model in `packages/core/domain/models/account.py` supports the data needs of the Sankey visualization in `packages/web/src/finance/SankeyChart.jsx`.
- [ ] **Step 2: Test Marker-Chain Root Detection (Vector 1.1)**
  Create a reproduction script `tests/audit/test_infra_root.py` that creates deep symlinks and verifies `Config.get_root()` behavior.
- [ ] **Step 3: Test Thread-Safe Config (Vector 1.2)**
  Create `tests/audit/test_infra_threads.py` using `threading` to stress-test the Config singleton.
- [ ] **Step 4: Audit boundary enforcement (Vector 1.3)**
  Run a custom lint check to ensure no `apps` are imported from `packages`.

---

## Phase 2: Financial Invariant Audit (Batch B)

### Objective
Validate math sovereignty and financial lot tracking (Vectors 2.1 - 2.10).

### Agent: tester
### Parallel: Yes (with Phase 3, 4)

### Files to Create
- `tests/audit/test_finance_precision.py` — Decimal audit.
- `tests/audit/test_finance_lots.py` — Lot tracking & FIFO.

- [ ] **Step 1: Validate Decimal Precision (Vector 2.1)**
  Ensure all financial calculations use `Decimal` and handle `0.1 + 0.2` correctly.
- [ ] **Step 2: Audit Lot Fragmentation (Vector 2.2)**
  Test micro-transactions (dust) and partial sell logic.
- [ ] **Step 3: Test ACID Transactions (Vector 2.8)**
  Simulate process crash during DB write and verify rollback/consistency.

---

## Phase 3: Security & Defense Audit (Batch C)

### Objective
Audit RLS, HMAC, and input sanitization (Vectors 3.1 - 3.10).

### Agent: security_engineer
### Parallel: Yes

### Files to Create
- `tests/audit/test_security_injection.py` — SQLi fuzzing.
- `tests/audit/test_security_traversal.py` — Path traversal guards.

- [ ] **Step 1: SQL Injection Fuzzing (Vector 3.1)**
  Attack profile switching and account queries with malicious payloads.
- [ ] **Step 2: Directory Traversal Check (Vector 3.3)**
  Attempt to export reports to system directories.
- [ ] **Step 3: Audit HMAC Chains (Vector 3.7)**
  Verify system detects database tampering/replay.

---

## Phase 4: AI/ML Service Chaos Audit (Batch D)

### Objective
Validate OCR consensus, model drift, and service resilience (Vectors 4.1 - 4.10).

### Agent: ml_engineer
### Parallel: Yes

- [ ] **Step 1: Adversarial Receipt Fuzzing (Vector 4.2)**
  Test OCR with receipts where Sum != Total.
- [ ] **Step 2: Majority Voting Deadlock (Vector 4.4)**
  Simulate 3-way disagreement between OCR engines and verify fallback.
- [ ] **Step 3: Prompt Injection Lockdown (Vector 4.10)**
  Verify sentiment analysis ignores "Ignore all instructions" payloads.

---

## Phase 5: Performance & Leak Analysis (Batch E)

### Objective
Profile N+1 queries, memory leaks, and concurrency (Vectors 5.1 - 5.10).

### Agent: performance_engineer
### Parallel: Yes

- [ ] **Step 1: N+1 Query Audit (Vector 5.1)**
  Profile portfolio load with 500+ items and count DB hits.
- [ ] **Step 2: Memory Leak Monitor (Vector 5.2 & 5.6)**
  Switch profiles 50x and monitor heap usage.
- [ ] **Step 3: FastAPI Concurrency (Vector 5.10)**
  Load test API endpoints under concurrent stress.

---

## Phase 6: GUI Stability Audit (Next.js)

### Objective
Full UI/UX validation of the Next.js frontend.

### Agent: ux_designer
### Parallel: No

- [ ] **Step 1: Hydration & Layout Audit**
  Check for hydration mismatches and layout jank during resize/load.
- [ ] **Step 2: Animation & Theme Stability**
  Verify animation smoothnes and dark/light mode consistency.
- [ ] **Step 3: Data Mapping & Analytics Validation**
  Ensure Sankey charts and graphs render correctly with real runtime data.

---

## Phase 7: CLI End-to-End Validation

### Objective
Validate CLI functionality across all profiles and menu options.

### Agent: coder
### Parallel: No

- [ ] **Step 1: Profile Switching Stability**
  Validate switching between Personal/Business profiles 10x.
- [ ] **Step 2: Menu Option Audit**
  Test all 8 options in `main.py` including advanced features (Genetic Optimizer, Whale Profiler).
- [ ] **Step 3: Verify SSOT Path Alignment**
  Ensure all data is stored in `apps/cli/profiles/` and not at root.

---

## Phase 8: Consolidation & Reporting

### Objective
Generate detailed audit findings and stability reports.

### Agent: technical_writer
### Parallel: No

- [ ] **Step 1: Generate AUDIT_FINDINGS_20260525.md**
  Detail root-cause for every detected issue.
- [ ] **Step 2: Generate STABILITY_REPORT.md**
  Provide final health score and actionable remediation tasks.

---

## Phase 9: Archiving & Handoff

### Objective
Archive the session and update project metadata.

### Agent: technical_writer
### Parallel: No

- [ ] **Step 1: Update CURRENT_STATE.md**
- [ ] **Step 2: Archive Maestro Session**

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `tests/audit/` | 1-5 | Reproduction scripts for Elite Matrix vectors |
| 2 | `docs/planning/AUDIT_FINDINGS_20260525.md` | 8 | Audit results |
| 3 | `docs/planning/STABILITY_REPORT.md` | 8 | Health score |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1-5 | HIGH | Testing against DB invariants; potential for corruption if not on test DB. |
| 6-7 | MEDIUM | Runtime stability tests might hang if concurrency issues exist. |

## Execution Profile

```
Execution Profile:
- Total phases: 9
- Parallelizable phases: 4 (Batches B, C, D, E)
- Sequential-only phases: 5
- Estimated parallel wall time: 4 hours
- Estimated sequential wall time: 8 hours
```
