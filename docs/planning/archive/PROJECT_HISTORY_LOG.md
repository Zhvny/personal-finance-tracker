Last Updated: 29-05-2026 (14:30)

# 📜 Project History & Milestone Logs

Comprehensive record of project achievements, version history, and historical technical debt.

### [Tasks 1, 2 & 5 UI Refinement] – 2026-05-12
- **Remove Aggressive Warning Banner**: Stripped persistent infrastructure-level warnings (API keys, backend details) from the GUI.
- **Refactored AIInsightPanel**: Redesigned empty states to be consumer-grade; removed developer-oriented setup instructions.
- **Replace With Passive Status Indicator**: Replaced interactive `AIStatusBadge` with `AIPassiveStatus`.
- **Visual Consistency Audit**: Harmonized new components with theme variables (`var(--ind-d)`, `var(--gr)`), circular radii, and pixel-perfect vertical alignment. Verified mobile responsiveness.
- **Cleanup**: Deprecated and deleted `AIStatusBadge.jsx`.

### [DXY Asynchronous Panel & Divergence Tooltip] – 2026-05-14
- **Independent DXY Fetching**: Decoupled DXY loading from the main analysis pipeline.
- **Async Recovery & Caching**: Verified background sync, cache refresh (TTL: 300s), and stale data replacement.
- **Regression Testing**: Successfully passed `tests/regression/test_dxy_async.py` covering restart, refresh, and failure recovery scenarios.
- **UI States**: Implemented specific states: `Macro data syncing`, `DXY unavailable`, and `Awaiting correlation data`.

---

## 🏆 Completed Milestones (v10.2)

### [v10.2] – 2026-05-09 (Profile Logic & Business Isolation)
- **Task 1: Profile Logic & Data Isolation**: Centralized profile switching in `config.py` with feature gating.
- **Business Report Engine**: `BusinessReportService` for quarterly Excel reports.
- **Dashboard Ticker Starring**: support for starred tickers (*) and 5-min auto-refresh.
- **Schema Isolation**: Verified physical isolation in PostgreSQL.

### [v10.1] – 2026-05-09 (Maintenance & Infrastructure)
- **Butterfly Effect Correlation Engine**: `ButterflyService` with Pearson correlation mapping macro risks.
- **Dashboard Optimization**: Streamlit auto-refresh and CLI macro insights.
- **Enhanced Health Monitoring**: Upgraded `health_check.py`.
- **Quota & Profile Isolation**: `Profile` domain model with quota tracking.
- **Testing Infrastructure**: Initialized `pytest` suite.
- **Code Quality**: Strict Type Safety refactor.

### [v10.0] – 2026-05-08 (The "Remedial Truth" Update)
- **Governance Restoration**: Re-established v10.0 as authoritative.
- **Audit Remediation**: Documented hallucinations and scrubbing attempts.
- **Infrastructure Confirmation**: Final confirmation of PostgreSQL as SSOT.

### [v2.2.0] – 2026-05-03 (The "Legit Sniper" Release)
- Purged deceptive implementations.
- ML Engine Upgrade: Replaced EMA-slope heuristics with **XGBRegressor**.

### [v2.1.10] – 2026-04-27 (Infrastructure Modernization)
- **PostgreSQL Genesis**: Migration of 20+ SQLite databases to Postgres.

---

## 📝 Documentation Log: 2026-05-09

### 1. Files Updated
- `master-plan.md`, `PHASE_5_STATUS_REPORT.md`, `COMPLETED_MILESTONES.md`.

### 2. Technical Summary
- **ButterflyService**: Pearson correlation calculation, caching in `butterfly_cache.json`.
- **Streamlit Refresh**: JS trigger (300s).
- **CLI Dashboard**: Real-time macro correlation display.

### 3. Verification Evidence
- **Correlation Logic**: Verified with `test_butterfly.py` (AAPL +0.56 vs SPY).
- **Auto-Refresh**: Confirmed JS execution.
- **Cache Integrity**: Confirmed `butterfly_cache.json` creation.

---

## 🚩 Historical Technical Debt & Pain Points

### Audit Findings (2026-05-08)
1. **PostgreSQL Infrastructure Denial**: Master Plan claimed return to SQLite despite code confirming Postgres.
2. **Version Downgrade Attempt**: Attempt to force v2.2.1-Strategic over v10.0.
3. **"Ghost" Verification**: Hallucinated figures for Butterfly Service.
4. **Reality Scrubbing**: Deletion of critical documents (`TICKET_DEV_A`, `TICKET_DEV_B`).

### Long-Term Prevention
1. **Immutable History**: Strategic changes must be backed by backups/git.
2. **Log Integrity**: Automated verification of `usage.db`.
3. **Audit Trails**: Infrastructure changes must have associated ADRs.
