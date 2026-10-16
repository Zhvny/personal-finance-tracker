"""
behavioral-finance/application/use_cases.py
=============================================
Application Layer — Use-case orchestration with Database bridge.

Clean Architecture: second ring outward from domain.
  • Depends on: domain layer only.
  • Depended on by: interface layer.

Responsibilities:
  • Load and parse data via Database bridge (transparent Postgres redirection).
  • Orchestrate domain scoring functions.
  • Return structured result DTOs to the interface layer.

SOLID  : each use-case class has one clear responsibility.
DRY    : database query helpers defined once in _DataLoader.
YAGNI  : only use-cases needed by the CLI are implemented.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..domain.models import (
    ImpulseTransaction,
    Transaction,
    compute_fbs,
    compute_fragility,
    compute_impulse_score,
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

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# § INFRASTRUCTURE — Database adapter (Application layer owns I/O)
# ══════════════════════════════════════════════════════════════════════════════

class _DataLoader:
    """
    Adapter pattern — wraps Database access so use-cases stay pure.
    Centralises all DB path resolution (DRY).
    """

    def __init__(self, cli_root: Optional[Path] = None):
        self._root = cli_root or Path(__file__).parent.parent.parent

    def _db(self, module: str, filename: str) -> str:
        p = self._root / module / "data" / filename
        return str(p.resolve())

    def _query(self, db_path: str, sql: str, params: tuple = ()) -> List[dict]:
        return Database.query(db_path, sql, params)

    def _month_range(self, year: int, month: int) -> Tuple[str, str]:
        """Return (start, end) YYYY-MM-DD strings for the given month."""
        start = f"{year:04d}-{month:02d}-01"
        end   = f"{year:04d}-{month+1:02d}-01" if month < 12 else f"{year+1:04d}-01-01"
        return start, end

    def _prev_month(self, year: int, month: int) -> Tuple[int, int]:
        return (year - 1, 12) if month == 1 else (year, month - 1)

    def load_transactions(self, year: int, month: int) -> List[Transaction]:
        """Load all expense + income transactions for the given month."""
        exp_db = self._db("expense_tracker", "expense.db")
        inc_db = self._db("income_tracker",  "income.db")
        s, e   = self._month_range(year, month)
        txs    = []

        for row in self._query(exp_db,
            "SELECT date, amount, category FROM expenses WHERE date>=? AND date<?", (s, e)):
            txs.append(Transaction(
                date=str(row["date"])[:10],
                amount=float(row["amount"]),
                category=row.get("category", "other"),
                is_income=False,
            ))

        for row in self._query(inc_db,
            "SELECT date, amount FROM incomes WHERE date>=? AND date<?", (s, e)):
            txs.append(Transaction(
                date=str(row["date"])[:10],
                amount=float(row["amount"]),
                category="income",
                is_income=True,
            ))

        return txs

    def load_monthly_totals(self, year: int, month: int) -> Dict:
        """Return income/expense totals for current and previous month."""
        exp_db = self._db("expense_tracker", "expense.db")
        inc_db = self._db("income_tracker",  "income.db")
        s,  e  = self._month_range(year, month)
        py, pm = self._prev_month(year, month)
        ps, pe = self._month_range(py, pm)

        exp_this = sum(r["amount"] for r in self._query(exp_db,
            "SELECT amount FROM expenses WHERE date>=? AND date<?", (s,e)))
        exp_prev = sum(r["amount"] for r in self._query(exp_db,
            "SELECT amount FROM expenses WHERE date>=? AND date<?", (ps,pe)))
        inc_this = sum(r["amount"] for r in self._query(inc_db,
            "SELECT amount FROM incomes WHERE date>=? AND date<?", (s,e)))
        inc_prev = sum(r["amount"] for r in self._query(inc_db,
            "SELECT amount FROM incomes WHERE date>=? AND date<?", (ps,pe)))

        return {
            "income_this": inc_this, "income_prev": inc_prev,
            "expense_this": exp_this, "expense_prev": exp_prev,
        }

    def load_investment_values(self) -> Dict[str, float]:
        """Return {asset_type: total_value} for portfolio diversification check."""
        inv_db = self._db("investment_tracker", "portfolio.db")
        rows = self._query(inv_db,
            "SELECT asset_type, buy_price, remaining_quantity, quantity, buy_currency "
            "FROM investments WHERE status!='sold'")
        result: Dict[str, float] = {}
        # Unified FX rate or fetch from service if possible
        FX = 16000
        try:
            pass
            # We don't have direct access to FX service here easily without circular deps
            # but we can try to use a standardized rate or fetch from PG market data
        except Exception:
            logger.exception("Error loading Config in load_investment_values")

        for r in rows:
            qty = r.get("remaining_quantity") or r.get("quantity", 0)
            price = r["buy_price"] * (1 if r["buy_currency"] == "IDR" else FX)
            result[r["asset_type"]] = result.get(r["asset_type"], 0) + price * qty
        return result

    def count_income_sources(self, year: int, month: int) -> int:
        """Count distinct income sources this month."""
        inc_db = self._db("income_tracker", "income.db")
        s, e   = self._month_range(year, month)
        rows   = self._query(inc_db,
            "SELECT DISTINCT source FROM incomes WHERE date>=? AND date<?", (s, e))
        return max(1, len(rows))


# ══════════════════════════════════════════════════════════════════════════════
# § USE CASES
# ══════════════════════════════════════════════════════════════════════════════

class AnalyseFBSUseCase:
    """
    Use case: compute Financial Behaviour Score for a given month.
    Returns structured FBSResult from the domain layer.
    """

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()

    def execute(self, year: int, month: int, emergency_fund: float = 0.0):
        txs    = self._loader.load_transactions(year, month)
        totals = self._loader.load_monthly_totals(year, month)
        return compute_fbs(
            transactions=txs,
            income_this=totals["income_this"],
            income_prev=totals["income_prev"],
            expense_this=totals["expense_this"],
            expense_prev=totals["expense_prev"],
            emergency_fund=emergency_fund,
        )


class AnalyseFragilityUseCase:
    """
    Use case: compute Financial Fragility Score.
    Higher score = more financially stable (less fragile).
    """

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()

    def execute(self, year: int, month: int, emergency_fund: float = 0.0):
        totals        = self._loader.load_monthly_totals(year, month)
        income_sources = self._loader.count_income_sources(year, month)
        asset_values   = self._loader.load_investment_values()
        return compute_fragility(
            income_sources=income_sources,
            expense_this=totals["expense_this"],
            emergency_fund=emergency_fund,
            asset_values=asset_values,
        )


class ListImpulseTransactionsUseCase:
    """
    Use case: return expense transactions ranked by impulsivity score.
    Useful for spotting problematic spending patterns.
    """

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()

    def execute(self, year: int, month: int, top_n: int = 10) -> List[ImpulseTransaction]:
        txs = [t for t in self._loader.load_transactions(year, month) if not t.is_income]
        scored = [
            ImpulseTransaction(
                transaction=t,
                impulse_score=compute_impulse_score(t),
                risk_category=t.category,
                bias_applied="weekend" if t.is_weekend() else "none",
            )
            for t in txs
        ]
        return sorted(scored, key=lambda x: x.impulse_score, reverse=True)[:top_n]


class MonthlyReportUseCase:
    """
    Use case: generate a complete behavioral summary for a given month.
    Orchestrates FBS + Fragility + Impulse analysis in a single call.
    """

    def __init__(self, loader: Optional[_DataLoader] = None):
        self._loader = loader or _DataLoader()
        self._fbs        = AnalyseFBSUseCase(self._loader)
        self._fragility  = AnalyseFragilityUseCase(self._loader)
        self._impulse    = ListImpulseTransactionsUseCase(self._loader)

    def execute(self, year: int, month: int, emergency_fund: float = 0.0) -> Dict:
        fbs       = self._fbs.execute(year, month, emergency_fund)
        fragility = self._fragility.execute(year, month, emergency_fund)
        impulse   = self._impulse.execute(year, month)
        totals    = self._loader.load_monthly_totals(year, month)

        return {
            "period":    f"{year}-{month:02d}",
            "fbs":       fbs,
            "fragility": fragility,
            "top_impulse_transactions": impulse,
            "totals":    totals,
        }
