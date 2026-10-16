---
title: "Fix Backend Connection and API Errors"
created: "2026-06-05T04:05:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Fix Backend Connection and API Errors Design Document

## Problem Statement
The Backend Connection Problem is caused by three distinct technical failures:
1. **Path Resolution Error**: Incorrect `sys.path` configuration in the `stocks` router prevents it from finding the `stock_analyzer` domain logic.
2. **Dependency Injection Mismatch**: `DashboardService` is initialized with incorrect argument order in `deps.py`, causing an `AttributeError` on `get_all`.
3. **Database Schema Inconsistency**: Conflicting definitions of `audit_log` table between `security/core.py` and `infrastructure/schemas.py`.

## Approach
**Standardized Backend Convergence**
- **Unified Path Resolution**: Standardize `sys.path` additions to point to `apps/cli` for CLI-based domain logic.
- **DI Correction**: Correct `DashboardService` instantiation in `deps.py` and call signature in `api_server.py`.
- **Schema Synchronization**: Centralize `audit_log` definition in `schemas.py` using `ts` column to match `core.py` logic.

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| sys.path pollution | MEDIUM | LOW | Use Path objects, scope to specific routers |
| Data loss in audit_log | LOW | LOW | Standardize on most active column naming (ts) |
