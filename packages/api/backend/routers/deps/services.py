"""
backend/routers/deps/services.py — DI container
================================================
Service singletons shared across routers.

Extracted from deps.py (M3 refactor, 2026-09-05). Each service is instantiated
once at module load. Initialization is order-sensitive (fx_service needed by
investment_service, etc.) so the section order is preserved.
"""
from packages.core.application.butterfly_service import ButterflyService
from packages.core.application.dashboard_service import DashboardService
from packages.core.application.expense_service import ExpenseService
from packages.core.application.income_service import IncomeService
from packages.core.application.investment_service import InvestmentService
from packages.core.application.market_data_service import MarketDataService
from packages.core.application.reward_service import RewardService
from packages.core.application.whale_analysis_service import WhaleAnalysisService
from packages.core.infrastructure.external.fx_service import FXService
from packages.core.infrastructure.persistence.postgres_expense_repository import PostgresExpenseRepository
from packages.core.infrastructure.persistence.postgres_fx_repository import PostgresFXRepository
from packages.core.infrastructure.persistence.postgres_income_repository import PostgresIncomeRepository
from packages.core.infrastructure.persistence.postgres_investment_repository import PostgresInvestmentRepository
from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
from packages.core.infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository

# Persistence Layer
_exp_repo = PostgresExpenseRepository()
_inc_repo = PostgresIncomeRepository()
_inv_repo = PostgresInvestmentRepository()
_mkt_repo = PostgresOHLCVRepository()
_fx_repo = PostgresFXRepository()
_acc_repo = SqliteVirtualAccountRepository()

# Service Layer (Singletons)
reward_service = RewardService()
fx_service = FXService(_fx_repo)
expense_service = ExpenseService(_exp_repo, reward_service)
income_service = IncomeService(_inc_repo, reward_service)
investment_service = InvestmentService(_inv_repo, fx_service)
dashboard_service = DashboardService(_exp_repo, _inc_repo, _inv_repo, _acc_repo, fx_service, investment_service)
market_service = MarketDataService(_mkt_repo)
butterfly_service = ButterflyService(_mkt_repo)
whale_service = WhaleAnalysisService()
