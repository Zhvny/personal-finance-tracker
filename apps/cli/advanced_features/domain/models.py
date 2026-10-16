"""
advanced_features/domain/models.py
====================================
Domain Layer — pure value objects and business rules.

Clean Architecture: innermost ring. No I/O, no frameworks, no side effects.
DRY   : all thresholds/constants defined once.
SOLID : single responsibility per dataclass; immutable where possible.
YAGNI : only models actively used by the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import List, Optional

# ══════════════════════════════════════════════════════════════════════
# § CONSTANTS
# ══════════════════════════════════════════════════════════════════════

BUDGET_ALERT_THRESHOLD   = 0.80   # near-limit warning at 80 %
FORECAST_LOOKBACK_DAYS   = 90     # days of history to build moving average
FORECAST_SMA_WINDOW      = 7      # 7-day simple moving average
FORECAST_PROJECTION_BASE = 14     # use last 14-day SMA as projection base
AUTO_SUGGESTION_FACTOR   = 0.90   # suggest 10 % below prev month spend


# ══════════════════════════════════════════════════════════════════════
# § VALUE OBJECTS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Goal:
    """A user-defined financial saving goal."""
    id:             int
    name:           str
    target_amount:  float
    current_amount: float
    target_date:    Optional[str] = None   # ISO date YYYY-MM-DD
    created_at:     str = ""

    @property
    def progress_pct(self) -> float:
        if self.target_amount <= 0:
            return 0.0
        return min(100.0, self.current_amount / self.target_amount * 100)

    @property
    def remaining(self) -> float:
        return max(0.0, self.target_amount - self.current_amount)

    @property
    def is_complete(self) -> bool:
        return self.current_amount >= self.target_amount

    def months_left(self) -> Optional[float]:
        """Calendar months remaining until target_date (None if no deadline)."""
        if not self.target_date:
            return None
        try:
            end   = date.fromisoformat(self.target_date)
            today = date.today()
            delta = (end - today).days
            return max(0.0, delta / 30.44)
        except ValueError:
            return None

    def required_monthly_saving(self) -> Optional[float]:
        """Monthly saving needed to reach goal by deadline."""
        ml = self.months_left()
        if ml is None:
            return None
        if ml <= 0:
            return self.remaining
        return ceil(self.remaining / ml)


@dataclass(frozen=True)
class ForecastPoint:
    """A single day in the 30-day cashflow projection."""
    date:              str
    projected_income:  float
    projected_expense: float
    net:               float
    running_balance:   float

    @property
    def is_negative(self) -> bool:
        return self.running_balance < 0


@dataclass(frozen=True)
class ForecastResult:
    """Full 30-day forecast output."""
    points:              List[ForecastPoint]
    avg_daily_net:       float
    avg_daily_income:    float
    avg_daily_expense:   float
    projected_month_net: float
    warning:             bool         # True if any day goes negative

    @property
    def first_negative(self) -> Optional[ForecastPoint]:
        for p in self.points:
            if p.is_negative:
                return p
        return None


@dataclass
class BudgetCategory:
    """Budget status for a single expense category."""
    category:         str
    current_spend:    float
    prev_month_spend: float
    limit:            Optional[float]
    suggestion:       Optional[float]   # auto: 10 % below prev

    @property
    def pct_change(self) -> Optional[float]:
        if self.prev_month_spend <= 0:
            return None
        return (self.current_spend - self.prev_month_spend) / self.prev_month_spend * 100

    @property
    def near_limit(self) -> bool:
        return bool(self.limit and self.current_spend >= self.limit * BUDGET_ALERT_THRESHOLD)

    @property
    def over_limit(self) -> bool:
        return bool(self.limit and self.current_spend >= self.limit)

    @property
    def pct_used(self) -> Optional[float]:
        if not self.limit or self.limit <= 0:
            return None
        return self.current_spend / self.limit * 100

    @property
    def recommendation(self) -> Optional[str]:
        pc = self.pct_change
        if pc is not None and pc > 20:
            return f"Your {self.category} spending increased {pc:.0f}% this month."
        return None
