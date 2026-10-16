Last Updated: 29-05-2026 (14:30)

# Elite System Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a full 50-vector system audit post-monorepo refactor to ensure structural, financial, security, AI, and performance integrity across GUI and CLI.

**Architecture:** Systematic audit grouping the 50 Elite Matrix vectors into batches, preceded by a "Gate 0" structural reconciliation and followed by container-based end-to-end validation.

**Tech Stack:** Python (pytest, cProfile), Next.js (Playwright), Docker, Chrome DevTools MCP.

---

### Task 1: Gate 0 Structural Reconciliation

**Files:**
- Create: `tests/reconciliation/test_imports.py`
- Modify: `packages/core/domain/models/account.py`
- Modify: `apps/cli/main.py`
- Modify: `apps/web/package.json`

- [ ] **Step 1: Create audit branch**
Run: `git checkout -b audit/elite-stability-matrix`

- [ ] **Step 2: Unify VirtualAccount model**
Update `packages/core/domain/models/account.py` to include `cashflow_velocity` and `sankey_node_id`.
```python
class VirtualAccount(BaseModel):
    id: str
    name: str
    balance: Decimal
    cashflow_velocity: Decimal = Decimal("0.0")
    sankey_node_id: Optional[str] = None
```

- [ ] **Step 3: Refactor CLI imports**
Update `apps/cli/main.py` to use `packages.core`.
```python
from packages.core.domain.models.account import VirtualAccount
```

- [ ] **Step 4: Verify imports**
Run: `pytest tests/reconciliation/test_imports.py`
Expected: PASS (no ModuleNotFoundError)

- [ ] **Step 5: Commit**
Run: `git add . && git commit -m "refactor: gate 0 structural reconciliation"`

---

### Task 2: Infrastructure Audit (Batch A)

**Files:**
- Create: `tests/audit/batch_a/test_1_1_root_detection.py`
- Create: `tests/audit/batch_a/test_1_2_thread_safety.py`
- Modify: `packages/core/infrastructure/config.py`

- [ ] **Step 1: Write root detection test (Vector 1.1)**
Create `tests/audit/batch_a/test_1_1_root_detection.py` that mocks deep symlinks.

- [ ] **Step 2: Implement thread-safe singleton (Vector 1.2)**
Modify `packages/core/infrastructure/config.py`:
```python
import threading
class Config:
    _lock = threading.Lock()
    _instance = None
    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
        return cls._instance
```

- [ ] **Step 3: Run Batch A tests**
Run: `pytest tests/audit/batch_a/`
Expected: PASS

---

### Task 3: Financial Integrity Audit (Batch B)

**Files:**
- Create: `tests/audit/batch_b/test_2_1_decimal_precision.py`
- Create: `tests/audit/batch_b/test_2_2_lot_fragmentation.py`

- [ ] **Step 1: Write decimal precision test (Vector 2.1)**
Verify `0.1 + 0.2 == 0.3` using `Decimal`.

- [ ] **Step 2: Write lot fragmentation test (Vector 2.2)**
Simulate selling `1e-8` BTC.

- [ ] **Step 3: Run Batch B tests**
Run: `pytest tests/audit/batch_b/`
Expected: PASS

---

### Task 4: Security & Defense Audit (Batch C)

**Files:**
- Create: `tests/audit/batch_c/test_3_1_sqli_fuzz.py`
- Create: `tests/audit/batch_c/test_3_7_hmac_replay.py`

- [ ] **Step 1: Implement SQLi protection audit (Vector 3.1)**
Test profile switcher with `' OR 1=1 --`.

- [ ] **Step 2: Implement HMAC chain audit (Vector 3.7)**
Modify a byte in `dummy_test.db` and verify system lockout.

- [ ] **Step 3: Run Batch C tests**
Run: `pytest tests/audit/batch_c/`
Expected: PASS

---

### Task 5: AI/ML Service Chaos Audit (Batch D)

**Files:**
- Create: `tests/audit/batch_d/test_4_2_adversarial_receipt.py`
- Create: `scripts/generate_fake_receipts.py`

- [ ] **Step 1: Generate synthetic adversarial receipts**
Use `PIL` to create images with mismatched totals.

- [ ] **Step 2: Run consensus audit (Vector 4.2)**
Verify OCR flags low confidence on mismatched receipts.

---

### Task 6: Performance & Leak Analysis (Batch E)

**Files:**
- Create: `tests/audit/batch_e/test_5_2_ui_leaks.js`
- Create: `tests/audit/batch_e/test_5_6_handle_leaks.py`

- [ ] **Step 1: Profile UI leaks (Vector 5.2)**
Use Playwright + Chrome DevTools MCP to check heap.

- [ ] **Step 2: Profile handle leaks (Vector 5.6)**
Open/close DB 1000x and check `psutil.Process().num_fds()`.

---

### Task 7: Full-Stack Stability Audit (GUI/CLI)

**Files:**
- Create: `tests/audit/e2e/test_gui_docker.py`
- Create: `tests/audit/e2e/test_cli_flows.py`

- [ ] **Step 1: Run GUI in Docker**
Run: `docker-compose up -d gui`
Verify health check at `localhost:3000`.

- [ ] **Step 2: Validate CLI flows**
Run all 8 main menu options in `apps/cli/main.py` using a wrapper script.

---

### Task 8: Consolidation & Reporting

**Files:**
- Create: `docs/planning/AUDIT_FINDINGS_20260525.md`
- Create: `docs/planning/STABILITY_REPORT.md`

- [ ] **Step 1: Aggregate reproduction logs**
- [ ] **Step 2: Write findings and final health score**

---

### Task 9: Archiving & Handoff

- [ ] **Step 1: Update .ai metadata**
- [ ] **Step 2: Merge fixes to testing**
- [ ] **Step 3: Archive session**
