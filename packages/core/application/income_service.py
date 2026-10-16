import logging

logger = logging.getLogger(__name__)

import inspect
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from packages.core.domain.models import Income, IncomeType
from packages.core.domain.repositories.income_repository import IIncomeRepository

from .reward_service import RewardService

# Try to import DatabaseManager but handle absence
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError:
    DatabaseManager = None


class IncomeService:
    """
    Orchestrates income tracking use cases, including "Smart Saving" allocation.
    """

    def __init__(self, repository: IIncomeRepository, reward_service: RewardService = None):
        self.repository = repository
        self.reward_service = reward_service or RewardService()

    async def record_income(
        self,
        amount: Decimal,
        source: str,
        income_type: str,
        date: Optional[datetime] = None,
        description: Optional[str] = None,
        is_taxed: bool = False,
        apply_allocation: bool = True,
    ) -> Dict[str, Any]:
        """
        Records a new income and optionally applies smart saving allocation.
        """
        inc_type = IncomeType.from_str(income_type)
        income = Income(
            amount=amount,
            source=source,
            income_type=inc_type,
            date=date or datetime.now(),
            description=description,
            is_taxed=is_taxed,
        )

        # Save record
        res = self.repository.save(income)
        if inspect.isawaitable(res):
            income_id = await res
        else:
            income_id = res

        side_effects = await self.apply_post_record_side_effects(
            amount=amount,
            source=source,
            income_type=income_type,
            description=description,
            apply_allocation=apply_allocation,
        )
        return {"income_id": income_id, **side_effects}

    async def apply_post_record_side_effects(
        self,
        *,
        amount: Decimal,
        source: str,
        income_type: str,
        description: Optional[str] = None,
        apply_allocation: bool = True,
    ) -> Dict[str, Any]:
        """Run non-transactional notification and reward work after an income commit.

        Financial persistence is deliberately finished before these best-effort
        side effects run. A notification or reward-store failure must never
        turn a committed income into an ambiguous API result.
        """
        inc_type = IncomeType.from_str(income_type)

        # Send Telegram notification
        try:
            from packages.core.utils.telegram_notifier import send_telegram_notification

            amt_val = float(amount)
            amt_formatted = f"Rp {amt_val:,.0f}".replace(",", ".")
            msg = (
                "💰 <b>Pemasukan Baru Dicatat!</b>\n\n"
                f"• <b>Sumber:</b> {source}\n"
                f"• <b>Nominal:</b> {amt_formatted}\n"
                f"• <b>Kategori/Tipe:</b> {income_type}\n"
                f"• <b>Deskripsi:</b> {description or '-'}"
            )
            send_telegram_notification(msg)
        except Exception:
            logger.exception("Error while persisting income record")
            pass

        # Transfers do NOT trigger allocation or rewards (not real income)
        is_real_income = inc_type != IncomeType.TRANSFER

        allocation = None
        newly_unlocked = []
        if apply_allocation and is_real_income:
            allocation = self.calculate_allocation(amount)

            # ── Reward Logic ──
            try:
                # 1. Add Reward points: 1 point per 100,000 IDR
                reward_to_add = amount / Decimal("100000")
                self.reward_service.add_reward_points(float(reward_to_add))

                # 2. Add Savings to cumulative
                savings_delta = allocation.get("db_writes", {}).get("bank_savings", Decimal("0")) + allocation.get(
                    "db_writes", {}
                ).get("emergency_fund", Decimal("0"))
                if savings_delta > 0:
                    newly_unlocked = self.reward_service.add_savings(float(savings_delta))
                else:
                    newly_unlocked = self.reward_service.check_and_apply()
            except Exception:
                logger.exception("Error while updating income record")
                pass  # Skip rewards if DB unavailable
        else:
            allocation = {"enabled": False, "income_amount": amount, "buckets": [], "db_writes": {}}
            if not is_real_income:
                try:
                    newly_unlocked = self.reward_service.check_and_apply()
                except Exception:
                    logger.exception("Error while deleting income record")
                    pass

        return {"allocation": allocation, "newly_unlocked": newly_unlocked, "is_real_income": is_real_income}

    def calculate_allocation(self, amount: Decimal, rules: Optional[Dict] = None) -> Dict[str, Any]:
        if rules is None:
            rules = {
                "enabled": True,
                "mode": "percentage",
                "rules": [
                    {"bucket": "expenses", "pct": 50, "label": "Biaya Hidup", "description": ""},
                    {"bucket": "bank_savings", "pct": 30, "label": "Tabungan Bank", "description": ""},
                    {"bucket": "investment", "pct": 10, "label": "Investasi", "description": ""},
                    {"bucket": "emergency_fund", "pct": 10, "label": "Dana Darurat", "description": ""},
                ],
            }

        if not rules.get("enabled", True) or amount <= 0:
            return {"enabled": False, "income_amount": amount, "buckets": [], "db_writes": {}}

        rule_list = rules.get("rules", [])
        buckets = []
        db_writes = {}
        remainder = amount

        for i, r in enumerate(rule_list):
            bucket = r.get("bucket", "unknown")
            pct = Decimal(str(r.get("pct", 0)))
            label = r.get("label", bucket)
            desc = r.get("description", "")

            if i == len(rule_list) - 1:
                bucket_amount = remainder
            else:
                bucket_amount = (amount * pct / Decimal("100")).quantize(Decimal("0.01"))
                remainder -= bucket_amount

            buckets.append(
                {"bucket": bucket, "label": label, "description": desc, "pct": float(pct), "amount": bucket_amount}
            )

            if bucket in ["bank_savings", "emergency_fund"]:
                db_writes[bucket] = bucket_amount

        return {
            "enabled": True,
            "income_amount": amount,
            "mode": rules.get("mode", "percentage"),
            "buckets": buckets,
            "db_writes": db_writes,
        }

    async def get_incomes(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        income_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Income]:
        res = self.repository.get_all(start_date=start_date, end_date=end_date, income_type=income_type, search=search)
        if inspect.isawaitable(res):
            return await res
        return res

    async def get_monthly_summary(self, year: int, month: int) -> Dict:
        res = self.repository.get_monthly_summary(year, month)
        if inspect.isawaitable(res):
            return await res
        return res

    async def delete_income(self, income_id: int) -> bool:
        res = self.repository.delete(income_id)
        if inspect.isawaitable(res):
            return await res
        return res
