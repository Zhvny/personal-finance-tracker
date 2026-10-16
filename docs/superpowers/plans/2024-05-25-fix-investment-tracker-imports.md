Last Updated: 29-05-2026 (14:30)

# Fix Investment Tracker Absolute Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor absolute imports starting with `apps.cli.investment_tracker` to local imports across the `investment_tracker` module to improve portability and maintain consistency.

**Architecture:** Systematic replacement of absolute package paths with relative/local paths within the `apps/cli/investment_tracker/` directory tree.

**Tech Stack:** Python

---

### Task 1: Fix Imports in Core and UI

**Files:**
- Modify: `apps/cli/investment_tracker/core/__init__.py`
- Modify: `apps/cli/investment_tracker/ui/cli_view.py`

- [ ] **Step 1: Update `core/__init__.py`**
Replace `apps.cli.investment_tracker.core.calculator` with `core.calculator` and `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 2: Update `ui/cli_view.py`**
Replace `apps.cli.investment_tracker.core.calculator` with `core.calculator`.

- [ ] **Step 3: Verify changes**
Ensure no syntax errors.

### Task 2: Fix Imports in Services

**Files:**
- Modify: `apps/cli/investment_tracker/services/__init__.py`
- Modify: `apps/cli/investment_tracker/services/base_price_service.py`
- Modify: `apps/cli/investment_tracker/services/crypto_service.py`
- Modify: `apps/cli/investment_tracker/services/fx_service.py`
- Modify: `apps/cli/investment_tracker/services/gold_service.py`
- Modify: `apps/cli/investment_tracker/services/price_service.py`
- Modify: `apps/cli/investment_tracker/services/stock_service.py`

- [ ] **Step 1: Update `services/__init__.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 2: Update `services/base_price_service.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 3: Update `services/crypto_service.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 4: Update `services/fx_service.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 5: Update `services/gold_service.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 6: Update `services/price_service.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

- [ ] **Step 7: Update `services/stock_service.py`**
Replace `apps.cli.investment_tracker.core.interfaces` with `core.interfaces`.

### Task 3: Fix Fallback Imports in main.py

**Files:**
- Modify: `apps/cli/investment_tracker/main.py`

- [ ] **Step 1: Update `main.py`**
Replace all occurrences of `apps.cli.investment_tracker.` with nothing (making them local) in the `except ImportError` block. Keep `apps.cli.prediction_service` as is.

- [ ] **Step 2: Verify `main.py` execution**
Run the main script to ensure it still starts correctly.
Run: `python apps/cli/investment_tracker/main.py` (Wait, I might need to be in the right directory or have PYTHONPATH set. The script adds root to sys.path, so running from root should work).

---

Plan complete and saved to `docs/superpowers/plans/2024-05-25-fix-investment-tracker-imports.md`.

Which approach?
1. Subagent-Driven (recommended)
2. Inline Execution
