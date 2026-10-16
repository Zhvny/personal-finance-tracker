Last Updated: 29-05-2026 (14:30)

# Virtual Accounts (Pockets/Buckets) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Virtual Accounts (Pockets/Buckets) for granular goal tracking, allowing users to allocate funds towards specific targets without affecting real balances.

**Architecture:** Domain-Driven Design (DDD) with Repository pattern. SQLite (goals.db) for persistence with Postgres redirection support. REST API via FastAPI.

**Tech Stack:** Python, FastAPI, SQLite, Pydantic, Dataclasses.

---

### Task 1: Domain Model

**Files:**
- Create: `packages/core/src/domain/models/account.py`
- Modify: `packages/core/src/domain/models/__init__.py`

- [ ] **Step 1: Create VirtualAccount model**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class VirtualAccount:
    """A virtual bucket or pocket for granular money tracking."""
    id:                Optional[int] = None
    name:              str = ""
    parent_account_id: Optional[int] = None
    balance:           float = 0.0
    target_amount:     float = 0.0
    currency:          str = "USD"
    profile_id:        str = "default"

    @property
    def progress_pct(self) -> float:
        if self.target_amount <= 0:
            return 0.0
        return min(100.0, (self.balance / self.target_amount) * 100)
```

- [ ] **Step 2: Export model in __init__.py**

Add `from .account import VirtualAccount` and add it to `__all__`.

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/domain/models/account.py packages/core/src/domain/models/__init__.py
git commit -m "feat(domain): add VirtualAccount model"
```

### Task 2: Repository Interface

**Files:**
- Create: `packages/core/src/domain/repositories/account_repository.py`
- Modify: `packages/core/src/domain/repositories/__init__.py`

- [ ] **Step 1: Define IVirtualAccountRepository interface**

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from ..models.account import VirtualAccount

class IVirtualAccountRepository(ABC):
    @abstractmethod
    def save(self, account: VirtualAccount) -> int:
        pass

    @abstractmethod
    def get_all(self, profile_id: str) -> List[VirtualAccount]:
        pass

    @abstractmethod
    def get_by_id(self, account_id: int, profile_id: str) -> Optional[VirtualAccount]:
        pass

    @abstractmethod
    def delete(self, account_id: int, profile_id: str) -> bool:
        pass

    @abstractmethod
    def update_balance(self, account_id: int, profile_id: str, new_balance: float) -> bool:
        pass
```

- [ ] **Step 2: Export interface in __init__.py**

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/domain/repositories/account_repository.py packages/core/src/domain/repositories/__init__.py
git commit -m "feat(domain): add IVirtualAccountRepository interface"
```

### Task 3: SQLite Repository Implementation

**Files:**
- Create: `packages/core/src/infrastructure/persistence/sqlite_account_repository.py`
- Modify: `packages/core/src/infrastructure/persistence/__init__.py`

- [ ] **Step 1: Implement SqliteVirtualAccountRepository**

```python
from typing import List, Optional, Dict
from ...domain.repositories.account_repository import IVirtualAccountRepository
from ...domain.models.account import VirtualAccount
from ..config import Config
from .database import Database

class SqliteVirtualAccountRepository(IVirtualAccountRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.get_db_path("goals")
        self._init_db()

    def _init_db(self):
        script = """
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
        """
        Database.execute_script(self.db_path, script)

    def save(self, account: VirtualAccount) -> int:
        sql = """
            INSERT INTO virtual_accounts (name, parent_account_id, balance, target_amount, currency, profile_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (account.name, account.parent_account_id, account.balance, 
                  account.target_amount, account.currency, account.profile_id)
        result = Database.execute(self.db_path, sql, params)
        if result:
            account.id = result
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

    def _row_to_account(self, row: Dict) -> VirtualAccount:
        return VirtualAccount(
            id=row['id'],
            name=row['name'],
            parent_account_id=row['parent_account_id'],
            balance=row['balance'],
            target_amount=row['target_amount'],
            currency=row['currency'],
            profile_id=row['profile_id']
        )
```

- [ ] **Step 2: Export in __init__.py**

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/infrastructure/persistence/sqlite_account_repository.py packages/core/src/infrastructure/persistence/__init__.py
git commit -m "feat(infra): add SqliteVirtualAccountRepository"
```

### Task 4: API Router

**Files:**
- Create: `packages/api/backend/routers/accounts.py`
- Modify: `packages/api/api_server.py`

- [ ] **Step 1: Create accounts router**

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from .deps import get_active_profile
from packages.core.domain.models.account import VirtualAccount
from packages.core.infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

class VirtualAccountCreate(BaseModel):
    name: str
    target_amount: float
    balance: float = 0.0
    currency: str = "USD"
    parent_account_id: int = None

class VirtualAccountUpdate(BaseModel):
    balance: float = None
    target_amount: float = None

@router.get("/virtual", response_model=List[VirtualAccount])
async def list_virtual_accounts(profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    return repo.get_all(profile_id)

@router.post("/virtual")
async def create_virtual_account(account_in: VirtualAccountCreate, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    account = VirtualAccount(
        name=account_in.name,
        target_amount=account_in.target_amount,
        balance=account_in.balance,
        currency=account_in.currency,
        parent_account_id=account_in.parent_account_id,
        profile_id=profile_id
    )
    repo.save(account)
    return account

@router.get("/virtual/{id}")
async def get_virtual_account(id: int, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    account = repo.get_by_id(id, profile_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.put("/virtual/{id}")
async def update_virtual_account(id: int, update: VirtualAccountUpdate, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    account = repo.get_by_id(id, profile_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if update.balance is not None:
        repo.update_balance(id, profile_id, update.balance)
    
    # Reload and return
    return repo.get_by_id(id, profile_id)

@router.delete("/virtual/{id}")
async def delete_virtual_account(id: int, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    if repo.delete(id, profile_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Account not found")
```

- [ ] **Step 2: Register router in api_server.py**

- [ ] **Step 3: Commit**

```bash
git add packages/api/backend/routers/accounts.py packages/api/api_server.py
git commit -m "feat(api): add virtual accounts router"
```

### Task 5: Verification

- [ ] **Step 1: Create verification script**

```python
import sys
import os
# Add packages/core to path
sys.path.append(os.path.abspath("packages/core/src"))

from domain.models.account import VirtualAccount
from infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository

def test_va_flow():
    repo = SqliteVirtualAccountRepository("test_goals.db")
    
    # 1. Save
    va = VirtualAccount(name="New Car", target_amount=20000.0, profile_id="test_user")
    repo.save(va)
    print(f"Saved VA with ID: {va.id}")
    
    # 2. Retrieve
    retrieved = repo.get_by_id(va.id, "test_user")
    assert retrieved.name == "New Car"
    print("Retrieval successful")
    
    # 3. Update
    repo.update_balance(va.id, "test_user", 500.0)
    updated = repo.get_by_id(va.id, "test_user")
    assert updated.balance == 500.0
    print(f"Progress: {updated.progress_pct}%")
    
    # 4. List
    all_va = repo.get_all("test_user")
    assert len(all_va) >= 1
    print(f"Total virtual accounts: {len(all_va)}")
    
    # 5. Delete
    repo.delete(va.id, "test_user")
    assert repo.get_by_id(va.id, "test_user") is None
    print("Delete successful")
    
    os.remove("test_goals.db")
    print("Test passed!")

if __name__ == "__main__":
    test_va_flow()
```

- [ ] **Step 2: Run verification script**

Run: `python scripts/verify_virtual_accounts.py`

- [ ] **Step 3: Commit script**

```bash
git add scripts/verify_virtual_accounts.py
git commit -m "test: add virtual accounts verification script"
```
