# Cloud-Native Maturation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the identified microservices/cloud-native gaps so Alpha reaches production-ready maturity: per-service data sovereignty, resilient inter-service communication, full observability integration, and automated operations.

**Architecture:** Phase-separated approach — (1) infrastructure primitives that services consume, (2) per-service schema migration from shared DB, (3) deployment and operational hardening. Each phase produces a deployable, testable state.

**Tech Stack:** PostgreSQL schemas + RLS, Redis (stack already in CI), Prometheus metrics, Jaeger tracing, Kubernetes HPA, CronJob backup.

**Spec:** `PRD.md` §6 Persistence Model, §7 Non-Functional Requirements, `STATE.md` technical debt register D1/D2/D3/D5.

## Global Constraints

- Python 3.12, FastAPI, uvicorn
- Single PostgreSQL instance in stage-1; split by schema, not instance
- Do NOT remove existing unique constraints or break existing migration chain
- Do NOT add new top-level dependencies without explicit approval
- All secrets via env var or Vault; never hardcoded
- Commands: `pytest`, `ruff check .`, `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps`

---

## File Structure

```
services/
  runtime/
    redis_rate_limiter.py        # New: Redis-backed rate limiter
    circuit_breaker.py           # New: HTTP circuit breaker
    vault_client.py              # New: Vault secret loader
packages/
  shared/
    security/
      core.py                    # Modify: swap rate limiter backend
k8s/
  redis.yaml                     # New: Redis StatefulSet/Service
  hpa.yaml                       # New: HPA for domain services
  backup-cronjob.yaml            # New: PostgreSQL backup CronJob
  domain-services.yaml           # Modify: add HPA ref, resource tuning
  gateway.yaml                   # Modify: add Vault CSI, readiness
docs/
  maintenance/
    DATABASE_SPLIT_GUIDE.md      # New: runbook for schema migration
```

---

## Phase 1 — Infrastructure Primitives

### Task 1: Redis-backed rate limiter

**Files:**
- Create: `services/runtime/redis_rate_limiter.py`
- Modify: `services/gateway/main.py:122-138`
- Test: `tests/test_redis_rate_limiter.py`

**Interfaces:**
- Consumes: `REDIS_URL` env var, `_effective_client_ip()`
- Produces: `check_rate_limit(request) -> None`, raises `_RateLimitExceeded`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_redis_rate_limiter.py
import asyncio
import os

import pytest
import httpx

from services.runtime.redis_rate_limiter import check_rate_limit, _RateLimitExceeded

pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    yield

@pytest.fixture
def redis_pool(redis_url):
    from services.runtime.redis_rate_limiter import get_pool
    pool = get_pool()
    yield pool
    asyncio.get_event_loop().run_until_complete(pool.flushdb())

async def test_allows_requests_under_limit(redis_pool):
    for _ in range(5):
        check_rate_limit("127.0.0.1")  # loopback bypass, just ensure no crash

async def test_blocks_over_limit(redis_pool):
    from services.runtime.redis_rate_limiter import _RATE_LIMIT, _RATE_WINDOW_SECS
    ip = "10.0.0.99"
    for _ in range(_RATE_LIMIT):
        check_rate_limit(ip)
    with pytest.raises(_RateLimitExceeded):
        check_rate_limit(ip)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_redis_rate_limiter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.runtime.redis_rate_limiter'`

- [ ] **Step 3: Write minimal implementation**

```python
# services/runtime/redis_rate_limiter.py
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("alpha.rate_limiter")

_REDIS_URL = os.getenv("REDIS_URL", "")
_RATE_LIMIT = int(os.getenv("ALPHA_GATEWAY_RATE_LIMIT", "300"))
_RATE_WINDOW_SECS = 60
_POOL: Optional[aioredis.ConnectionPool] = None


def get_pool() -> aioredis.ConnectionPool:
    global _POOL
    if _POOL is None:
        _POOL = aioredis.ConnectionPool.from_url(_REDIS_URL, decode_responses=True, max_connections=20)
    return _POOL


async def _sliding_window_allow(ip: str, limit: int, window: int) -> tuple[bool, int]:
    if not _REDIS_URL or limit <= 0:
        return True, 0
    pool = get_pool()
    key = f"rate:{ip}:{int(time.time() // window)}"
    try:
        async with pool.acquire() as r:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window + 1)
            allowed = count <= limit
            retry_after = window - int(time.time() % window) if not allowed else 0
            return allowed, retry_after
    except Exception as e:
        logger.warning(f"rate limiter redis error: {e}")
        return True, 0


class _RateLimitExceeded(Exception):
    def __init__(self, retry_after: int, ip: str, limit: int) -> None:
        super().__init__(f"rate limit exceeded for {ip}")
        self.retry_after = retry_after
        self.ip = ip
        self.limit = limit


def check_rate_limit(ip: str) -> None:
    if ip in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return
    loop = asyncio.get_event_loop()
    allowed, retry_after = loop.run_until_complete(_sliding_window_allow(ip, _RATE_LIMIT, _RATE_WINDOW_SECS))
    if not allowed:
        raise _RateLimitExceeded(retry_after=retry_after, ip=ip, limit=_RATE_LIMIT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_redis_rate_limiter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/runtime/redis_rate_limiter.py tests/test_redis_rate_limiter.py
git commit -m "feat: add redis-backed rate limiter for gateway"
```

- [ ] **Step 6: Wire into gateway (no test cycle — integration smoke only)**

Edit `services/gateway/main.py`:
- Replace in-memory `_check_rate_limit()` to call `services.runtime.redis_rate_limiter.check_rate_limit(ip)`
- Add startup warning when `ALPHA_REDIS_URL` is unset in production (already present)

- [ ] **Step 7: Smoke test gateway**

```bash
REDIS_URL=redis://localhost:6379/0 ALPHA_REDIS_URL=redis://localhost:6379/0 python -m services.gateway.main &
# request 301 times from same IP -> expect 429 on 301st
```

---

### Task 2: Circuit breaker for outbound HTTP

**Files:**
- Create: `services/runtime/circuit_breaker.py`
- Modify: `services/gateway/main.py:344-360` (proxy upstream call)
- Test: `tests/test_circuit_breaker.py`

**Interfaces:**
- Consumes: httpx.AsyncClient
- Produces: `CircuitBreaker` class, `call_with_breaker(breaker, fn, *args)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_circuit_breaker.py
import asyncio
import pytest

from services.runtime.circuit_breaker import CircuitBreaker, CircuitOpen

pytestmark = pytest.mark.asyncio

async def test_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    async def fail():
        raise ConnectionError("boom")
    for _ in range(3):
        with pytest.raises(ConnectionError):
            await cb.call(fail)
    with pytest.raises(CircuitOpen):
        await cb.call(fail)

async def test_half_open_after_timeout():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    async def fail():
        raise ConnectionError("boom")
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await cb.call(fail)
    await asyncio.sleep(0.15)
    with pytest.raises(ConnectionError):
        await cb.call(fail)  # one probe allowed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_circuit_breaker.py -v`

- [ ] **Step 3: Write minimal implementation**

```python
# services/runtime/circuit_breaker.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

logger = logging.getLogger("alpha.circuit_breaker")


class CircuitOpen(Exception):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    _failure_count: int = 0
    _opened_at: datetime | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def call(self, fn: Callable[[], Awaitable[Any]]) -> Any:
        async with self_lock():
            if self._opened_at:
                if datetime.now() - self._opened_at > timedelta(seconds=self.recovery_timeout):
                    self._failure_count = 0
                    self._opened_at = None
                else:
                    logger.warning("circuit breaker open")
                    raise CircuitOpen()
        try:
            result = await fn()
        except Exception:
            async with self._lock:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._opened_at = datetime.now()
            raise
        else:
            async with self._lock:
                self._failure_count = 0
                self._opened_at = None
            return result

def self_lock():
    return asyncio.Lock()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_circuit_breaker.py -v`

- [ ] **Step 5: Commit**

```bash
git add services/runtime/circuit_breaker.py tests/test_circuit_breaker.py
git commit -m "feat: add circuit breaker for outbound http"
```

- [ ] **Step 6: Wire into gateway proxy**

In `services/gateway/main.py`, wrap `app.state.client.request(...)` with a per-downstream `CircuitBreaker`.

---

### Task 3: Vault runtime integration

**Files:**
- Create: `services/runtime/vault_client.py`
- Modify: `services/runtime/bootstrap.py` (lifetime Vault token refresh)
- Modify: `k8s/vault.yml` (fix metadata duplicate, add ServiceAccount)
- Test: `tests/test_vault_client.py`

**Interfaces:**
- Consumes: `VAULT_ADDR`, `K8S_SERVICE_ACCOUNT_TOKEN`
- Produces: `get_secret(path: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vault_client.py
import os
import pytest

def test_vault_disabled_without_addr(monkeypatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    from services.runtime.vault_client import get_secret
    assert get_secret("secret/alpha/test") == {}
```

- [ ] **Step 2-5: Implement minimal Vault client, K8s auth, graceful fallback**

```python
# services/runtime/vault_client.py
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("alpha.vault")

_VAULT_ADDR = os.getenv("VAULT_ADDR", "")
_K8S_SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"


def _headers() -> dict[str, str]:
    if not _VAULT_ADDR:
        return {}
    try:
        token = open(_K8S_SA_TOKEN_PATH).read().strip()
        return {"X-Vault-Token": token}
    except Exception:
        return {}


def get_secret(path: str) -> dict[str, Any]:
    if not _VAULT_ADDR:
        return {}
    try:
        resp = httpx.get(f"{_VAULT_ADDR}/v1/{path}", headers=_headers(), timeout=3)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        logger.warning(f"vault read {path} failed: {e}")
        return {}
```

Fix `k8s/vault.yml` duplicate metadata block; add ServiceAccount + RoleBinding.

- [ ] **Step 6: Bootstrap integration**

In `services/runtime/bootstrap.py` lifespan, optionally refresh secrets from Vault into env when `VAULT_ADDR` is set.

---

## Phase 2 — Database Per-Service Schema Isolation

### Task 4: Schema ownership and RLS enforcement

**Files:**
- Create: `migrations/schemas/0001_service_schemas.sql`
- Modify: `packages/database/schema.prisma` (add `@@schema` annotations per model)
- Modify: `packages/api/backend/infrastructure/schemas.py` (per-service schema init)
- Test: `tests/test_schema_isolation.py`

**Interfaces:**
- Consumes: `DATABASE_URL`
- Produces: `SchemaInitializer.ensure_all()` creates `ledger`, `portfolio`, `market`, `insights`, `engagement` schemas

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema_isolation.py
import pytest
from packages.api.backend.infrastructure.schemas import SchemaInitializer

def test_service_schemas_exist(db_url):
    init = SchemaInitializer(lambda m, f: None)
    init.ensure_all()
    import asyncpg
    import asyncio
    async def check():
        conn = await asyncpg.connect(db_url)
        rows = await conn.fetch("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'alpha_%'")
        names = {r["nspname"] for r in rows}
        for expected in {"alpha_ledger", "alpha_portfolio", "alpha_market", "alpha_insights", "alpha_engagement"}:
            assert expected in names
    asyncio.run(check())
```

- [ ] **Step 2-5: Create schema migration, update Prisma models with `@@schema("alpha_<service>")`, run `prisma db push`, verify**

Critical: keep existing `public` schema for shared tables (sessions, audit) — do NOT break current migrations 001-015.

- [ ] **Step 6: Commit**

```bash
git add migrations/schemas/0001_service_schemas.sql packages/database/schema.prisma tests/test_schema_isolation.py
git commit -m "feat: add per-service schemas for domain isolation"
```

---

### Task 5: Row-Level Security policies

**Files:**
- Create: `migrations/rls/0001_rls_policies.sql`
- Modify: `packages/api/backend/repositories/*` (set `SET RowSecurity = ON` per request)
- Test: `tests/test_rls_isolation.py`

**Interfaces:**
- Consumes: `request.state.profile_id`
- Produces: `rls_policy_script(profile_id) -> str` injected at connection start

- [ ] **Step 1-5: Add `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + per-schema policies for `profile_id`, create FastAPI middleware to set `app.current_set_id` or Postgres `SET row_security = on` with `SET LOCAL profile_id = X` via `ra`**

Minimal approach: use `SET LOCAL "app.current_profile" = 'X'` on each request from pool.

- [ ] **Step 6: Commit**

```bash
git add migrations/rls/0001_rls_policies.sql packages/api/backend/repositories/* tests/test_rls_isolation.py
git commit -m "feat: enable RLS for per-profile data isolation"
```

---

## Phase 3 — Deployment Hardening

### Task 6: Redis StatefulSet + Service

**Files:**
- Create: `k8s/redis.yaml`
- Modify: `k8s/domain-services.yaml` (env `REDIS_URL`)
- Modify: `docker-compose.prod.yml` (add redis service)
- Test: `kubectl apply -f k8s/redis.yaml && kubectl exec redis-0 -- redis-cli ping`

- [ ] **Step 1-3: Write Redis StatefulSet manifest, ClusterIP Service, password Secret reference**
- [ ] **Step 4: Apply to cluster, verify**
- [ ] **Step 5: Update gateway env `REDIS_URL=redis://redis:6379/0`**

---

### Task 7: HPA for domain services

**Files:**
- Create: `k8s/hpa.yaml`
- Test: `kubectl apply -f k8s/hpa.yaml && kubectl get hpa`

- [ ] **Step 1: Write HPA manifests targeting CPU 70% for each domain service**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: alpha-platform-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: alpha-platform
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

Repeat for ledger, portfolio, market, insights, engagement. Gateway HPA: min 2, max 5.

- [ ] **Step 2: Apply, watch scale-up under load with `kubectl get hpa -w`**

---

### Task 8: PostgreSQL backup CronJob

**Files:**
- Create: `k8s/backup-cronjob.yaml`
- Modify: `k8s/db-secret.yaml` (add `BACKUP_S3_BUCKET` or local PVC path)
- Test: `kubectl apply -f k8s/backup-cronjob.yaml && kubectl get cronjob`

- [ ] **Step 1: Write CronJob manifest**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: alpha-postgres-backup
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16-alpine
              command:
                - /bin/sh
                - -c
                - |
                  pg_dump -U postgres finance_tracker > /backups/finance_$(date +%Y%m%d).sql
                  # keep last 7 days
                  ls -t /backups/*.sql | tail -n +8 | xargs rm -f
              env:
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: db-secret
                      key: POSTGRES_PASSWORD
              volumeMounts:
                - name: backups
                  mountPath: /backups
          restartPolicy: OnFailure
          volumes:
            - name: backups
              persistentVolumeClaim:
                claimName: alpha-backups-pvc
```

- [ ] **Step 2: Create PVC `alpha-backups-pvc`, 10Gi, daily schedule, retention 7 days**

---

### Task 9: Image per service (build arg differentiation)

**Files:**
- Modify: `Dockerfile` (accept `SERVICE_CMD` build arg)
- Modify: `docker-compose.prod.yml` (per-service `build.args`)
- Modify: `.github/workflows/docker-image.yml` (matrix build)

- [ ] **Step 1: Update Dockerfile**

```dockerfile
ARG SERVICE_CMD="python apps/api/main.py"
CMD ["/bin/sh", "-c", "${SERVICE_CMD}"]
```

- [ ] **Step 2: Update compose `build` section per service with args**

```yaml
platform:
  build:
    context: .
    dockerfile: Dockerfile
    args:
      SERVICE_CMD: "python -m services.platform.main"
```

- [ ] **Step 3: Update GitHub Actions matrix to tag images `finance-tracker-<service>:<sha>`**

- [ ] **Step 4: Update k8s manifests to use service-specific image tags**

---

### Task 10: Gateway retry + timeout hardening

**Files:**
- Modify: `services/gateway/main.py:345-365`

- [ ] **Step 1: Add per-downstream timeout config**

```python
_DOWNSTREAM_TIMEOUT = float(os.getenv("ALPHA_DOWNSTREAM_TIMEOUT", "10"))
```

- [ ] **Step 2: Wrap upstream request with timeout and 1 retry on 502/503**

```python
for attempt in range(2):
    try:
        upstream = await app.state.client.request(
            request.method,
            f"{target_base}/{path}",
            params=dict(request.query_params),
            headers=headers,
            content=body,
            timeout=_DOWNSTREAM_TIMEOUT,
        )
        break
    except httpx.RequestError:
        if attempt == 1:
            raise
```

- [ ] **Step 3: Smoke test with a downstream that returns 503 — verify 502 returned and logged**

---

### Task 11: Multi-replica and readiness alignment

**Files:**
- Modify: `k8s/domain-services.yaml` (replicas: 2, add `podAntiAffinity`)
- Modify: `k8s/gateway.yaml` (replicas: 2 — already done)

- [ ] **Step 1: Set replicas to 2 for all domain services**
- [ ] **Step 2: Add soft `podAntiAffinity` to spread across nodes**

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app: alpha-platform
          topologyKey: kubernetes.io/hostname
```

---

### Task 12: Compose/K8s drift reconciliation

**Files:**
- Modify: `docker-compose.override.yml` (align env names with compose.prod)
- Modify: `docker-compose.prod.yml` (add `ALPHA_SERVICE_PORT` per service)
- Modify: `k8s/domain-services.yaml` (align env with STATE.md PORTS.md)

- [ ] **Step 1: Add `ALPHA_SERVICE_PORT` env in compose.prod.yml per service**
- [ ] **Step 2: Verify `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` renders without errors**
- [ ] **Step 3: Run `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` smoke test**

---

## Verification Gates

After each phase:
```bash
pytest --ignore=tests/automation
ruff check .
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
kubectl get deployments,services,hpa,cronjob
```

---

## Skipped / Deferred

| Item | Why Skipped | Trigger to Add |
|---|---|---|
| Service mesh (Istio/Linkerd) | Overhead > value at stage-1 single-cluster | Multi-cluster or mTLS requirement |
| Per-service DB instances | Stage-1 constraint; schema isolation covers data sovereignty | Any service needs independent backup/restore cadence |
| Vault CSI driver | Adds operator dependency; env fallback works | Compliance requires dynamic secrets with lease |
| Canary/blue-green deploy | Requires ArgoCD/Flux; manual rollout sufficient for N<5 services | Deployment frequency justifies GitOps |
