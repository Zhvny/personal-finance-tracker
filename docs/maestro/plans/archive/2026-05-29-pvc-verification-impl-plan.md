---
title: "Database Persistence (PVC) Verification Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-pvc-verification-design.md"
created: "2026-05-29T06:05:00Z"
status: "draft"
total_phases: 3
estimated_files: 5
task_complexity: "medium"
---

# Database Persistence (PVC) Verification Implementation Plan

## Plan Overview
Implement and verify a production-grade persistence strategy using Kubernetes StatefulSets, PVCs, and automated recovery testing.

- **Total phases**: 3
- **Agents involved**: `devops_engineer`, `coder`, `tester`
- **Estimated effort**: Medium (Manifest migration + Scripted verification)

## Dependency Graph
```
Phase 1: Infrastructure & Manifests
    |
Phase 2: Verification Logic Implementation
    |
Phase 3: Persistence & Backup Verification
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | K8s Scaffolding |
| 2     | Phase 2 | Sequential | 1 | Scripting |
| 3     | Phase 3 | Sequential | 1 | Verification |

## Phase 1: Infrastructure & Manifests
### Objective
Create a unified `k8s/` directory and implement the `StatefulSet` and `Secret` manifests for PostgreSQL.

### Agent: `devops_engineer`
### Parallel: No

### Files to Create
- `k8s/db-secret.yaml`: Contains `POSTGRES_PASSWORD` and `DATABASE_URL` as Base64 encoded secrets.
- `k8s/db-statefulset.yaml`: Implements `StatefulSet` with `volumeClaimTemplates` (1Gi) and `securityContext`.
- `k8s/api-deployment.yaml`: Migrated from root, updated to reference the new `Secret`.
- `k8s/ingress.yaml`: Migrated from root.

### Implementation Details
- **Storage**: Use `storageClassName: standard`.
- **Identity**: Postgres service must resolve to `postgres-db-0.postgres-db-service` (headless service).
- **Cleanup**: Delete root-level `k8s-deployment.yaml` and `k8s-ingress.yaml` after migration.

### Validation
- `kubectl apply -f k8s/`
- `kubectl get pods -l app=postgres-db` (Wait for Running)
- `kubectl get pvc` (Verify bound state)

### Dependencies
- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Verification Logic Implementation
### Objective
Develop a Python script to automate the "write-delete-verify" and "backup/restore" test cases.

### Agent: `coder`
### Parallel: No

### Files to Create
- `scripts/verify_pvc_persistence.py`: Uses `DatabaseManager` to write a "marker" record, deletes the pod, waits for recovery, and verifies the marker.

### Implementation Details
- **Marker Table**: `financials.pvc_test` (timestamp, marker_id).
- **Pod Deletion**: Execute `kubectl delete pod postgres-db-0` via subprocess.
- **Backup Verification**: Run `pg_dump` to `/tmp/backup.sql`, drop table, restore, and verify.

### Validation
- `python scripts/verify_pvc_persistence.py --dry-run`

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Persistence & Backup Verification
### Objective
Execute the verification suite in a live K8s environment and provide a signed task report.

### Agent: `tester`
### Parallel: No

### Implementation Details
- Run the full verification script against the K8s cluster.
- Capture logs and exit codes.
- Verify that no data loss occurred during the pod restart cycle.

### Validation
- All assertions in `verify_pvc_persistence.py` pass.

### Dependencies
- Blocked by: Phase 2
- Blocks: None

---

## File Inventory
| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `k8s/db-secret.yaml` | 1 | Secure credentials |
| 2 | `k8s/db-statefulset.yaml` | 1 | DB Persistence |
| 3 | `k8s/api-deployment.yaml` | 1 | App Deployment |
| 4 | `k8s/ingress.yaml` | 1 | Networking |
| 5 | `scripts/verify_pvc_persistence.py` | 2 | Automation |

## Risk Classification
| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | MEDIUM | Critical for DB availability; potential for permission errors on volumes. |
| 2 | LOW | Purely testing logic; low impact on system state. |
| 3 | MEDIUM | Destructive testing (pod deletion); requires stable K8s env. |

## Execution Profile
```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 10-15 minutes (includes K8s pod recovery time)

Note: Sequential execution is used to ensure infrastructure is ready before testing.
```
