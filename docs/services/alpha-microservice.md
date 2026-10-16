# ⚡ Alpha Microservice Architecture & API Reference

> **STATUS: legacy monolith.** Runtime sekarang = microservice topology di
> `services/` (gateway :8444 + platform/ledger/portfolio/market/insights/engagement).
> Endpoint reference di bawah masih valid — semua route kini dilayani lewat gateway.
> Launcher lama `run-api.bat` tidak ada; monolith dijalankan lewat
> `packages/api/api_server.py` (wrapper `apps/api/main.py`) atau `run.bat`.

`apps/api/` is the Single Source of Truth (SSOT) container for the **Alpha Microservice API**.

---

## 🏛️ 1. Overview & Key Capabilities

The **Alpha Microservice** encapsulates the entire core backend domain logic, financial computation engines, stock analytics & ML inferencing, and database access layer into a standalone, modular microservice built with **FastAPI**.

### Microservice Features:
- **Clean Architecture**: Decoupled domain routers, repository persistence, and application use-cases.
- **Resilient Startup**: Schema validation (`SchemaInitializer`) and automatic Prisma ORM connection with fallback handling.
- **Background Automation**: Market scheduler (`MarketScheduler`) for market data synchronization and ML model evaluation.
- **Health & Diagnostics**: Full Kubernetes/Docker readiness (`/health/ready`) and liveness (`/health/live`) probes.
- **Ensemble Domain Engines**: OCR receipt ensemble, Stock ML (XGBoost), Genetic Optimizer, Agent Senate voting, and Behavioral Finance.

---

## 🚀 2. Quick Start & Execution

### Standalone Local Runner
```cmd
run-api.bat
```
Or directly via Python:
```cmd
cd apps/api
python main.py
```

### Environment Configuration (`apps/api/config.py` / `.env`)
| Variable | Default | Description |
| :--- | :--- | :--- |
| `FINANCE_TRACKER_PORT` / `PORT` | `8444` | Microservice listening port |
| `HOST` | `0.0.0.0` | Host binding interface |
| `DATABASE_URL` | `postgresql://...` | Primary PostgreSQL database connection |
| `SECRET_KEY` | `alpha-microservice...` | Security signing key |

---

## 🔌 3. Endpoints & API Topology

### Health & Monitoring
- `GET /health` — Full diagnostic health check (DB connection, uptime, version).
- `GET /health/live` — Lightweight liveness probe.
- `GET /health/ready` — Database readiness probe.
- `GET /info` / `GET /version` — Operational metadata.

### Core Domain Routers (22 Modules Registered)
- `GET /api/dashboard` & `GET /api/dashboard/metadata` — Financial dashboard aggregator.
- `GET /api/expenses` & `POST /api/expenses` — Expense management.
- `GET /api/income` & `POST /api/income` — Income tracking & tax estimations.
- `GET /api/investments` — Investment portfolio & FIFO calculation.
- `POST /api/receipt/scan` — OCR receipt ensemble reader.
- `GET /api/stocks` & `GET /api/ml_stocks` — Technical analysis & XGBoost predictions.
- `GET /api/senate` — Regime-aware Agent Senate multi-agent voting.
- `GET /api/behavioral` — Behavioral Finance Index (FBS).
- `POST /telegram/webhook` — Telegram bot automation webhook.

---

## 🐳 4. Docker & Production Containerization

Run as a containerized microservice via Docker Compose:
```bash
docker compose up -d api
```
Production compose definition:
```yaml
api:
  build:
    context: .
    dockerfile: apps/api/Dockerfile
    target: production
  container_name: finance-tracker-api
  ports:
    - "8444:8444"
```
