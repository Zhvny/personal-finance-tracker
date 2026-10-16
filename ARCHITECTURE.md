# Alpha — Architecture

> Narasi cara sistem bekerja. Untuk inventaris file/area dan status kanonik-vs-legacy,
> lihat peta yang di-generate: `docs/PROJECT_MAP.md` dan `docs/STATUS.md`.

## 1. Ringkas

Alpha adalah monorepo **Turborepo + pnpm** (`apps/` + `packages/`) yang berjalan di atas
**topologi microservice**: satu gateway publik (`:8444`) di depan enam domain service,
plus dashboard Next.js, GUI Electron, dan CLI TUI Textual.

Entry point runtime yang resmi adalah `services/*` (gateway + 6 domain service).
`apps/api/main.py` adalah **monolit LEGACY** — jangan tambah fitur baru di sana.

## 2. Topologi runtime

```
                      ┌──────────────┐
  browser/GUI ───────►│   gateway    │ :8444  exact-route proxy dibangun dari
  CLI (lokal) ───────►│  (FastAPI)   │        /openapi.json tiap downstream
                      └──────┬───────┘
     ┌──────────┬───────────┬┴─────────┬────────────┬────────────┐
     ▼          ▼           ▼          ▼            ▼            ▼
 platform     ledger    portfolio    market     insights    engagement
 :8450        :8451     :8452        :8453      :8454       :8455
 auth         expenses  investments  stocks     receipts    behavioral
 profiles     income    reports      ml/genetic merchant    rewards
 logs/ws/tg   budget    dashboard    senate     ai/analytics
              goals/nl                scheduler
     └──────────┴───────────┴──────────┬─┴────────────┴────────────┘
                                       ▼
                                PostgreSQL (per-profile schemas)
```

| Service | Port | Memiliki |
|---|---|---|
| `gateway` | 8444 | Entri publik; reverse proxy HTTP (route table exact dari `/openapi.json`) + proxy WebSocket (`/ws/*`) |
| `platform` | 8450 | auth, profiles, logs, notifications (WS), Telegram bot/webhook, `/api/config` |
| `ledger` | 8451 | expenses, income, transactions/accounts/categories, budget, recurring, confirmations, safe-to-spend, forecast, net worth, goals, NL finance |
| `portfolio` | 8452 | investments (FIFO), reports, dashboard aggregator |
| `market` | 8453 | stocks, ML stocks, genetic optimizer, butterfly risk map, Agent Senate, market scheduler |
| `insights` | 8454 | receipt OCR ensemble, merchant map, AI advisor, analytics, anomalies, health score |
| `engagement` | 8455 | behavioral finance (FBS), reward economy |

Port registry otoritatif: `.env.example` (gateway `8444`, domain `8450–8455`) dan
`docs/PORTS.md`.

## 3. Runtime bersama (`services/runtime/bootstrap.py`)

Setiap service adalah proses/port sendiri yang dirakit oleh
`create_service_app(service_name, default_port, routers, ...)`:

- **Logging**: `RotatingFileHandler` ke `logs/<service-name>.log` + stdout berwarna,
  dengan `request_id` disuntik per record.
- **Middleware**: CORS (`ALLOWED_ORIGINS`, credentials), `audit_middleware`,
  global exception handler. HTTPS redirect **opt-in** via `ENABLE_HTTPS=1`
  (cert dev pernah menyebabkan massa socket hang up).
- **Lifespan startup**: auto-migrate opsional (`ALPHA_AUTO_MIGRATE=1`, pakai Postgres
  advisory lock agar tepat satu service apply), `SchemaInitializer(...).ensure_all()`,
  koneksi Prisma, muat Vault (`VAULT_ADDR`), scheduler market (opt-in),
  Telegram polling (opt-in via `ENABLE_TELEGRAM_POLL=1`).
- **Health**: `GET /health`, `/health/live` (liveness), `/health/ready` (cek schema DB,
  503 bila gagal), `GET /info` (butuh scope `read`).
- **Router mounting**: impor dari `packages.api.backend.routers.<name>` (atau module
  path ber-titik) dan `include_router`; service hanya me-mount subset-nya.

`run_service(app, name)` bind `settings.HOST` dan port dari `ALPHA_SERVICE_PORT`
(fallback `app.state.default_port`).

## 4. Library bersama

- Router tersimpan di `packages/api/backend/routers/`; tiap service me-mount subset
  (lihat `services/<name>/main.py`). Gateway menemukan route otomatis dari
  `/openapi.json` tiap downstream — menambah router tidak butuh ubah gateway.
- `packages/core/` = domain/application/infrastructure (Clean Architecture).
  `apps/cli/` memuat engine domain (SSOT logika bisnis yang dipakai service).
- `packages/database/` = bridge klien Prisma (Python).

## 5. Isolasi per-profil (2026-09-18)

- Tiap profil (`personal`, `business`, …) punya **schema Postgres sendiri**.
- Model Prisma **unqualified** (tanpa `multiSchema`/`@@schema`); query diarahkan ke
  profil aktif via connection `search_path={profile},public`.
- Data finansial baru terisolasi per profil; data lama pra-isolasi tetap di schema
  shared `alpha_*` (orphaned by decision — hanya data BARU yang terisolasi).

## 6. Otorisasi

Semua route `/api/*` **wajib** `require_scope(...)` (termasuk `/api/config`).
Hanya `/health*` yang publik. Nilai API key / bearer token tidak pernah di-log.

## 7. Catatan & konteks historis

- `docs/system/architecture.md` = blueprint domain era CLI (SQLite terdistribusi).
  Berguna untuk logika domain, **bukan** untuk topologi runtime saat ini.
- Utang stage-1 (DB bersama, image bersama) dilacak dengan trigger eksplisit di
  `docs/maintenance/HONEY_DEBT.md`.

## Sumber

- `README.md` §Overview, §Architecture, §Repository Structure, §Security Notes.
- `AGENTS.md` (status arsitektur + isolasi per-profil).
- `services/runtime/bootstrap.py`.
- `docs/project.toml` (blok `[service.*]` dan `[areas.*]`).
- `docs/system/architecture.md` (konteks domain era CLI).
- `docs/PORTS.md`, `.env.example` (port registry).
- `packages/database/index.py`, `packages/database/schema.prisma`.
- Inventaris generated: `docs/PROJECT_MAP.md`, `docs/STATUS.md`.
