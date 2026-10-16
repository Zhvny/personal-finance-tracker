# Alpha - Finance Tracker Ecosystem

> Full-stack personal finance, investment, and AI analytics suite.
> Developed by Zhvny · v10.x · Python + TypeScript monorepo running a **microservice topology**.

---

## Overview

Alpha tracks expenses, income, and investments (stocks/crypto/gold), computes FIFO P/L,
runs stock analytics (technical indicators, XGBoost ML "Sniper" models, genetic optimizer,
regime-aware Agent Senate voting), reads receipts via an OCR ensemble, and gamifies good
financial behavior (rewards + behavioral finance index).

- **Repo layout**: monorepo managed by **Turborepo + pnpm** (`apps/` + `packages/`).
- **Runtime**: microservices - one public gateway (:8444) fronting six domain services,
  plus a Next.js web dashboard, an Electron GUI, and a Textual TUI CLI.

---

## Architecture

```
                       ┌──────────────┐
   browser/GUI ───────►│   gateway    │ :8444  exact-route proxy built from
   CLI (local) ───────►│  (FastAPI)   │        each service's OpenAPI spec
                       └──────┬───────┘
      ┌──────────┬───────────┬┴─────────┬────────────┬────────────┐
      ▼          ▼           ▼          ▼            ▼            ▼
 platform     ledger    portfolio    market     insights    engagement
 :8450        :8451     :8452        :8453      :8454       :8455
 auth         expenses  investments  stocks     receipts    behavioral
 profiles     income    reports      ml/genetic merchant   rewards
 logs/ws/tg   budget    dashboard    senate     ai/analytics
              goals/nl                scheduler
      └──────────┴───────────┴──────────┬─┴────────────┴────────────┘
                                        ▼
                                 PostgreSQL (shared - stage 1)
```

| Service | Port | Owns |
|---|---|---|
| `gateway` | 8444 | Public entry; HTTP reverse proxy (exact route table from `/openapi.json`) + WebSocket proxy (`/ws/*`) |
| `platform` | 8450 | auth, profiles, logs, notifications (WS), Telegram bot/webhook, `/api/config` |
| `ledger` | 8451 | expenses, income, transactions/accounts/categories, budget, recurring, confirmations, safe-to-spend, forecast, net worth, goals, NL finance |
| `portfolio` | 8452 | investments (FIFO), reports, dashboard aggregator |
| `market` | 8453 | stocks, ML stocks, genetic optimizer, butterfly risk map, Agent Senate, market scheduler |
| `insights` | 8454 | receipt OCR ensemble, merchant map, AI advisor, analytics, anomalies, health score |
| `engagement` | 8455 | behavioral finance (FBS), reward economy |

Router implementations live in the shared library `packages/api/backend/routers/`;
each service mounts only its subset (see `services/<name>/main.py`). The gateway
discovers routes automatically - adding a router needs zero gateway changes.

---

## Repository Structure

```text
alpha/
├── apps/
│   ├── api/                 # legacy monolith entry (deprecated wrapper) + config
│   ├── cli/                 # Textual TUI - SSOT of domain engines
│   ├── finance-tracker-gui/ # desktop GUI (React/Electron)
│   └── web/                 # Next.js web dashboard
├── packages/
│   ├── api/                 # backend library: routers, security, automation, infra
│   ├── core/                # domain/application/infrastructure (Clean Architecture)
│   ├── database/            # Prisma client bridge (Python)
│   ├── types/               # shared TS definitions
│   └── web/                 # shared UI components
├── services/                # ← microservice runtime (canonical)
│   ├── runtime/bootstrap.py # shared app factory (logging, middleware, health, lifespan)
│   ├── gateway/  platform/  ledger/
│   ├── portfolio/ market/   insights/ engagement/
├── k8s/                     # gateway.yaml, domain-services.yaml, db-*, ingress
├── migrations/              # numbered SQL schema migrations
├── docs/                    # documentation hubs (see map below)
├── docker-compose.yml       # dev topology (hot-reload mounts)
├── docker-compose.prod.yml  # production topology
├── Dockerfile               # shared backend image (all services = same image, different CMD)
├── run.bat                  # unified launcher: GUI stack / CLI / log cockpit
├── run-services.bat         # boots all 6 services + gateway locally (no Docker)
└── .env.example             # port registry + required vars
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| API | Python 3.12, FastAPI, uvicorn, Prisma (Python client), httpx |
| Analytics/ML | pandas, yfinance, XGBoost, genetic optimizer, Ollama (local LLM, lazy-loaded) |
| OCR | Tesseract + EasyOCR + PaddleOCR ensemble w/ majority voting |
| Web/GUI | React, Next.js, Tailwind, Recharts; Electron for desktop |
| CLI | Python Textual (Rich) TUI |
| Data | PostgreSQL (canonical) + SQLite profile-isolated local stores |
| Orchestration | Turborepo, pnpm, Docker Compose, Kubernetes (k8s/) |

---

## Prerequisites

- Python 3.12+, Node.js 20+ (22 recommended), pnpm 11
- PostgreSQL 16 (or `docker compose up postgres`)
- Tesseract OCR binary (optional - receipt scanning)
- Ollama (optional - local AI advisor)

## Quick Start

### Option A - full topology with Docker (recommended)

```bash
cp .env.example .env          # set SECRET_KEY etc.
docker compose up --build     # gateway + 6 services + postgres + web
# web  → http://localhost:3000
# API  → http://localhost:8444  (gateway health: /health)
```

### Option B - local processes, no Docker

```bash
pnpm install                  # workspace deps (web/packages)
pip install -r requirements.prod.txt
./run-services.bat            # Windows; or run each: python -m services.<name>.main
```

### Legacy monolith (deprecated but functional)

```bash
./run.bat                     # menu: GUI stack (API+web+n8n), CLI, log cockpit
cd apps/api && python main.py # same app directly
```

The monolith mounts **all** routers on one port; new work must go through `services/`.

---

## Environment Variables

See [`.env.example`](.env.example) - highlights:

| Variable | Default | Notes |
|---|---|---|
| `ALPHA_GATEWAY_PORT` | `8444` | Gateway public port |
| `ALPHA_GATEWAY_TARGETS` | localhost peers | Override downstream URLs (compose/k8s set this) |
| `ALPHA_SERVICE_PORT` | per-service | Port override inside containers |
| `DATABASE_URL` | - | Shared Postgres DSN (stage-1) |
| `SECRET_KEY` | - | **Required**, never ship the default in production |
| `FINANCE_TRACKER_CORS_ORIGINS` | localhost list | Allowed browser origins |
| `ENABLE_TELEGRAM_POLL` | `0` | Opt-in Telegram bot long-polling (platform service) |

Port registry is authoritative in `.env.example`: gateway 8444, domain services 8450–8455.

---

## Development

```bash
pnpm dev            # turbo dev (web + packages)
pnpm lint           # eslint + ruff check .
pnpm test           # turbo test (vitest)
python -m pytest tests/          # python suites
ruff check .                     # python lint
python -m services.<name>.main   # run one service
```

Health endpoints per service: `/health` (live), `/health/ready` (DB readiness),
`/info` (authenticated metadata). Gateway aggregate: `GET :8444/health`.

Logs rotate into `logs/<service-name>.log`.

---

## Deployment

| Target | Entry point |
|---|---|
| Dev (Docker) | `docker compose up --build` |
| Production (Docker) | `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d` |
| Kubernetes | `kubectl apply -f k8s/` (db-secret → statefulset/service → domain-services → gateway → ingress) |

- One backend image serves every Python service (command differs per container).
- Ingress terminates at `alpha-gateway`; tailscale sidecar runs on gateway only.
- Run `psql "$DATABASE_URL" -f migrations/0XX_*.sql` in order after first boot
  (schema initializer also validates on startup).

---

## Security Notes

- Never deploy with the default `SECRET_KEY` (config raises at boot without it).
- CORS defaults to localhost only; override via `FINANCE_TRACKER_CORS_ORIGINS`.
- Internal services (8450–8455) are assumed network-private; expose only the gateway.
- Known stage-1 debts and their review triggers live in
  [`docs/maintenance/HONEY_DEBT.md`](docs/maintenance/HONEY_DEBT.md).

---

## Documentation Map

| Doc | Role |
|---|---|
| `services/` + `docker-compose.yml` | Current architecture (this file §Architecture) |
| [`docs/services/alpha-microservice.md`](docs/services/alpha-microservice.md) | Endpoint reference (legacy naming; valid through gateway) |
| [`docs/DATABASE_STRATEGY.md`](docs/DATABASE_STRATEGY.md) + `migrations/` | Persistence strategy & schema versions |
| [`docs/system/architecture.md`](docs/system/architecture.md) | Domain logic blueprint (CLI-era context) |
| [`docs/maintenance/HONEY_DEBT.md`](docs/maintenance/HONEY_DEBT.md) | Tech-debt ledger with triggers |
| [`docs/features/*.md`](docs/features) | Feature specs + n8n workflow JSONs |

---

> Finance Tracker Ecosystem - Zhvny
