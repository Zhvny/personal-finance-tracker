"""
advanced_features/application/use_cases.py
============================================
Application Layer — orchestrates domain logic + Database I/O with Postgres redirection.

Clean Architecture: second ring. Depends on domain only.
DRY  : _DataLoader centralises all DB path resolution and query logic.
SOLID: one use-case class per feature. Each class has one execute() method.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from domain.models import (
    AUTO_SUGGESTION_FACTOR,
    FORECAST_LOOKBACK_DAYS,
    FORECAST_PROJECTION_BASE,
    FORECAST_SMA_WINDOW,
    BudgetCategory,
    ForecastPoint,
    ForecastResult,
    Goal,
)

# Try to import shared Database utility for Postgres redirection
try:
    from packages.core.infrastructure.persistence.database import Database
except ImportError:
    # Fallback for local development if packages is not in path
    import sqlite3
    class Database:
        @staticmethod
        def query(db_path, sql, params=()):
            if not os.path.exists(db_path): return []
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        @staticmethod
        def execute(db_path, sql, params=()):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(sql, params)
                return cursor.lastrowid if "INSERT" in sql.upper() else cursor.rowcount
        @staticmethod
        def execute_script(db_path, script):
            with sqlite3.connect(db_path) as conn:
                conn.executescript(script)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# § INFRASTRUCTURE — Database adapter (owns I/O; domain stays pure)
# ══════════════════════════════════════════════════════════════════════

class _DataLoader:
    """
    Adapter pattern — wraps Database access.
    Centralises path resolution so use-cases never hardcode paths. (DRY)
    """

    def __init__(self, cli_root: Optional[Path] = None):
        self._root = cli_root or Path(__file__).parent.parent.parent

    # ── path helpers ──────────────────────────────────────────────────

    def _db(self, module: str, filename: str) -> str:
        p = self._root / module / "data" / filename
        return str(p.resolve())

    def goals_db(self) -> str:
        p = self._root / "advanced_features" / "data" / "goals.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        db = str(p.resolve())
        Database.execute_script(db, """CREATE TABLE IF NOT EXISTS goals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT    NOT NULL,
            target_amount  REAL    NOT NULL,
            current_amount REAL    NOT NULL DEFAULT 0,
            target_date    TEXT,
            created_at     TEXT    NOT NULL DEFAULT (date('now'))
        )""")
        return db

    def budget_db(self) -> str:
        p = self._root / "advanced_features" / "data" / "budget.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        db = str(p.resolve())
        Database.execute_script(db, """CREATE TABLE IF NOT EXISTS budgets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            year      INTEGER NOT NULL,
            month     INTEGER NOT NULL,
            category  TEXT    NOT NULL,
            limit_amt REAL    NOT NULL,
            UNIQUE(year, month, category)
        )""")
        return db

    # ── query helpers ─────────────────────────────────────────────────

    def _execute(self, db_path: str, sql: str, params: tuple = ()) -> int:
        result = Database.execute(db_path, sql, params)
        return result if isinstance(result, int) else 0

    def _query(self, db_path: str, sql: str, params: tuple = ()) -> List[dict]:
        return Database.query(db_path, sql, params)

    # ── date helpers ──────────────────────────────────────────────────

    def _month_range(self, year: int, month: int) -> Tuple[str, str]:
        start = f"{year:04d}-{month:02d}-01"
        end   = f"{year:04d}-{month+1:02d}-01" if month < 12 else f"{year+1:04d}-01-01"
        return start, end

    def _prev_month(self, year: int, month: int) -> Tuple[int, int]:
        return (year - 1, 12) if month == 1 else (year, month - 1)

    # ── data readers ──────────────────────────────────────────────────

    def daily_expense(self, start: str, end: str) -> Dict[str, float]:
        db = self._db("expense_tracker", "expense.db")
        out: Dict[str, float] = defaultdict(float)
        for r in self._query(db,
            "SELECT date, SUM(amount) as s FROM expenses WHERE date>=? AND date<=? GROUP BY date",
            (start, end)
        ):
            out[str(r["date"])[:10]] += r["s"]
        return dict(out)

    def daily_income(self, start: str, end: str) -> Dict[str, float]:
        db = self._db("income_tracker", "income.db")
        out: Dict[str, float] = defaultdict(float)
        for r in self._query(db,
            "SELECT date, SUM(amount) as s FROM incomes WHERE date>=? AND date<=? GROUP BY date",
            (start, end)
        ):
            out[str(r["date"])[:10]] += r["s"]
        return dict(out)

    def monthly_expense_by_cat(self, year: int, month: int) -> Dict[str, float]:
        db = self._db("expense_tracker", "expense.db")
        s, e = self._month_range(year, month)
        out: Dict[str, float] = {}
        for r in self._query(db,
            "SELECT category, SUM(amount) as s FROM expenses WHERE date>=? AND date<? GROUP BY category",
            (s, e)
        ):
            out[r["category"]] = r["s"]
        return out

    def monthly_totals(self, year: int, month: int) -> Dict[str, float]:
        s, e = self._month_range(year, month)
        exp_db = self._db("expense_tracker", "expense.db")
        inc_db = self._db("income_tracker",  "income.db")
        exp = sum(r["amount"] for r in self._query(exp_db,
            "SELECT amount FROM expenses WHERE date>=? AND date<?", (s, e)))
        inc = sum(r["amount"] for r in self._query(inc_db,
            "SELECT amount FROM incomes  WHERE date>=? AND date<?", (s, e)))
        return {"income": inc, "expense": exp}

    def user_budget_limits(self, year: int, month: int) -> Dict[str, float]:
        db = self.budget_db()
        out: Dict[str, float] = {}
        for r in self._query(db,
            "SELECT category, limit_amt FROM budgets WHERE year=? AND month=?", (year, month)
        ):
            out[r["category"]] = r["limit_amt"]
        return out

    def set_budget_limit(self, year: int, month: int, category: str, limit: float) -> None:
        db = self.budget_db()
        self._execute(db,
            "INSERT INTO budgets(year,month,category,limit_amt) VALUES(?,?,?,?)"
            " ON CONFLICT(year,month,category) DO UPDATE SET limit_amt=excluded.limit_amt",
            (year, month, category, limit))

    def delete_budget_limit(self, year: int, month: int, category: str) -> None:
        db = self.budget_db()
        self._execute(db,
            "DELETE FROM budgets WHERE year=? AND month=? AND category=?",
            (year, month, category))


# ══════════════════════════════════════════════════════════════════════
# § USE CASES
# ══════════════════════════════════════════════════════════════════════

class GoalUseCases:
    """CRUD + business logic for saving goals."""

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()

    def list_goals(self) -> List[Goal]:
        db   = self._loader.goals_db()
        rows = self._loader._query(db, "SELECT * FROM goals ORDER BY id")
        return [Goal(
            id=r["id"], name=r["name"],
            target_amount=r["target_amount"], current_amount=r["current_amount"],
            target_date=r.get("target_date"), created_at=r.get("created_at", ""),
        ) for r in rows]

    def add_goal(self, name: str, target: float,
                 current: float = 0.0, target_date: Optional[str] = None) -> int:
        if not name.strip() or target <= 0:
            raise ValueError("name required and target must be > 0")
        db = self._loader.goals_db()
        return self._loader._execute(db,
            "INSERT INTO goals (name, target_amount, current_amount, target_date) VALUES (?,?,?,?)",
            (name.strip(), target, current, target_date))

    def deposit(self, goal_id: int, amount: float) -> Goal:
        goals = {g.id: g for g in self.list_goals()}
        if goal_id not in goals:
            raise ValueError(f"Goal {goal_id} not found")
        g = goals[goal_id]
        new_amt = g.current_amount + amount
        db = self._loader.goals_db()
        self._loader._execute(db,
            "UPDATE goals SET current_amount=? WHERE id=?", (new_amt, goal_id))
        return Goal(id=g.id, name=g.name, target_amount=g.target_amount,
                    current_amount=new_amt, target_date=g.target_date)

    def delete_goal(self, goal_id: int) -> None:
        db = self._loader.goals_db()
        self._loader._execute(db, "DELETE FROM goals WHERE id=?", (goal_id,))


class CashflowForecastUseCase:
    """
    30-day cashflow forecast using 7-day simple moving average projection.

    Algorithm:
      1. Collect 90 days of historical daily income + expense.
      2. Compute 7-day SMA for each series.
      3. Use last-14-day SMA mean as the projection base.
      4. Start running balance from current month actuals.
      5. Project forward 30 days; flag any day with negative balance.
    """

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()

    def execute(self, days: int = 30) -> ForecastResult:
        today   = date.today()
        start90 = (today - timedelta(days=FORECAST_LOOKBACK_DAYS)).isoformat()
        end_td  = today.isoformat()

        d_exp = self._loader.daily_expense(start90, end_td)
        d_inc = self._loader.daily_income(start90, end_td)

        # Build 90-day history arrays
        inc_series = [d_inc.get((today - timedelta(days=FORECAST_LOOKBACK_DAYS - 1 - i)).isoformat(), 0.0)
                      for i in range(FORECAST_LOOKBACK_DAYS)]
        exp_series = [d_exp.get((today - timedelta(days=FORECAST_LOOKBACK_DAYS - 1 - i)).isoformat(), 0.0)
                      for i in range(FORECAST_LOOKBACK_DAYS)]

        def _sma(series: list, window: int = FORECAST_SMA_WINDOW) -> list:
            return [
                sum(series[max(0, i - window + 1):i + 1]) / len(series[max(0, i - window + 1):i + 1])
                for i in range(len(series))
            ]

        sma_inc = _sma(inc_series)
        sma_exp = _sma(exp_series)

        avg_inc = sum(sma_inc[-FORECAST_PROJECTION_BASE:]) / FORECAST_PROJECTION_BASE
        avg_exp = sum(sma_exp[-FORECAST_PROJECTION_BASE:]) / FORECAST_PROJECTION_BASE
        avg_net = avg_inc - avg_exp

        # Running balance starts from current-month actuals
        y, m   = today.year, today.month
        totals = self._loader.monthly_totals(y, m)
        running_balance = totals["income"] - totals["expense"]

        points: List[ForecastPoint] = []
        warning = False
        for i in range(1, days + 1):
            running_balance += avg_net
            if running_balance < 0:
                warning = True
            points.append(ForecastPoint(
                date=(today + timedelta(days=i)).isoformat(),
                projected_income=round(avg_inc, 2),
                projected_expense=round(avg_exp, 2),
                net=round(avg_net, 2),
                running_balance=round(running_balance, 2),
            ))

        return ForecastResult(
            points=points,
            avg_daily_net=round(avg_net, 2),
            avg_daily_income=round(avg_inc, 2),
            avg_daily_expense=round(avg_exp, 2),
            projected_month_net=round(avg_net * 30, 2),
            warning=warning,
        )


class BudgetPlannerUseCase:
    """
    Monthly budget planner: actuals vs limits + auto-suggestion + alerts.
    Auto-suggestion = 10 % below previous month's spend per category.
    """

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()

    def get_status(self, year: int, month: int) -> List[BudgetCategory]:
        py, pm = self._loader._prev_month(year, month)
        current = self._loader.monthly_expense_by_cat(year, month)
        prev    = self._loader.monthly_expense_by_cat(py, pm)
        limits  = self._loader.user_budget_limits(year, month)

        all_cats = sorted(set(list(current) + list(prev) + list(limits)))
        result = []
        for cat in all_cats:
            cur_amt  = current.get(cat, 0.0)
            prev_amt = prev.get(cat, 0.0)
            lim      = limits.get(cat)
            sugg     = round(prev_amt * AUTO_SUGGESTION_FACTOR, 0) if prev_amt > 0 else None
            result.append(BudgetCategory(
                category=cat, current_spend=cur_amt, prev_month_spend=prev_amt,
                limit=lim, suggestion=sugg,
            ))
        return result

    def set_limit(self, year: int, month: int, category: str, limit: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be > 0")
        self._loader.set_budget_limit(year, month, category, limit)

    def remove_limit(self, year: int, month: int, category: str) -> None:
        self._loader.delete_budget_limit(year, month, category)
