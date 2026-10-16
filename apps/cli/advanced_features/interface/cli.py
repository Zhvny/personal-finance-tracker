"""
advanced_features/interface/cli.py
====================================
Interface Layer — terminal I/O for Advanced Features.

Clean Architecture: outermost ring. Depends on application layer only.
SRP  : each presenter renders exactly one domain concept.
DRY  : _bar(), _rp(), _pct() helpers defined once.
YAGNI: only commands needed by the menu are implemented.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import List

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

# ── Add parent dirs to sys.path so application/domain imports work ────
_IFACE_DIR = os.path.dirname(os.path.abspath(__file__))
_ADV_DIR   = os.path.dirname(_IFACE_DIR)
_CLI_ROOT  = os.path.dirname(_ADV_DIR)
for _p in [_ADV_DIR, _CLI_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from application.use_cases import BudgetPlannerUseCase, CashflowForecastUseCase, GoalUseCases
from domain.models import BudgetCategory, Goal

console = Console()


# ══════════════════════════════════════════════════════════════════════
# § SHARED HELPERS (DRY)
# ══════════════════════════════════════════════════════════════════════

def _rp(amount: float) -> str:
    return f"Rp{amount:,.0f}"

def _pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"

def _bar(value: float, max_val: float, width: int = 20, color: str = "cyan") -> str:
    pct  = min(1.0, value / max_val) if max_val > 0 else 0
    fill = int(pct * width)
    return f"[{color}]{'█' * fill}[/{color}][dim]{'░' * (width - fill)}[/dim]"

def _progress_color(pct: float) -> str:
    if pct >= 100: return "green"
    if pct >= 60:  return "cyan"
    return "yellow"


# ══════════════════════════════════════════════════════════════════════
# § GOAL TRACKER — presenter + interactive commands
# ══════════════════════════════════════════════════════════════════════

class GoalPresenter:
    def __init__(self, use_case: GoalUseCases):
        self._uc = use_case

    def show_all(self, goals: List[Goal]) -> None:
        if not goals:
            console.print("[dim]  No goals yet. Press [A] to add one.[/dim]")
            return
        for g in goals:
            color  = _progress_color(g.progress_pct)
            bar    = _bar(g.current_amount, g.target_amount, width=24, color=color)
            req    = g.required_monthly_saving()
            ml     = g.months_left()
            detail = f"  {_rp(g.current_amount)} / {_rp(g.target_amount)}"
            if req is not None:
                detail += f"   need/month: [{color}]{_rp(req)}[/{color}]"
            if ml is not None:
                detail += f"   {int(ml)+1} month(s) left"
            status = "[green]DONE[/green]" if g.is_complete else f"[{color}]{g.progress_pct:.1f}%[/{color}]"
            console.print(
                f"  [bold]{g.id:>3}.[/bold]  [bold white]{g.name}[/bold white]  {status}\n"
                f"        {bar}\n"
                f"        {detail}\n"
            )

    def run_menu(self) -> None:
        while True:
            console.clear()
            console.print(Panel.fit("[bold cyan]GOAL-BASED SAVING[/bold cyan]", border_style="cyan"))
            goals = self._uc.list_goals()
            self.show_all(goals)
            console.print("[dim]  [A] Add  [D] Deposit  [X] Delete  [0] Back[/dim]")
            choice = Prompt.ask("  Action").strip().upper()

            if choice == "0":
                break

            elif choice == "A":
                name   = Prompt.ask("  Goal name")
                target = Prompt.ask("  Target amount (Rp)")
                td     = Prompt.ask("  Deadline (YYYY-MM-DD, optional)", default="")
                try:
                    self._uc.add_goal(
                        name=name,
                        target=float(target.replace(",", "").replace(".", "")),
                        target_date=td or None,
                    )
                    console.print("[green]  Goal added.[/green]")
                except Exception as e:
                    console.print(f"[red]  Error: {e}[/red]")
                Prompt.ask("  Enter to continue")

            elif choice == "D":
                gid = Prompt.ask("  Goal ID")
                amt = Prompt.ask("  Deposit amount (Rp)")
                try:
                    g = self._uc.deposit(int(gid), float(amt.replace(",", "").replace(".", "")))
                    console.print(f"[green]  Deposited. New total: {_rp(g.current_amount)}[/green]")
                except Exception as e:
                    console.print(f"[red]  Error: {e}[/red]")
                Prompt.ask("  Enter to continue")

            elif choice == "X":
                gid = Prompt.ask("  Goal ID to delete")
                if Confirm.ask(f"  Delete goal {gid}?"):
                    self._uc.delete_goal(int(gid))
                    console.print("[yellow]  Deleted.[/yellow]")
                Prompt.ask("  Enter to continue")


# ══════════════════════════════════════════════════════════════════════
# § CASHFLOW FORECAST — presenter
# ══════════════════════════════════════════════════════════════════════

class ForecastPresenter:
    def __init__(self, use_case: CashflowForecastUseCase):
        self._uc = use_case

    def run(self) -> None:
        console.clear()
        console.print(Panel.fit("[bold cyan]30-DAY CASHFLOW FORECAST[/bold cyan]  [dim](7-day SMA projection)[/dim]",
                                border_style="cyan"))
        console.print("[dim]  Computing...[/dim]", end="\r")

        result = self._uc.execute(days=30)

        # Summary row
        net_color = "green" if result.avg_daily_net >= 0 else "red"
        console.print(Columns([
            Panel(f"[bold {net_color}]{_rp(result.avg_daily_net)}/day[/bold {net_color}]",
                  title="Avg Daily Net",      border_style=net_color, padding=(0, 2)),
            Panel(f"[bold {net_color}]{_rp(result.projected_month_net)}[/bold {net_color}]",
                  title="Projected 30d Net",  border_style=net_color, padding=(0, 2)),
            Panel(f"[bold cyan]{_rp(result.avg_daily_income)}[/bold cyan]",
                  title="Avg Daily Income",   border_style="cyan",    padding=(0, 2)),
            Panel(f"[bold yellow]{_rp(result.avg_daily_expense)}[/bold yellow]",
                  title="Avg Daily Expense",  border_style="yellow",  padding=(0, 2)),
        ], equal=True))

        # Warning
        if result.warning:
            neg = result.first_negative
            console.print(
                Panel(
                    f"[bold red]  Negative balance predicted![/bold red]\n"
                    f"  First deficit on: [bold]{neg.date}[/bold]  "
                    f"({_rp(abs(neg.running_balance))} shortfall)",
                    border_style="red",
                )
            )

        # 30-day table (show every 5th day + any negative day)
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        t.add_column("Date",      width=12)
        t.add_column("Income",    justify="right", width=14)
        t.add_column("Expense",   justify="right", width=14)
        t.add_column("Net",       justify="right", width=14)
        t.add_column("Balance",   justify="right", width=16)
        t.add_column("",          width=4)

        for i, p in enumerate(result.points):
            if i % 5 != 0 and not p.is_negative:
                continue
            bal_color = "red" if p.is_negative else "green"
            net_c     = "red" if p.net < 0 else "green"
            flag      = "[red][/red]" if p.is_negative else ""
            t.add_row(
                p.date[5:],   # MM-DD
                f"[cyan]{_rp(p.projected_income)}[/cyan]",
                f"[yellow]{_rp(p.projected_expense)}[/yellow]",
                f"[{net_c}]{_rp(p.net)}[/{net_c}]",
                f"[{bal_color}]{_rp(p.running_balance)}[/{bal_color}]",
                flag,
            )

        console.print(t)
        Prompt.ask("\n  Press enter to go back...")


# ══════════════════════════════════════════════════════════════════════
# § BUDGET PLANNER — presenter + interactive limit setting
# ══════════════════════════════════════════════════════════════════════

class BudgetPresenter:
    def __init__(self, use_case: BudgetPlannerUseCase):
        self._uc = use_case

    def _render(self, cats: List[BudgetCategory], year: int, month: int) -> None:
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]BUDGET PLANNER — {year}/{month:02d}[/bold cyan]",
            border_style="cyan"))

        # Recommendations
        for c in cats:
            if c.recommendation:
                console.print(f"  [bold yellow]  {c.recommendation}[/bold yellow]")

        t = Table(box=box.ROUNDED, show_header=True, header_style="bold dim", padding=(0, 1))
        t.add_column("Category",    width=14)
        t.add_column("Spent",       justify="right", width=14)
        t.add_column("Limit",       justify="right", width=14)
        t.add_column("Used",        justify="right", width=8)
        t.add_column("Suggestion",  justify="right", width=14)
        t.add_column("vs Last",     justify="right", width=9)
        t.add_column("Status",      width=10)

        for c in cats:
            pct_str  = f"{c.pct_used:.0f}%" if c.pct_used is not None else "—"
            lim_str  = _rp(c.limit) if c.limit else "[dim]not set[/dim]"
            sugg_str = _rp(c.suggestion) if c.suggestion else "—"
            chg_str  = _pct(c.pct_change) if c.pct_change is not None else "—"
            chg_col  = "red" if (c.pct_change or 0) > 0 else "green"

            if c.over_limit:
                status = "[bold red]OVER[/bold red]"
            elif c.near_limit:
                status = "[yellow]NEAR[/yellow]"
            else:
                status = "[green]OK[/green]"

            t.add_row(
                c.category.upper()[:13],
                f"[white]{_rp(c.current_spend)}[/white]",
                lim_str,
                pct_str,
                sugg_str,
                f"[{chg_col}]{chg_str}[/{chg_col}]",
                status,
            )

        console.print(t)

    def run_menu(self, year: int, month: int) -> None:
        while True:
            cats = self._uc.get_status(year, month)
            self._render(cats, year, month)
            console.print("[dim]  [S] Set limit  [R] Remove limit  [0] Back[/dim]")
            choice = Prompt.ask("  Action").strip().upper()

            if choice == "0":
                break

            elif choice == "S":
                cat   = Prompt.ask("  Category name").strip().lower()
                limit = Prompt.ask(f"  Limit for {cat} (Rp)")
                try:
                    self._uc.set_limit(year, month, cat, float(limit.replace(",", "").replace(".", "")))
                    console.print(f"[green]  Limit set for {cat}.[/green]")
                except Exception as e:
                    console.print(f"[red]  Error: {e}[/red]")
                Prompt.ask("  Enter to continue")

            elif choice == "R":
                cat = Prompt.ask("  Category name").strip().lower()
                self._uc.remove_limit(year, month, cat)
                console.print(f"[yellow]  Limit removed for {cat}.[/yellow]")
                Prompt.ask("  Enter to continue")


# ══════════════════════════════════════════════════════════════════════
# § MAIN ENTRY POINT — called by root main.py menu option 5
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    now   = datetime.now()
    year  = now.year
    month = now.month

    goal_uc     = GoalUseCases()
    forecast_uc = CashflowForecastUseCase()
    budget_uc   = BudgetPlannerUseCase()

    goal_p    = GoalPresenter(goal_uc)
    forecast_p = ForecastPresenter(forecast_uc)
    budget_p  = BudgetPresenter(budget_uc)

    MENU = [
        ("1", "Goal-Based Saving",      lambda: goal_p.run_menu()),
        ("2", "Cashflow Forecast",       lambda: forecast_p.run()),
        ("3", "Budget Planning",         lambda: budget_p.run_menu(year, month)),
    ]

    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]ADVANCED FEATURES[/bold cyan]\n"
            "[dim]Goal Saving  ·  30-day Forecast  ·  Budget Planning[/dim]",
            border_style="cyan"))

        t = Table(box=box.ROUNDED, show_header=False, padding=(0, 2), border_style="dim cyan")
        t.add_column("No",  style="bold yellow", width=4, justify="right")
        t.add_column("Feature", style="bold white", width=28)
        for num, label, _ in MENU:
            t.add_row(f"{num}.", label)
        t.add_row("0.", "[dim]Back[/dim]")
        console.print(t)

        choice = Prompt.ask("  Select (0-3)").strip()
        if choice == "0":
            break
        action = {num: fn for num, _, fn in MENU}
        if choice in action:
            action[choice]()
        else:
            console.print("[red]  Invalid choice[/red]")
            Prompt.ask("  Enter to continue")
