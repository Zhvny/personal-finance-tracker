
from datetime import date, datetime
from typing import Any, Dict, Optional

from packages.core.domain.repositories.account_repository import IVirtualAccountRepository
from packages.core.domain.repositories.expense_repository import IExpenseRepository
from packages.core.domain.repositories.income_repository import IIncomeRepository
from packages.core.domain.repositories.investment_repository import IInvestmentRepository
from packages.core.infrastructure.external.fx_service import FXService


class DashboardService:
    """
    Aggregates data from all trackers for a unified summary.
    Refers to logic in finance-tracker-gui/backend/services/dashboard_service.py
    """
    def __init__(self,
                 expense_repo: IExpenseRepository,
                 income_repo: IIncomeRepository,
                 investment_repo: IInvestmentRepository,
                 account_repo: IVirtualAccountRepository,
                 fx_service: Optional[FXService] = None,
                 investment_service: Optional[Any] = None):
        self.expense_repo = expense_repo
        self.income_repo = income_repo
        self.investment_repo = investment_repo
        self.account_repo = account_repo
        self.fx_service = fx_service or FXService()
        self.investment_service = investment_service

    async def _call_repo_method(self, func, *args):
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return await func(*args)
        else:
            return await asyncio.to_thread(func, *args)

    async def get_metadata(self, profile_id: str, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """
        Lighter version of get_summary, skipping expensive investment calculations.
        """
        import asyncio
        now = datetime.now()
        y = year or now.year
        m = month or now.month

        # Execute DB calls in parallel
        tasks = [
            self._call_repo_method(self.expense_repo.get_monthly_summary, y, m),
            self._call_repo_method(self.income_repo.get_monthly_summary, y, m)
        ]

        results = await asyncio.gather(*tasks)
        expense_summary = results[0]
        income_summary = results[1]

        month_label = date(y, m, 1).strftime("%B %Y")
        inc_this = income_summary.get("total", 0)
        exp_this = expense_summary.get("total", 0)

        return {
            "month_label": month_label,
            "income_total": inc_this,
            "expense_total": exp_this,
            "net": inc_this - exp_this
        }

    async def get_summary(self, profile_id: str, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves a comprehensive summary of financial health for a specific month.
        Uses historical FX rates for the target month for accurate reporting.
        Parallelizes database calls to eliminate bottlenecks.
        Auto-falls back to the last active month if target month has 0 data and parameters were omitted.
        """
        import asyncio
        now = datetime.now()
        y = year or now.year
        m = month or now.month
        fallback_applied = False

        # First test current/requested month summaries
        inc_init = await self._call_repo_method(self.income_repo.get_monthly_summary, y, m)
        exp_init = await self._call_repo_method(self.expense_repo.get_monthly_summary, y, m)

        # Fallback check: if no explicit year/month requested and current month is empty
        if (year is None and month is None) and (inc_init.get("total", 0) == 0 and exp_init.get("total", 0) == 0):
            # Ambil ringkasan 12 bulan terakhir sekaligus (paralel), pilih bulan
            # terbaru yang berisi data — hindari hingga 24 roundtrip sekuensial.
            import asyncio
            cy, cm = y, m
            months = []
            for _ in range(12):
                cy, cm = self._get_prev_month(cy, cm)
                months.append((cy, cm))
            summaries = await asyncio.gather(*[
                asyncio.gather(
                    self._call_repo_method(self.income_repo.get_monthly_summary, my, mm),
                    self._call_repo_method(self.expense_repo.get_monthly_summary, my, mm),
                )
                for my, mm in months
            ])
            for (my, mm), (inc_test, exp_test) in zip(months, summaries):
                if inc_test.get("total", 0) > 0 or exp_test.get("total", 0) > 0:
                    y, m = my, mm
                    fallback_applied = True
                    break

        # Get historical FX rate for the start of the target month
        target_date = date(y, m, 1)
        py, pm = self._get_prev_month(y, m)

        inv_task = self.investment_service.get_active_investments() if self.investment_service else self._call_repo_method(self.investment_repo.get_all_active)

        # Execute all DB calls in parallel
        tasks = [
            self._call_repo_method(self.fx_service.get_rate_at, "USD/IDR", target_date),
            self._call_repo_method(self.expense_repo.get_monthly_summary, y, m),
            self._call_repo_method(self.income_repo.get_monthly_summary, y, m),
            self._call_repo_method(self.expense_repo.get_monthly_summary, py, pm),
            self._call_repo_method(self.income_repo.get_monthly_summary, py, pm),
            inv_task,
        ]

        # Gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Safely resolve each result, replacing exceptions with safe defaults
        def _safe(result, default):
            return default if isinstance(result, Exception) else result

        fx               = _safe(results[0], 16_000.0)
        expense_summary  = _safe(results[1], {"total": 0, "by_category": {}})
        income_summary   = _safe(results[2], {"total": 0})
        prev_expense_summary = _safe(results[3], {"total": 0})
        prev_income_summary  = _safe(results[4], {"total": 0})
        holdings         = _safe(results[5], [])

        # FIX #3: account_repo uses SQLite but can fail when DB routing hits Postgres.
        # Isolated to avoid killing the whole dashboard response.
        try:
            accounts = await self._call_repo_method(self.account_repo.get_all, profile_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"account_repo.get_all failed (non-fatal): {e}")
            accounts = []


        # Process Investments using backend-calculated P/L from InvestmentService
        def _f(val, default=0.0) -> float:
            """Safe cast to float, returning default on None/error."""
            try:
                return float(val) if val is not None else default
            except (TypeError, ValueError):
                return default

        holdings_data = []
        pl_total = 0.0
        for inv in holdings:
            qty_f = _f(inv.remaining_quantity if inv.remaining_quantity is not None else inv.quantity)
            pl = _f(getattr(inv, "pl", 0.0))
            pl_pct = _f(getattr(inv, "pl_pct", 0.0))
            pl_total += pl
            holdings_data.append({
                "ticker": inv.ticker,
                "asset_type": inv.asset_type,
                "qty": qty_f,
                "pl": pl,
                "pl_pct": pl_pct
            })

        # Process Virtual Accounts
        total_balance = sum(acc.balance for acc in accounts)
        accounts_data = [{
            "name": acc.name,
            "balance": acc.balance,
            "target": acc.target_amount,
            "progress": acc.progress_pct
        } for acc in accounts]

        month_label = date(y, m, 1).strftime("%B %Y")

        return {
            "month_label": month_label,
            "fallback_applied": fallback_applied,
            "selected_year": y,
            "selected_month": m,
            "income": {
                "total_this": income_summary.get("total", 0),
                "total_prev": prev_income_summary.get("total", 0),
                "real_this": income_summary.get("real_income", 0),
                "transfer_this": income_summary.get("transfer_income", 0),
                "gross_this": income_summary.get("gross_total", 0)
            },
            "expense": {
                "total_this": expense_summary.get("total", 0),
                "total_prev": prev_expense_summary.get("total", 0),
                "by_category": expense_summary.get("by_category", {})
            },
            "investments": {
                "holdings_count": len(holdings),
                "pl_total": pl_total,
                "holdings": holdings_data
            },
            "accounts": {
                "total_balance": total_balance,
                "pockets": accounts_data
            },
            "fx_rate": fx
        }


    def _get_prev_month(self, year: int, month: int):
        if month == 1:
            return year - 1, 12
        return year, month - 1
