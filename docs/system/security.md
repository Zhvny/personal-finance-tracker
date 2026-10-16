# 🔐 Finance Tracker: Security Architecture & Controls (v10.0)

This document specifies the security controls, CIA Triad implementation, AAA framework, and secure defaults enforced across the Finance Tracker API and microservices.

---

## 🛡️ 1. Security Design (CIA Triad + AAA)

### Confidentiality
- **Authentication**: Bearer API Key via `FINANCE_TRACKER_API_KEY`.
- **IP Whitelisting**: `audit_middleware` validates client IP against `ALLOWED_IP_WHITELIST` (`127.0.0.1,localhost`).
- **Secret Isolation**: Secrets reside exclusively in `.env` (gitignored). Hardcoded fallback defaults are removed or emit high-priority warnings in non-debug mode.
- **Log Sanitation**: API keys, bearer tokens, and internal stack trace details are strictly scrubbed from HTTP responses and audit logs.

### Integrity
- **Request Signing**: Optional HMAC-SHA256 request verification via `X-Request-Signature`.
- **File Upload Guard**: Strict MIME type validation (`image/jpeg`, `image/png`, `image/webp`, `image/gif`, `image/bmp`) and file extension whitelist (`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`). Maximum file upload size is capped at **10 MB**.
- **Audit Ledger**: All state-mutating requests write an immutable entry to `audit_log.db`.

### Availability
- **Sliding-Window Rate Limiter**: In-memory rate limiting per IP enforced via `audit_middleware`. Default limit is **120 requests/minute** (overrideable via `FINANCE_TRACKER_RATE_LIMIT`).
- **Health Polling**: `run.bat` and `setup.bat` perform non-blocking HTTP readiness checks against `http://localhost:8444/api/health` before launching frontend or dependent services.

---

## 🔑 2. AAA Framework & Authorization

### Authentication & Dev Mode
- **Secure Default**: `FINANCE_TRACKER_DEV_MODE` defaults to `"0"` (auth enforced).
- **Opt-In Dev Mode**: `FINANCE_TRACKER_DEV_MODE="1"` is allowed only for isolated local development.
- **Token Verification**: Handled by `verify_api_key` FastAPI dependency using constant-time comparison (`hmac.compare_digest`).

### Scope Hierarchy
| Scope | Level | Description | Applied Routes |
|---|---|---|---|
| `read` | 1 | Read-only access to financial summaries, dashboard, & indicators | Dashboard, Config, Version/Info, Health, Analytics |
| `write` | 2 | Mutation access to create/update/delete expenses, income, investments | Expenses, Income, Investments, Balances, Receipts, Rewards |
| `admin` | 3 | Full administrative system access & audit log queries | Admin audit endpoints |

---

## 🌐 3. Network & Transport Security

- **Host Binding**: API Server defaults to `127.0.0.1` (`FINANCE_TRACKER_HOST`). Public binding (`0.0.0.0`) must be explicitly set in `.env`.
- **CORS Policy**: Configured strictly via `FINANCE_TRACKER_CORS_ORIGINS`. Default origins: `http://localhost:5173,http://127.0.0.1:5173`. Wildcard (`*`) is explicitly prohibited in production.
- **WebSocket Security**: `/ws/notifications/{client_id}` enforces Bearer token validation via `?token=<API_KEY>` query param in production mode.
- **Security Headers**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Cache-Control: no-store, no-cache, must-revalidate` (Financial endpoints)

---

## ⚡ 4. Operations & Launcher Security

- **Launcher Health Checks**: Both `run.bat` and `setup.bat` wait for active HTTP 200 response on `/api/health` before starting Vite dev server or opening browser tabs.
- **Process Cleanup**: Old orphan Python and Node processes on ports `8443`, `8444`, `45678`, `8501`, `5678` are gracefully reclaimed during launcher startup.
