Last Updated: 29-05-2026 (14:30)

---
title: \"Infrastructure Integrity Remediation Implementation Plan\"
design_ref: \"docs/maestro/plans/2026-05-29-fix-elite-audit-infra-integrity-design.md\"
created: \"2026-05-29T23:55:00Z\"
status: \"draft\"
total_phases: 3
estimated_files: 8
task_complexity: \"medium\"
---

# Infrastructure Integrity Remediation Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: `devops_engineer`, `coder`, `tester`
- **Estimated effort**: Moderate. Normalizing the execution environment to ensure 100% audit reliability.

## Dependency Graph

```
Phase 1: Environment Foundation (Bootstrap/PYTHONPATH)
    |
Phase 2: Config (BOM Support)
    |
Phase 3: Validation (Audit Success)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Fix environment blockers first. |
| 2     | Phase 2 | Sequential | 1 | Fix encoding issues. |
| 3     | Phase 3 | Sequential | 1 | Re-run audit and verify all PASS. |

## Phase 1: Environment Foundation (Bootstrap & PYTHONPATH)

### Objective
Ensure the monorepo `packages/` structure is correctly recognized by all processes, fixing `ModuleNotFoundError`.

### Agent: `devops_engineer`
### Parallel: No

### Files to Modify

- `packages/core/bootstrap.py` — Ensure robust detection of project root and correct `PYTHONPATH` injection for inherited environments.
- `tests/audit/reproduce_vector.py` — Ensure `bootstrap.setup_environment()` is called correctly at the entry point.
- `tests/audit/run_infra_audit.py` — Align with bootstrap logic and fix any broken relative pathing in vector implementations.

### Implementation Details

- `bootstrap.py`: Ensure `os.environ["PYTHONPATH"]` is updated before any subprocesses are spawned.
- `reproduce_vector.py`: Import `bootstrap` and call `setup_environment()` before other imports.

### Validation

- `python tests/audit/reproduce_vector.py 1.1` (Verify no `ModuleNotFoundError`).

### Dependencies

- Blocked by: None
- Blocks: Phase 2, 3

---

## Phase 2: Configuration Robustness (BOM Support)

### Objective
Resolve `UnicodeDecodeError` when loading `.env` files with Byte Order Mark (BOM).

### Agent: `coder`
### Parallel: No

### Files to Modify

- `packages/core/infrastructure/config.py` — Refactor `load_with_encoding` to use robust signature detection (BOM) and reliable decoding for UTF-8-SIG and UTF-16 variants.

### Implementation Details

- Implement explicit BOM check for `utf-8-sig`, `utf-16-le`, and `utf-16-be`.
- Ensure `python-dotenv` is passed a clean stream after decoding.

### Validation

- `python tests/audit/reproduce_vector.py 1.8` (Verify PASS for BOM parsing).

### Dependencies

- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Path Resolution & Audit Verification

### Objective
Eliminate `WinError 2` (file not found) in subprocess calls and verify the full audit passes.

### Agent: `tester`
### Parallel: No

### Files to Modify

- `tests/audit/harness.py` — Update `BaseAuditVector.run_command` to utilize `AuditHarness.get_canonical_root()` for script resolution.
- `tests/audit/vectors/vector_1_6.py` — Update to use absolute script paths resolved from `harness`.

### Implementation Details

- Add `AuditHarness.resolve_script_path(rel_path)` helper.
- Ensure all subprocess calls in vectors use absolute paths for both the executable and the script.

### Validation

- `python tests/audit/run_infra_audit.py` (All 10 vectors must PASS).
- Verify log at `docs/planning/INFRA_AUDIT_LOG.md`.

### Dependencies

- Blocked by: Phase 1, 2
- Blocks: None

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/core/bootstrap.py` | 1 | Environment normalization |
| 2 | `tests/audit/reproduce_vector.py` | 1 | Audit entry point |
| 3 | `tests/audit/run_infra_audit.py` | 1 | Bulk audit execution |
| 4 | `packages/core/infrastructure/config.py` | 2 | BOM/encoding support |
| 5 | `tests/audit/harness.py` | 3 | Command execution standardization |
| 6 | `tests/audit/vectors/*.py` | 3 | Path resolution fixes |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | MEDIUM | Systemic impact on module resolution. |
| 2     | LOW | Targeted configuration fix. |
| 3     | MEDIUM | Cross-platform (Windows) path stability verification. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 10 minutes

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
