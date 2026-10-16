---
title: "Database Persistence (PVC) Verification"
created: "2026-05-29T05:30:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Database Persistence (PVC) Verification Design Document

## Problem Statement
The `finance-tracker` application is transitioning to a cloud-native Kubernetes (K8s) architecture. While API deployments are scaffolded, the **PostgreSQL database** lacks a verified persistence layer within the cluster.

**Current Risks:**
* **Ephemeral Data**: Without a Persistent Volume Claim (PVC), database Pod restarts will result in total data loss.
* **Infrastructure Fragility**: Absence of defined StorageClasses prevents database survival across lifecycle events.
* **Recovery Gap**: No verified backup/restore protocol exists.

## Requirements

### Functional Requirements
* **REQ-1 (Persistence)**: Postgres data must persist across Pod deletions using K8s `PersistentVolumeClaim`.
* **REQ-2 (Security)**: Credentials must be stored in K8s `Secrets`.
* **REQ-3 (Portability)**: Use dynamic `storageClassName` to support common K8s distributions.
* **REQ-4 (Verification)**: Scripted "write-delete-verify" process.
* **REQ-5 (Disaster Recovery)**: Validated backup/restore test.

### Non-Functional Requirements
* **Durability**: Zero data loss during standard Pod rescheduling.
* **Clarity**: K8s manifests must follow standard labeling.

## Approach

### Selected Approach: StatefulSet + VolumeClaimTemplate
This approach uses the K8s `StatefulSet` controller to provide stable network identities and automated PVC management.

### Decision Matrix

| Criterion | Weight | Approach A (StatefulSet) | Approach B (Deployment) |
|-----------|--------|--------------------------|-------------------------|
| Data Integrity | 40% | 5: Stable identity prevents multi-writer risk. | 3: Potential race conditions on remount. |
| Verification Ease | 30% | 4: Predictable PVC naming (`data-db-0`). | 5: Direct PVC management. |
| Cloud-Native Fit | 30% | 5: Industry standard for K8s databases. | 3: Anti-pattern for stateful loads. |
| **Weighted Total** | | **4.7** | **3.6** |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **StorageClass Mismatch** | MEDIUM | MEDIUM | Use generic `storageClassName: standard`. |
| **Permission Errors** | HIGH | MEDIUM | Add `securityContext: fsGroup: 999` to pod spec. |
| **Orphaned PVCs** | LOW | HIGH | Document that PVCs persist after StatefulSet deletion. |
| **Data Corruption during Backup** | MEDIUM | LOW | Perform backup verification via `pg_dump`. |

## Success Criteria
1. PostgreSQL StatefulSet is running and accessible.
2. `kubectl delete pod` does not result in data loss.
3. Database credentials successfully retrieved from K8s Secrets.
4. Backup/Restore script successfully recovers a deleted database state.
