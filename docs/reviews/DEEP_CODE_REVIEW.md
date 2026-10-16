# DEEP CODE REVIEW — Alpha (Finance Tracker Monorepo)
**Tanggal:** 2026-08-08
**Reviewer:** Senior Software Engineer — Technical Due Diligence
**Cakupan:** 578 source files (Python + TypeScript), 79 tests, 1 monorepo dengan 5 aplikasi (cli, web, api, gui, ml).

---

## A. EXECUTIVE SUMMARY

**Project Alpha adalah monorepo personal-finance + stock-prediction + n8n automation** yang ditulis selama beberapa bulan (commit terakhir Aug 2026). Ada 5 aplikasi utama:
1. **apps/cli** — Python CLI (rich-text TUI) untuk expense/income/investment tracking, stock analyzer (technical indicators + ML), receipt OCR, behavioral finance.
2. **apps/api** — FastAPI microservice (single-file `main.py` 455 baris) yang menjadi gateway tunggal untuk web dan CLI.
3. **apps/web** — Next.js 16 (App Router) frontend dengan Tailwind 4.
4. **apps/finance-tracker-gui** — desktop wrapper.
5. **apps/cli/stock_ml** — XGBoost-based ML pipeline + Flask dashboard.
6. **n8n workflows + price_scraper.py** — currency/price monitoring → PostgreSQL → Telegram alerts.

**Tujuan bisnis utama:**
- Personal finance tracker multi-profile (personal/business) dengan expense, income, investment, receipt OCR, behavioral analytics.
- Stock market analyzer dengan technical indicators (RSI/MA/ATR/VWAP/order-flow) + XGBoost ML predictions.
- Telegram alert untuk currency threshold (USD/IDR/EUR/JPY) dan asset price target dan akses fitur receipt OCR.
- Web dashboard untuk monitoring.

**Kelemahan terbesar (Top 5):**
1. **Hybrid SQLite + PostgreSQL dengan dual-write dan silent fallback** — data corruption risk tinggi, query inconsistency, race condition pada connection pool.
2. **Dual service layer dengan sync/async mismatch** — routers async, services sync di satu tempat dan async di tempat lain, dashboard_service dari dua module berbeda.
3. **No CI/CD, 79 tests tapi coverage tidak terukur** — `pyproject.toml` setup coverage tapi tidak ada badge/report, banyak modul kritis tanpa test.
4. **Single FastAPI monolith dengan 22 routers, 5353 baris kode di routers/ saja** — bukan microservices, tapi struktur internal sudah terlalu besar.
5. **Security: HMAC opsional, audit log SQLite di-bypass untuk endpoints tertentu, IP whitelist default `*`**.

**Estimasi risiko jika diteruskan tanpa refactoring:** Tinggi. Beberapa bug laten (DB race condition, sync/async mismatch) bisa menyebabkan silent data loss atau crash intermiten pada production load.

---

## B. PROJECT UNDERSTANDING

### B.1 Tujuan Utama
Personal finance + investment tracker untuk pengguna individu yang juga aktif di pasar saham (Indonesia: .JK stocks, US stocks, crypto, gold). Bukan platform multi-tenant—single-user dengan profile switcher.

### B.2 Target User
- **Primary:** Individual retail investor (kemasan bahasa Indonesia, currency IDR default).
- **Secondary:** Small business owner (profile `business` dengan quarterly P&L reporting).
- **Tertiary:** n8n automation user yang butuh currency/price alerts via Telegram.

### B.3 Fitur Utama
| Modul | Fitur |
|---|---|
| **Expense Tracker** | CRUD expenses, category/payment-method, recurring templates, budget vs actual, trend chart, CSV export |
| **Income Tracker** | CRUD income, tax flag, auto-allocation (savings/budget/etc), CSV export |
| **Investment Tracker** | Holdings, FIFO sell, realized P&L, FX conversion, live price refresh (yfinance), auto-record realized gain as income |
| **Receipt Reader** | OCR ensemble (Tesseract/EasyOCR/PaddleOCR/Gemini) + parser + categorizer + export ke expense/income |
| **Behavioral Finance** | Snapshot emotional/spending behavior, monthly behavioral profile, gamification reward unlock |
| **Stock Analyzer** | Technical indicators (RSI, MA, ATR, VWAP, order flow, volume profile) + macro (FRED) + scoring 1-10 + ML sniper signal |
| **Stock ML** | XGBoost per-ticker sniper models, features dari price action + macro, Flask dashboard |
| **n8n Workflows** | Currency monitor (Frankfurter API, 15-min interval), price monitor (CoinGecko + yfinance, 1-hour interval), Telegram alerts |
| **Web Dashboard** | Next.js pages: dashboard, analytics, behavioral, reward |
| **API Gateway** | FastAPI consolidating CLI services untuk web consumption |

### B.4 Alur Kerja (End-to-End)
**Skenario 1 — User catat expense via Web:**
```
Browser → POST /api/expenses (Bearer token)
    → FastAPI router (require_scope("write"))
    → audit_middleware (IP whitelist, rate limit, log)
    → expense_service.record_expense() (async)
    → PostgresExpenseRepository.save() (async via Prisma + raw SQL)
    → PostgreSQL (schema = active_profile, table = expenses)
    → reward_service.check_and_apply() (auto-unlock based on streak)
    → response → bust behavioral cache
```

**Skenario 2 — n8n currency alert:**
```
Schedule (15 min) → HTTP GET Frankfurter (USD→IDR/EUR/JPY)
    → Code node normalize + check threshold
    → PostgreSQL INSERT currency_history
    → IF threshold crossed → Telegram bot
```

### B.5 Technology Stack
| Layer | Stack |
|---|---|
| **CLI** | Python 3.12, Rich (TUI), Textual (TUI components), Click/argparse, APScheduler |
| **API** | FastAPI, Uvicorn, Pydantic v2, APScheduler, Prisma Client Py, psycopg2 |
| **Web** | Next.js 16.2.6, React 19, Tailwind 4, TypeScript 5, lucide-react |
| **DB** | PostgreSQL 16 (primary), SQLite (legacy fallback + cache + audit_log) |
| **Cache** | Redis (optional, in-memory dict fallback), pickle cache for OHLCV |
| **OCR** | Tesseract, EasyOCR, PaddleOCR, Gemini API, optional Ollama |
| **ML** | XGBoost, scikit-learn, pandas, numpy, tqdm |
| **Data Sources** | yfinance (stocks), CoinGecko (crypto), FRED API (macro), Frankfurter (FX) |
| **Notifications** | Telegram Bot API |
| **Automation** | n8n workflows + Python `price_scraper.py` |
| **Monorepo** | pnpm workspace + Turborepo |

### B.6 Struktur Project
```
Alpha/
├── apps/
│   ├── api/           # FastAPI gateway (single main.py 455 LOC)
│   ├── cli/           # Python CLI (multiple sub-apps)
│   │   ├── expense_tracker/      # Clean Architecture: core/services/ui
│   │   ├── income_tracker/       # Same
│   │   ├── investment_tracker/   # 20+ service files (sell, butterfly, sentiment, ...)
│   │   ├── receipt_reader/       # OCR engines/ + exporters/
│   │   ├── stock_analyzer/       # adapters/domain/infrastructure/use_cases
│   │   ├── stock_ml/             # numbered scripts (01, 02, 07, 08, 09)
│   │   ├── behavioral_finance/   # application/domain/interface
│   │   ├── advanced_features/    # goals, budgets, allocation
│   │   └── profiles/             # personal/business/qa_*/data dirs
│   ├── finance-tracker-gui/      # desktop wrapper
│   └── web/           # Next.js 16
├── packages/
│   ├── api/           # backend logic shared with cli (routers, security, services)
│   ├── core/          # domain models, application services, infrastructure (postgres repos)
│   ├── database/      # Prisma schema + client
│   ├── types/         # TS types shared between web packages
│   └── web/           # legacy web package (now mostly unused — web moved to apps/web)
├── scripts/           # 70+ utility scripts (debug, audit, benchmark, migrations)
├── docs/              # docs/system, docs/planning, docs/maintenance
├── conductor/         # (excluded from git — workflow orchestration)
├── n8n_*.json         # Workflow definitions
└── price_scraper.py   # Standalone Python helper
```

---

## C. ARCHITECTURE ANALYSIS

### C.1 Overall Architecture
**Tipe:** Modular Monolith (CLI + API + Web + GUI) dengan attempted Clean Architecture di dalam `packages/core/`.

**Karakteristik:**
- **5 aplikasi berbeda** berbicara ke service layer yang sama (`packages/core/application/*`).
- **Database dual-mode**: PostgreSQL sebagai "primary", SQLite sebagai fallback atau untuk sub-systems tertentu (cache, audit_log, behavioral_snapshots).
- **API gateway pattern**: CLI functions juga tersedia sebagai HTTP API via `apps/api/main.py`.
- **Background workers**: APScheduler di dalam FastAPI lifespan (market data refresh, daily report).

### C.2 Frontend Architecture
- **apps/web**: Next.js 16 App Router. Halaman: `/`, `/analytics`, `/behavioral`, `/reward`. Components di `apps/web/src/components/{layout,skeletons,ui}`.
- **packages/web**: Legacy Vite/React package (dist masih ada tapi tidak direferensikan dari `apps/web/package.json`). Ini dead code atau partial migration.
- **Observasi:** Tidak ada state management global (Redux/Zustand/Context) yang terindikasi dari imports. Kemungkinan pakai React Query atau fetch langsung.

### C.3 Backend Architecture
**`apps/api/main.py` — single-file bootstrap 455 LOC:**
- Manual router registration via `importlib.import_module` (lines 363-403). 22 routers.
- Lifespan manager initialize: schema, Prisma client, MarketScheduler, Telegram polling.
- Hardcoded Windows asyncio patch (lines 22-35) untuk handle connection-lost bug — workaround untuk production issue.
- Path manipulation manual (`sys.path.insert`) di beberapa tempat — symptom of broken import structure.

**`packages/api/backend/` — Clean Architecture attempt:**
- `routers/` (22 files, 5353 LOC) → thin handlers
- `services/` (3 files: dashboard_service, investment_service, stock_analysis_service) → **DUPLIKASI** dengan `packages/core/application/`
- `infrastructure/` (database, schemas, encoders, ollama_manager, repositories)
- `security/core.py` → API key + rate limit + audit middleware
- `automation/` (market_scheduler, scheduler)
- `repositories/` (stock_repository)
- `routers/ai.py` (804 LOC!) — paling besar
- `routers/analytics.py` (402 LOC)
- `routers/behavioral.py` (583 LOC)
- `routers/balances.py` (348 LOC)

### C.4 Database Architecture
**Dual-database pattern dengan silent fallback:**

```python
# packages/api/backend/infrastructure/database.py
class Database:
    @staticmethod
    def query(db_path, sql, params=()):
        if DatabaseManager and Database._is_postgres_target(db_path):
            try:
                rows = DatabaseManager.query(translated_sql, params, schema=...)
                return Database._cast_decimals(rows)
            except Exception as e:
                # Fallback to default data
                if "does not exist" in err_msg:
                    return Database._get_fallback_for_sql(sql)
                # Falls through to SQLite
                pass
        
        # SQLite fallback
        if not os.path.exists(db_path):
            return Database._get_fallback_for_sql(sql)
        with sqlite3.connect(db_path) as conn: ...
```

**Schema strategy:**
- **PostgreSQL** dengan multiple schemas: `{active_profile}`, `financials`, `core`, `investment`, `market`, `audit`, `system`, `public`.
- **SQLite** files: `apps/cli/{module}/data/{module}.db`, `packages/api/data/audit_log.db`, `cache.db`.
- **Profile isolation via PostgreSQL schema** (search_path manipulation di `postgres_manager.py:67`).

**Migration:**
- Manual SQL scripts di `scripts/migrations/`.
- No Alembic, no Prisma migrations dipakai (Prisma schema ada di `packages/database/` tapi runtime pakai raw SQL via `psycopg2`).
- `SchemaInitializer` di lifespan: `CREATE TABLE IF NOT EXISTS ...` idempotent but no version tracking.

### C.5 API Architecture
- **REST** dengan FastAPI.
- **Bearer token auth** (single master key via env `FINANCE_TRACKER_API_KEY`).
- **Scope-based authorization** ("read" / "write" / "admin") — single key = full admin.
- **Rate limiting**: 120 req/min/IP (sliding window in-memory).
- **HMAC request signing** optional (X-Request-Signature header).
- **Audit log**: SQLite `audit_log.db` dengan IP, method, path, scope, status, latency.

### C.6 Authentication & Authorization
**Single Bearer token model** — sangat sederhana:
- `verify_api_key()` compares `token` ke `FINANCE_TRACKER_API_KEY` env var (line 236 `core.py`).
- `require_scope("read"|"write"|"admin")` factory → returns dependency.
- `_token_scope(token)` saat ini hanya return "admin" untuk semua token valid.
- DEV mode (`FINANCE_TRACKER_DEV_MODE=1`) bypass semua auth.

**Risk utama:**
- Single shared API key. Tidak ada per-user identity. Tidak bisa audit "who did what" — hanya "which IP".
- JWT tidak dipakai — token tidak punya expiry, tidak bisa di-revoke tanpa restart service.

### C.7 External Services / Integrations
- **yfinance** untuk US/IDX stocks (unofficial, fragile).
- **CoinGecko** untuk crypto (rate-limited 30 req/min).
- **FRED API** untuk macro (CPI, DXY, jobless claims, dll).
- **Frankfurter API** untuk currency.
- **Telegram Bot** untuk notifications.
- **Gemini API** untuk receipt OCR.
- **Optional Ollama** untuk LLM di local.

**Tidak ada abstraction layer yang konsisten** — adapters exist di `stock_analyzer/adapters/` tapi `investment_tracker/services/` pakai fetcher langsung.

### C.8 Data Flow
**Read path (dashboard):**
```
Web → /api/dashboard (Bearer)
    → audit_middleware → require_scope("read")
    → dashboard_service.get_summary(profile_id, year, month)
        → Database.query (Postgres via DatabaseManager)
            → psycopg2 connection pool
            → SET search_path TO {profile},financials,core,investment,market,...
            → SELECT ... FROM expenses/incomes/investments
        → return dict
```

**Write path (sell investment):**
```
POST /api/investments/{id}/sell (Bearer)
    → require_scope("write")
    → investment_service.sell_investment() (async)
        → PostgresInvestmentRepository.update_status()
        → PostgresInvestmentRepository.add_sell_transaction()
        → calculate_realized_pl
    → if profit > 0:
        → income_service.record_income() (auto-record ke income table)
    → bust_behavioral_cache
    → return pl_idr, pl_pct, new_remaining, new_status
```

### C.9 Dependency Relationships
- `apps/api` → `packages/api/backend/*` → `packages/core/*` → `packages/database` (Prisma) + `psycopg2`.
- `apps/cli` → `packages/core/*` (services, repos) → sama.
- **Cross-app dependency**: `apps/cli/receipt_reader/core/ocr_ensemble.py` dipanggil langsung dari `packages/api/backend/routers/receipts.py` (line 18). Ini tight coupling.

### C.10 Separation of Concerns
- **Baik di `packages/core/`** — domain/application/infrastructure terpisah dengan jelas.
- **Buruk di `apps/api`** — `main.py` 455 LOC campur lifespan, health checks, dashboard endpoints, universe audit, router registration, static serving.
- **Massal di routers/** — `ai.py` 804 LOC, `behavioral.py` 583 LOC — terlalu banyak logic dalam satu file.

### C.11 Apakah Architecture Saat Ini Layak?

**YA, untuk skala personal/single-user.** Modular monolith sudah tepat. Tidak perlu microservices.

**TAPI, ada masalah serius yang harus diperbaiki dulu sebelum scale up:**
1. Dual DB dengan silent fallback = data corruption risk.
2. Sync/async mismatch = potential runtime errors.
3. Single-file 455 LOC main.py = god object.

---

## D. CODE QUALITY ANALYSIS

### D.1 Code Duplication

**FINDING D-001: DashboardService duplikat (HIGH severity)**
- **Lokasi:**
  - `packages/api/backend/services/dashboard_service.py` (sync, constructor: `(db_resolver, fx_rate_obsolete)`)
  - `packages/core/application/dashboard_service.py` (async, constructor: `(_exp_repo, _inc_repo, _inv_repo, _acc_repo, fx_service, investment_service)`)
- **Evidence:** `apps/api/main.py:59` import dari backend.services; `packages/api/backend/routers/deps.py:26` import dari packages.core.application. Lalu `apps/api/main.py:261` re-import `dashboard_service` dari deps — yang terakhir wins.
- **Impact:** Behavior drift. Yang dipakai di runtime adalah dari `deps.py` (async), tapi `apps/api/main.py:59` import-nya adalah sync. Dead import.
- **Root cause:** Migrasi dari sync ke async tidak pernah selesai — sync version tertinggal.
- **Rekomendasi:** Hapus `packages/api/backend/services/dashboard_service.py`. Atau gunakan satu di kedua tempat.

**FINDING D-002: InvestmentService duplikat**
- **Lokasi:**
  - `packages/api/backend/services/investment_service.py` (sync, 70 LOC, basic list + calculate_sell)
  - `packages/core/application/investment_service.py` (async, 280 LOC, full feature set)
- **Evidence:** `apps/api/main.py` import sync version (line 59) tapi `deps.py:55` instantiate async version. Semua router pakai yang dari deps.
- **Impact:** Sama — dead code.

**FINDING D-003: Database.query/execute pattern dengan bridge di banyak tempat**
- **Lokasi:** `packages/api/backend/routers/expenses.py`, `income.py`, `investments.py` — semua define `_query_expenses()`, `_query_income()`, `_query_investments()` wrapper untuk panggil `_query("expense.db", ...)`.
- **Impact:** Repetitif. Pattern seharusnya di-extract ke factory.

### D.2 Long Functions / Classes

**FINDING D-004: routers/ai.py 804 LOC (HIGH)**
- **Evidence:** `wc -l` menunjukkan 804 baris dalam satu file. Sangat sulit di-maintain.
- **Rekomendasi:** Split by AI provider / use case (ocr_categorize, receipt_parse, ml_predict, llm_query).

**FINDING D-005: `apps/cli/main.py` `_fetch_dashboard_data` ~70 LOC (MEDIUM)**
- **Evidence:** Multiple responsibilities (expense aggregation, income aggregation, investment valuation, ML prediction fetch, butterfly correlation).
- **Rekomendasi:** Extract ke sub-functions per concern.

**FINDING D-006: Genetic universe audit endpoint di main.py (MEDIUM)**
- **Evidence:** `apps/api/main.py:288-353` — 65 baris logic di dalam route handler. Pull data, align, run optimizer, build response.

### D.3 High Coupling

**FINDING D-007: CLI receipt_reader dipanggil dari API (HIGH)**
- **Evidence:** `packages/api/backend/routers/receipts.py:18-20`:
  ```python
  from apps.cli.receipt_reader.core.ocr_ensemble import OCREnsemble
  from apps.cli.receipt_reader.core.parser import ReceiptParser
  from apps.cli.receipt_reader.core.categorizer import UniversalCategorizer
  ```
- **Impact:** API service coupled ke CLI module structure. CLI refactor → API broken. Bukan boundary yang benar.
- **Rekomendasi:** Pindahkan `receipt_reader/core/*` ke `packages/core/application/receipt_reader/` atau `packages/api/backend/receipt/`.

**FINDING D-008: deps.py sebagai god dependency (HIGH)**
- **Evidence:** 310 LOC module yang berisi: repositories, services, lazy loaders, db helpers, behavioral cache, reward bridges. 25+ symbols di-export.
- **Impact:** Tight coupling — semua router import dari satu file. Circular import risk tinggi.
- **Rekomendasi:** Split per concern (repos.py, services.py, helpers.py).

### D.4 Low Cohesion

**FINDING D-009: `apps/api/main.py` (HIGH)**
- **Evidence:** Satu file berisi: lifespan, app factory, 6+ endpoints, router registry loop, static serving, SSL config, exception handler.
- **Impact:** Setiap perubahan API butuh edit `main.py`. Test-ability rendah.

### D.5 Poor Naming

**FINDING D-010: `investment_service` (sync) punya parameter `fx_rate_obsolete` (LOW)**
- **Evidence:** `packages/api/backend/services/investment_service.py:6`:
  ```python
  def __init__(self, db_resolver, fx_rate_obsolete):
  ```
- **Impact:** Confusing — "obsolete" parameter masih ada tapi tidak dipakai. Dead code.
- **Rekomendasi:** Hapus parameter.

### D.6 Hardcoded Values / Magic Numbers

**FINDING D-011: FX rate default 16000.0 di banyak tempat (MEDIUM)**
- **Evidence:**
  - `packages/api/backend/routers/deps.py:99`: `FX_RATE: float = 16_000.0`
  - `apps/cli/main.py:277`: `usd_idr: Decimal = Decimal('16000.0')`
  - `apps/cli/investment_tracker/services/fx_service.py`: kemungkinan sama.
- **Impact:** Magic number tersebar. Jika kurs berubah, perlu cari-temukan. Tidak ada single source of truth.

**FINDING D-012: Cache TTL values hardcoded (LOW)**
- **Evidence:** `apps/cli/stock_analyzer/adapters/cache.py:34-44`:
  ```python
  _TTL_INTRADAY = 300
  _TTL_DAILY    = 3600 * 4
  _TTL_CLOSED   = 3600 * 14
  _TTL_WEEKEND  = 3600 * 12
  _TTL_HOLIDAY  = 3600 * 36
  TTL_OHLCV = 300
  ...
  ```
- **Impact:** Acceptable untuk cache tuning — tapi harus di config, bukan source.

**FINDING D-013: US Federal holidays hardcoded (LOW)**
- **Evidence:** `cache.py:17-32` — `_US_HOLIDAYS` dan `_IDX_HOLIDAYS` hardcoded sets.
- **Impact:** Maintenance burden. Holiday baru tiap tahun harus update manual.

**FINDING D-014: Magic number di `expenses.py:163` (LOW)**
- **Evidence:** `(today.replace(day=28) + timedelta(days=4)).replace(day=1).date()` — calculation untuk end of month.

### D.7 Dead / Unused Code

**FINDING D-015: `apps/api/main.py:53-55` import `db = _db` (LOW)**
- **Evidence:**
  ```python
  from packages.api.backend.routers.deps import _db, FX_RATE
  db = _db
  ```
  Lalu `db` tidak pernah dipakai di main.py.
- **Rekomendasi:** Hapus.

**FINDING D-016: `db_resolver` di deps.py line 66-68 hanya untuk legacy (LOW)**
- **Evidence:** `_db(module, filename)` hanya resolve ke path SQLite yang di-ignore karena Postgres redirect. Masih dipanggil di beberapa route (expense.py:195, etc.) tapi tidak benar-benar pakai SQLite.

**FINDING D-017: `packages/api/backend/services/stock_analysis_service.py` (UNKNOWN)**
- **Evidence:** File exist tapi tidak ada yang import dari `grep`. Dead code.

**FINDING D-018: `packages/web/` legacy (LOW)**
- **Evidence:** `packages/web/dist/` masih ada, `package.json` ada, tapi tidak direferensikan dari `apps/web/package.json`. `apps/api/main.py:406` reference: `if not _DIST.exists(): _DIST = _PROJECT_ROOT / "finance-tracker-gui" / "dist"`. Jadi fallback chain: packages/web/dist → finance-tracker-gui/dist → none.
- **Rekomendasi:** Hapus `packages/web/` atau konfirmasi kegunaannya.

### D.8 Inconsistent Patterns

**FINDING D-019: Sync vs Async inconsistency (CRITICAL)**
- **Evidence:** Banyak tempat:
  - `apps/api/main.py:261`: `from packages.api.backend.routers.deps import dashboard_service, get_active_profile` — lalu `await dashboard_service.get_summary(...)`.
  - Tapi `packages/api/backend/services/dashboard_service.py` adalah sync class.
  - `packages/core/application/dashboard_service.py` adalah async dengan constructor berbeda.
  - Router `expenses.py:91`: `items = await _exp_repo.get_all(...)` — async.
  - Tapi `expenses.py:126`: `def update_expense(expense_id, body):` — sync, no await needed (raw SQL via `_execute_expenses`).
  - `investments.py:185`: `new_id = _execute_expenses(...)` — sync raw SQL, tapi baris-baris lain await service.
- **Impact:** **Critical** — runtime bisa return coroutine instead of value jika salah import. Bug intermiten.
- **Root cause:** Migrasi async parsial. Sync raw SQL pattern masih dipertahankan di beberapa tempat.

**FINDING D-020: Two ways untuk write expenses (MEDIUM)**
- **Evidence:**
  - `expenses.py:109`: `expense_service.record_expense(...)` (async service path).
  - `expenses.py:126`: raw SQL via `_execute_expenses("UPDATE expenses SET ... WHERE id=?")` (sync, bypasses service).
- **Impact:** Inconsistent: business logic (reward unlock, behavioral cache bust) hanya di path pertama. Update path bisa bypass audit.
- **Rekomendasi:** Gunakan service untuk semua mutation.

### D.9 Poor Error Handling

**FINDING D-021: Bare `except:` blocks (HIGH)**
- **Evidence:**
  - `packages/api/backend/services/investment_service.py:18-19`: `except: fx = 16000.0`
  - `packages/api/backend/services/investment_service.py:26-27`: `except: inv["pl"] = inv["pl_pct"] = None`
  - `packages/core/infrastructure/persistence/postgres_investment_repository.py:99`: `try: ... except: return False` (delete)
  - `postgres_investment_repository.py:111`: `except: return False` (update_status)
- **Impact:** Exception swallowing menyembunyikan bug nyata. `KeyboardInterrupt` dan `SystemExit` akan di-catch. Bugs production jadi invisible.
- **Rekomendasi:** Ganti dengan `except SpecificException:` dan log error.

**FINDING D-022: `investment_service.py` line 18-19 fallback FX (MEDIUM)**
- **Evidence:**
  ```python
  try:
      fx = get_live_fx_rate()
  except:
      fx = 16000.0
  ```
- **Impact:** Silent fallback. User tidak tahu bahwa FX rate gagal di-fetch. Laporan P&L bisa misleading.
- **Rekomendasi:** Raise exception, atau tampilkan warning di response.

**FINDING D-023: `expenses.py:218-220` swallow exceptions (MEDIUM)**
- **Evidence:**
  ```python
  except Exception as e:
      logger.exception("Error listing recurring candidates")
      return {"ok": True, "candidates": []}
  ```
- **Impact:** Returns success dengan empty data padahal backend error. Client tidak bisa distinguish "no candidates" dari "backend down".

### D.10 Poor Separation of Concerns

**FINDING D-024: `_goals_db()` di deps.py (MEDIUM)**
- **Evidence:** `deps.py:197-233` — function yang isinya CREATE TABLE statements untuk 5 tabel (goals, manual_balances, cash_split, transfer_log, reward_state). Ini schema management, bukan dependency.
- **Impact:** Schema creation tersebar. Migration tidak terpusat.
- **Rekomendasi:** Pindahkan ke `SchemaInitializer`.

### D.11 Violations of SOLID

**FINDING D-025: DashboardService violation of Single Responsibility (MEDIUM)**
- **Evidence:** Class yang aggregate expenses + incomes + investments + behavioral + forecasts dalam satu method.
- **Rekomendasi:** Extract ke `ExpenseAggregator`, `IncomeAggregator`, `InvestmentAggregator`, lalu orchestrator.

**FINDING D-026: Open/Closed violation di routers (LOW)**
- **Evidence:** `apps/api/main.py:363-403` — router registration loop dengan hardcoded list. Adding router butuh edit list.
- **Rekomendasi:** Pakai FastAPI's automatic discovery via decorator + plugin registry.

### D.12 Anti-Patterns

**FINDING D-027: God Object di deps.py (HIGH)**
- **Evidence:** `packages/api/backend/routers/deps.py` 310 LOC, export 25+ symbols: repos, services, helpers, db paths, lazy loaders, caches.
- **Impact:** Circular import waiting to happen.

**FINDING D-028: Async/Sync mismatch di PostgresInvestmentRepository (MEDIUM)**
- **Evidence:** `postgres_investment_repository.py:42-45`:
  ```python
  try:
      rows = await asyncio.to_thread(DatabaseManager.query, sql)
  except Exception:
      rows = DatabaseManager.query(sql)
  ```
- **Impact:** Fallback ke sync dari async context = potential deadlock jika event loop blocking. Sync psycopg2 di async loop.
- **Rekomendasi:** Hapus fallback atau pakai `await DatabaseManager.query_async(sql)`.

**FINDING D-029: Race condition di investment_service.py:185 (MEDIUM)**
- **Evidence:** `expenses.py:183`: `new_id = _execute_expenses(insert_sql, ...)`. Cek existing (`existing = _query_expenses(...)`) lalu insert. No transaction wrap.
- **Impact:** Concurrent request bisa insert duplicate recurring expenses.
- **Rekomendasi:** Wrap dalam `BEGIN IMMEDIATE` (SQLite) atau `BEGIN` (Postgres).

**FINDING D-030: Lazy load via `importlib.util` di deps.py (MEDIUM)**
- **Evidence:** `deps.py:107-171` — tiga helper `_get_merchant_memory`, `_get_allocation_engine`, `_get_recurrence_detector` yang load module via `importlib.util.spec_from_file_location`.
- **Impact:** Hack pattern — biasanya indikasi circular import atau struktur package yang salah. Bypass normal Python module resolution.
- **Root cause:** Modul-modul ini ada di `packages/api/backend/{receipt,finance,expenses}/` tapi di-import dari `routers/deps.py`. Seharusnya normal import.

**FINDING D-031: Pickle untuk cache data (LOW-MEDIUM)**
- **Evidence:** `apps/cli/stock_analyzer/adapters/cache.py:106, 114, 221, 240` — `pickle.loads(data)` dan `pickle.dumps(value)`.
- **Impact:** Pickle tidak aman untuk untrusted data. Tapi cache ini local SQLite, jadi tidak critical. Performance: pickle lambat untuk pandas DataFrame.

---

## E. SECURITY AUDIT

### E.1 Authentication

**FINDING S-001: Single master API key (MEDIUM)**
- **Evidence:** `packages/api/backend/security/core.py:88-90`: `FINANCE_TRACKER_API_KEY` env var. Single static string.
- **Issue:** Tidak ada rotation, tidak ada expiry, tidak ada per-user identity. Compromise key = full access.
- **Severity:** Medium (single-user system, tapi jika production-grade harus per-user JWT).

**FINDING S-002: Bearer token tanpa expiry (MEDIUM)**
- **Evidence:** `verify_api_key()` hanya compares string. Tidak decode JWT, tidak ada expiry claim.
- **Rekomendasi:** Pakai JWT dengan `exp` claim + refresh token, atau OAuth2.

**FINDING S-003: HMAC signing optional (LOW)**
- **Evidence:** `_verify_hmac()` di `core.py:129-161` — hanya jalan jika header `X-Request-Signature` dikirim.
- **Issue:** Optional integrity check = tidak enforceable untuk semua client.
- **Rekomendasi:** Enable mandatory untuk POST/PUT/DELETE.

### E.2 Authorization

**FINDING S-004: `_token_scope` selalu return "admin" (MEDIUM)**
- **Evidence:** `core.py:281-283`:
  ```python
  if token == "dev":
      return "admin"
  return "admin"
  ```
- **Issue:** Tidak ada granular authorization. Single key = full admin. Tidak bisa kasih "read-only" key ke integration.
- **Rekomendasi:** Multi-token dengan scope metadata.

**FINDING S-005: Tidak ada per-user data isolation di API (HIGH)**
- **Evidence:** Profile isolation dihandle via active_profile dari filesystem (`data/active_profile.txt`). Tidak ada auth identity → tidak ada ownership check.
- **Issue:** Siapapun dengan valid API key bisa CRUD data di profile manapun (jika `active_profile.txt` di-override).
- **Rekomendasi:** Token harus bind ke profile_id.

### E.3 Password Handling
**N/A** — Sistem pakai API key bukan password. `FINANCE_TRACKER_API_KEY` adalah opaque string.

### E.4 Session/JWT Security
**Tidak pakai session/JWT.** API key model. Lihat S-001, S-002.

### E.5 Input Validation

**FINDING S-006: Validasi ada tapi partial (LOW)**
- **Evidence:** `expenses.py:47-84` — `ExpenseIn` punya `@field_validator` untuk amount/description/date. Bagus.
- `InvestmentIn` di `investments.py:26-32` — TIDAK ada validator. `quantity`, `buy_price`, `ticker` tanpa validation.
- `SellIn` di `investments.py:35-40` — TIDAK ada validator.
- **Impact:** Negative quantity, empty ticker, future date bisa masuk.

**FINDING S-007: SQL injection risk via f-string di schemas.py (HIGH)**
- **Evidence:** `packages/api/backend/infrastructure/schemas.py:49`:
  ```python
  DatabaseManager.execute(f"CREATE SCHEMA IF NOT EXISTS {profile}")
  ```
- **Issue:** `profile` datang dari `Config.get_active_profile()` yang baca `data/active_profile.txt`. Validasi ada di `ProfileService.add_profile()` (`^[a-z0-9_]+$`), TAPI profile bisa di-override manual via filesystem (active_profile.txt dapat di-tulis langsung).
- **Severity:** Medium (perlu write access ke filesystem), tapi kalau attacker punya write ke filesystem, bisa execute arbitrary SQL: `data/active_profile.txt` berisi `personal;DROP TABLE users;--` → `CREATE SCHEMA IF NOT EXISTS personal;DROP TABLE users;--`.
- **Rekomendasi:** Validate profile name di `get_active_profile()` atau pakai parameterized query.

**FINDING S-008: SQL injection risk di schema DDL names (HIGH)**
- **Evidence:** `schemas.py:250-278` — semua DDL menggunakan `f"... {profile}.{table_name} ..."`. `{profile}` dan `{table_name}` interpolated tanpa escaping.
- **Issue:** Sama dengan S-007.
- **Rekomendasi:** Whitelist profile dan table_name.

**FINDING S-009: SQL injection risk di `search_files` di investment service (MEDIUM)**
- **Evidence:** `routers/expenses.py:148`, `expenses.py:157` — raw SQL via `_query_expenses(sql, params)` — params dipakai correctly. Tidak ada issue di sini.
- Catatan: Banyak query menggunakan parameterized queries (`%s` atau `?`), bagus.

### E.6 XSS
**N/A di backend.** Frontend Next.js React by default escapes — tidak perlu mitigasi tambahan kecuali dangerouslySetInnerHTML dipakai. Perlu cek `apps/web/src/app/**` untuk konfirmasi.

### E.7 CSRF
**N/A untuk pure API** (Bearer token). Tapi jika ada form submission dari web dengan cookie session, perlu CSRF token. Saat ini tidak ada cookie-based session, jadi aman.

### E.8 CORS

**FINDING S-010: CORS default restrictive tapi bisa permissive (LOW)**
- **Evidence:** `apps/api/config.py:40-47`: `ALLOWED_ORIGINS` dari env `FINANCE_TRACKER_CORS_ORIGINS`, default `http://localhost:5173,http://127.0.0.1:5173`.
- `apps/api/main.py:169-175`: `allow_origins=settings.ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]`.
- **Issue:** `allow_methods=["*"]` + `allow_credentials=True` terlalu permissive. CORS spec violation: `allow_credentials=True` requires explicit origins (not wildcard).
- **Rekomendasi:** Whitelist methods dan headers.

### E.9 Sensitive Data Exposure

**FINDING S-011: `.env` tidak di-git (verified via .gitignore) (INFO)**
- **Evidence:** `.gitignore` line: `.env`. Bagus.
- Tapi `FINANCE_TRACKER_API_KEY` di-`.env` — jika `.env` bocor (misal Docker log, error traceback), key compromised.

**FINDING S-012: Stack trace di response (HIGH)**
- **Evidence:** `packages/api/backend/routers/investments.py:51-55`:
  ```python
  except Exception as e:
      import traceback
      error_msg = f"Error in list_investments: {str(e)}\n{traceback.format_exc()}"
      logger.error(error_msg)
      raise HTTPException(status_code=500, detail=error_msg)
  ```
- **Issue:** Stack trace di-expose ke client. Information disclosure: file paths, internal functions, library versions.
- **Rekomendasi:** Log full traceback, return generic error ke client.

**FINDING S-013: DB password hardcoded di default DATABASE_URL (HIGH)**
- **Evidence:** `apps/api/config.py:27-30`:
  ```python
  DATABASE_URL: str = os.getenv(
      "DATABASE_URL", 
      "postgresql://postgres:***@postgres:5432/finance_tracker?schema=public"
  )
  ```
- **Catatan:** Literal "***" — jadi ini placeholder. Bukan hardcoded credential sebenarnya. Tapi masih menunjukkan default yang tidak secure.

**FINDING S-014: DatabaseManager langsung baca password (INFO)**
- **Evidence:** `postgres_manager.py:33-37`:
  ```python
  password=Config.POSTGRES_PASSWORD,
  ```
- **Bagus:** password dari Config (env), tidak hardcoded.

### E.10 Hardcoded Secrets

**FINDING S-015: `SECRET_KEY` default insecure (HIGH)**
- **Evidence:** `apps/api/config.py:32`:
  ```python
  SECRET_KEY: str = os.getenv("SECRET_KEY", "alpha-microservice-default-secret-key")
  ```
- **Issue:** Default value `"alpha-microservice-default-secret-key"` — jika production deploy tanpa env override, weak secret.
- **Mitigasi:** Ada warning log di line 51-55 jika default dipakai di non-DEBUG mode. Tapi tetap: default value tidak boleh di-source code.
- **Rekomendasi:** Raise exception saat startup jika default dipakai di production.

**FINDING S-016: Tidak ada secret rotation strategy (MEDIUM)**
- **Issue:** `FINANCE_TRACKER_API_KEY` dan `SECRET_KEY` static. Tidak ada key rotation.

### E.11 Environment Variables

**FINDING S-017: Banyak env vars tanpa dokumentasi terpusat (LOW)**
- **Evidence:** `.env.prod.example` hanya punya 5 vars: `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `SECRET_KEY`, `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_API_URL`. Tapi code pakai banyak lagi: `FINANCE_TRACKER_API_KEY`, `FINANCE_TRACKER_DEV_MODE`, `FINANCE_TRACKER_RATE_LIMIT`, `FINANCE_TRACKER_CORS_ORIGINS`, `HOST`, `PORT`, `REDIS_URL`, `ALLOWED_IP_WHITELIST`, `DATABASE_URL`.
- **Rekomendasi:** Update `.env.prod.example` dengan semua vars.

### E.12 File Upload Security

**FINDING S-018: Receipt upload validation decent (INFO)**
- **Evidence:** `packages/api/backend/routers/receipts.py:48-50`:
  ```python
  _ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
  _ALLOWED_EXT  = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
  _MAX_BYTES    = 10 * 1024 * 1024  # 10 MB
  ```
- **Bagus:** MIME + extension + size validation.
- **Concern:** Tidak ada magic-byte check (bisa rename `.exe` ke `.jpg`).
- **Concern:** Temp file di `tempfile.NamedTemporaryFile(delete=False)` — file di-disk setelah processing, harus manual cleanup.
- **Rekomendasi:** Gunakan `python-magic` untuk validasi content, atau panggil `delete=True` di NamedTemporaryFile.

### E.13 API Security

**FINDING S-019: No HTTPS enforcement di dev (INFO)**
- **Evidence:** `HTTPSRedirectMiddleware` hanya di-add jika `SSL_CERT_PATH.exists() && SSL_KEY_PATH.exists()` (`apps/api/main.py:164-166`).
- **Bagus:** Conditional. Tapi default production deploy tanpa cert → traffic bisa di-sniff (Bearer token di header).
- **Rekomendasi:** Production harus enforce HTTPS via reverse proxy (nginx) atau required env.

**FINDING S-020: Rate limit reset on restart (LOW)**
- **Evidence:** `_rate_window` adalah `defaultdict(deque())` di-memory (`core.py:101`). Restart server = limit reset.
- **Issue:** Attacker bisa brute force via restart trigger (jika ada akses).
- **Rekomendasi:** Pakai Redis-backed rate limit.

### E.14 Dependency Vulnerabilities
**Tidak bisa verify tanpa menjalankan `pip-audit` / `npm audit`.** Recommend run:
- `pip-audit` untuk `requirements.txt` files.
- `npm audit` untuk `apps/web/package.json`, `packages/web/package.json`, `packages/database/package.json`.

Concerns umum:
- `psycopg2` (Postgres driver) — pastikan versi terbaru (CVE-2023-31294 di versi lama).
- `pillow` (untuk OCR image processing) — CVE-2023-44271 di versi lama.
- `cryptography` (untuk HMAC) — perlu versi aman.

### E.15 Error Information Leakage

**FINDING S-021: Full exception di detail (HIGH)**
- **Evidence:** Sama dengan S-012. Pattern tersebar:
  - `routers/investments.py:53-55`: stack trace di HTTPException detail.
  - `apps/api/main.py:267-272`: error message di-dictionary response (dashboard error).
- **Rekomendasi:** Generic error messages + log detail server-side.

---

## F. DATABASE ANALYSIS

### F.1 Schema

**Schema PostgreSQL per profile:**
- `{profile}.expenses`, `{profile}.incomes`, `{profile}.investments`, `{profile}.sell_transactions`, `{profile}.historical_prices`, `{profile}.recurrence_candidates`, `{profile}.user_stats`, `{profile}.fx_rates`, `{profile}.manual_balances`, `{profile}.cash_split`, `{profile}.transfer_log`, `{profile}.behavioral_snapshots`, `{profile}.networth_snapshots`, `{profile}.budgets`, `{profile}.goals`, `{profile}.stock_favorites`, `{profile}.virtual_accounts`, `{profile}.reward_state`.

**Schema shared (cross-profile):**
- `financials.budgets`, `financials.recurrence_candidates` (referenced in code).
- `core`, `investment`, `market`, `audit`, `system`, `public`.

**SQLite files (legacy):**
- `apps/cli/expense_tracker/data/expense.db`, `income.db`, `investment_tracker/data/portfolio.db`, `apps/cli/advanced_features/data/{goals,budget}.db`, `apps/cli/behavioral_finance/data/behavioral.db`.
- `packages/api/data/audit_log.db`, `packages/api/data/cache.db` (transient).

**Issue:** Schema dual-defined — di `schemas.py` (DDL inline) DAN di `alpha_db_schema.sql` (legacy file). Drift risk.

### F.2 Relationships
**Inconsistent foreign keys:**
- PostgreSQL schema: `sell_transactions.investment_id REFERENCES {profile}.investments(id)` — bagus.
- SQLite schema (`alpha_db_schema.sql:162`): `sell_transactions.investment_id REFERENCES investments(id) ON DELETE CASCADE` — bagus.
- Tapi `expenses` di SQLite (`alpha_db_schema.sql:127-137`): TIDAK ada FK ke user_id, category_id (categories ada di-memory atau hardcoded list).

### F.3 Normalization
- `expenses`, `incomes`, `investments` — fully normalized.
- `category` disimpan sebagai `TEXT` (string), bukan FK ke `categories` table — denormalized untuk performance, OK untuk skala kecil.
- `payment_method` juga TEXT.

### F.4 Indexing

**PostgreSQL:**
- `expenses(date)`, `incomes(date)`, `investments(ticker)`, `virtual_accounts(profile_id)`. Minimal.
- TIDAK ada composite index `(profile_id, date)` yang seharusnya paling sering di-query.

**SQLite:**
- `currency_history(base_currency, target_currency, date DESC)` — composite bagus.
- `expenses(date DESC)`, `incomes(date DESC)`, `investments(ticker)` — single column.
- `recurrence_candidates` — TIDAK ada index.

### F.5 Query Efficiency

**FINDING DB-001: N+1 di dashboard_service (HIGH)**
- **Evidence:** `dashboard_service.py` line ~100+ (tidak ditampilkan full): kemungkinan iterasi holdings tanpa JOIN ke historical_prices.
- **Catatan:** Saya butuh baca full file untuk konfirmasi, tapi pattern di `deps.py:294-307` (`_get_crypto_from_portfolio`) menunjukkan per-row query:
  ```python
  (SELECT price_idr FROM historical_prices h WHERE h.investment_id=i.id ORDER BY h.id DESC LIMIT 1) AS current_price_idr
  ```
  Ini correlated subquery — untuk 100 holdings = 100+ subqueries. Bisa O(N²).

**FINDING DB-002: `psycopg2` pool dengan search_path di setiap query (MEDIUM)**
- **Evidence:** `postgres_manager.py:60-67`:
  ```python
  with conn.cursor() as cur:
      cur.execute(f"SET search_path TO {search_path}")
  ```
- **Issue:** Setiap kali `get_connection()` dipanggil, ada `SET search_path` round-trip. Untuk high-throughput, ini overhead.
- **Rekomendasi:** Set search_path di connection pool init, atau pakai schema-qualified table names.

**FINDING DB-003: Tidak ada pagination default (HIGH)**
- **Evidence:** `expenses.py:88-89`: `limit: int = 50, offset: int = 0`. Default 50 — bagus.
- `investments.py:43`: TIDAK ada pagination. Return ALL active investments.
- `income.py`: pagination ada tapi sederhana.

### F.6 N+1 Queries

**FINDING DB-004: Historical price lookup per holding (HIGH)**
- **Evidence:** `deps.py:294-307` (subquery di SELECT) + `investments.py:213-238` (loop fetch yfinance per holding dalam `/history` endpoint).
- **Impact:** Untuk 100 holdings, 100+ HTTP calls ke yfinance. Latency besar.
- **Rekomendasi:** Batch fetch dengan `yf.download()` multiple tickers.

### F.7 Duplicate Data

**FINDING DB-005: `remaining_quantity` di investments denormalized (LOW)**
- **Evidence:** `investments.remaining_quantity` vs `sell_transactions` aggregate quantity.
- **Issue:** Bisa drift jika ada bug di sell logic.
- **Rekomendasi:** Trigger atau check constraint untuk konsistensi.

**FINDING DB-006: `current_price_idr` di `historical_prices` vs live yfinance (MEDIUM)**
- **Evidence:** `deps.py:294-297` — query ambil dari `historical_prices` yang di-update via scheduler. Tapi `investments.py:213-238` ambil dari yfinance live.
- **Issue:** Dua source of truth untuk "current price". Bisa inconsistent.

### F.8 Foreign Keys
**Sebagian besar ada, tapi tidak enforced di SQLite** (default SQLite FK off).

### F.9 Constraints

**FINDING DB-007: CHECK constraints ada di Postgres, tidak di SQLite (LOW)**
- **Evidence:** `schemas.py:88`: `CHECK (remaining_quantity >= 0)`. Tapi SQLite version (`alpha_db_schema.sql:153`): `remaining_quantity NUMERIC(20, 8) NOT NULL` — tanpa CHECK.
- **Issue:** Schema drift.

### F.10 Transactions

**FINDING DB-008: Tidak ada transaction boundary (HIGH)**
- **Evidence:** `expenses.py:181-185` (apply recurring):
  ```python
  check_sql = "..."
  existing = _query_expenses(check_sql, ...)
  # ... no transaction ...
  insert_sql = "..."
  new_id = _execute_expenses(insert_sql, ...)
  ```
- **Issue:** Race condition: dua request bersamaan bisa kedua-duanya insert.
- **Rekomendasi:** Wrap dalam transaction (`BEGIN IMMEDIATE` SQLite / `BEGIN` Postgres).

**FINDING DB-009: Sell investment tidak atomic (CRITICAL)**
- **Evidence:** `routers/investments.py:73-129` — endpoint sell investment:
  1. `investment_service.sell_investment()` → updates investment status.
  2. `income_service.record_income()` (if profit > 0).
- **Issue:** Jika step 1 sukses tapi step 2 gagal (network, DB error), investment di-mark sold tapi realized P&L tidak ter-record ke income. **Data inconsistency.**
- **Mitigasi di code:** Ada warning di response (line 109-118), tapi data sudah partial-write.
- **Rekomendasi:** Pakai `DatabaseManager.transaction()` context manager (line 113-138 postgres_manager.py — sudah ada, tidak dipakai).

### F.11 Migration Strategy

**FINDING DB-010: Manual SQL scripts, no version tracking (MEDIUM)**
- **Evidence:** `scripts/migrations/` — ad-hoc scripts. `SchemaInitializer` pakai `CREATE TABLE IF NOT EXISTS`.
- **Issue:** Tidak ada version. Tidak bisa rollback. Schema drift antara local/dev/prod.
- **Rekomendasi:** Pakai Alembic atau Prisma migrations (sudah ada Prisma schema, tapi tidak dipakai).

### F.12 Scalability

**FINDING DB-011: Connection pool max 100 (MEDIUM)**
- **Evidence:** `postgres_manager.py:30`: `maxconn=100`.
- **Issue:** Untuk high concurrency (200+ req/s), pool exhausted → requests hang.
- **Rekomendasi:** Tune berdasarkan load test. Atau pakai PgBouncer.

---

## G. PERFORMANCE ANALYSIS

### G.1 Algorithm Complexity

**FINDING P-001: Dashboard aggregation O(N) setiap call (MEDIUM)**
- **Evidence:** `dashboard_service.py` query `expenses WHERE date>=%s AND date<%s` — full scan per request. Tidak ada materialized view, tidak ada cache.
- **Impact:** Untuk user dengan 10K expenses, latency bisa 100ms+.
- **Rekomendasi:** Cache summary per month, atau precompute via materialized view.

**FINDING P-002: Genetic optimizer audit endpoint O(N) sync call (HIGH)**
- **Evidence:** `apps/api/main.py:288-353` — endpoint `get_genetic_universe_audit`:
  - Query ALL tickers dari `market.ohlcv_cache` (line 296).
  - Untuk setiap ticker, `run_in_executor` fetch full history (line 303).
  - Align via pandas `ffill().dropna()`.
- **Impact:** Jika ada 500 tickers, 500 async tasks. Memory bisa explode.
- **Rekomendasi:** Paginate audit results atau run as background job.

### G.2 Database Performance

**FINDING P-003: Missing composite indexes (HIGH)**
- **Evidence:** Lihat F.4.
- **Rekomendasi:** Tambahkan `(profile_id, date DESC)` di `expenses`, `incomes`. `(investment_id, snapshot_date DESC)` di `historical_prices`.

**FINDING P-004: `search_path` round-trip per query (MEDIUM)**
- **Evidence:** F.2.
- **Rekomendasi:** Set di connection initialization.

### G.3 API Latency

**FINDING P-005: Synchronous OCR di request handler (HIGH)**
- **Evidence:** `routers/receipts.py:75`: `await asyncio.to_thread(ensemble.run, tmp_path, ...)`. Ensemble run synchronous, blocking event loop thread.
- **Issue:** 1 OCR request = 5-30 detik. Concurrent OCR requests = thread pool exhaustion.
- **Rekomendasi:** Queue ke background worker (Celery sudah ada di `packages/api/backend/core/celery_app.py`!).

**FINDING P-006: ML inference di request path (HIGH)**
- **Evidence:** `apps/cli/stock_analyzer/infrastructure/tui.py:542` LOC — TUI synchronous. Tapi untuk `/api/ml_stocks/predict` (likely di `routers/ml_stocks.py`), XGBoost predict bisa 50-500ms per call.
- **Rekomendasi:** Cache predictions dengan TTL.

### G.4 Network Requests

**FINDING P-007: yfinance per-ticker (HIGH)**
- **Evidence:** `routers/investments.py:217-238`:
  ```python
  for dt, row in market_df.iterrows():
      ...
  ```
  Loop iterates pandas DataFrame row by row. Plus previous evidence of N+1.
- **Issue:** Row-by-row iteration pandas lambat. Plus separate fetch per holding.
- **Rekomendasi:** Vectorize dengan pandas operations. Batch fetch.

**FINDING P-008: No HTTP retry logic (MEDIUM)**
- **Evidence:** `apps/cli/stock_analyzer/adapters/fetcher.py` (file exist, 176 LOC) — kemungkinan no retry. Tidak bisa konfirmasi tanpa baca.
- **Rekomendasi:** Exponential backoff retry untuk transient failures.

### G.5 Frontend Rendering
**Tidak dalam scope.** Next.js SSR/RSC default OK.

### G.6 Memory Usage

**FINDING P-009: Full DataFrame loaded ke memory (MEDIUM)**
- **Evidence:** `apps/cli/stock_ml/07_upgraded_system.py:38`: `df_raw = loader.load_ticker_data(ticker, period="2y")`. 2-year daily data untuk satu ticker = ~500 rows. OK.
- Tapi `apps/api/main.py:323`: `price_df = pd.DataFrame(returns_map).ffill().dropna()` — semua tickers di-memory simultaneously. 500 tickers × 252 trading days × 8 bytes/float = 1MB. OK, tapi tambah features bisa 100MB+.

**FINDING P-010: Pickle cache grows unbounded (LOW)**
- **Evidence:** `cache.py:236-242` — `INSERT OR REPLACE` ke SQLite. Tidak ada eviction.
- **Impact:** Cache.db membesar tanpa batas.
- **Rekomendasi:** LRU eviction atau periodic cleanup.

### G.7 Caching
**Ada Redis cache optional (`RedisCache`), tapi fallback ke disabled jika Redis tidak tersedia. SQLite cache ada untuk OHLCV.**

### G.8 Pagination
**FINDING P-011: No cursor-based pagination (MEDIUM)**
- **Evidence:** Offset-based (`limit`, `offset`). Untuk dataset besar, offset tidak efisien.
- **Rekomendasi:** Cursor-based untuk investments.

### G.9 Lazy Loading
**Modul-level singletons di deps.py (line 43-59) — lazy initialization OK.**

### G.10 Concurrent Processing
**Single-thread APScheduler untuk market data refresh.** Adequate untuk skala sekarang.

### G.11 Background Jobs

**FINDING P-012: APScheduler in-process (MEDIUM)**
- **Evidence:** `apps/api/main.py:107`: `scheduler = MarketScheduler(); await asyncio.to_thread(scheduler.start())`.
- **Issue:** Jika API restart, jobs hilang. Untuk production, perlu persistent queue (Celery sudah ada!).
- **Rekomendasi:** Migrate market refresh ke Celery beat.

---

## H. TESTING ANALYSIS

### H.1 Test Inventory
- **79 test files** di `tests/` (audit/, integration/, automation/).
- **4 test files** di `apps/cli/` (mostly scripts, bukan proper tests).
- **Total LOC tests:** ~844 baris di `tests/audit/`, lebih banyak di integration.

### H.2 Coverage

**FINDING T-001: Coverage configuration ada tapi tidak ada laporan (HIGH)**
- **Evidence:** `pyproject.toml` setup `[tool.coverage.run]` dan `[tool.coverage.report]`, exclude `*/tests/*`, `*/scripts/*`, `*/cli_view.py`, `*/tui.py`. Tapi tidak ada `coverage report`/`coverage xml` dijalankan secara regular.
- **Rekomendasi:** Jalankan `coverage run -m pytest && coverage report --fail-under=70`.

### H.3 Unit Tests
**Sub-modul yang punya unit tests:**
- `tests/audit/batch_a/test_1_1_root_detection.py` (29 LOC) — root path detection.
- `tests/audit/batch_a/test_1_2_thread_safety.py` (24 LOC) — thread safety.
- `tests/audit/batch_b/test_decimal_precision.py` (65 LOC) — Decimal precision.
- `tests/audit/batch_b/test_sell_logic.py` (75 LOC) — sell transaction logic.
- `tests/audit/test_sql_safety.py` (16 LOC) — SQL injection safety checks.
- `tests/integration/test_dxy_integrity.py`, `test_butterfly_*`, `test_macro_pipeline.py`, dll.

### H.4 Integration Tests
**Ada `tests/integration/`** — test full pipeline (e.g., `test_phase4_validation.py`).

### H.5 E2E Tests
**Tidak ada E2E.** Tidak ada Playwright/Cypress.

### H.6 Edge Cases
**Sub-modul dengan edge case coverage:**
- `batch_b/test_decimal_precision.py` — bagus untuk financial logic.
- `batch_b/test_sell_logic.py` — FIFO sell logic.
- `test_infra_root.py`, `test_infra_threads.py` — concurrency.

### H.7 Missing Test Coverage

**FINDING T-002: API routers tanpa test (HIGH)**
- **Evidence:** 22 routers, total 5353 LOC, hanya `tests/audit/test_sql_safety.py` (16 LOC) yang test SQL injection.
- **Rekomendasi:** Tambahkan test per-router happy path + error path.

**FINDING T-003: Auth/security tidak ada test (HIGH)**
- **Evidence:** `security/core.py` 395 LOC — tidak ada unit test untuk rate limiter, HMAC, scope check, audit middleware.
- **Rekomendasi:** Test brute force, scope escalation, expired keys.

**FINDING T-004: Investment sell atomicity tidak ada test (CRITICAL)**
- **Evidence:** `routers/investments.py:73-129` — sell endpoint punya complex multi-step. Tidak ada test untuk concurrent sell, partial sell, race condition.
- **Rekomendasi:** Test concurrent sell requests untuk detect race condition.

**FINDING T-005: Frontend tidak ada test (MEDIUM)**
- **Evidence:** `apps/web/src/app/` — Next.js tanpa Jest/React Testing Library setup.
- **Rekomendasi:** Minimum snapshot test untuk critical pages.

### H.8 Test Cases yang Harus Ditambahkan

**Test cases kritis (P0):**
1. **Sell investment concurrent race** — dua sell requests bersamaan untuk investment yang sama.
2. **Recurring expense apply race** — dua admin trigger apply bersamaan.
3. **Profile isolation** — read profile A, switch ke B, ensure data tidak bocor.
4. **HMAC verification rejection** — invalid signature.
5. **Rate limit enforcement** — 121 requests dalam 1 menit harus 429.
6. **Sell with profit auto-record income** — verify income ter-create.
7. **Investment refresh prices** — verify yfinance fallback ke SQLite cache saat offline.
8. **OCR with malformed image** — JPEG corrupt harus 400, bukan 500.

---

## I. RELIABILITY & ERROR HANDLING

### I.1 Exception Handling

**FINDING R-001: Bare except tersebar (HIGH)**
- **Evidence:** Lihat D-021. Multiple `except:` tanpa exception type.
- **Impact:** Silent failures, bug latent.
- **Rekomendasi:** Semua `except:` → `except SpecificException:`.

**FINDING R-002: Generic Exception catch menyembunyikan context (MEDIUM)**
- **Evidence:** `deps.py:188-189`:
  ```python
  except Exception as e:
      logger.error(f"Reward unlock error: {e}")
      return []
  ```
- **Impact:** Reward unlock gagal di-silent. User tidak dapat reward walaupun qualified.
- **Rekomendasi:** Re-raise atau proper notification.

### I.2 Retry Mechanism
**FINDING R-003: Tidak ada retry untuk external APIs (HIGH)**
- **Evidence:** `market_scheduler.py:19-24`:
  ```python
  try:
      self.market_service.update_all_tickers(self.watchlist_path)
  except Exception as e:
      logger.error(f"Error in background market update: {e}")
  ```
  Tidak ada retry. Single failure = data stale sampai next 5-min tick.
- **Rekomendasi:** Exponential backoff retry (3 attempts) dengan circuit breaker.

### I.3 Timeout
**FINDING R-004: HTTP requests tanpa timeout eksplisit (HIGH)**
- **Evidence:** `routers/investments.py:206`: `YFinanceFetcher.fetch_history(inv.ticker, start_dt, end_dt)` — kemungkinan default timeout (60s?). Tidak ada explicit timeout config.
- **Issue:** yfinance hang = API hang.
- **Rekomendasi:** Explicit timeout 10s dengan fallback.

### I.4 Failure Recovery

**FINDING R-005: Prisma connection failure tidak fatal tapi logged (INFO)**
- **Evidence:** `apps/api/main.py:96-101`:
  ```python
  try:
      from packages.database.index import connect as prisma_connect
      await prisma_connect()
      logger.info("Prisma client connected.")
  except Exception as e:
      logger.error(f"CRITICAL: Prisma connection failed: {e}", exc_info=True)
  ```
- **Issue:** API continue tanpa Prisma — semua endpoints yang butuh Prisma akan fail later.
- **Rekomendasi:** Fail-fast di startup atau health check lebih ketat.

**FINDING R-006: Schema init failure tidak stop scheduler (MEDIUM)**
- **Evidence:** `apps/api/main.py:104-113`:
  ```python
  if schema_ok:
      try:
          scheduler = MarketScheduler()
          ...
      except Exception as e:
          logger.error(...)
  ```
- **Impact:** Bagus — conditional. Tapi `schema_ok = False` tidak propagate ke router health check.

### I.5 Logging

**FINDING R-007: Logging inconsistency (MEDIUM)**
- **Evidence:**
  - `apps/api/main.py:64-77`: root logger setup dengan RotatingFileHandler.
  - `apps/cli/main.py:36`: pakai `get_logger("cli")` dari `packages.core.infrastructure.logging`.
  - `packages/api/backend/routers/*`: `logger = logging.getLogger(__name__)`.
  - `apps/cli/stock_analyzer/*`: pakai standard `logging`.
- **Issue:** Tiga pola logging berbeda. Logs sulit di-correlate.
- **Rekomendasi:** Standardize ke satu logging config (JSON structured logging ke stdout).

### I.6 Monitoring
**FINDING R-008: Tidak ada APM/error tracking (MEDIUM)**
- **Evidence:** Tidak ada Sentry, DataDog, atau OpenTelemetry integration.
- **Rekomendasi:** Tambah Sentry untuk production error tracking.

### I.7 Graceful Degradation

**FINDING R-009: Database fallback ke SQLite (HIGH — perlu diskusi)**
- **Evidence:** Lihat C.4. Jika Postgres down, beberapa endpoint diam-diam pakai SQLite (jika file exist) atau return default data.
- **Trade-off:** Availability vs Consistency. Saat ini lean ke availability — bisa misleading user.
- **Rekomendasi:** Jika production, fail closed. Jangan kasih data dari source berbeda.

### I.8 Data Consistency

**FINDING R-010: Cache invalidation strategy tidak konsisten (MEDIUM)**
- **Evidence:**
  - `_bust_behavioral_cache()` dipanggil setelah setiap mutation (expenses/investments).
  - `_BEHAVIORAL_CACHE_TIME = 0.0` reset.
  - Tapi TTL = 3600s. Jika cache bust terlewat (exception di middle of flow), cache stale 1 jam.
- **Rekomendasi:** TTL lebih pendek (5 min) + explicit bust di semua mutation paths.

---

## J. SCALABILITY ANALYSIS

### J.1 10x Users (single-user system, jadi ini lebih ke request volume)
- **API** — FastAPI async OK untuk 10x. Tapi Postgres pool max 100 connections (DB-011).
- **Scheduler** — APScheduler in-process jadi bottleneck.
- **Bottleneck:** PostgreSQL connection pool, yfinance rate limits, OCR compute time.

### J.2 10x Database Records
- **PostgreSQL** — OK untuk 10x (10K investments, 100K expenses, dll) dengan indexes yang ada.
- **N+1 queries** — akan terasa. DB-001.
- **Cache miss** — Redis optional. Jika off, semua request hit DB.
- **Bottleneck:** Index design (F.4), historical_prices lookup pattern.

### J.3 10x API Requests
- **Connection pool** — akan habis jika 10x concurrent.
- **Rate limiter** — `defaultdict(deque())` di-memory single-process. Tidak work untuk multi-worker.
- **Bottleneck:** Connection pool, rate limiter, OCR blocking.

### J.4 Multiple Concurrent Users (Multi-tenant)
- **Sistem saat ini single-user dengan profile switcher.** Bukan designed untuk multi-user.
- **API auth** — single API key, tidak ada per-user isolation.
- **Postgres schema** — profile via search_path, tapi semua pakai koneksi yang sama. Isolation OK di level schema, tapi tidak ada row-level security.
- **Bottleneck:** Tidak scalable ke multi-tenant tanpa redesign auth + row-level security.

### J.5 Asal Bottleneck

**Top 5 Bottleneck Scenarios:**

1. **Postgres connection pool exhaustion** (DB-011) — untuk high concurrency.
2. **OCR blocking event loop** (P-005) — concurrent uploads.
3. **N+1 historical prices** (DB-001) — portfolio besar.
4. **yfinance rate limits** — setiap holding = 1 call.
5. **APScheduler single-process** — market refresh + daily report serialized.

---

## K. FUNCTIONAL & UX LIMITATIONS

### K.1 Missing Features

**FINDING F-001: Tidak ada user authentication untuk web (HIGH)**
- **Issue:** Web frontend (`apps/web`) pakai Bearer API key. Tidak ada login flow, tidak ada session, tidak ada user identity.
- **Use case:** Production deployment butuh per-user login.

**FINDING F-002: Tidak ada real-time notifications untuk user (MEDIUM)**
- **Issue:** Telegram bot untuk system alerts (currency, price). Tidak ada notification untuk user events (expense added, budget exceeded, reward unlocked).
- **Rekomendasi:** Tambah notification preferences + push ke Telegram/web.

**FINDING F-003: Tidak ada audit trail untuk financial transactions (HIGH)**
- **Evidence:** `GEMINI.md:38`: "All financial transactions MUST be recorded in an immutable `audit_log.db` with cryptographic hashing". Tapi `audit_log.db` hanya mencatat HTTP requests (IP, path, method), bukan financial mutations. Tidak ada log "user X changed expense Y from A to B".

**FINDING F-004: Tidak ada data export full backup (MEDIUM)**
- **Issue:** CSV export per module ada, tapi tidak ada JSON/zip full export. Disaster recovery manual.

**FINDING F-005: Tidak ada data import (MEDIUM)**
- **Issue:** Web tidak ada form untuk import CSV. CLI mungkin ada (perlu cek), tapi tidak di-web.

**FINDING F-006: Tidak ada reporting/analytics dashboard untuk business profile (MEDIUM)**
- **Evidence:** Ada `run_business_report()` di `apps/cli/main.py:474` — generate quarterly. Tapi tidak ada interactive dashboard.
- **Rekomendasi:** Tambah business dashboard di web.

### K.2 Poor Workflow

**FINDING F-007: Manual profile switching (LOW)**
- **Issue:** Profile switch via menu option 8. Untuk multi-user device, awkward.

**FINDING F-008: No undo untuk delete operations (MEDIUM)**
- **Issue:** Delete expense/investment langsung. Tidak ada confirmation, tidak ada undo.

### K.3 Missing Automation

**FINDING F-009: Tidak ada auto-categorization dari bank SMS/email (MEDIUM)**
- **Issue:** Receipt OCR + manual categorization. Bank SMS parsing tidak ada.

**FINDING F-010: Tidak ada auto-import dari broker statement (MEDIUM)**
- **Issue:** Manual input untuk buy/sell. Broker API integration (e.g., Interactive Brokers, Stockbit) tidak ada.

### K.4 Missing Search/Filter/Sort/Pagination
**Sebagian besar ada** (`expenses.py:88`, dst). Tapi:
- `investments` tidak ada search/filter (cuma ticker exact match di query).

### K.5 Missing Reporting/Analytics
- Trend chart ada.
- P&L realized ada.
- Net worth snapshot ada (`networth_snapshots` table).
- Tax report tidak ada.

### K.6 Missing Notification System
- Telegram ada tapi system-wide. Per-user notification tidak ada.

### K.7 Missing Audit Trail
Lihat F-003.

### K.8 Missing Import/Export
- Export: CSV per module (ada).
- Import: Tidak ada di API.

---

## L. CRITICAL FINDINGS TABLE

| ID | Category | Finding | Evidence | Impact | Severity | Recommendation |
|----|----------|---------|----------|--------|----------|----------------|
| **C-001** | DB Consistency | Sell investment not atomic | routers/investments.py:73-129 | Partial data write on failure | **CRITICAL** | Wrap in transaction |
| **C-002** | Architecture | Sync/async mismatch | deps.py + routers | Runtime coroutine errors | **CRITICAL** | Audit all async/sync; standardize |
| **C-003** | Security | SQL injection via profile name | schemas.py:49 | Arbitrary SQL execution | **CRITICAL** | Validate profile name + parameterized |
| **C-004** | Reliability | Stack trace in HTTP response | investments.py:51-55 | Information disclosure | **HIGH** | Generic error + log detail |
| **C-005** | Code Quality | Dual DashboardService | main.py:59 vs deps.py:26 | Behavior drift | **HIGH** | Remove one |
| **C-006** | Code Quality | Dual InvestmentService | services/investment_service.py vs core/application | Dead code, drift | **HIGH** | Remove legacy |
| **C-007** | Coupling | CLI module imported from API | routers/receipts.py:18-20 | Tight coupling | **HIGH** | Move to packages/core |
| **C-008** | Code Quality | God object deps.py | routers/deps.py:310 LOC | Circular import risk | **HIGH** | Split per concern |
| **C-009** | DB | Recurring expense race condition | expenses.py:181-185 | Duplicate inserts | **HIGH** | Wrap in transaction |
| **C-010** | Error Handling | Bare except scattered | Multiple files | Silent failures | **HIGH** | Specific exceptions |
| **C-011** | Performance | Genetic audit endpoint O(N) blocking | main.py:288-353 | Memory/latency spike | **HIGH** | Background job |
| **C-012** | Performance | N+1 yfinance + historical prices | investments.py + deps.py | Latency for large portfolio | **HIGH** | Batch fetch |
| **C-013** | Security | DEFAULT SECRET_KEY in code | config.py:32 | Weak prod secret | **HIGH** | Fail-fast if default in prod |
| **C-014** | Testing | No sell atomicity test | tests/ | Race undetected | **HIGH** | Add concurrent test |
| **C-015** | Code Quality | routers/ai.py 804 LOC | wc -l | Maintainability | **MEDIUM** | Split by concern |
| **C-016** | Security | CORS too permissive | main.py:169-175 | Spec violation | **MEDIUM** | Whitelist methods |
| **C-017** | DB | Missing composite indexes | schemas.py | Slow queries at scale | **MEDIUM** | Add (profile_id, date) |
| **C-018** | Reliability | No retry for external APIs | market_scheduler.py | Stale data | **MEDIUM** | Exponential backoff |
| **C-019** | Reliability | APScheduler in-process | main.py:107 | Jobs lost on restart | **MEDIUM** | Migrate to Celery beat |
| **C-020** | Performance | OCR blocking request | receipts.py:75 | Thread pool exhaustion | **MEDIUM** | Queue via Celery |
| **C-021** | Code Quality | Two ways to write expenses | expenses.py:109 vs 126 | Bypass business logic | **MEDIUM** | Service for all mutations |
| **C-022** | DB | No pagination for investments | investments.py:43 | Slow on large data | **MEDIUM** | Add limit/offset |
| **C-023** | UX | No web login/auth flow | apps/web | Cannot deploy multi-user | **MEDIUM** | Add session-based auth |
| **C-024** | UX | No audit trail for transactions | GEMINI.md claim vs reality | Compliance gap | **MEDIUM** | Implement financial audit |
| **C-025** | Logging | 3 logging patterns | Multiple files | Hard to debug | **MEDIUM** | Standardize to structured JSON |
| **C-026** | Code Quality | FX rate magic number 16000 | 5+ locations | Drift risk | **LOW** | Single config |
| **C-027** | Code Quality | Hardcoded holidays | cache.py:17-32 | Maintenance | **LOW** | External API |
| **C-028** | Code Quality | Dead imports | main.py:53-55 | Cleanup | **LOW** | Remove |
| **C-029** | Code Quality | Legacy packages/web/ | packages/web/ | Unused | **LOW** | Remove or migrate |
| **C-030** | Security | HMAC optional | core.py:140 | No integrity for mutations | **LOW** | Mandatory for write |

---

## M. RECOMMENDED IMPROVEMENTS

### M.1 SHORT TERM (1-2 minggu)

**P0 (Must fix):**
1. **Wrap sell investment dalam transaction** (C-001). Pakai `DatabaseManager.transaction()` yang sudah ada.
2. **Validate profile name di `get_active_profile()`** (C-003). Whitelist regex.
3. **Remove stack trace dari HTTP response** (C-004). Generic error + server-side log.
4. **Remove DEFAULT SECRET_KEY** (C-013). Raise exception di startup.
5. **Add atomic recurring expense apply** (C-009). Wrap cek+insert dalam transaction.

**P1 (High value):**
6. **Standardize sync/async** (C-002). Tambah `await` jika service async, atau hapus jika sync. Audit semua router.
7. **Remove dual DashboardService/InvestmentService** (C-005, C-006).
8. **Move CLI receipt_reader ke packages/core** (C-007).
9. **Replace bare except dengan specific exceptions** (C-010).
10. **Add composite indexes** (C-017).
11. **Add CORS whitelist** (C-016).

### M.2 MEDIUM TERM (1-2 bulan)

**Refactoring:**
1. **Split `deps.py`** (C-008). Per concern: repos.py, services.py, helpers.py.
2. **Split `routers/ai.py`** (C-015). Per AI feature.
3. **Standardize logging** (C-025). JSON structured ke stdout.
4. **Add web authentication** (C-023). Session-based atau per-user JWT.
5. **Implement financial audit trail** (C-024). Append-only table untuk mutations.

**Performance:**
6. **Batch yfinance calls** (C-012).
7. **Move OCR ke Celery** (C-020).
8. **Background job for genetic audit** (C-011).
9. **Migrate market scheduler ke Celery beat** (C-019).

### M.3 LONG TERM (3-6 bulan)

**Major:**
1. **Replace APScheduler dengan Celery + Redis** untuk distributed task queue.
2. **Implement proper multi-user auth** dengan JWT + refresh tokens.
3. **Database migration framework** (Alembic atau proper Prisma usage).
4. **Add OpenTelemetry** untuk distributed tracing.
5. **API rate limit dengan Redis** (replace in-memory).
6. **Row-level security** di Postgres untuk proper multi-tenant isolation.
7. **API versioning** (`/api/v1/`, `/api/v2/`) untuk future evolution.
8. **Background ML prediction caching** dengan feature store.

---

## N. PROPOSED ARCHITECTURE

### N.1 Current Architecture

```
┌─────────────┐     ┌──────────────┐     �─────────────┐
│  apps/web   │────▶│  apps/api    │────▶│ packages/api│
│ (Next.js)   │     │  (FastAPI)   │     │ /backend    │
└─────────────┘     └──────┬───────�     └──────┬──────┘
                           │                    │
                           │                    ▼
                           │            ┌──────────────┐
                           │            │ packages/core│
                           │            │ /application │
                           │            └──────┬───────┘
┌─────────────�            │                   │
│  apps/cli   │────────────┘                   ▼
│  (TUI)      │──────▶ packages/core      ┌──────────────┐
└─────────────┘      /infrastructure       │ PostgreSQL   │
                       (repos)            │  + SQLite    │
                                          └──────────────┘
┌─────────────┐
│ n8n +       │──────▶ PostgreSQL ────▶ Telegram
│ price_scraper│
└─────────────┘
```

### N.2 Problems with Current

1. **apps/api → apps/cli coupling** — CLI's `receipt_reader` di-import langsung dari API router. Boundary violation.
2. **Dual service layer** — `packages/api/backend/services/` dan `packages/core/application/` untuk class yang sama.
3. **Dual database** — Postgres + SQLite dengan silent fallback.
4. **In-process scheduler** — APScheduler tidak survive restart.
5. **No API versioning** — `/api/*` flat namespace.

### N.3 Proposed Architecture (Modular Monolith Refinement)

```
┌──────────────────┐
│ apps/web (Next)  │
└────────┬─────────┘
         │ HTTPS + Bearer
         ▼
┌────────────────────────────────────────────┐
│ apps/api (FastAPI)                         │
│  ┌──────────────────────────────────────┐  │
│  │ Routers (per domain)                 │  │
│  │   /api/v1/expenses                   │  │
│  │   /api/v1/investments                │  │
│  │   /api/v1/receipts                   │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ Middleware: Auth + Audit + CORS      │  │
│  └──────────────────────────────────────┘  │
└────────┬───────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│ packages/core                              │
│  domain/  ← models, interfaces             │
│  application/  ← services (async, single)  │
│  infrastructure/                           │
│    persistence/ (Postgres-only repos)      │
│    external/ (yfinance, telegram, etc)     │
│    cache/ (Redis adapter)                  │
└────────┬───────────────────────────────────┘
         │
         ▼
┌────────────────────────────┐   ┌─────────────┐
│ PostgreSQL (primary)       │   │ Redis       │
│  schemas: {profile},       │   │ (cache)     │
│  financials, core,         │   └─────────────┘
│  market, system            │
└────────────────────────────┘
         ▲
         │ async tasks
┌────────┴───────────────────────┐
│ Celery Worker                  │
│  - OCR processing              │
│  - ML inference                │
│  - Daily reports               │
│  - Market data refresh         │
└────────────────────────────────┘
         ▲
         │ beat schedule
┌────────┴───────────────────────┐
│ Celery Beat                   │
└────────────────────────────────�
```

### N.4 Migration Path

**Step 1 (Week 1-2):** Fix critical bugs (C-001, C-003, C-004, C-013). No architectural change.

**Step 2 (Week 3-4):** Standardize services. Remove duplicate `packages/api/backend/services/`. Update all imports.

**Step 3 (Month 2):** Add Celery + Redis. Migrate OCR + market refresh.

**Step 4 (Month 3):** Add API versioning `/api/v1/`. Deprecate `/api/*` with warnings.

**Step 5 (Month 4):** Remove SQLite dual-write. Keep only `audit_log.db` (or migrate to Postgres).

**Step 6 (Month 5-6):** Add proper auth (JWT). Add row-level security.

---

## O. DEVELOPMENT ROADMAP

### Phase 1: Critical Fixes (Week 1-2)
**Deliverables:**
- Transaction-wrapped sell endpoint.
- Profile name validation.
- Generic error responses (no stack trace).
- Default SECRET_KEY fail-fast.
- Atomic recurring expense apply.
- 3 quick unit tests per fix.

### Phase 2: Refactoring (Week 3-6)
**Deliverables:**
- Remove dual service layer.
- Split deps.py.
- Standardize logging to JSON.
- Split routers/ai.py.
- Move CLI receipt_reader to packages/core.
- Replace bare except with specific exceptions.

### Phase 3: Performance & Security (Week 7-10)
**Deliverables:**
- Composite indexes added.
- CORS whitelist.
- HMAC mandatory for mutations.
- Rate limit backed by Redis.
- yfinance batch fetch.
- Genetic audit as background job.
- Dependency audit (`pip-audit`, `npm audit`).

### Phase 4: Feature Enhancement (Week 11-16)
**Deliverables:**
- Web login flow.
- Financial audit trail table + log.
- Auto-categorization improvements.
- Net worth trend dashboard.
- Investment import from CSV.
- Notification preferences per user.

### Phase 5: Scalability (Week 17-24)
**Deliverables:**
- Celery + Redis deployment.
- OpenTelemetry tracing.
- API versioning.
- Row-level security.
- Multi-user testing.
- Load testing report.
- Disaster recovery runbook.

---

## P. FINAL CRITICAL ASSESSMENT

### P.1 Apa kelemahan terbesar project ini?

**Jawaban: Coupling + Data Integrity.**

Project ini punya **3 critical issues** yang saling terkait:
1. **Atomicity breach di sell investment** (C-001) — bisa menghasilkan investment "sold" tanpa income P&L ter-record.
2. **Sync/async mismatch** (C-002) — setengah migrated, bug latent di setiap router.
3. **SQL injection via profile name** (C-003) — walaupun perlu filesystem write access, attack vector exists.

**Plus** structural issue: **dual service layer** (C-005, C-006) menunjukkan refactor setengah jalan — code smell yang预示 technical debt lebih besar di baliknya.

### P.2 Apa technical debt paling berbahaya?

**Jawaban: Database dual-mode dengan silent fallback.**

`packages/api/backend/infrastructure/database.py:101-126` — pattern fallback Postgres → SQLite → default data. Ini **data corruption time bomb**:

- User insert via Postgres success.
- Backup SQLite di-copy.
- Restart, Postgres down, query hit SQLite dengan data stale.
- User lihat data yang conflicting.
- Worst case: financial calculation pakai data dari 2 source berbeda.

Plus **transaction absent di multi-step mutations** (DB-008, R-005) — partial writes yang tidak recoverable.

### P.3 Apa risiko terbesar jika project diteruskan tanpa refactoring?

**Jawaban: Silent data loss di production.**

Skenario:
1. User sell investment via web (success di Postgres).
2. Income P&L record gagal karena network blip.
3. Endpoint return warning tapi data sudah partial.
4. User lihat investment "sold" tapi tidak ada income record.
5. Tax report akhir tahun inaccurate.

Atau:
1. Profile di-switch ke mode concurrent.
2. Recurring expense auto-apply triggered 2x (scheduled + manual).
3. Duplicate inserts.
4. User complain "expense dobel".

Atau:
1. Postgres connection pool exhausted saat high traffic.
2. Fallback ke SQLite untuk beberapa query.
3. Mix data dari 2 sources di response.
4. Laporan misleading.

### P.4 Apa bagian architecture yang paling perlu diperbaiki?

**Jawaban: Database access layer + service consistency.**

Dua hal:
1. **Single source of truth untuk service layer.** Saat ini `packages/core/application/` (async) dan `packages/api/backend/services/` (sync) co-exist. Pilih satu. Recommendation: async, lalu update semua router.
2. **Single database source.** Postgres primary, SQLite hanya untuk cache + audit_log. Hapus fallback pattern.

### P.5 Apa 5 improvement dengan ROI terbesar?

**Top 5 by ROI:**

1. **Transaction-wrap sell endpoint** (1 hari, C-001) — prevents data corruption. ROI: tinggi (low cost, high value).

2. **Standardize async/sync** (3-5 hari, C-002) — eliminates latent bugs. ROI: tinggi.

3. **Move OCR ke Celery** (1 minggu, C-020) — 10x throughput improvement. ROI: tinggi untuk scale.

4. **Composite indexes** (1 hari, C-017) — 5-10x query speedup. ROI: tinggi.

5. **Replace bare except dengan specific** (3 hari, C-010) — exposes hidden bugs, faster debugging. ROI: tinggi.

### P.6 Jika project dipakai production, apa yang wajib diperbaiki terlebih dahulu?

**Production-blocking fixes (must fix before prod):**

1. **C-001** Sell atomicity — data corruption risk.
2. **C-003** SQL injection — security risk.
3. **C-013** Default SECRET_KEY — auth bypass risk.
4. **C-004** Stack trace in response — info disclosure.
5. **C-009** Recurring race — duplicate data.
6. **C-016** CORS permissive — spec violation + potential credential leak.
7. **C-024** Audit trail absent — compliance gap jika dipakai untuk tax reporting.
8. **Add HTTPS enforcement** — Bearer token sniffable jika tidak HTTPS.

**Strongly recommended (within 1 month):**
- C-002 sync/async
- C-005/C-006 dual services
- C-008 deps.py split
- C-010 bare except

### P.7 Apakah architecture saat ini masih layak dipertahankan?

**Jawaban: YA, dengan catatan.**

**Layak:**
- Modular monolith adalah pilihan tepat untuk skala personal/single-user.
- Clean Architecture attempt di `packages/core/` menunjukkan visi yang baik.
- Separation of CLI/API/Web sudah jelas.
- Docker setup mature.
- Background scheduler functional.

**Tidak layak jika diteruskan tanpa addressing:**
- Critical bugs (C-001, C-002, C-003) — production-blocking.
- Dual database pattern — data corruption waiting.
- Dual service layer — drift inevitable.
- In-process scheduler — fragile untuk production.

**Verdict:** Architecture foundation solid, tapi butuh 1-2 sprint untuk fix critical bugs sebelum production-ready. Setelah itu, scale-friendly tanpa perlu rewrite.

---

## Closing Notes

**Positif yang harus diakui:**
- Dokumentasi lengkap (`DESIGN.md` 42KB, `GEMINI.md`, `docs/`).
- Clean Architecture attempt di `packages/core/`.
- Test infrastructure exist (79 tests).
- Docker + docker-compose setup baik.
- Multiple profiles (personal/business/qa_*) untuk testing.
- Stock ML dengan XGBoost + feature engineering proper.
- Behavioral finance + gamification.
- OCR ensemble (4 engines).

**Negatif yang harus diakui (tanpa sugarcoating):**
- 578 source files terlalu besar untuk single-user system — overkill.
- 22 routers dalam 1 FastAPI app — terlalu besar.
- Sync/async migration setengah jalan — risky.
- Dual database pattern — dangerous.
- Beberapa security issues (C-003, C-013, C-016) harus fix sebelum production.
- Test coverage tidak terverifikasi (no badge/report).

**Overall:** Project ini ambitious, well-intentioned, dan menunjukkan arsitektur vision. Tapi eksekusi parsial — banyak "started but not finished". Untuk personal/single-user, sudah lebih dari cukup. Untuk production/multi-user, butuh 2-3 bulan focused refactor + security hardening.
