# Changelog

Semua perubahan penting pada Alpha didokumentasikan di sini. Format mengikuti
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); entri terbaru di atas.

> Konsolidasi dari `docs/maintenance/change-log.md` (terkini) dan
> `docs/maintenance/archive/change-log.md` (historis). Riwayat memakai beberapa seri
> nomor versi: seri `2.x` terkini (2026-07/08, era web/API), seri arsip `2.x`
> (2026-01–05, era **CLI/SQLite "Finance Tracker Ecosystem"**), dan seri `10.x`/`11.x`
> (2026-05/06, era monorepo `finance-tracker-gui`). Semua dipertahankan apa adanya.
> Entri arsip yang nomor versinya bertabrakan dengan seri terkini diberi suffix
> `(arsip: era CLI/SQLite)` agar heading tetap unik. Peristiwa yang belum diberi tag
> versi disimpan di `Unreleased`.

## [Unreleased]

### Changed

- **Isolasi per-profil (2026-09-18).** Data finansial diisolasi per profil via
  Postgres **schema-per-profile** + `search_path`. Prisma `multiSchema` dan semua
  `@@schema("alpha_*")` dihapus dari `packages/database/schema.prisma`; tabel jadi
  unqualified dan `packages/database/index.py` mengarahkan baca/tulis ke profil aktif.
  Data `alpha_*` lama dibiarkan (isolasi hanya untuk data baru).
- **Paritas skema.** Kolom `user_id` ditambahkan ke tabel per-profil
  `expenses`/`incomes`/`investments` di `per_profile_ddl.py`; schema `personal`/`business`
  existing di-ALTER (`ADD COLUMN IF NOT EXISTS user_id`).
- **Reads dipindah dari SQLite legacy (kosong) ke Postgres profile-scoped**:
  `analytics.py`, `balances.py`, `behavioral.py`, `advanced.py`, `income.py` (pajak),
  `health_score_service.py`, `safe_spend_service.py`.

### Added

- Helper bersama `pg_sum_income`/`pg_sum_expense` di `deps/domain_helpers.py`.
- Regression test `tests/regression/test_prisma_float_serialization.py`
  (Decimal→float Prisma, 8 test, verified red-on-revert).

### Fixed

- `deps/domain_helpers.py` yang kosong pasca-split M3 memulihkan `_get_cash_split`
  (penyebab `/api/balances` 500→502).
- `legacy_bridge._query` memulihkan `sqlite3.Row` dict-like (stub mengembalikan tuple).
- Koersi Decimal→float sebelum field Prisma `Float` (investment save, add_sell_transaction,
  expense save).
- `prune_sold_lots`: filter Prisma `None` tidak valid → `lte: 0`.
- Frontend: import `apiFetch`/`IconWarning`; migrasi `fetch()` mentah ke `apiFetch`;
  hapus route `/reward` duplikat (pertahankan `/earn`); guard `serveStatic` 503.

### Security

- Gate frontend dipindah dari `/config` publik ke `POST /api/auth/verify` yang
  terproteksi; hapus fallback token `"dev"`.
- `/api/config` kini `require_scope("read")` — semua `/api/*` seragam terautentikasi.
- Hapus log DEBUG yang membocorkan API key/bearer token di `shared/security/core.py`
  dan `routers/auth.py`.

## [2.2.0] - 2026-08-12

### Added

- `packages/core/utils/api_resilience.py` (`safe_requests_get`, `retry_with_backoff`).
- `packages/web/src/rewards/SelfRewards.jsx` (card list, modal emas, tab filter).
- Helper API Self-Rewards di `lustStore.js`; tab "My Rewards" di `LustDashboard.jsx`.
- Suite `tests/integration/test_external_api_hardening.py`.

### Hardened

- Integrasi API eksternal (CoinGecko, yfinance, FXService, FREDFetcher, TelegramNotifier)
  dengan verifikasi status code, retry otomatis 429/5xx, dan fallback data.

## [2.1.3] - 2026-07-20

### Added

- `packages/core/utils/telegram_notifier.py` (kirim pesan Telegram async/sync).
- `packages/api/telegram_handler.py` (query bahasa alami Indonesia, cek pocket, laporan).
- Integrasi handler ke webhook (`telegram_bot.py`) dan polling (`telegram_poll.py`).
- Notifikasi transaksi otomatis di `ExpenseService`/`IncomeService`.
- Alert batas budget (80% peringatan, 100% over-budget).
- Ringkasan harian terjadwal (08:00) di APScheduler.
- CLI TUI: Log Cockpit live (parsed level, filter, pencarian instan).

## [2.1.2] - 2026-07-20

### Added

- Konfigurasi token Telegram Bot webhook di `packages/api/.env`.
- Test routing/health Telegram bot di `packages/api/tests/test_telegram_bot.py`.
- Integrasi workflow `n8n_telegram_workflow.json` ke n8n lokal.

### Fixed

- Bug registrasi router `packages/api/api_server.py` (modul ber-prefix `packages.`).
- Server API lokal terverifikasi di `https://localhost:8444`.

## [11.3.0] - 2026-06-24

### Fixed

- Override `PRISMA_PY_DEBUG_GENERATOR=1` untuk bypass assertion engine Prisma.
- `KeyError: 'ym'` pada fallback SQLite saat mismatch schema.
- Provisioning schema Postgres `qa_financial` (18 tabel) saat startup.

## [11.2.0] - 2026-05-23

### Added

- Verifikasi isolasi multi-profil: nol kebocoran `personal`↔`business` via `search_path`.
- Fallback global `investment.fx_rates` (rename dari `legacy_fx_rates`).

### Fixed

- Hardcode schema `investment.` di `PostgresFXRepository`.
- Resolusi `fx_rates` dinamis (profil menimpa default global).

## [11.1.0] - 2026-05-22

### Changed

- Konsolidasi komponen halaman GUI ke `finance-tracker-gui/src/pages/`.
- Migrasi data legacy `financials` → schema profil aktif (`personal`).

### Fixed

- Normalisasi indikator DCDS/MRZG (flatten-before-process, MultiIndex yfinance).
- `search_path` mengecualikan `financials` (mencegah kebocoran).

## [11.0.0] - 2026-05-20

### Added

- Workflow rekayasa 7 langkah (Analyze→Plan→Execute→Validate→Document→Verify→Next).
- Design System Binance untuk TUI (`apps/cli/tui_components.py`).
- Subcommand `workflow` di `main.py` (setiap fitur wajib punya komponen UI).

## [2.4.0] - 2026-05-18

### Changed

- Validasi skalabilitas/stabilitas (Session 7): LCP 740 ms, ticker switch ~200 ms
  post-cache, stress test 50 switch tanpa kegagalan, RSS stabil 203 MB, bebas leak.

## [10.2.0] / [2.3.0] - 2026-05-08

### Added

- **Agent Senate (Phase 5)**: sistem voting 7 agen (Momentum, Value, Macro, Mean
  Reversion, Risk, Sentiment, Quant) dengan pembobotan regime-aware.
- **Genetic Optimizer**: tuner hyperparameter `XGBRegressor` (50 iterasi), model
  terbaik disimpan ke `models/prod/`, audit SQLite (`genetic_audit.db`).
- Scheduler: Job F (trigger bulanan genetic optimizer), daily audit evaluasi agen.
- Schema Postgres `audit` untuk melacak prediksi & hasil.

## [10.1.1] / [10.1.0] - 2026-05-08

### Added

- Dockerisasi produksi 3-stage (`~180 MB`), serving aset statis lewat FastAPI
  (tanpa Nginx), `requirements.prod.txt` versi terpaku.
- Scheduler bulanan (`apps/cli/scheduler.py`), Whale Profiler (Option 9).

### Fixed

- Revert status "DONE" palsu untuk Genetic Optimization & Whale Tracking.
- Purge dummy data dari `genetic_audit.db` (ganti run 50 iterasi nyata).

## [2.2.1] - 2026-05-07

### Changed

- Mulai "Agile Master Improvement Program" (Testing, Guardrails, Logging, Context, Types).
- Refactor menu dinamis `apps/cli/main.py` (feature gating Personal vs Business).
- Refactor dokumentasi `docs/` ke blueprints Markdown terstandar.

### Fixed

- SSOT logika CLI di `apps/cli/`; verifikasi infrastruktur SQLite + isolasi profil.
- FX historis date-aware untuk P/L; parameter binding SQL + perbandingan token constant-time.

## [2.2.0] - 2026-05-03 (arsip: era CLI/SQLite)

### Fixed

- Purge implementasi "Fake Done"; ganti heuristik EMA-slope dengan `XGBRegressor` nyata.
- Filter "Anti-Pucuk": penalti struktural untuk saham overextended (`MA20R > 1.06` / `RET5 > 10%`).
- Win rate dinamis dari `MLEngine.get_ticker_stats()`.

## [2.1.12] - 2026-05-02

### Fixed

- Restorasi `quick_analyze` (import `FREDFetcher`).
- Pathing portabel (root proyek relatif, bukan path lokal hardcoded).
- Standarisasi penamaan sinyal `MLEngine` ↔ `Backtester`.

## [2.1.11] - 2026-05-02

### Changed

- Refactor `DataFetcher`, `StockRepository`, `IncomeService`, `ExpenseService` ke PostgreSQL.
- Row-level locking + tuning `max_connections`; sinkronisasi real-time CLI↔GUI via Postgres.

## [2.1.10] - 2026-05-01

### Changed

- Konsolidasi 20+ file SQLite terdistribusi ke satu schema PostgreSQL.
- ETL migrasi SQLite→Postgres (tanpa kehilangan data).
- `DatabaseManager` dengan `ThreadedConnectionPool` (psycopg2).

## [2.1.9] - 2026-04-30

### Added

- Integrasi prediksi ML ke Kelly Criterion (position sizing).
- Seksi "H+1 Target Price" di TUI dan Web Dashboard.
- Logging prediksi harian berbasis Postgres.

## [2.1.8] - 2026-04-30

### Changed

- Migrasi `XGBClassifier` → `XGBRegressor` (forecast harga).
- Tuning hyperparameter hingga MAE < 1.5% pada validation set.

## [2.1.7] - 2026-04-29

### Changed

- Target regresi → `Close_Price_T+1`; `StandardScaler`/`MinMaxScaler` untuk normalisasi.
- Hapus "hacky zero padding" dari feature-shape.

## [2.1.6] - 2026-04-29

### Added

- Agent Senate awal (agen Agressive, Value, Contrarian).
- Sentiment core berbasis LLM (Gemini) untuk skor pengaruh berita.
- Lust Points dikaitkan dengan kepatuhan manajemen risiko.

## [2.1.5] - 2026-04-28

### Added

- Harga real-time (polling/websocket 5 menit).
- Sistem "Star/Favorite" ticker di dashboard.

## [2.1.4] - 2026-04-28

### Changed

- Integrasi ML probability + expected value ke position sizing.
- Proteksi volatilitas (reduksi lot otomatis untuk setup berisiko).

## [2.1.3] - 2026-04-27 (arsip: era CLI/SQLite)

### Changed

- Price Sniper v1.0: transisi dari klasifikasi arah ke regresi harga.
- Cakupan lintas pasar (US NYSE/NASDAQ + IDX).

## [2.1.2] - 2026-04-27 (arsip: era CLI/SQLite)

### Added

- Genesis arsitektur PostgreSQL; schema data historis untuk training ML.

## [2.1.1] - 2026-04-26

### Added

- ML Sniper v2.1 (3-class BUY/NEUTRAL/SELL, Thin Neutral Zone 0.1×ATR).
- Precision lock 90% (`>0.90` conviction + `>1.8×` volume spike); 27-vector microstructure.
- Universal API Bridge v2.2 (compatibility layer multi-schema, crash-proof routing).

### Fixed

- "Column not in index" di `02_feature_engineering.py`; normalisasi suffix `.JK` ticker.

## [2.1.0] - 2026-04-24

### Added

- Lust Engine 2.0 (rebalance 10×, multiplier bertingkat, Season 28 protocol).
- ML: resolusi `_PROJECT_ROOT` di `StockPredictor`.

### Fixed

- Port mismatch React (8000) vs FastAPI (8443).
- P/L memakai Live Market FX (bukan fallback basi).
- Prefix `APIRouter` `behavioral.py` di-flatten (hindari 307).

## [2.0.5] - 2026-03-15

### Added

- AI Vision (Claude-4-5) menggantikan Tesseract-only; blacklist Ollama (proteksi OOM).

### Fixed

- Memory leak `TrendChart` saat ganti tab.

## [2.0.0] - 2026-01-01

### Changed

- Peluncuran GUI React (`finance-tracker-gui`); migrasi CLI-to-DB → RESTful API.
- `AuthContext` + `audit_middleware`; pemisahan modular GUI/API/CLI/ML.

## [1.12.164] - 2025-11-20

### Added

- Suite Financial Behavior Score (impulse index, fragility scoring).
- Sistem transfer internal (kas ↔ tabungan bank); peningkatan CLI Rich TUI.

### Fixed

- Voting OCR ensemble berbobot; edge case "dust" pada penjualan crypto parsial.

## [1.11.0] - 2025-08-05

### Added

- Tax engine Indonesia (PPh 21 + PTKP + bracket progresif).
- Merchant Brain (fuzzy matching kategorisasi merchant).

## [1.0.0] - 2025-03-01

### Added

- CRUD awal Expenses/Income; penyimpanan SQLite; pelacakan investasi (saham).

## Sumber

- `docs/maintenance/change-log.md` (v2.2.0 2026-08-12, v2.1.3/v2.1.2 2026-07-20).
- `docs/maintenance/archive/change-log.md` (seri `11.x` dan `2.x` historis).
- `STATE.md` §Session 2026-09-18 (isolasi per-profil + perbaikan gateway/data) —
  entri ini **tidak** ada di `docs/maintenance/change-log.md`.
- `docs/SDD.md`, `docs/SRS.md`, `docs/TP.md`, `docs/API.md` (riwayat revisi 1.1,
  2026-09-18).
- `AGENTS.md` §Isolasi per-profil (2026-09-18), `docs/SCHEMA_AUTHORITY.md`.
