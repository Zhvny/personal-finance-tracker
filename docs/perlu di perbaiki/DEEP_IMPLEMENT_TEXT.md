# DEEP IMPLEMENTATION TASK — Alpha Finance Tracker

You are acting as a **Senior Software Architect, Staff Backend Engineer, Security Engineer, and Code Maintainer**.

Your job is NOT to simply review the project.

Your job is to **deeply inspect the actual repository, verify the findings below against the source code, then
implement the necessary fixes directly in the codebase**.

The project is a personal finance / investment monorepo called **Alpha**.

The repository currently contains:

* Python CLI
* FastAPI backend
* Next.js frontend
* PostgreSQL
* legacy SQLite storage
* Prisma/schema definitions
* n8n automation
* OCR
* stock analysis
* XGBoost ML
* Telegram integration
* background schedulers

The existing deep code review identified major risks including:

1. PostgreSQL failure can fall through to SQLite.
2. PostgreSQL and SQLite are both used as competing persistence paths.
3. Sync/async patterns are inconsistent.
4. Duplicate service implementations exist.
5. `apps/api/main.py` has excessive responsibilities.
6. `routers/ai.py`, `behavioral.py`, etc. contain excessive logic.
7. `deps.py` acts as a god dependency module.
8. CLI modules are directly imported by the API.
9. Schema ownership is fragmented.
10. Security uses a single master API key.
11. Development authentication bypass exists.
12. WebSocket authentication may expose credentials through query parameters.
13. Some exceptions are swallowed.
14. Stack traces can be returned to API clients.
15. Scheduler execution is tied to the API process.
16. Dependency locking and CI are incomplete.
17. Runtime artifacts, caches, logs, databases, and model assets pollute the repository.

The review specifically concludes that the project should remain a **modular monolith**, rather than prematurely
being converted into microservices.

---

# PRIMARY OBJECTIVE

Transform the current repository into a **stable, maintainable, testable, and production-safer modular monolith**
without unnecessarily rewriting working functionality.

Do NOT perform a blind rewrite.

Do NOT introduce microservices unless there is concrete technical evidence that a particular component requires
independent deployment/scaling.

Prioritize:

**Correctness > Data integrity > Security > Reliability > Maintainability > Performance > New features**

---

# PHASE 0 — UNDERSTAND THE ACTUAL CODEBASE

Before modifying anything:

1. Inspect the complete repository structure.
2. Identify all Python applications/packages.
3. Identify all TypeScript/JavaScript applications/packages.
4. Identify all database access layers.
5. Identify all SQLite databases.
6. Identify all PostgreSQL access paths.
7. Identify all Prisma usage.
8. Identify all raw SQL usage.
9. Identify all schema initialization code.
10. Identify all migration scripts.
11. Identify all service implementations.
12. Identify all API routers.
13. Identify all CLI → core dependencies.
14. Identify all API → CLI dependencies.
15. Identify all sync/async boundaries.
16. Identify all background schedulers.
17. Identify all authentication and authorization paths.
18. Identify all environment variables.
19. Identify all generated/runtime artifacts.
20. Identify existing tests and determine which critical paths they actually cover.

Do not trust the previous review blindly.

Treat the review as a set of hypotheses that must be verified against the repository.

For every finding:

**VERIFY → LOCATE → UNDERSTAND → FIX → TEST**

If a finding is incorrect, outdated, or already fixed, explicitly record that instead of modifying unrelated code.

---

# PHASE 1 — DATABASE INTEGRITY

This is the highest priority.

## 1. Eliminate dangerous financial SQLite fallback

Find every path where:

PostgreSQL failure → SQLite fallback

especially for:

* expenses
* income
* investments
* sell transactions
* balances
* budgets
* goals
* financial transactions
* profile data

Financial writes must NEVER silently switch persistence stores.

Required behavior:

```text
PostgreSQL succeeds
↓
commit transaction
↓
return success
```

If PostgreSQL fails:

```text
PostgreSQL fails
↓
rollback
↓
structured error
↓
NO SQLite financial write
```

Do not silently convert infrastructure failure into a successful response.

Add regression tests proving this behavior.

---

# PHASE 2 — ESTABLISH ONE DATABASE AUTHORITY

Determine the intended canonical database.

The target architecture should be:

```text
Application
↓
Application Service
↓
Repository Interface
↓
PostgreSQL
↓
Versioned Migration
```

PostgreSQL should become the authoritative persistent financial store.

SQLite may remain temporarily for:

* local cache
* temporary data
* legacy import/export
* explicitly isolated local-only features

But SQLite must NOT act as an invisible fallback for PostgreSQL financial persistence.

Inventory every table and classify it:

```text
CANONICAL POSTGRES
LEGACY SQLITE
CACHE
AUDIT
TEMPORARY
UNKNOWN
```

Do not delete legacy databases blindly.

If migration is necessary:

1. create migration plan
2. preserve backup
3. migrate data
4. validate row counts
5. validate financial totals
6. validate relationships
7. only then remove legacy path

---

# PHASE 3 — FIX TRANSACTION BOUNDARIES

Financial operations must be atomic.

Audit operations such as:

* create expense
* update expense
* delete expense
* create income
* investment buy
* investment sell
* realized P&L
* automatic income creation
* balance updates
* recurring transaction creation

Identify operations currently performing multiple writes without a transaction.

Convert them into atomic application-level transactions.

Example:

```text
SELL INVESTMENT

BEGIN TRANSACTION

1. validate holding
2. calculate realized P&L
3. update investment
4. create sell transaction
5. create income if applicable
6. update related state

COMMIT
```

If any step fails:

```text
ROLLBACK EVERYTHING
```

Never leave partially completed financial operations.

---

# PHASE 4 — FIX SYNC / ASYNC ARCHITECTURE

Perform a complete audit of:

* `async def`
* `await`
* synchronous DB calls
* `asyncio.to_thread`
* psycopg2
* Prisma
* repository interfaces
* service methods
* router handlers

Choose one consistent architecture.

Preferred target:

```text
FastAPI async router
↓
Async application service
↓
Async repository
↓
Async database access
```

If synchronous libraries must remain temporarily:

```text
Async router
↓
service
↓
explicit thread boundary
↓
sync DB operation
```

Do NOT mix both patterns randomly.

Do NOT create:

```python
try:
await async_operation()
except:
sync_operation()
```

unless there is a deliberate and tested reason.

Search the entire repository for similar patterns.

Add regression tests for coroutine misuse and event-loop blocking.

---

# PHASE 5 — CONSOLIDATE DUPLICATED SERVICES

Identify duplicate implementations such as:

* DashboardService
* InvestmentService
* StockAnalysisService
* other duplicate service classes

Determine which implementation is actually canonical.

Do not simply delete files because they appear unused.

First verify:

```text
who imports it
who calls it
runtime path
tests referencing it
CLI usage
API usage
```

Then consolidate.

Target:

```text
packages/core/application/
dashboard_service.py
investment_service.py
expense_service.py
income_service.py
receipt_service.py
```

API and CLI should consume the same application-layer services where appropriate.

---

# PHASE 6 — FIX ARCHITECTURAL BOUNDARIES

The API must not directly depend on CLI implementation details.

For example, if API currently imports:

```python
apps.cli.receipt_reader...
```

move the reusable domain/application functionality into the appropriate shared package.

Target:

```text
apps/
api/
cli/
web/

packages/
core/
domain/
application/
infrastructure/
api/
database/
```

Dependency direction should generally be:

```text
apps/api ───────┐
apps/cli ───────┼──→ packages/core
apps/web ───────┘

packages/core
↓
infrastructure adapters
↓
external systems
```

Avoid:

```text
API → CLI
CLI → API
Core → API
Core → CLI
```

unless there is a deliberate adapter boundary.

---

# PHASE 7 — BREAK UP GOD MODULES

Audit:

* `apps/api/main.py`
* `packages/api/backend/routers/deps.py`
* `routers/ai.py`
* `routers/behavioral.py`
* other files with excessive LOC or responsibilities

Do not split files purely based on line count.

Split based on responsibility.

For example:

```text
routers/
ai/
router.py
ocr.py
categorization.py
ml.py
llm.py
```

And:

```text
dependencies/
repositories.py
services.py
security.py
cache.py
profiles.py
```

`main.py` should primarily handle:

* application creation
* middleware
* lifespan
* router registration
* global exception handling

It should not become the place where business logic accumulates.

---

# PHASE 8 — SECURITY HARDENING

Audit the entire security implementation.

## Required fixes

### Production secret validation

Production startup must fail if insecure defaults are used.

Examples:

```text
SECRET_KEY
FINANCE_TRACKER_API_KEY
DATABASE_URL
POSTGRES_PASSWORD
```

Never silently run production using development credentials.

### DEV MODE

Ensure:

```text
FINANCE_TRACKER_DEV_MODE=1
```

cannot accidentally enable authentication bypass in production.

### API authentication

Determine whether the single-user API-key model is intentional.

If yes, keep it simple but improve:

* key rotation
* secure storage
* environment validation
* scope enforcement
* auditability

Do NOT introduce JWT just because JWT is common.

Only introduce JWT/session architecture if there is a real requirement for multiple users or independent identities.

### Error disclosure

Never return:

```python
traceback.format_exc()
```

to external clients.

Return:

```json
{
"error": "Internal server error",
"request_id": "..."
}
```

Log the actual traceback server-side.

### WebSocket credentials

Audit token transmission through query strings.

Prefer:

* Authorization header
* short-lived WebSocket ticket
* another secure handshake mechanism

Do not expose long-lived credentials unnecessarily.

### SQL identifier validation

Any dynamic:

```text
schema
table
column
profile
```

must be validated against a strict allow-list/identifier policy.

Do not assume filesystem-controlled values are trusted.

---

# PHASE 9 — ERROR HANDLING

Search for:

```python
except:
except Exception:
pass
return False
return []
return {}
```

Determine whether each occurrence is legitimate.

Replace broad exception swallowing with specific exception handling.

Every error path must answer:

1. What failed?
2. Should operation retry?
3. Should transaction rollback?
4. Should user receive an error?
5. Should the service remain available?
6. Should the event be logged?
7. Should an alert be triggered?

Do not turn real failures into fake success responses.

Example:

Bad:

```python
except Exception:
return {"ok": True, "items": []}
```

Better:

```python
except ExpectedDataUnavailableError:
return {"ok": False, "error": "data_unavailable"}
```

---

# PHASE 10 — SCHEDULER / BACKGROUND JOBS

Audit APScheduler and all background jobs.

Determine whether multiple API replicas would execute the same scheduler.

Prevent duplicate jobs.

Implement an explicit strategy such as:

```text
Dedicated scheduler process
```

or:

```text
Leader election / distributed lock
```

or another justified architecture.

Do not introduce Redis merely because it is popular.

Only add infrastructure when the architecture requires it.

Every important background job should have:

* timeout
* retry policy
* backoff
* idempotency
* structured logging
* failure state
* health visibility

---

# PHASE 11 — SCHEMA / MIGRATION SYSTEM

Establish one authoritative migration mechanism.

Audit:

* Prisma schema
* raw SQL
* `CREATE TABLE IF NOT EXISTS`
* schema initializer
* migration scripts
* n8n SQL
* startup DDL

Do not blindly remove existing schema initialization.

Design:

```text
migration/
001_initial.sql
002_add_profiles.sql
003_add_investments.sql
...
```

or use an appropriate migration framework already compatible with the project.

Requirements:

* version tracking
* repeatable deployment
* rollback/recovery strategy
* migration testing
* schema drift detection

---

# PHASE 12 — TESTING

Do not merely increase test count.

Test invariants.

Highest-priority tests:

### Financial integrity

* failed PostgreSQL write never writes SQLite
* failed transaction rolls back all writes
* investment sell is atomic
* realized P&L is correct
* income generated from investment sell is consistent
* duplicate concurrent operation cannot corrupt state
* profile isolation works

### Security

* production cannot start with default secrets
* DEV mode cannot bypass production authentication
* invalid API key rejected
* scopes are enforced
* stack traces are not returned
* malformed profile identifiers are rejected

### Architecture

* API does not import CLI implementation modules
* canonical service is used
* legacy services are not accidentally executed
* sync DB operations do not block event loop unexpectedly

### Scheduler

* duplicate scheduler execution prevented
* failed jobs retry correctly
* jobs are idempotent

---

# PHASE 13 — CI / QUALITY GATES

Create or repair CI.

Minimum pipeline:

```text
Install dependencies
↓
Lint
↓
Type check
↓
Unit tests
↓
Integration tests
↓
Coverage
↓
Security checks
↓
Build
```

Use frozen dependency installation.

For Node/pnpm, avoid production builds that mutate dependency resolution.

For Python, determine whether the repository needs a single lockfile or per-application lock strategy, then implement
a reproducible approach.

Do not invent dependency versions.

---

# PHASE 14 — REPOSITORY HYGIENE

Identify and classify:

* `.db`
* `.sqlite`
* `.log`
* `.cache`
* `.pyc`
* generated model files
* generated images
* build artifacts
* temporary files
* datasets
* large binaries

Do not blindly delete anything.

For each artifact:

```text
TRACK
IGNORE
MOVE TO ARTIFACT STORAGE
MIGRATE
DELETE AFTER VERIFICATION
```

Update `.gitignore` appropriately.

Check tracked artifacts separately from merely untracked artifacts.

---

# PHASE 15 — FRONTEND

Audit `apps/web`.

Do not rewrite the frontend unless required.

Verify:

* API contract
* error handling
* authentication
* loading states
* empty states
* profile handling
* financial number formatting
* API error leakage
* duplicated legacy frontend code

Determine whether `packages/web` is truly obsolete.

If confirmed obsolete:

1. verify no runtime/build dependency
2. verify no deployment dependency
3. verify no tests depend on it
4. remove it
5. update documentation

---

# PHASE 16 — PERFORMANCE

Only optimize based on evidence.

Do not prematurely introduce:

* Redis
* Kafka
* RabbitMQ
* microservices
* Kubernetes
* distributed caching

Measure first.

Focus on:

* DB query efficiency
* N+1 queries
* connection pool usage
* blocking calls
* cache effectiveness
* external API rate limits
* scheduler duplication
* expensive ML/OCR operations

---

# IMPLEMENTATION RULES

Follow these rules strictly.

### Rule 1

Never make a large destructive rewrite without understanding the existing behavior.

### Rule 2

Preserve existing features unless they are demonstrably broken or unsafe.

### Rule 3

Do not change public API contracts unnecessarily.

### Rule 4

If a breaking change is necessary, document:

```text
OLD
NEW
MIGRATION
```

### Rule 5

Every meaningful code change should have a corresponding test when practical.

### Rule 6

Do not claim a test passed if you could not actually execute it.

### Rule 7

If the environment prevents execution, state:

```text
NOT VERIFIED — environment limitation
```

### Rule 8

Never fabricate benchmark results.

### Rule 9

Never claim a security vulnerability is exploitable unless you can demonstrate the required conditions.

### Rule 10

Do not fix unrelated cosmetic issues while critical architectural problems remain unresolved.

---

# EXECUTION ORDER

Work in this order:

```text
1. Repository discovery
2. Verify review findings
3. Database fallback removal
4. Transaction boundaries
5. Database authority / migration strategy
6. Sync/async consolidation
7. Service consolidation
8. Dependency/boundary cleanup
9. Security hardening
10. Error handling
11. Scheduler reliability
12. Tests
13. CI
14. Repository hygiene
15. Frontend cleanup
16. Performance optimization
```

Do not jump directly to phase 15 or feature development while P0/P1 correctness problems remain.

---

# REQUIRED OUTPUT AFTER EACH PHASE

After completing each phase, provide:

## Changes Made

List exact files modified.

## Problems Fixed

List the specific findings addressed.

## Architecture Impact

Explain how the change affects the architecture.

## Tests Added

List tests created/modified.

## Verification

State exactly what was executed.

Example:

```text
pytest tests/unit/test_database_fallback.py
PASS
```

or:

```text
NOT VERIFIED — Python is not available on PATH.
```

## Remaining Risks

List anything unresolved.

---

# FINAL DELIVERABLE

At the end, produce a concise engineering report containing:

### 1. Executive Summary

What changed and why.

### 2. Before vs After Architecture

Show:

```text
BEFORE
...
```

and:

```text
AFTER
...
```

Use Mermaid if useful.

### 3. Critical Findings

For each:

```text
Finding
Root Cause
Fix
Files
Tests
Status
```

### 4. Database Strategy

Clearly document:

```text
Canonical database
Schema ownership
Migration mechanism
SQLite role
Transaction strategy
Backup/recovery assumptions
```

### 5. Security Posture

Document:

```text
Authentication
Authorization
Secrets
DEV mode
Input validation
SQL injection protections
Error disclosure
WebSocket security
HTTPS expectations
Rate limiting
```

### 6. Testing Status

Include:

```text
Tests discovered
Tests added
Tests executed
Tests passed
Tests failed
Tests blocked by environment
Coverage
```

Do not invent coverage numbers.

### 7. Remaining Technical Debt

Rank:

```text
P0
P1
P2
P3
```

### 8. Recommended Next Steps

Give the next 5-10 highest-value engineering tasks.

---

# IMPORTANT


**trust the source code and explain the discrepancy.**

If you cannot verify something:

**say "Cannot confirm from the available source."**

If a proposed fix introduces a new architectural risk:

**stop and explain the trade-off before implementing it.**

The goal is not to make the repository look cleaner.

The goal is to make **Alpha materially safer, more deterministic, more maintainable, and more trustworthy for
financial data while preserving its existing functionality.**

Start with repository discovery and verification of the P0 findings.
C:\Users\Zhvn\Documents\Zhvny\Project\Alpha\docs\perlu di perbaiki\DEEP_CODE_REVIEW (1).md dan C:
\Users\Zhvn\Documents\Zhvny\Project\Alpha\docs\perlu di perbaiki\DEEP_CODE_REVIEW.md