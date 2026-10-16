Last Updated: 29-05-2026 (14:30)

# Design Document: Centralized Logging & TUI Dashboard

**Date:** 2026-05-26
**Project:** Finance Tracker (Independent)
**Topic:** Logging Overhaul & Dashboard

## 1. Objective
Overhaul the logging system to provide standardized log levels across all modules and implement a centralized, Grafana-style dashboard within the TUI (GUI in terminal) for real-time monitoring.

## 2. Architectural Design

### 2.1 Centralized Logging (The Record)
All modules (CLI, Scheduler, API, etc.) will use a unified logging configuration to ensure consistency.

- **Component:** `packages/core/infrastructure/logging.py`
- **Levels:** `DEBUG` > `INFO` > `WARNING` > `ERROR` > `CRITICAL`
- **Output:** 
    - `logs/app.log`: Rotating file containing all logs.
    - `logs/error.log`: Rotating file containing only ERROR and CRITICAL levels.
- **Independence:** This manager will be self-contained within `finance-tracker/`.

### 2.2 TUI Dashboard (The Visualization)
The existing `Textual` application in `apps/cli/tui.py` will be extended with a new "Logging Dashboard" view.

- **Component:** `apps/cli/logs_dashboard.py` (integrated into `DesktopTUI`)
- **Visual Features:**
    - **Real-time Stream:** Tail logic to display new log entries.
    - **Color Coding:** Standard colors for levels (Dim white for DEBUG, Cyan for INFO, Yellow for WARNING, Red for ERROR, Bold Red for CRITICAL).
    - **Metrics Bar:** Counters for errors/warnings in the current session.
    - **Level Filter:** Interactive toggle to show/hide specific levels.
- **Non-CLI Display:** Per requirement, the CLI (`main.py`) will NOT display logs. It will only initialize the logger to save to disk.

## 3. Implementation Strategy

### Phase 1: Infrastructure
1. Create `packages/core/infrastructure/logging.py`.
2. Refactor existing modules to import and use the centralized logger.
3. Update `apps/cli/main.py` to initialize logging quietly.

### Phase 2: Dashboard Implementation
1. Develop `LogStream` widget in `Textual`.
2. Integrate `LogsDashboard` into `DesktopTUI` in `apps/cli/tui.py`.
3. Add "6. LOGS" to the TUI menu.

### Phase 3: Validation
1. Verify log rotation and level filtering.
2. Ensure no logs leak into the standard CLI output.
3. Stress test the dashboard with high log volume.

## 4. Success Criteria
- [ ] Centralized logging is used by all `finance-tracker` components.
- [ ] Log levels follow the DEBUG > INFO > WARNING > ERROR > CRITICAL hierarchy.
- [ ] CLI remains clean (no logs in console).
- [ ] TUI provides a functional, real-time logging dashboard.
