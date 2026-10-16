Last Updated: 29-05-2026 (14:30)

# Decimal Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce `Decimal` usage in all repository implementations (Postgres, SQLite, Prisma) for financial fields to ensure precision and consistency with the domain layer.

**Architecture:** Repositories will explicitly cast financial fields to `Decimal` when mapping database rows to domain models and when performing internal calculations.

**Tech Stack:** Python, Decimal, Pydantic, psycopg2, sqlite3, prisma-client-py.

---

### Task 1: Update PostgresRepository (Repository.py)

**Files:**
- Modify: `packages/core/infrastructure/investment_tracker/repository.py`

- [ ] **Step 1: Add Decimal imports**

Ensure `Decimal` is imported from `decimal`.

- [ ] **Step 2: Update _row_to_investment to use Decimal**

```python
    def _row_to_investment(self, row: Dict) -> Investment:
        from decimal import Decimal
        inv = Investment(
            asset_type=row["asset_type"],
            ticker=row["ticker"],
            quantity=Decimal(str(row["quantity"])),
            buy_price=Decimal(str(row["buy_price"])),
            buy_currency=row["buy_currency"],
            buy_price_idr=Decimal(str(row["buy_price_idr"])) if row.get("buy_price_idr") is not None else None,
            buy_date=row["buy_date"], 
            id=row["id"],
            is_favorite=bool(row["is_favorite"])
        )
        inv.status = InvestmentStatus(row["status"]) if row["status"] else InvestmentStatus.HOLDING
        inv.remaining_quantity = (
            Decimal(str(row["remaining_quantity"]))
            if row["remaining_quantity"] is not None
            else inv.quantity
        )
        return inv
```

- [ ] **Step 3: Update save_sell_transaction to handle Decimal**

Ensure that division by FX rate uses Decimal if applicable.

- [ ] **Step 4: Update get_realized_pl_summary to return Decimal (or float for summary if appropriate)**

Update to keep precision until final return.

- [ ] **Step 5: Commit**

```bash
git add packages/core/infrastructure/investment_tracker/repository.py
git commit -m "refactor: enforce Decimal in PostgresRepository"
```

### Task 2: Update SQLiteInvestmentRepository

**Files:**
- Modify: `packages/core/infrastructure/investment_tracker/sqlite_repository.py`

- [ ] **Step 1: Add Decimal imports**

- [ ] **Step 2: Update _map_row_to_investment to use Decimal**

```python
    def _map_row_to_investment(self, row: sqlite3.Row) -> Investment:
        from decimal import Decimal
        # ... date parsing ...
        return Investment(
            id=row['id'],
            asset_type=row['asset_type'],
            ticker=row['ticker'],
            quantity=Decimal(str(row['quantity'])),
            buy_price=Decimal(str(row['buy_price'])),
            buy_currency=row['buy_currency'],
            buy_date=_parse_date(row['buy_date']),
            status=InvestmentStatus(row['status']),
            remaining_quantity=Decimal(str(row['remaining_quantity'])) if row['remaining_quantity'] is not None else None,
            is_favorite=bool(row['is_favorite'])
        )
```

- [ ] **Step 3: Update _map_row_to_sell_transaction to use Decimal**

```python
    def _map_row_to_sell_transaction(self, row: sqlite3.Row) -> SellTransaction:
        from decimal import Decimal
        # ...
        return SellTransaction(
            id=row['id'],
            investment_id=row['investment_id'],
            sell_date=_parse_date(row['sell_date']),
            quantity=Decimal(str(row['quantity'])),
            sell_price=Decimal(str(row['sell_price'])),
            sell_currency=row.get('sell_currency', 'IDR'),
            fees=Decimal(str(row.get('fees', 0.0))),
            realized_pl=Decimal(str(row.get('realized_pl', 0.0))),
            realized_pl_pct=Decimal(str(row.get('realized_pl_pct', 0.0))),
            ticker=row.get('ticker')
        )
```

- [ ] **Step 4: Commit**

```bash
git add packages/core/infrastructure/investment_tracker/sqlite_repository.py
git commit -m "refactor: enforce Decimal in SQLiteInvestmentRepository"
```

### Task 3: Update PostgresInvestmentRepository (Prisma)

**Files:**
- Modify: `packages/core/infrastructure/persistence/postgres_investment_repository.py`

- [ ] **Step 1: Update get_all_active mapping**

Prisma rows should be mapped to `Investment` models which now expect `Decimal`. If `prisma-client-py` returns floats, Pydantic might handle it, but explicit cast in mapping (if manual) or verification of `model_validate` behavior is needed.

- [ ] **Step 2: Update get_realized_pl mapping**

Ensure all financial fields are Decimal.

- [ ] **Step 3: Commit**

```bash
git add packages/core/infrastructure/persistence/postgres_investment_repository.py
git commit -m "refactor: verify Decimal enforcement in Prisma repository"
```

### Task 4: Verification

- [ ] **Step 1: Run repo tests**

If tests exist, run them. If not, create a small script to verify that `remaining_quantity` is indeed a `Decimal` after retrieval.

- [ ] **Step 2: Verify math precision**

```python
from packages.core.infrastructure.investment_tracker.repository import PostgresRepository
# mock/fetch one, check type(inv.quantity) is Decimal
```
