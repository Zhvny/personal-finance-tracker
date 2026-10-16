# A-XXX: Fix All CrewAI Findings

**Created:** 2026-09-04
**Status:** Completed (CRITICAL + HIGH done)
**Priority:** HIGH
**Estimates:** ~142 hours total (~83h done: CRITICAL 33h + HIGH 50h)

## Source
- CrewAI analysis output: `.claude/zhvn_crew/analysis_output/`
- 27 tasks completed, 3 failed (security_auditor, ml_engineer, frontend_developer)
- 30+ findings across security, devops, database, monitoring, data quality, financial

---

## ✅ COMPLETED: All CRITICAL + HIGH

### SECURITY

| # | Finding | Fix Applied | Files |
|---|---------|-------------|-------|
| S1 | WebSocket No Authentication | Added `_verify_ws_token()` in gateway, auth before `ws.accept()` | `services/gateway/main.py` |
| S2 | API Key Dev Mode Bypass | Added `STRICT_API_VALIDATION=1` env, enforced in `verify_api_key()` | `packages/api/backend/security/core.py` |
| S3 | Missing Replay Attack Protection | Made HMAC mandatory in production (`STRICT_HMAC=1` for non-prod) | `packages/api/backend/security/core.py` |
| S4 | CORS Not Implemented | Added `CORSMiddleware` in gateway with `CORS_ALLOWED_ORIGINS` env | `services/gateway/main.py` |
| S5 | TLS Not Configured in k8s | Added TLS config + cert-manager + security headers in ingress.yaml | `k8s/ingress.yaml` |
| S6 | Single Replica (SPOF) | Changed `replicas: 1` → `replicas: 2` for all 6 domain services | `k8s/domain-services.yaml` |
| H1 | Services on Public Network | Already isolated (ClusterIP only, gateway bridges); added additional annotations | `k8s/domain-services.yaml` |
| H2 | No Rate Limiting in k8s | Added `limit-rps`, `limit-connections`, `limit-rpm` in ingress.yaml | `k8s/ingress.yaml` |
| H3 | No WAF Rules | Added basic SQL injection/XSS protection in nginx config; note for full WAF | `k8s/ingress.yaml` |

### DATABASE

| # | Finding | Fix Applied | Files |
|---|---------|-------------|-------|
| DB1 | Missing idx: sell_transactions.investment_id | Added `idx_sell_transactions_investment_id` | `alpha_db_schema.sql` |
| DB2 | Missing idx: expenses.category_date | Added `idx_expenses_category_date` composite index | `alpha_db_schema.sql` |
| DB3 | Connection pool exhaustion | Added `connect_timeout=10`, `statement_timeout=30000` in pool init | `packages/core/infrastructure/persistence/postgres_manager.py` |
| DB4 | No query timeouts | Added `ALTER DATABASE SET statement_timeout = '30s'` | `alpha_db_schema.sql` |

### MONITORING/OBSERVABILITY

| # | Finding | Fix Applied | Files |
|---|---------|-------------|-------|
| M1 | /metrics endpoint not implemented | Added `/metrics` endpoint in gateway exposing upstream health | `services/gateway/main.py` |
| M2 | No Prometheus scrape targets | Created `k8s/prometheus.yml` with scrape configs for all services | `k8s/prometheus.yml` |
| M3 | No AlertManager/PagerDuty | Created `k8s/alertmanager.yml` with PagerDuty + email receivers | `k8s/alertmanager.yml` |
| M4 | No P0/P1 alerts defined | Created `k8s/alert_rules.yml` with P0/P1/P2 severity alerts | `k8s/alert_rules.yml` |
| M5 | No on-call rotation documented | Created `docs/infrastructure/ONCALL_ROTATION.md` | `docs/infrastructure/ONCALL_ROTATION.md` |

### DEVOPS

| # | Finding | Fix Applied | Files |
|---|---------|-------------|-------|
| D1 | Mutable Python Base Image | Pinned `python:3.12-alpine3.20@sha256:...` in Dockerfile | `Dockerfile` |
| D4 | Node.js Base Image Not Reviewed | Pinned `node:22-alpine3.20` in web Dockerfile | `apps/web/Dockerfile` |
| D3 | No Logging Configuration | Added `JSONFormatter` class, `LOG_FORMAT=json` env support | `packages/core/infrastructure/logging.py` |
| D2 | No Backup Strategy | Created `scripts/tools/backup.py` + `docs/infrastructure/BACKUP_STRATEGY.md` | `scripts/tools/backup.py`, `docs/infrastructure/BACKUP_STRATEGY.md` |

### FINANCIAL (Behavioral — Not Code)

| # | Finding | Action Required | Doc |
|---|---------|----------------|-----|
| F1 | Emergency Fund < 3 months | Build to 6-month reserve (~$61,800) — ongoing discipline | `docs/task/FINANCIAL_ACTION_ITEMS.md` |
| F2 | Primary Income 84.4% single source | Diversify: scale freelance to 20%+ within 3 years | `docs/task/FINANCIAL_ACTION_ITEMS.md` |
| F3 | W-4 Under-withheld $732/year | Adjust W-4 allowance, recalculate quarterly estimates | `docs/task/FINANCIAL_ACTION_ITEMS.md` |
| F4 | $312,450 amount outliers | Review flagged transactions, implement approval workflow | `docs/task/FINANCIAL_ACTION_ITEMS.md` |
| F5 | $156,780 pattern breakages | Investigate + categorize unusual spends | `docs/task/FINANCIAL_ACTION_ITEMS.md` |
| F6 | Tax optimization not maximized | Max Traditional IRA ($7k), HSA ($4,150), track freelance | `docs/task/FINANCIAL_ACTION_ITEMS.md` |

---

## 🟡 MEDIUM (Next Priority — ~55h)

### SECURITY

| # | Finding | Action | Effort |
|---|---------|--------|--------|
| M1 | No External Secret Management | Migrate to HashiCorp Vault or AWS Secrets Manager | 16h |
| M2 | No Secret Rotation Policy | Implement 90-day rotation for API keys, tokens | 4h |
| M3 | Implicit Public Schema Access | Create per-service schemas, revoke public access | 4h |
| M4 | Path Traversal in serve_frontend | Sanitize + validate all file paths, add static allowlist | 3h |

### DATABASE

| # | Finding | Action | Effort |
|---|---------|--------|--------|
| DB5 | Missing idx: investments.status | Add index (already in schema as of this fix) | 15min |
| DB6 | Missing CHECK constraints | Add CHECK for: positive amounts, valid dates, enum values | 2h |
| DB7 | Views not materialized | Convert `monthly_summary`, `category_breakdown` to matviews | 4h |
| DB8 | No query logging | Enable `log_min_duration_statement=1000` for slow query analysis | 30min |

### DEVOPS

| # | Finding | Action | Effort |
|---|---------|--------|--------|
| D5 | Postgres on alpha-public (dev-only) | Migrate to internal network only | 1h |
| D6 | Missing Volume Size Limits | Add storage quotas in PVC specs | 30min |
| D7 | Loki/Jaeger not implemented | Deploy for centralized logging + distributed tracing | 8h |

### DATA QUALITY

| # | Finding | Action | Effort |
|---|---------|--------|--------|
| DQ1 | 56 merchant mismatches ($28,900) | Auto-correct via mapping table, manual review for unmapped | 6h |
| DQ2 | 23 duplicate transactions ($47,230) | Confirm and remove duplicates, add dedup logic | 4h |
| DQ3 | 53 data quality issues | Batch correction run, improve OCR pipeline | 8h |

---

## 🟢 LOW (When Convenient — ~4h)

| # | Finding | Action | Effort |
|---|---------|--------|--------|
| L1 | 41 timing anomalies (monitor only) | Add to dashboard, no action needed | 1h |
| L2 | Redundant lock in postgres_manager | Review + remove if confirmed redundant | 30min |
| L3 | Standardize table naming | Low priority — migration cost > benefit | deferred |
| L4 | Several sector allocations underweight | Rebalance during next scheduled allocation | 1h |

---

## Effort Summary

| Priority | Hours Done | Remaining |
|----------|-----------|-----------|
| ✅ CRITICAL | 33h | 0h |
| ✅ HIGH | 50h | 0h |
| 🟡 MEDIUM | 0h | ~55h |
| 🟢 LOW | 0h | ~4h |

**Completed: ~83h | Remaining: ~59h**

---

## Files Modified/Created

**Modified:** 10 files
- `Dockerfile`
- `apps/web/Dockerfile`
- `k8s/domain-services.yaml`
- `k8s/ingress.yaml`
- `packages/api/backend/security/core.py`
- `packages/core/infrastructure/logging.py`
- `packages/core/infrastructure/persistence/postgres_manager.py`
- `services/gateway/main.py`
- `alpha_db_schema.sql`

**Created:** 7 files
- `scripts/tools/backup.py`
- `docs/infrastructure/BACKUP_STRATEGY.md`
- `k8s/prometheus.yml`
- `k8s/alertmanager.yml`
- `k8s/alert_rules.yml`
- `docs/infrastructure/ONCALL_ROTATION.md`
- `docs/task/FINANCIAL_ACTION_ITEMS.md`

## Notes

- 3 crew tasks failed: security_auditor, ml_engineer, frontend_developer — may have additional findings
- F1-F6 are personal finance behavioral items — not code
- Consider re-running failed tasks after MEDIUM fixes complete
- MEDIUM items are less urgent but still important for production readiness
