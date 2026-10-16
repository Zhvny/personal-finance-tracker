Last Updated: 29-05-2026 (14:30)

# System Remediation Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement missing repository methods and remove residual QA profile data.

**Architecture:** Extend SQLiteInvestmentRepository with ticker-specific query methods using existing mapping patterns. Clean up non-standard test profiles.

**Tech Stack:** Python, SQLite, PowerShell

---

### Task 1: Implement get_all_lots_by_ticker

**Files:**
- Modify: `packages/core/infrastructure/investment_tracker/sqlite_repository.py`

- [ ] **Step 1: Add method implementation**

```python
    def get_all_lots_by_ticker(self, ticker: str) -> List[Investment]:
        """Fetch all investment records for a specific ticker, ordered by buy_date ASC."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM investments WHERE ticker = ? ORDER BY buy_date ASC",
                (ticker,)
            ).fetchall()
            return [self._map_row_to_investment(row) for row in rows]
```

- [ ] **Step 2: Verify code placement**
Ensure it is placed before `_map_row_to_investment`.

### Task 2: Implement get_all_sell_transactions_by_ticker

**Files:**
- Modify: `packages/core/infrastructure/investment_tracker/sqlite_repository.py`

- [ ] **Step 1: Add method implementation**

```python
    def get_all_sell_transactions_by_ticker(self, ticker: str) -> List[SellTransaction]:
        """Fetch all sell transactions for a specific ticker, ordered by sell_date DESC."""
        sql = """
            SELECT s.*, i.ticker, i.asset_type
            FROM sell_transactions s
            JOIN investments i ON s.investment_id = i.id
            WHERE i.ticker = ?
            ORDER BY s.sell_date DESC
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (ticker,)).fetchall()
            return [self._map_row_to_sell_transaction(row) for row in rows]
```

### Task 3: Profile Cleanup

**Files:**
- Delete: `apps/cli/profiles/qa_financial/`

- [ ] **Step 1: Remove directory**

Run: `Remove-Item -Recurse -Force "apps/cli/profiles/qa_financial/"`

### Task 4: Final Validation

- [ ] **Step 1: Run health check**

Run: `python scripts/health_check.py`
Expected: Profile integrity PASS.
