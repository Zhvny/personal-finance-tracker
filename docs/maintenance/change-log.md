# Change Log

## [2.2.0] - 12-08-2026 (06:00)

### Added
- Created `packages/core/utils/api_resilience.py` providing `safe_requests_get` and `retry_with_backoff` exponential backoff retry mechanism.
- Created `packages/web/src/rewards/SelfRewards.jsx` component featuring card list, creation modal with emoji picker, and tab filtering (All/Active/Redeemed).
- Integrated Self-Rewards API helper methods into `lustStore.js` (`fetchSelfRewards`, `createSelfReward`, `redeemSelfReward`, `deleteSelfReward`).
- Added Self-Rewards scoped styling in `rewards.css` and added "My Rewards" tab to `LustDashboard.jsx`.
- Added comprehensive unit and integration test suite `tests/integration/test_external_api_hardening.py` covering rate limits, HTTP errors, exponential backoff, and stale/fallback data recovery.

### Hardened
- Hardened external API integrations (`CoinGecko`, `yfinance`, `FXService`, `FREDFetcher`, `TelegramNotifier`) with status code verification, automatic retries on 429/5xx errors, and resilient fallback data mechanisms.

## [2.1.3] - 20-07-2026 (21:53)

### Added
- Created `packages/core/utils/telegram_notifier.py` to send real-time Telegram messages asynchronously and synchronously.
- Created `packages/api/telegram_handler.py` to parse natural language queries, add transactions via Indonesian text (e.g. `tambah pengeluaran 50000 makan siang`), check active pockets, and generate daily/monthly reports.
- Integrated central text handler into webhook (`packages/api/telegram_bot.py`) and polling (`packages/api/telegram_poll.py`) runners.
- Integrated automated transaction notifications into `ExpenseService` and `IncomeService`.
- Added automatic budget limit alerting check (80% near-limit warning and 100% over-budget alert) triggered after recording any new expense.
- Added scheduled daily financial summary reports (at 08:00 AM every day) to APScheduler in the API background runner (`packages/api/backend/automation/market_scheduler.py`).
- Upgraded the CLI TUI's Log screen in `apps/cli/tui.py` to a full Live Log Cockpit/Dashboard with real-time parsed level counting, filter highlights, source toggling (CLI vs API log files), and instant key-matching search query input.

## [2.1.2] - 20-07-2026 (01:37)

### Added
- Configured the Telegram Bot webhook API key token in `packages/api/.env`.
- Added unit and integration tests for Telegram bot routing and health checks in `packages/api/tests/test_telegram_bot.py`.
- Checked the local n8n service and successfully imported the `n8n_telegram_workflow.json` workflow directly into the local n8n database (`C:\Users\Zhvn\.n8n\database.sqlite`).
- Imported the Telegram Bot API credentials into n8n and linked them to the appropriate Telegram Trigger and messaging nodes.
- Configured HTTP Request nodes in the n8n workflow to run without API headers (simplified auth) and map requests directly to `localhost` (the local API server).
- Started and verified the local API server on `https://localhost:8444`.

### Fixed
- Fixed router registration import bug in `packages/api/api_server.py` where modules starting with `packages.` failed to load due to incorrect path prefixing. The loader now detects absolute imports starting with `packages.` and imports them directly.
