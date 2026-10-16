# Alpha — Product Requirements Document (PRD) Master

**Version**: 1.0  
**Date**: 2026-09-10  
**Status**: DRAFT — awaiting review  
**Owner**: Zhvny  
**Audiences**: Engineering, Product, Handoff/Hiring, Investor/Demo

---

## 1. Executive Summary

Alpha is a local-first personal finance and investment intelligence platform that unifies expense tracking, FIFO portfolio accounting, OCR-based receipt ingestion, behavioral finance scoring, and AI-assisted market analysis in a single deployable stack. It runs as a Python/TypeScript microservice mesh behind a FastAPI gateway, exposing a Next.js web dashboard, an Electron desktop GUI, and a Textual TUI CLI.

Alpha is built for users who treat financial data as sensitive: it stores data primarily in a local PostgreSQL instance, supports multi-profile isolation for Personal and Business entities, and avoids mandatory cloud egress for core operations. Its differentiators are local-first architecture, ensemble OCR with learning-based categorization, institutional-grade FIFO investment accounting, and a regime-aware multi-agent market intelligence system.

The platform is in active development with a functional microservice runtime, production ML model artifacts, Kubernetes deployment manifests, and completed security hardening passes.

---

## 2. Problem / Solution / Market / Traction

### 2.1 Problem

Individuals and small business operators managing finances across multiple entities face four compounding frictions:

1. **Fragmented tooling**: Expense trackers, portfolio managers, tax preparers, and receipt scanners operate in silos. Data must be manually reconciled.
2. **Privacy/cloud lock-in**: Mainstream finance apps require cloud storage and broad data sharing. Users with sensitive transaction histories or compliance requirements have no viable alternative that matches feature depth.
3. **Manual data entry fatigue**: Even "smart" categorizers require user correction. Receipt scanning solutions are brittle and rarely learn per-user patterns.
4. **Disconnected insights**: Spending behavior, portfolio performance, and market outlook are analyzed in separate tools. Users cannot correlate behavioral discipline with investment outcomes.

### 2.2 Solution

Alpha replaces the fragmented stack with one coherent local-first system:

- **Unified ledger**: expenses, income, accounts, categories, budgets, recurring transactions, goals, forecasts, and net worth in one coherent model with multi-entity isolation.
- **Institutional-grade investments**: FIFO P/L, multi-asset support (stocks, crypto, gold), dynamic FX conversion, and allocation reporting.
- **Learning receipt capture**: ensemble OCR (Tesseract, EasyOCR, PaddleOCR) with majority voting and a fuzzy-match merchant map that improves per profile.
- **Behavioral coaching**: Financial Behavior Score (FBS), impulse/fragility metrics, and a Lust reward economy tied to discipline milestones.
- **Local market intelligence**: technical indicators, XGBoost "Sniper" models, a genetic hyperparameter optimizer, butterfly risk mapping, and a regime-aware 7-agent Senate that votes on market direction without sending data to third-party APIs.

### 2.3 Market

Target segments:

- **Privacy-first individual investors**: users who run local tools (Obsidian, self-hosted email) and want financial software that respects that posture.
- **Small business operators / side-business professionals**: need clean P&L separation, tax-ready outputs, and receipt capture without subscribing to QuickBooks-level complexity.
- **Power users / engineers**: want CLI speed, automation, and extensibility.

Adjacent whitespace: very few local-first finance tools offer both ledger depth and ML market intelligence in one package. YNAB, Lunch Money, and Copilot Money are cloud-first. Portfolio tracking tools (Folio, StockRockets) do not unify ledger + behavioral + ML. Alpha owns the intersection.

### 2.4 Traction

Current state signals product-market fit at hobbyist/prosumer level:

- Functional 6-service microservice runtime with gateway auto-discovery.
- Production model artifacts for 11 tickers plus integration test ticker.
- Deployed Kubernetes manifests, CI workflows, and security audit reports.
- Completed security hardening batch covering auth, session validation, credential storage, and anti-replay signing.
- Active test suites (Python + JS) with documented gate commands.

---

## 3. Vision & Strategy

### 3.1 Vision

Build the most trusted local-first financial command center by combining accurate accounting, disciplined privacy, and actionable intelligence.

### 3.2 Strategic Pillars

1. **Local-first, cloud-optional**: core operations never depend on external APIs; optional integrations are opt-in.
2. **One source of truth**: shared domain engines power every interface (web, GUI, CLI) so behavior is identical regardless of entry point.
3. **Privacy-preserving intelligence**: ML inference, OCR, and market analysis run in the user's environment.
4. **Institutional precision**: FIFO accounting, regime-aware ensemble voting, and auditable model lineages.

### 3.3 Competitive Positioning

| Dimension | Alpha | Cloud-first PFM | Portfolio-only tools |
|---|---|---|---|
| Local-first | Yes | No | Rarely |
| Unified ledger + investments | Yes | Partial | No |
| Receipt OCR with learning | Yes | Rare | No |
| Behavioral scoring | Yes | Basic | No |
| Local ML market intel | Yes | No | Rare |
| Multi-entity isolation | Yes | Partial | No |

### 3.4 Go-to-Market Strategy

- **Phase 1**: self-hosted / local-first community (GitHub, HN, privacy forums).
- **Phase 2**: packaged Docker image and one-click Kubernetes manifests.
- **Phase 3**: optional sync layer (e2e encrypted, user-controlled keys) for multi-device convenience without compromising architecture.

---

## 4. Personas & User Journeys

### 4.1 Personas

**P1 — The Engineer / Power User**  
- Proficiency: high  
- Primary goal: automate everything, audit internals, extend via CLI/scripts  
- Pain points: opaque UIs, forced cloud sync, limited scripting access  
- Success criteria: full CLI coverage, local DB access, webhook/API access

**P2 — The Personal Investor**  
- Proficiency: medium  
- Primary goal: understand portfolio health, reduce behavioral mistakes, get market context  
- Pain points: tools that conflate personal spending with investment tracking, lack of behavioral feedback  
- Success criteria: clean P/L view, FBS score with actionable tips, market regime indicator

**P3 — The Small Business Operator**  
- Proficiency: medium  
- Primary goal: separate business and personal finances, generate tax-ready reports, capture receipts efficiently  
- Pain points: manual categorization at tax time, blurred entity boundaries  
- Success criteria: per-entity reports, P&L export, receipt-to-category flow

**P4 — The Onboarding Engineer**  
- Proficiency: high (but new to Alpha)  
- Primary goal: understand architecture, make a change, deploy  
- Pain points: large unfamiliar repo, unclear conventions, legacy vs canonical entry points  
- Success criteria: AGENTS.md + PRD + architecture doc enable first deploy under 2 hours

### 4.2 User Journeys

**J1 — Daily Capture**  
Trigger: user makes a purchase or receives income.  
Steps:  
1. User opens web app or CLI.  
2. Enters amount, category, notes; or scans receipt.  
3. If receipt: OCR ensemble votes, merchant map suggests category, user confirms.  
4. Ledger writes transaction; budget bar updates; FBS score recalculates.  
Success: captured in <30 seconds, correctly categorized, no context switch.

**J2 — Portfolio Review**  
Trigger: user wants to understand current investment health.  
Steps:  
1. User opens dashboard.  
2. Sees allocation, FIFO realized/unrealized P/L, top positions.  
3. Clicks into a ticker to see sniper signals and senate vote breakdown.  
4. Exports report if needed.  
Success: full picture visible in one view, drill-down available, export works offline.

**J3 — Receipt Ingestion**  
Trigger: user has a physical or digital receipt.  
Steps:  
1. User uploads receipt image or PDF.  
2. OCR ensemble processes; field-level consensus is computed.  
3. Low-confidence fields are flagged for manual verification.  
4. Merchant/category suggestion is presented; user accepts or overrides.  
5. Merchant map updates fuzzy-match rules for future receipts.  
Success: majority of receipts auto-categorized correctly after 3–5 confirmations.

**J4 — Market Intelligence**  
Trigger: user wants to decide whether to add/reduce a position.  
Steps:  
1. User opens market module.  
2. Views technical indicators, sniper model confidence, regime state.  
3. Reviews Senate vote breakdown by agent.  
4. Optionally triggers a fresh optimizer run.  
Success: actionable signal presented with confidence and caveats, no manual data export.

**J5 — Behavioral Check**  
Trigger: weekly or post-expense-spike review.  
Steps:  
1. User opens behavioral module.  
2. Reviews FBS score, impulse events, fragility trend.  
3. Sees suggested actions (spending freeze, category caps).  
4. Lust rewards update if milestones hit.  
Success: one clear next action, not a data dump.

**J6 — Operational Task**  
Trigger: deploy, debug, or maintain Alpha.  
Steps:  
1. Engineer reads AGENTS.md + PRD for conventions.  
2. Edits service or UI; runs pytest and ruff.  
3. Deploys via Docker or kubectl.  
4. Verifies health endpoints and tail logs.  
Success: deploy completes with zero manual config drift.

---

## 5. Features & Scope

### 5.1 In Scope

**Ledger & Finance**
- Expense and income tracking with accounts, categories, and tags
- Budgets with configurable thresholds and alerts
- Recurring transaction detection and management
- Goals (savings, debt payoff) with progress tracking
- Forecasts: projected balances based on recurring and historical patterns
- Net worth calculation with asset/liability rollup
- Natural-language finance queries
- Tax engine for Indonesian PPh 21 brackets and PTKP logic

**Investments**
- FIFO position tracking for stocks, crypto, and gold
- Realized and unrealized P/L with lot-level audit
- Dynamic FX conversion (USD/IDR tiered resolution)
- Portfolio allocation and drift reporting
- Integration with yfinance and CoinGecko for price feeds

**Market Intelligence**
- Technical indicators (RSI, DCDS, MRZG, Bollinger, MA)
- XGBoost Sniper models with monthly auto-regeneration via genetic optimizer
- Butterfly risk map and regime-aware Agent Senate (7 agents)
- Market scheduler and background evaluation engine

**Receipts & OCR**
- Multi-engine OCR ensemble with majority voting
- Merchant map with fuzzy-match learning
- Mandatory manual verification for low-confidence results

**Behavioral & Engagement**
- Financial Behavior Score (FBS): impulse and fragility scoring
- Lust reward economy with milestone-based unlocks
- Behavioral index and trend tracking

**Platform**
- Authentication with session validation and fail-closed guards
- Multi-profile isolation (Personal and Business)
- Logs, notifications, WebSocket events, Telegram bot
- Health checks and readiness probes per service

**Interfaces**
- Web dashboard (Next.js + Tailwind)
- Desktop GUI (Electron + React)
- CLI (Textual TUI)
- Gateway API with OpenAPI-discovered routing

### 5.2 Out of Scope

- Mandatory cloud sync or hosted SaaS
- Non-financial CRM or accounting automation beyond receipt capture
- Mobile-native apps outside web/Electron wrappers
- Financial advisor matching or human advisory marketplace

### 5.3 Prioritization

| Priority | Theme |
|---|---|
| P0 | Ledger correctness, auth, multi-profile isolation, gateway stability |
| P1 | Receipt OCR, portfolio FIFO, web dashboard parity |
| P2 | Market intelligence, behavioral scoring, CLI feature completeness |
| P3 | Electron GUI refinement, Telegram bot, advanced analytics |

---

## 6. Architecture & Data Flow

### 6.1 High-Level Topology

```
 browser/GUI/CLI ─────► gateway :8444
                          │
         ┌────────┬───────┼───────┬───────────┬───────────┐
         ▼        ▼       ▼       ▼           ▼           ▼
    platform  ledger  portfolio  market    insights   engagement
      :8450    :8451    :8452    :8453      :8454       :8455
```

> Tujuh container: `gateway` (`:8444`) + enam domain service (`:8450`–`:8455`).
> Narasi runtime selengkapnya ada di `ARCHITECTURE.md`; rencana & utang teknis di
> `ROADMAP.md`. Port kanonik: `docs/PORTS.md`.

### 6.2 Service Responsibilities

**Gateway (8444)**  
Public HTTPS entry. Exact-route reverse proxy built from each service's mounted OpenAPI spec. WebSocket proxy for `/ws/*`. Unified serving mode mounts compiled web assets.

**Platform (8450)**  
Authentication, profile management, logs, notifications, Telegram bot/webhook, `/api/config`.

**Ledger (8451)**  
Expenses, income, transactions/accounts/categories, budget, recurring, confirmations, safe-to-spend, forecast, net worth, goals, natural-language finance.

**Portfolio (8452)**  
Investments (FIFO), reports, dashboard aggregation.

**Market (8453)**  
Stocks, ML stock inference, genetic optimizer, butterfly risk map, Agent Senate, market scheduler.

**Insights (8454)**  
Receipt OCR ensemble, merchant map, AI advisor, analytics, anomalies, health score.

**Engagement (8455)**  
Behavioral finance (FBS), reward economy.

### 6.3 Data Flow

1. Client sends HTTPS request to gateway.
2. Gateway matches route from OpenAPI-discovered table and proxies to the owning service.
3. Service validates auth/profile, executes domain logic, persists to PostgreSQL.
4. For async work (OCR, optimizer, senate evaluation), service enqueues to background scheduler.
5. WebSocket events stream back to subscribed clients through the gateway.
6. CLI can bypass the gateway and write to local stores for fully offline operation.

### 6.4 Persistence Model

- Shared PostgreSQL database in stage-1 deployment.
- Per-profile directory isolation for local SQLite stores and artifacts.
- Row-Level Security enforced at repository layer to prevent cross-profile leakage.
- Migrations owned by a single domain service per schema object.

### 6.5 Service Runtime

All services run from one backend Docker image; command differs per container. This reduces image sprawl while keeping domain boundaries intact at the process level.

---

## 7. Non-Functional Requirements

### 7.1 Privacy

- Core operations must function without external API calls.
- No mandatory telemetry or analytics egress.
- Profile directories are physically isolated; cross-profile reads are blocked at the repository layer.

### 7.2 Security

- **Authentication**: fail-closed session validation; PBKDF2 with 600k iterations.
- **Authorization**: internal service ports (8450–8455) are network-private; only the gateway is exposed.
- **Anti-replay**: HMAC over method|path|timestamp|body for state-changing requests.
- **Rate limiting**: XFF-aware with default-deny posture for unlisted IPs.
- **Secrets**: SECRET_KEY required at boot; no default credentials in production.
- **CORS**: localhost-only by default; explicit allowlist override via env.

### 7.3 Reliability

- Health endpoints: `/health` (liveness), `/health/ready` (DB readiness), `/info` (authenticated metadata).
- Gateway aggregate health at `GET :8444/health`.
- Structured logs rotate to `logs/<service-name>.log`.
- Cross-service smoke tests gate merges.

### 7.4 Performance

- Gateway routing overhead <1 ms per request.
- OCR ensemble bounded by majority voting with timeout fallback.
- ML inference runs asynchronously; results stream via WebSocket or polling.
- Frontend lazy-loads route chunks; charts hydrate on demand.

### 7.5 Maintainability

- Single repo, shared domain engines, clean architecture boundaries.
- Conventional commits; small, reviewable diffs.
- Agent contract in `AGENTS.md` enforces plan-approve-execute workflow.

---

## 8. Roadmap & Milestones

### Q3 2026 — Stabilize Core

- Complete microservice split: compose/k8s alignment, WebSocket proxy, cross-service smoke tests.
- Finalize security hardening: anti-replay, rate limiter, IP policy, remove legacy default credentials.
- Legacy monolith (`apps/api/main.py`) deprecated but functional; routing fully through gateway.

### Q4 2026 — Harden Platform Primitives

- Profile isolation audit: verify no cross-profile reads in any service.
- Observability stack: Prometheus metrics, Loki logs, Jaeger traces, alert rules in k8s/.
- Backup strategy and on-call rotation runbooks.

### Q1 2027 — Intelligence Expansion

- Extend sniper model coverage to top-20 user-held tickers.
- Improve OCR coverage for Indonesian receipt formats.
- Behavioral coaching: action recommendations tied to FBS thresholds.

### Q2 2027 — Distribution & Sync

- Packaged Docker image with one-click compose.
- Optional e2e-encrypted sync layer with user-held keys.
- Public demo environment for investor/hiring reviews.

---

## 9. OKRs & Success Metrics

### O1: Core Flow Reliability

- KR1: Ledger write succeeds >99.5% in CI smoke runs.
- KR2: OCR intake completes without manual verification for >80% of receipts after 5 confirmations.
- KR3: Portfolio refresh end-to-end p95 <2s in local topology.

### O2: Privacy & Security Posture

- KR1: Zero default-credential findings in quarterly audit.
- KR2: 100% of external-facing paths require authenticated session.
- KR3: Anti-replay signing enabled for all state-changing gateway routes.

### O3: Insight Velocity

- KR1: Sniper model monthly regeneration completes without manual intervention for top-10 tickers.
- KR2: Genetic optimizer produces a new candidate model each run with lower MAE than prior baseline.
- KR3: Senate evaluation processes T+24h outcomes and updates weights within 6 hours.

### O4: Onboarding Efficiency

- KR1: New engineer reaches first service deploy in under 2 hours using `AGENTS.md` + PRD.
- KR2: PRD master is referenced in >80% of new-issue onboarding checklists.

---

## 10. Technical Debt & Risks

### 10.1 Debt Register

| ID | Debt | Severity | Trigger to Fix |
|---|---|---|---|
| D1 | Shared PostgreSQL database across services | High | When any service needs independent scaling or schema isolation |
| D2 | Shared backend image for all services | Medium | When service-specific runtime dependencies diverge |
| D3 | Compose and k8s configs drifted from services/* runtime | High | Before first production deployment |
| D4 | Legacy monolith wrapper (`apps/api/main.py`, `run.bat`) still referenced | Low | When gateway/runner migration is complete |
| D5 | Windows BOM in config writes | Low | When config tooling moves to cross-platform stdlib paths |
| D6 | Flaky pre-existing optimizer test (`test_genetic_status`) | Medium | When genetic optimizer is modified |

### 10.2 Risks

- **Runtime split regression**: breaking microservice boundaries can introduce silent data inconsistencies. Mitigation: cross-service smoke tests and shared contract tests.
- **Local-first expectation gap**: users may expect cloud backup. Mitigation: explicit docs and optional sync with clear tradeoffs.
- **ML dependency drift**: yfinance and XGBoost APIs change. Mitigation: pin dependencies and monthly regression tests against production models.
- **OCR coverage limits**: ensemble does not cover all receipt formats. Mitigation: manual verification flow + merchant map learning.

---

## 11. API / Interface Summary

### 11.1 Public Surface

- **Gateway HTTPS**: `:8444`
- **WebSocket**: `/ws/*` through gateway
- **Web dashboard**: served by gateway in unified-serving mode

### 11.2 Service Contracts

Each service mounts only its domain routers under `services/<name>/main.py`. The gateway discovers routes from each service's `/openapi.json`. Adding a router requires zero gateway changes.

| Service | Port | Health | Ready | Info |
|---|---|---|---|---|
| platform | 8450 | `/health` | `/health/ready` | `/info` |
| ledger | 8451 | `/health` | `/health/ready` | `/info` |
| portfolio | 8452 | `/health` | `/health/ready` | `/info` |
| market | 8453 | `/health` | `/health/ready` | `/info` |
| insights | 8454 | `/health` | `/health/ready` | `/info` |
| engagement | 8455 | `/health` | `/health/ready` | `/info` |

Gateway aggregate: `GET :8444/health`

### 11.3 Authentication

- Session-based auth with server-side session validation.
- Fail-closed on invalid or expired sessions.
- Test-only auth endpoint exists for CI/audit tooling in non-production builds.

### 11.4 Rate Limiting

- XFF-aware rate limiter planned.
- Default-deny IP whitelist planned.
- Internal services assumed network-private; only gateway is externally reachable.

### 11.5 Client Interfaces

| Interface | Tech | Offline Capable |
|---|---|---|
| Web dashboard | Next.js + Tailwind | Partial (reads cached gateway state) |
| Desktop GUI | Electron + React | No |
| CLI | Textual TUI | Yes (local stores) |

---

## 12. References

| Document | Role | Path |
|---|---|---|
| Agent contract | Architecture snapshot, conventions, commands | `AGENTS.md` |
| Runtime status | Current blockers and tooling | `STATE.md` |
| Architecture blueprint | Domain logic and tiers | `docs/system/architecture.md` |
| Product manual | User-facing capabilities | `docs/system/product-manual.md` |
| API reference | Endpoint documentation | `docs/API.md` |
| User manual | Operational guidance | `docs/UM.md` |
| Technical plan | Implementation notes | `docs/TP.md` |
| Database strategy | Persistence and migrations | `docs/DATABASE_STRATEGY.md` |
| Tech-debt ledger | Review-triggered debt | `docs/maintenance/HONEY_DEBT.md` |
| Security audit | Hardening results | `docs/audits/AUDIT-security-full-2026-08-23.md` |
| Quality audit | Performance and test results | `docs/audits/AUDIT-quality-perf-2026-08-23.md` |
| UI/UX audit design | UI quality gate design | `docs/superpowers/specs/2026-09-05-ui-audit-design.md` |
| Architecture narrative | Runtime topology & shared libraries | `ARCHITECTURE.md` |
| Roadmap | Fase, utang teknis & trigger | `ROADMAP.md` |
| Changelog | Riwayat perubahan (Keep a Changelog) | `CHANGELOG.md` |
| Contributing | Alur kerja & gate kualitas | `CONTRIBUTING.md` |
| Project map | Inventaris area, kanonik vs legacy (generated) | `docs/PROJECT_MAP.md` |
| Status | Snapshot git state, known-broken, kandidat karantina (generated) | `docs/STATUS.md` |
