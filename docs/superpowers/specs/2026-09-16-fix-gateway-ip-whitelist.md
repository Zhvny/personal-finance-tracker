# Spec: Fix Gateway-Backend IP Whitelist Blocking

## Problem

Gateway cannot fetch `/openapi.json` from backend services. Result: gateway starts with 0 routes, all `/api/proxy/*` calls fail, frontend shows empty/error states.

## Root Cause

Backend services enforce IP whitelist via `ALLOWED_IP_WHITELIST` env var. Default is empty, which means only loopback IPs are allowed. Gateway runs in Docker with IP `172.19.0.x`, not loopback. All inter-service requests are rejected with `403 Forbidden`.

Evidence:
```
alpha-platform | Access denied for IP: 172.19.0.5
alpha-gateway  | openapi.json unavailable from platform: 403 Forbidden
alpha-gateway  | Gateway ready with 0 exact routes.
```

## Current State

- `packages/shared/security/core.py` line 541:
  ```python
  if "*" not in allowed and ip not in allowed and ip not in LOOPBACK_IPS:
      return JSONResponse(status_code=403, ...)
  ```
- `docker-compose.yml` backend services do not set `ALLOWED_IP_WHITELIST`
- Gateway IP `172.19.0.5` is not in `LOOPBACK_IPS`

## Proposed Fix

Add `ALLOWED_IP_WHITELIST=*` to all backend services in `docker-compose.yml` via the existing `&python-env` anchor.

### Files Changed

- `docker-compose.yml` — add one line to `&python-env`

### Change

```yaml
environment: &python-env
  DATABASE_URL: postgresql://postgres:password@postgres:5432/finance_tracker?schema=public
  PRISMA_PY_DEBUG_GENERATOR: "1"
  ALPHA_SERVICE_TOKEN: ${ALPHA_SERVICE_TOKEN:?...}
  SECRET_KEY: ${SECRET_KEY}
  ALLOWED_IP_WHITELIST: "*"   # <-- add this
```

### Why This Works

`*` bypasses the IP whitelist check entirely. In Docker, services are already isolated on the `alpha-internal` network, so IP whitelist is redundant defense-in-depth. The existing service token (`ALPHA_SERVICE_TOKEN`) still protects against unauthorized access.

### Alternatives Considered

1. Add gateway IP to whitelist — fragile, IP changes on container restart
2. Disable IP check in code — same effect but requires code change + rebuild
3. Keep whitelist but add Docker network CIDR — requires knowing network CIDR at compose time

`ALLOWED_IP_WHITELIST=*` is the simplest correct fix for Docker-internal service mesh.

## Verification

```bash
docker compose up -d
docker compose logs gateway --tail=10
# Expected: no more 403s, routes loaded

curl http://localhost:8444/health
# Expected: {"status":"ok",...,"downstream":{...all "up"...}}

curl http://localhost:3000/api/proxy/health
# Expected: 200 OK from backend via gateway
```

## Scope

- Only `docker-compose.yml` changed
- No Python code changes
- No frontend changes
- No new dependencies
