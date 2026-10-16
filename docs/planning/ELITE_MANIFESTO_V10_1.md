# 🏴‍☠️ THE ELITE QA MANIFESTO: MISSION-CRITICAL HARDENING (v10.1)

This is the definitive, low-level technical specification for turning the Finance Tracker into a fortress. No fluff. Just absolute system control.

---

## 🏗️ Battlefront 1: Structural & Environment Fortification
**Target:** 100% predictable execution in any environment.

### 1.1 Atomic Root & Marker-Chain Discovery
- **Deep Implementation:** Create `packages/core/infrastructure/shared/root.py` using `pathlib`.
- **Logic:**
    1.  Start at `__file__`.
    2.  Recurse upwards until a directory contains ALL of: `GEMINI.md`, `.setup_done`, `package.json`, AND `.git/`.
    3.  If root not found in 10 levels, RAISE `SystemExit` with environment dump.
    4.  Cache the result in a thread-safe singleton.
- **Verification:** Call from a virtualenv, a docker container, and a symlinked folder. Must resolve to the same canonical path.

### 1.2 Strict Monorepo Boundary Enforcement
- **Task:** Implement a custom `lint-imports.py` script.
- **Rule:** `apps/cli` CANNOT import from `apps/api`. `packages/core` CANNOT import from any `apps/`.
- **DoD:** CI fails if circular dependencies or boundary violations are detected.

---

## 💰 Battlefront 2: Financial Fuzzing & Invariant Sovereignty
**Target:** Mathematical proof of correctness.

### 2.1 The "Sovereign Math" Engine (Decimal-Only)
- **Task:** Systematic replacement of `float` with `decimal.Decimal` in:
    - `InvestmentTracker` (P/L, Cost Basis, Yield)
    - `ExpenseTracker` (Budget usage, Thresholds)
    - `IncomeTracker` (Net vs Gross, Tax brackets)
- **Quant Rule:** Every financial operation MUST specify rounding (e.g., `ROUND_HALF_UP`) and precision context.

### 2.2 Property-Based Fuzzing (The "Infinity" Test)
- **Framework:** `Hypothesis` + `pytest`.
- **Test Set 1 (FIFO Invariant):**
    ```python
    @given(transactions=st.lists(st.builds(Transaction, ...)))
    def test_fifo_integrity(transactions):
        # Invariant: Total Assets (H) + Total Sold (S) == Total Bought (B)
        # Invariant: Realized P/L + Unrealized P/L == Market_Value - Total_Cost
    ```
- **Test Set 2 (Tax Engine):** Generate 1,000,000 income profiles with varied marital status, PTKP, and bonuses. Compare against Indonesian Tax Law (UU HPP) 2024.

---

## 🛡️ Battlefront 3: Offensive Security & Zero-Day Mitigation
**Target:** Break the system before it's deployed.

### 3.1 SQLite Hardening & RLS Emulation
- **Task:** Implement "Row-Level Security" in the `Repository` layer.
- **Mechanism:** Every query `SELECT * FROM table` must be automatically intercepted and rewritten to `SELECT * FROM table WHERE profile_id = ?`.
- **Audit:** Use `bandit` for static analysis and `sqlmap` to try and bypass the RLS layer.

### 3.2 HMAC-SHA256 Audit Chain (The "Black Box")
- **Task:** For every write to `transactions.db`, calculate `HMAC(row_data + previous_row_hash, secret_key)`.
- **Storage:** Save hash in a hidden `_audit` table.
- **Verification:** On application start, verify the entire chain. If a single byte was changed by an external tool (SQLite Browser, etc.), the app LOCKS and requires a recovery key.

---

## 🧠 Battlefront 4: AI/ML Service Chaos & Reliability
**Target:** Verifiable intelligence, not "Hallucination-as-a-Service".

### 4.1 Senate "Regime-Switching" Stress Test
- **Task:** Implement `SenateService` Chaos Injector.
- **Scenario:** Force the `regime_service` to output 'EXTREME_VOLATILITY'.
- **Requirement:** `SenateService` must automatically reduce the weight of 'Momentum' agents and increase 'Risk' and 'Value' agents by exactly 40%.
- **Verification:** Log every internal weight calculation during the switch.

### 4.2 OCR Adversarial Benchmarking
- **Task:** Create a dataset of 500 "Evil Receipts":
    - Overlapping text.
    - Faded ink (low contrast).
    - Handwritten modifications to printed totals.
    - Multiple currencies on one page.
- **Logic:** Majority voting MUST return `Confidence: LOW` and trigger manual approval. If it "guesses" incorrectly, it counts as a failure.

---

## 🚀 Battlefront 5: Low-Level Performance & Leak Detection
**Target:** Efficient resource usage at scale.

### 5.1 Python Heap Analysis (memray)
- **Task:** Integrate `memray` into the test runner.
- **Baseline:** Measure memory usage after processing 50,000 transactions.
- **Leak Detection:** If memory grows >1% between transaction batch 1 and batch 100, fail the audit.

### 5.2 React Rendering Audit (GUI)
- **Task:** Use `React.Profiler` to identify "Wasted Renders" in the dashboard.
- **Metric:** Main Dashboard load time must be <100ms with a 10,000 row dataset.
- **Constraint:** Use Web Workers for heavy financial calculations to keep the UI thread at 60 FPS.

---

## 📋 Granular Task List (Part 1: Infra)
| ID | Task | Code Level | DoD |
| :--- | :--- | :--- | :--- |
| **1.1.1** | Fix `config.py` Conflict | Resolve markers; implement `find_root()`. | No syntax errors; `BASE_DIR` is absolute. |
| **1.1.2** | Marker-Chain Verifier | Add `.git` and `package.json` check to root. | Safe for symlinked or nested folders. |
| **1.1.3** | Idempotent sys.path | Inject root to `sys.path` only if missing. | No duplicate paths in `sys.path`. |
| **1.1.4** | Registry Migration | Move `packages/cli` references to `apps/cli`. | Zero `ModuleNotFoundError` during collect. |
| **1.1.5** | Health Check Utility | Script to verify all DB paths exist. | Returns JSON report of system health. |

---
**Status:** ELITE RED-TEAM PROTOCOL
**Complexity:** MAX
**Last Updated:** 25-05-2026 (22:00)
