# Alpha — API

> Ringkasan arsitektur API dan kontrak lintas-service. **Bukan** inventaris endpoint.
> Inventaris per-service yang di-generate dari kode ada di `services/<name>/docs/API.md`;
> peta area/status kanonik ada di `docs/PROJECT_MAP.md` dan `docs/STATUS.md`.

## 1. Topologi

Semua trafik HTTP masuk lewat **gateway** `:8444`, yang me-reverse-proxy ke enam
domain service. Gateway **tidak** menyimpan daftar path hardcoded: saat startup ia
membangun route table `(method, path)` dari `/openapi.json` tiap downstream, jadi
route drift tidak bisa salah-rute secara diam-diam. WebSocket `/ws/*` diproxy
terpisah (default ke `platform :8450`).

| Service | Port | Domain |
|---|---|---|
| `gateway` | 8444 | Entri publik; reverse proxy HTTP + proxy WebSocket |
| `platform` | 8450 | auth, profiles, logs, notifications (WS), Telegram, `/api/config` |
| `ledger` | 8451 | expenses, income, accounts/categories, budget, goals, NL finance |
| `portfolio` | 8452 | investments (FIFO), reports, dashboard aggregator |
| `market` | 8453 | stocks, ML stocks, genetic, butterfly, senate, scheduler |
| `insights` | 8454 | receipts OCR, merchant, AI advisor, analytics, anomalies, health score |
| `engagement` | 8455 | behavioral finance (FBS), reward economy |

Port otoritatif: `.env.example` dan `docs/PORTS.md`.

## 2. Autentikasi & otorisasi

- **Skema:** Bearer API key atau session token di header `Authorization: Bearer <key>`
  (master key `FINANCE_TRACKER_API_KEY` atau token sesi hasil login).
- **Aturan repo:** semua route `/api/*` **wajib** `require_scope(...)` — termasuk
  `/api/config`. **Hanya** `/health*` yang publik. Nilai API key / bearer token tidak
  pernah di-log.
- **Verifikasi key:** `POST /api/auth/verify` (200 = valid, 401 = invalid) —
  `packages/api/backend/routers/auth.py`.
- **Isolasi per-profil:** setiap request diarahkan ke schema Postgres profil aktif
  via connection `search_path` (lihat `DESIGN.md`, `docs/SCHEMA_AUTHORITY.md`).

## 3. Base URL

```
http://localhost:8444        # gateway (langsung)
http://localhost:3000/api    # web dev server proxy -> gateway
```

## 4. Cross-cutting gateway

- **Circuit breaker per downstream** (`services/runtime/circuit_breaker.py`) —
  downstream yang mati dibuka circuitnya, bukan menggantung.
- **Service token** (`services/runtime/service_token.py`) disuntik ke request
  downstream.
- **Rate limit per-IP** (`services/runtime/redis_rate_limiter.py`): default
  `ALPHA_GATEWAY_RATE_LIMIT=300` per 60 s; IP loopback dikecualikan.
- **WS routing:** `ALPHA_WS_ROUTES` (mis. `notifications=http://platform:8450`),
  fallback `ALPHA_WS_UPSTREAM` (default `platform :8450`).

## 5. Health

Setiap service (via `services/runtime/bootstrap.py`) mengekspos:

- `GET /health` — health lengkap.
- `GET /health/live` — liveness.
- `GET /health/ready` — readiness (cek schema DB, 503 bila gagal).
- `GET /info` — metadata operasional (butuh scope `read`).

## 6. Di mana inventaris endpoint berada

Jangan menyalin endpoint ke sini. Sumber per-service (generated dari AST kode):

- `services/gateway/docs/API.md`, `services/platform/docs/API.md`,
  `services/ledger/docs/API.md`, `services/portfolio/docs/API.md`,
  `services/market/docs/API.md`, `services/insights/docs/API.md`,
  `services/engagement/docs/API.md` — regenerate: `python scripts/gen_service_docs.py`.
- `docs/services/alpha-microservice.md` — referensi endpoint era monolith
  (penamaan legacy; route tetap valid lewat gateway).
- `docs/features/*.md` — spesifikasi fitur + workflow n8n.

## 7. Error & status

Kode error per-service di-derive dari literal `status_code=<n>` di AST
(`services/<name>/docs/SPEC.md`). Konvensi lintas-service: `401`/`403` untuk
auth/scope, `422` untuk validasi Pydantic, `502` dari gateway saat downstream
gagal/circuit-open. Endpoint yang saat ini rusak dicatat di `docs/STATUS.md`.

## Sumber

- `services/*/main.py` (`ROUTERS`, `DEFAULT_PORT`, inline endpoints).
- `services/gateway/main.py` (route table dari `/openapi.json`, WS, circuit breaker).
- `services/runtime/bootstrap.py`, `services/runtime/redis_rate_limiter.py`,
  `services/runtime/service_token.py`, `services/runtime/circuit_breaker.py`.
- `packages/api/backend/routers/auth.py` (`POST /api/auth/verify`).
- `docs/API.md`, `docs/PORTS.md`, `.env.example`.
- `docs/services/alpha-microservice.md`, `docs/features/*.md`.
- Inventaris generated: `services/*/docs/API.md`, `docs/PROJECT_MAP.md`, `docs/STATUS.md`.
