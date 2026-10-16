Last Updated: 29-05-2026 (14:30)

# Core Financial Flows Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate the QA testing for Core Financial Flows (A, B, C, J) of the Finance Tracker CLI.

**Architecture:** A Python-based automation suite using `subprocess` to drive the CLI and `pytest` for orchestration and assertions. It will target a clean test profile to ensure isolation and repeatable results.

**Tech Stack:** Python 3, Pytest, Subprocess.

---

### Task 1: Foundation & CLI Driver

**Files:**
- Create: `tests/automation/cli_driver.py`
- Create: `tests/automation/conftest.py`

- [ ] **Step 1: Implement `CLIDriver`**
Implement a class that can run `apps/cli/main.py` with a given list of inputs and return the output.

```python
import subprocess
import os
from pathlib import Path

class CLIDriver:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cli_path = project_root / "apps" / "cli" / "main.py"
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(project_root)
        
    def run(self, inputs: list, timeout=30):
        input_str = "\n".join(str(i) for i in inputs) + "\n"
        process = subprocess.Popen(
            ["python", str(self.cli_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=self.env,
            cwd=str(self.project_root)
        )
        stdout, _ = process.communicate(input=input_str, timeout=timeout)
        return stdout
```

- [ ] **Step 2: Setup Pytest Fixtures**
Create `conftest.py` to provide the `cli_driver` to tests.

- [ ] **Step 3: Verify CLI Driver**
Run a simple "Exit" test (input `0`) to confirm the driver works.

---

### Task 2: Flow A (Profile Isolation) Implementation

**Files:**
- Create: `tests/automation/test_flow_a_isolation.py`

- [ ] **Step 1: Write Isolation Test**
Implement a test that switches between Personal and Business profiles and verifies that data added in one is not visible in the other.

- [ ] **Step 2: Run and Verify**
Run: `pytest tests/automation/test_flow_a_isolation.py`

---

### Task 3: Flow J (Income Management) Implementation

**Files:**
- Create: `tests/automation/test_flow_j_income.py`

- [ ] **Step 1: Write Income Flow Test**
Implement a test to add income and verify it appears in the history.

- [ ] **Step 2: Run and Verify**
Run: `pytest tests/automation/test_flow_j_income.py`

---

### Task 4: Flow C (Expense & Budget) Implementation

**Files:**
- Create: `tests/automation/test_flow_c_expense.py`

- [ ] **Step 1: Write Expense Flow Test**
Implement a test to add an expense and verify it in the summary.

- [ ] **Step 2: Run and Verify**
Run: `pytest tests/automation/test_flow_c_expense.py`

---

### Task 5: Flow B (Investment & FIFO) Implementation

**Files:**
- Create: `tests/automation/test_flow_b_investment.py`

- [ ] **Step 1: Write Investment FIFO Test**
Implement the purchase of two lots and a partial sale, then verify the remaining units and P/L calculation.

- [ ] **Step 2: Run and Verify**
Run: `pytest tests/automation/test_flow_b_investment.py`

---

### Task 6: Unified Runner & Reporting

**Files:**
- Create: `tests/automation/run_core_flows.py`

- [ ] **Step 1: Create a simple script to run all core flows and report results.**

- [ ] **Step 2: Final Verification**
Run the unified script and ensure all tests pass.
