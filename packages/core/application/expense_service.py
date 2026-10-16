import logging

logger = logging.getLogger(__name__)

import inspect
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from packages.core.domain.models.expense import Expense, ExpenseCategory, PaymentMethod
from packages.core.domain.repositories.expense_repository import IExpenseRepository

from .reward_service import RewardService


class ExpenseService:
    """
    Orchestrates expense tracking use cases.
    All methods are native async to match the async PostgresExpenseRepository.
    """

    def __init__(self, repository: IExpenseRepository, reward_service: RewardService = None):
        self.repository = repository
        self.reward_service = reward_service or RewardService()

    async def record_expense(
        self,
        amount: Decimal,
        description: str,
        category: str,
        payment_method: str,
        date: Optional[datetime] = None,
        is_recurring: bool = False,
        recurring_period: Optional[str] = None,
    ) -> Dict:
        """
        Records a new expense and checks for rewards.
        """
        expense = Expense(
            amount=amount,
            description=description,
            category=ExpenseCategory(category.lower()),
            payment_method=PaymentMethod(payment_method.lower()),
            date=date or datetime.now(),
            is_recurring=is_recurring,
            recurring_period=recurring_period,
        )
        res = self.repository.save(expense)
        if inspect.isawaitable(res):
            expense_id = await res
        else:
            expense_id = res

        # Send Telegram notification & check budget status
        try:
            import asyncio

            from packages.core.utils.telegram_notifier import check_budget_limit_and_alert, send_telegram_notification

            # 1. Format and send transaction notification
            amt_val = float(amount)
            amt_formatted = f"Rp {amt_val:,.0f}".replace(",", ".")
            msg = (
                "🔔 <b>Pengeluaran Baru Dicatat!</b>\n\n"
                f"• <b>Deskripsi:</b> {description}\n"
                f"• <b>Nominal:</b> {amt_formatted}\n"
                f"• <b>Kategori:</b> {category}\n"
                f"• <b>Metode:</b> {payment_method}"
            )
            send_telegram_notification(msg)

            # 2. Check and alert if budget limit exceeded
            # We run it as a background task to prevent slowing down the save operation
            dt = date or datetime.now()
            asyncio.create_task(check_budget_limit_and_alert(category, dt.year, dt.month, self.repository))
        except Exception:
            logger.exception("Error while persisting expense record")
            pass

        # Check for rewards (e.g. streaks or milestones)
        newly_unlocked = []
        try:
            newly_unlocked = self.reward_service.check_and_apply()
        except Exception:
            logger.exception("Error while updating expense record")
            pass  # Skip rewards if DB unavailable

        return {"id": expense_id, "newly_unlocked": newly_unlocked}

    async def get_expenses(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, category: Optional[str] = None
    ) -> List[Expense]:
        """
        Retrieves expenses with optional filters.
        """
        res = self.repository.get_all(start_date, end_date, category)
        if inspect.isawaitable(res):
            return await res
        return res

    async def get_monthly_summary(self, year: int, month: int) -> Dict:
        """
        Gets a summary of expenses for a specific month.
        """
        res = self.repository.get_monthly_summary(year, month)
        if inspect.isawaitable(res):
            return await res
        return res

    async def delete_expense(self, expense_id: int) -> bool:
        """
        Deletes an expense.
        """
        res = self.repository.delete(expense_id)
        if inspect.isawaitable(res):
            return await res
        return res
