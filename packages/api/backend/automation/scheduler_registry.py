from typing import Optional

from packages.api.backend.automation.market_scheduler import MarketScheduler

_scheduler_instance: Optional[MarketScheduler] = None

def get_scheduler() -> Optional[MarketScheduler]:
    return _scheduler_instance

def register_scheduler(s: MarketScheduler):
    global _scheduler_instance
    _scheduler_instance = s
