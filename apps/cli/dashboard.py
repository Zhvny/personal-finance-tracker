#!/usr/bin/env python3
"""
apps/cli/dashboard.py
============================
Dashboard data fetching + rendering.
"""

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from rich.console import Console
from rich.rule import Rule

from packages.core.application.profile_service import ProfileService
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.expense_tracker.repository import SQLiteExpenseRepository
from packages.core.infrastructure.income_tracker.repository import SQLiteIncomeRepository
from packages.core.infrastructure.investment_tracker.sqlite_repository import SQLiteInvestmentRepository
from packages.core.infrastructure.logging import get_logger

from prediction_service import PredictionService


console = Console()
logger = get_logger("cli")

expense_repo = SQLiteExpenseRepository(db_path=Config.get_db_path("expense"))
income_repo = SQLiteIncomeRepository(db_path=Config.get_db_path("income"))
investment_repo = SQLiteInvestmentRepository(db_path=Config.get_db_path("investment"))

profile_service = ProfileService(Config.BASE_DIR)


def _fetch_dashboard_data() -> Dict[str, Any]:
    now: datetime = datetime.now(timezone.utc)
    y, m = now.year, now.month
    start_date: datetime = datetime(y, m, 1, tzinfo=timezone.utc)
    if m == 12:
        end_date: datetime = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date: datetime = datetime(y, m + 1, 1, tzinfo=timezone.utc)

    expenses = expense_repo.get_all(start_date=start_date, end_date=end_date)
    exp_this = sum((e.amount for e in expenses), Decimal("0"))

    incomes = income_repo.get_all(start_date=start_date, end_date=end_date)
    inc_this = sum((i.amount for i in incomes), Decimal("0"))

    cat_counts = Counter()
    for e in expenses:
        cat_counts[e.category.value] += e.amount
    top_cat = cat_counts.most_common(1)[0][0] if cat_counts else "-"

    all_inc = sum((i.amount for i in income_repo.get_all()), Decimal("0"))
    all_exp = sum((e.amount for e in expense_repo.get_all()), Decimal("0"))
    bank_savings = max(Decimal("0"), all_inc - all_exp)

    holdings = investment_repo.get_all_active()

    usd_idr: Decimal = Decimal("16000.0")
    fx_error = None
    try:
        from apps.cli.investment_tracker.services.fx_service import FXService

        usd_idr = Decimal(str(FXService().get_usd_idr()))
    except Exception as e:
        logger.exception(f"Failed to fetch USD/IDR rate from FXService: {e}. Using default 16000.0")
        fx_error = f"FX Rate Error: {e}"

    port_value_idr = sum(h.buy_price * h.remaining_quantity * usd_idr for h in holdings)
    port_pl_pct: float = 0.0

    saving_rate = ((inc_this - exp_this) / inc_this * Decimal("100")) if inc_this > Decimal("0") else Decimal("0")

    top_pred = PredictionService.get_top_prediction()

    butterfly_insights = []
    if top_pred:
        try:
            from investment_tracker.services.butterfly_service import ButterflyService

            svc = ButterflyService()
            butterfly_insights = svc.get_risk_map(top_pred["ticker"])
        except Exception:
            logger.exception(f"Failed to fetch butterfly insights for {top_pred['ticker']}")

    return {
        "month_label": now.strftime("%B %Y").upper(),
        "exp_this": exp_this,
        "inc_this": inc_this,
        "saving_rate": saving_rate,
        "top_cat": top_cat.upper(),
        "port_value": port_value_idr,
        "port_pl_pct": port_pl_pct,
        "bank_savings": bank_savings,
        "top_pred": top_pred,
        "butterfly": butterfly_insights[:3],
        "profile": profile_service.get_active_profile(),
        "error": fx_error,
    }


def _get_dashboard_data() -> Dict[str, Any]:
    try:
        return _fetch_dashboard_data()
    except Exception as e:
        logger.exception("Dashboard data fetch failed")
        return {
            "month_label": datetime.now().strftime("%B %Y").upper(),
            "exp_this": 0.0,
            "inc_this": 0.0,
            "saving_rate": 0.0,
            "top_cat": "-",
            "port_value": 0.0,
            "port_pl_pct": 0.0,
            "bank_savings": 0.0,
            "top_pred": None,
            "butterfly": [],
            "profile": profile_service.get_active_profile(),
            "error": str(e),
        }


def fmt(amount: float) -> str:
    if abs(amount) >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M"
    if abs(amount) >= 1_000:
        return f"{amount / 1_000:.0f}K"
    return f"{amount:,.0f}"


def render_dashboard(d: Dict[str, Any]) -> None:
    if d.get("error"):
        console.print(f" [bold red]WARNING:[/bold red] Dashboard data partial. Error: {d['error']}")

    console.print(f"\n [bold cyan]{d['month_label']}[/bold cyan] [dim]• {d['profile'].upper()} OVERVIEW[/dim]")
    console.print(Rule(style="dim"))
    stats = (
        f" [dim white]INC[/dim white] [bold green]{fmt(d['inc_this'])}[/bold green]  "
        f" [dim white]EXP[/dim white] [bold red]-{fmt(d['exp_this'])}[/bold red] [dim white]({d['top_cat']})[/dim white]  "
        f" [dim white]SAV[/dim white] [bold green]{fmt(d['bank_savings'])}[/bold green] [dim white]({d['saving_rate']:+.1f}%)[/dim white]"
    )
    console.print(stats)

    if d["port_value"] > 0:
        console.print(
            f" [dim white]PRT[/dim white] [bold cyan]{fmt(d['port_value'])}[/bold cyan] [dim white]• PORTFOLIO[/dim white]"
        )

    if d.get("top_pred"):
        p = d["top_pred"]
        color = "bold green" if p["pred_return"] > 0 else "bold red"
        console.print(
            f" [dim white]SNIPER[/dim white] [{color}]{p['ticker']}[/]"
            f" [dim white]• Target: {p['target_price']:.2f} ({p['pred_return']:+.2f}%) • Conf: {p['confidence']*100:.0f}%[/dim white]"
        )

    if d.get("butterfly"):
        b_text = " ".join([f"[dim]{n.ticker}[/dim] [bold]{n.correlation:+.2f}[/bold]" for n in d["butterfly"]])
        console.print(f" [dim white]BUTTERFLY[/dim white] {b_text} [dim white]• MACRO CORR[/dim white]")

    console.print(Rule(style="dim"))
