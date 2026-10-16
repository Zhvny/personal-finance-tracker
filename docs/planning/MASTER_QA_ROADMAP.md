# 🗺️ Master QA & Debugging Roadmap: Finance Tracker v10.0

This document defines the exhaustive plan for stabilizing, auditing, and verifying the Finance Tracker ecosystem. It is divided into five specialized "Battlefronts."

---

## 🏗️ Phase 1: Infrastructure & Core Stability (Foundation)
**Goal:** Eliminate "Broken State" and ensure the system is buildable and bootable across all environments.

### 1.1 Root Pathing & Config Stabilization
- **Task 1.1.1:** Implement `RootFinder` utility using marker files (`GEMINI.md`).
- **Task 1.1.2:** Resolve `packages/core` merge conflicts and unify imports.
- **Task 1.1.3:** Audit `PYTHONPATH` in all `.bat` and `Dockerfile` scripts.
- **Debug Scenario:** "Application runs from root but fails when called from a subdirectory."
- **DoD:** `python -m packages.core.infrastructure.config` returns valid absolute paths in Windows and Linux.

### 1.2 Dependency & Environment Audit
- **Task 1.2.1:** Synchronize `requirements.txt` across `apps/cli`, `apps/api`, and `packages/core`.
- **Task 1.2.2:** Implement `.env.schema` validation on startup (fail-fast if keys are missing).
- **Task 1.2.3:** Verify Node.js/PNPM workspace integrity for the GUI.
- **DoD:** `setup.bat` completes in < 5 minutes on a clean machine.

---

## 📈 Phase 2: Financial Integrity & Math Audit (The Core)
**Goal:** Ensure 100% mathematical accuracy for all wealth calculations.

### 2.1 FIFO & Investment Logic
- **Task 2.1.1:** Unit test for "Partial Sell" scenarios (Selling 50 shares of a 100-share lot).
- **Task 2.1.2:** Audit "Lot Washing" prevention (ensuring sold lots aren't reused).
- **Task 2.1.3:** Verify Corporate Action handling (Stock Splits/Reverse Splits).
- **Debug Scenario:** "Total Portfolio Value doesn't match sum of individual holdings after a sell."
- **DoD:** Zero variance in a 1,000-transaction simulation.

### 2.2 Indonesian Tax (PPh 21) & FX Resolution
- **Task 2.2.1:** Implement regression tests for 2024-2026 progressive tax brackets (5% to 35%).
- **Task 2.2.2:** Test dynamic USD/IDR fallback (Postgres -> SQLite -> Hardcoded).
- **Task 2.2.3:** Verify PTKP (Non-taxable income) logic for different marital statuses.
- **DoD:** Tax calculations match official government calculators to within 1 IDR.

---

## 🛡️ Phase 3: Data Security & Multi-Profile Isolation (The Shield)
**Goal:** Guarantee zero data leakage and transaction immutability.

### 3.1 Multi-Profile Physical Isolation
- **Task 3.1.1:** Stress test the "Switcher" (switching profiles 100x rapidly).
- **Task 3.1.2:** Verify that `apps/cli/profiles/Business` cannot access `profiles/Personal` DB files.
- **Task 3.1.3:** Audit `goals.db` for Row-Level Security (RLS) bypasses.
- **DoD:** Automated "Leak Test" script returns 0 found cross-profile IDs.

### 3.2 Immutability & Disaster Recovery
- **Task 3.2.1:** Verify `audit_log.db` HMAC hashing (detecting manual DB edits).
- **Task 3.2.2:** Test `scripts/dr_backup.py` for cloud-sync integrity (Supabase).
- **Task 3.2.3:** Implement "Dry Run" restoration to verify backup viability.
- **DoD:** Manual database tampering is detected and flagged on next boot.

---

## 🧠 Phase 4: AI & Analytical Service Validation (The Brain)
**Goal:** Transition from "AI Theater" to verifiable analytical confidence.

### 4.1 OCR Ensemble & Merchant Intelligence
- **Task 4.1.1:** Run 100-receipt benchmark for Tesseract vs. EasyOCR vs. PaddleOCR.
- **Task 4.1.2:** Tune Fuzzy Matching in `merchant_map.db` to prevent category drift.
- **Task 4.1.3:** Verify "Uncertainty Flags" for low-confidence OCR extractions.
- **DoD:** >95% accuracy for "Total Amount" and "Date" fields across diverse receipt formats.

### 4.2 Senate Service & ML Sniper Audit
- **Task 4.2.1:** Verify "Regime-Aware" weighting (e.g., giving the 'Value' agent more weight in bear markets).
- **Task 4.2.2:** Audit `genetic_audit.db` for the ML Optimizer's MAE (Mean Absolute Error).
- **Task 4.2.3:** Test `ButterflyService` for DXY/Gold correlation lag.
- **DoD:** Senate predictions outperform a "Random Buy" strategy by at least 15% in backtests.

---

## 🌐 Phase 5: API & UI Orchestration (The Interface)
**Goal:** Provide a seamless, high-performance experience across CLI and GUI.

### 5.1 API Bridge & Performance
- **Task 5.1.1:** Audit FastAPI middleware for latency overhead.
- **Task 5.1.2:** Implement Pydantic schema validation for all incoming financial payloads.
- **Task 5.1.3:** Test SSE (Server-Sent Events) for real-time market price updates.
- **DoD:** API response time < 150ms for 95th percentile of requests.

### 5.2 GUI Fidelity & State Parity
- **Task 5.2.1:** Verify "Data Parity" (GUI shows the same balance as CLI).
- **Task 5.2.2:** Audit React "Lazy Loading" for large transaction lists (>10,000 items).
- **Task 5.2.3:** Test Responsive Design on 4.7" (iPhone SE) vs. 32" (4K Desktop).
- **DoD:** Zero UI "jank" (60 FPS) during heavy data filtering/sorting.

---
**Last Updated:** 25-05-2026 (21:30)
