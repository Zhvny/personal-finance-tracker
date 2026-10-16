Last Updated: 29-05-2026 (14:30)

# Logging Overhaul & TUI Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul logging levels and add a centralized Grafana-style dashboard to the TUI.

**Architecture:** Centralized `LoggingManager` in `packages/core` for recording, and a `Textual` dashboard in `apps/cli/tui.py` for visualization. CLI remains log-free in its console output.

**Tech Stack:** Python standard `logging`, `Textual`, `Rich`.

---

### Task 1: Centralized Logging Infrastructure

**Files:**
- Create: `finance-tracker/packages/core/infrastructure/logging.py`
- Modify: `finance-tracker/packages/core/infrastructure/config.py`

- [ ] **Step 1: Create the Logging Manager**
Implement a singleton or factory to configure logging with `RotatingFileHandler`. Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL.

- [ ] **Step 2: Update Config to support Log Paths**
Add `LOG_DIR` and log file paths to the `Config` class.

- [ ] **Step 3: Test Logger Initialization**
Write a temporary script to verify that `get_logger()` creates the files and writes at the correct levels.

---

### Task 2: Refactor Existing Modules

**Files:**
- Modify: `finance-tracker/apps/cli/main.py`
- Modify: `finance-tracker/apps/cli/scheduler.py`
- Modify: `finance-tracker/packages/api/api_server.py`

- [ ] **Step 1: Update main.py**
Remove localized logging setup. Initialize the central logger quietly.

- [ ] **Step 2: Update Scheduler and API**
Replace `logging.basicConfig` with the new centralized logger.

---

### Task 3: Build TUI Logging Dashboard

**Files:**
- Create: `finance-tracker/apps/cli/widgets/log_panel.py`
- Modify: `finance-tracker/apps/cli/tui.py`

- [ ] **Step 1: Create LogStream Widget**
Build a `Textual` widget that reads `app.log` and displays it with syntax highlighting based on levels.

- [ ] **Step 2: Integrate into TUI**
Add a new screen or panel to `DesktopTUI` for logs.

- [ ] **Step 3: Add Menu Option**
Update `on_mount` in `DesktopTUI` to include "6. LOGS".

---

### Task 4: Validation & Cleanup

- [ ] **Step 1: Verify CLI Silence**
Run CLI commands and ensure NO logs appear in the console.

- [ ] **Step 2: Verify TUI Dashboard**
Open the TUI, navigate to LOGS, and ensure live updates work.

- [ ] **Step 3: Verify Log Levels**
Check `app.log` to ensure all levels are recorded correctly.
