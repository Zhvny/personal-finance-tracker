# Fix Backend Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix path resolution, dependency injection, and method signatures in the backend, and restore missing SqliteVirtualAccountRepository.

**Architecture:** Create missing repository, fix hardcoded paths in router, update service dependencies in deps.py, and ensure profile_id is passed to dashboard service.

**Tech Stack:** Python, FastAPI, SQLite, PostgreSQL

---

### Task 1: Create SqliteVirtualAccountRepository

**Files:**
- Create: `packages/core/infrastructure/persistence/sqlite_account_repository.py`

- [ ] **Step 1: Create the file with provided content**

```python
from typing import List, Optional
from packages.core.domain.repositories.account_repository import IVirtualAccountRepository
from packages.core.domain.models.account import VirtualAccount
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database

class SqliteVirtualAccountRepository(IVirtualAccountRepository):
    def __init__(self, db_path: Optional[str] = None):
        # Use Config.get_db_path("goals") which is where accounts are stored
        self.db_path = db_path or Config.get_db_path("goals")
        self._init_db()

    def _init_db(self):
        script = \"\"\"
            CREATE TABLE IF NOT EXISTS virtual_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_account_id INTEGER,
                balance REAL DEFAULT 0,
                target_amount REAL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                profile_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_va_profile ON virtual_accounts(profile_id);
        \"\"\"
        Database.execute_script(self.db_path, script)

    def save(self, account: VirtualAccount) -> int:
        sql = \"\"\"
            INSERT INTO virtual_accounts (name, parent_account_id, balance, target_amount, currency, profile_id)
            VALUES (?, ?, ?, ?, ?, ?)
        \"\"\"
        params = (account.name, account.parent_account_id, float(account.balance),
                  0.0, "IDR", account.profile_id) # Mapping to existing model fields
        result = Database.execute(self.db_path, sql, params)
        if result:
            account.id = str(result)
            return result
        return 0

    def get_all(self, profile_id: str) -> List[VirtualAccount]:
        sql = "SELECT * FROM virtual_accounts WHERE profile_id = ?"
        rows = Database.query(self.db_path, sql, (profile_id,))
        return [self._row_to_account(row) for row in rows]

    def get_by_id(self, account_id: int, profile_id: str) -> Optional[VirtualAccount]:
        sql = "SELECT * FROM virtual_accounts WHERE id = ? AND profile_id = ?"
        rows = Database.query(self.db_path, sql, (account_id, profile_id))
        if rows:
            return self._row_to_account(rows[0])
        return None

    def delete(self, account_id: int, profile_id: str) -> bool:
        sql = "DELETE FROM virtual_accounts WHERE id = ? AND profile_id = ?"
        result = Database.execute(self.db_path, sql, (account_id, profile_id))
        return bool(result)

    def update_balance(self, account_id: int, profile_id: str, new_balance: float) -> bool:
        sql = "UPDATE virtual_accounts SET balance = ? WHERE id = ? AND profile_id = ?"
        result = Database.execute(self.db_path, sql, (new_balance, account_id, profile_id))
        return bool(result)

    def _row_to_account(self, row: dict) -> VirtualAccount:
        return VirtualAccount(
            id=str(row["id"]),
            name=row["name"],
            balance=row["balance"],
            # cashflow_velocity and sankey_node_id can be default
        )
```

### Task 2: Fix Path Resolution in stocks.py

**Files:**
- Modify: `packages/api/backend/routers/stocks.py`

- [ ] **Step 1: Update path resolution and sys.path**

```python
<<<<
# Resolve paths
_HERE = Path(__file__).resolve().parent
_GUI = _HERE.parent.parent
_PROJECT_ROOT = _GUI.parent
_APPS = _PROJECT_ROOT / "apps"
_STOCK_ANALYZER = _APPS / "stock_analyzer"

if str(_APPS) not in sys.path: sys.path.insert(0, str(_APPS))
====
# Resolve paths
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent.parent
_APPS = _PROJECT_ROOT / "apps"
_STOCK_ANALYZER = _APPS / "cli" / "stock_analyzer"

if str(_APPS / "cli") not in sys.path: sys.path.insert(0, str(_APPS / "cli"))
>>>>
```

### Task 3: Fix Dependency Injection in deps.py

**Files:**
- Modify: `packages/api/backend/routers/deps.py`

- [ ] **Step 1: Import SqliteVirtualAccountRepository and update DashboardService instantiation**

```python
<<<<
from packages.core.infrastructure.persistence.postgres_fx_repository import PostgresFXRepository

from packages.core.application.expense_service import ExpenseService
====
from packages.core.infrastructure.persistence.postgres_fx_repository import PostgresFXRepository
from packages.core.infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository

from packages.core.application.expense_service import ExpenseService
>>>>
```

```python
<<<<
_mkt_repo = PostgresOHLCVRepository()
_fx_repo  = PostgresFXRepository()

# Service Layer (Singletons)
reward_service = RewardService()
fx_service = FXService(_fx_repo)
expense_service = ExpenseService(_exp_repo, reward_service)
income_service = IncomeService(_inc_repo, reward_service)
investment_service = InvestmentService(_inv_repo, fx_service)
dashboard_service = DashboardService(_exp_repo, _inc_repo, _inv_repo, fx_service)
====
_mkt_repo = PostgresOHLCVRepository()
_fx_repo  = PostgresFXRepository()
_acc_repo = SqliteVirtualAccountRepository()

# Service Layer (Singletons)
reward_service = RewardService()
fx_service = FXService(_fx_repo)
expense_service = ExpenseService(_exp_repo, reward_service)
income_service = IncomeService(_inc_repo, reward_service)
investment_service = InvestmentService(_inv_repo, fx_service)
dashboard_service = DashboardService(_exp_repo, _inc_repo, _inv_repo, _acc_repo, fx_service)
>>>>
```

### Task 4: Fix Method Signature in api_server.py

**Files:**
- Modify: `packages/api/api_server.py`

- [ ] **Step 1: Update get_dashboard call**

```python
<<<<
    @app.get("/api/dashboard")
    async def get_dashboard(year: Optional[int] = None, month: Optional[int] = None):
        try:
            from packages.api.backend.routers.deps import dashboard_service
            return await dashboard_service.get_summary(year, month)
====
    @app.get("/api/dashboard")
    async def get_dashboard(year: Optional[int] = None, month: Optional[int] = None):
        try:
            from packages.api.backend.routers.deps import dashboard_service, get_active_profile
            profile_id = get_active_profile()
            return await dashboard_service.get_summary(profile_id, year, month)
>>>>
```

### Task 5: Validation

- [ ] **Step 1: Run py_compile on modified files**

```bash
python -m py_compile packages/core/infrastructure/persistence/sqlite_account_repository.py packages/api/api_server.py packages/api/backend/routers/stocks.py packages/api/backend/routers/deps.py
```
