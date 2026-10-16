"""alpha-ledger :8451 — core money flows: expenses, income, transactions,
balances/accounts, budget, recurring, confirmations, goals, NL finance.

honey: business_analytics (construction-style projects) parked here because
its income feeds the ledger; extract when it grows its own persistence.
"""

from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "expenses",
    "income",
    "ledger",
    "balances",
    "accounts",
    "budget",
    "advanced",
    "recurring",
    "confirmations",
    "safe_spend",
    "forecast",
    "net_worth",
    "goals",
    "nl_finance",
    "business_analytics",
]

app = create_service_app(
    service_name="alpha-ledger",
    default_port=8451,
    routers=ROUTERS,
)

if __name__ == "__main__":
    run_service(app, "alpha-ledger")
