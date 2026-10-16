Last Updated: 29-05-2026 (14:30)

# 🗺️ Finance Tracker: Master Strategic Blueprint (v10.2)

This document consolidates the roadmap, maintenance plans, and upcoming evolutionary phases for the Finance Tracker ecosystem.

---

## 🚩 1. Strategic Roadmap

### 1.1 Phase 1: Infrastructure Modernization (Done)
- **Target**: Stability & Concurrency.
- **Outcome**: Successful migration to **PostgreSQL**.

### 1.2 Phase 2: Predictive Core (The "Sniper" Update) (Done)
- **Target**: Mathematical Precision.
- **Outcome**: Transition from XGBClassifier to XGBRegressor for T+1 Price Forecasting.

### 1.3 Phase 3: Infrastructure Maintenance & Health (Done)
- **Target**: Reliability & Quality.
- **Outcome**:
    - **Health Checks**: Automated PostgreSQL/API/Profile verification in `health_check.py`.
    - **Testing**: Initialized pytest suite for core logic (e.g., Profile Quotas).
    - **Type Safety**: Enforced strict typing in CLI and Core Application layers.

### 1.4 Phase 4: UX & Real-time Integration (Done)
- **Target**: Profile Isolation & Dashboard Polish.
- **Outcome**:
    - **Profile Logic**: Implemented centralized profile switching in `config.py`.
    - **Business Report**: Created `BusinessReportService` for quarterly Excel generation.
    - **Dashboard**: Added 5-minute auto-refresh and Ticker Starring.
    - **Stability Audit**: Consolidated GUI components in `src/pages/` and verified multi-profile isolation with dynamic FX fallback.

### 1.5 Phase 5: Autonomous Intelligence (Agent Senate) (Done)
- **Task 5.1**: Multi-Agent Voting Engine (COMPLETED).
- **Task 5.2**: Butterfly Effect Correlation Engine (VERIFIED & INTEGRATED).
- **Task 5.3**: Gemini Sentiment Integration (COMPLETED).
- **Task 5.4**: Evaluation Engine & Dynamic Weighting (COMPLETED).
- **Task 11**: Dynamic DXY Divergence Tooltip (COMPLETED).

### 1.6 Phase 6: Evolutionary Intelligence (In Progress)
- **Task 6.1**: Whale Tracker & Profiler (Option 9 in CLI).
- **Task 6.2**: Model Evolution Engine.
- **Task 6.3**: Genetic Optimizer (Monthly Hyperparameter Tuning).

### 1.7 Phase 7: Cloud-Native K8s (Active)
- **Task 7.1**: Production Dockerization (Multi-Stage).
- **Task 7.2**: Kubernetes Manifests & Self-Healing.
- **Task 7.3**: Tailscale/Tunnel Secure Entry.

---

## 🛠️ 2. Phase 3: Infrastructure Improvements (Maintenance Plan)

**Goal:** Enhance system health monitoring, initialize testing suite, and enforce type safety.

### 2.1 Tasks
1. **Fix Corrupted Config**: Repair `packages/core/infrastructure/config.py` formatting (remove literal `\n` sequences).
2. **Enhance Health Check Script**: Add PostgreSQL connection check, external API checks (yfinance, FRED), and Profile integrity checks to `scripts/health_check.py`.
3. **Profile Domain Model**: Create Pydantic-based `Profile` model with quota logic (`requests_today`, `daily_limit`).
4. **Initialize Test Suite**: Set up `pytest` infrastructure in `tests/` with fixtures for profile isolation.
5. **Type Safety Refactor**: Apply strict type hints to `ProfileService` and `apps/cli/main.py`.

---

## 🧬 3. Phase 6: Advanced Evolution (Technical Spec)

**Status:** [INCOMPLETE / STALLED] - Integrity Audit (2026-05-08)

### 3.1 Tasks
- **6.1 Dr. Strange Monte Carlo Simulator**: 1,000 price paths based on ATR_R. Calculate "Probability of Ruin". *Initial implementation exists but ProcessPoolExecutor fails.*
- **6.2 Whale/Smart Money Volume Profiler**: Track `Volume / Average_Volume_20D`. Identify absorption logic. *Partial implementation.*
- **6.3 Evolving Sniper (Genetic Optimizer)**: Monthly cron job for `XGBRegressor` hyperparameter tuning. *Non-functional; audit revealed fabricated data.*

---

## ☁️ 4. Phase 7: Cloud-Native K8s (Technical Spec)

**Status:** Active Focus

### 4.1 Tasks
- **7.1 Production Dockerization**: Multi-stage Alpine image (~180MB).
- **7.2 Kubernetes Manifests**: Liveness/Readiness probes via `/health` (Postgres `SELECT 1`).
- **7.3 Tailscale/Tunnel**: Zero-Trust access via Tailscale sidecar.

### 4.2 Definition of Done
- [x] Size < 300MB.
- [x] K8s self-healing verified.
- [x] Secure Zero-Trust entry verified.
- [x] Database Persistence (PVC) verification (Verified 2026-05-29).
