Last Updated: 29-05-2026 (14:30)

# Fix Date Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix date validation in Income and Expense models to allow any transaction on the current day by switching to date-only comparison.

**Architecture:** Update the `validate()` method in both `Income` and `Expense` models to compare `self.date.date()` against `datetime.now().date()`.

**Tech Stack:** Python 3.x, Dataclasses

---

### Task 1: Fix Expense Model Date Validation

**Files:**
- Modify: `packages/core/infrastructure/expense_tracker/models.py:59-61`

- [ ] **Step 1: Update validation logic**

```python
<<<<
        # Future date check (with 1 hour buffer for timezone/sync drift)
        if self.date > datetime.now().replace(microsecond=0) + timedelta(hours=1):
            raise ValueError("Transaction date cannot be in the future.")
====
        # Future date check: allow any time today, reject tomorrow+
        if self.date.date() > datetime.now().date():
            raise ValueError("Transaction date cannot be in the future.")
>>>>
```

- [ ] **Step 2: Commit**

```bash
git add packages/core/infrastructure/expense_tracker/models.py
git commit -m "fix(core): allow expense transactions on today's date"
```

### Task 2: Fix Income Model Date Validation

**Files:**
- Modify: `packages/core/infrastructure/income_tracker/models.py:38-39`

- [ ] **Step 1: Update validation logic**

```python
<<<<
        if self.date > datetime.now().replace(microsecond=0) + timedelta(hours=1):
            raise ValueError("Transaction date cannot be in the future.")
====
        # Future date check: allow any time today, reject tomorrow+
        if self.date.date() > datetime.now().date():
            raise ValueError("Transaction date cannot be in the future.")
>>>>
```

- [ ] **Step 2: Commit**

```bash
git add packages/core/infrastructure/income_tracker/models.py
git commit -m "fix(core): allow income transactions on today's date"
```
