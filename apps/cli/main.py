#!/usr/bin/env python3
"""
apps/cli/main.py
============================
Root entry point — Live dashboard + main menu.
Minimalist & Monochrome Edition.
"""

import argparse
import importlib.util
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

# Add monorepo root and apps/cli to sys.path to access shared packages and sub-modules
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path: sys.path.insert(0, str(_root))

from packages.core import bootstrap

MONOREPO_ROOT = bootstrap.PROJECT_ROOT
CLI_ROOT = Path(__file__).parent.resolve()
if str(CLI_ROOT) not in sys.path: sys.path.insert(0, str(CLI_ROOT))

from rich.console import Console
from rich.rule import Rule

from packages.core.application.profile_service import ProfileService
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.expense_tracker.repository import SQLiteExpenseRepository
from packages.core.infrastructure.income_tracker.repository import SQLiteIncomeRepository
from packages.core.infrastructure.investment_tracker.sqlite_repository import SQLiteInvestmentRepository
from packages.core.infrastructure.logging import get_logger

console = Console()

# Initialize Logger
logger = get_logger("cli")

# Initialize Environment & Config
Config.initialize()

# Initialize Profile Service
profile_service = ProfileService(Config.BASE_DIR)

# Initialize Repositories (SQLite - No Prisma)
expense_repo = SQLiteExpenseRepository(db_path=Config.get_db_path("expense"))
income_repo = SQLiteIncomeRepository(db_path=Config.get_db_path("income"))
investment_repo = SQLiteInvestmentRepository(db_path=Config.get_db_path("investment"))


# ─────────────────────────────────────────────────────────────────────────────
# CLI Subcommands
# ─────────────────────────────────────────────────────────────────────────────


def handle_profile_args(args):
    """Handles 'profile' subcommand."""
    if args.action == "list":
        console.print(f" Available: {profile_service.get_available_profiles()}")
    elif args.action == "add":
        if not args.name:
            console.print(" [red]Error:[/red] Profile name required for 'add' action.")
            return
        try:
            profile_service.add_profile(args.name)
            console.print(f" [green]Success:[/green] Profile '{args.name.lower()}' created.")
        except ValueError as ve:
            console.print(f" [red]Error:[/red] {ve}")
        except Exception as e:
            logger.exception(f"Failed to add profile {args.name}: {e}")
            console.print(f" [red]Error:[/red] {e}")
    elif args.action == "set":
        if not args.name:
            console.print(" [red]Error:[/red] Profile name required for 'set' action.")
            return
        try:
            profile_service.set_active_profile(args.name)
            Config.reset_cache()
            console.print(f" [green]Success:[/green] Switched to {args.name.upper()}")
        except Exception as e:
            logger.exception(f"Failed to set profile {args.name}: {e}")
            console.print(f" [red]Error:[/red] {e}")
    else:
        console.print(f" Active: {profile_service.get_active_profile().upper()}")


def run_maintenance(args):
    """Runs health checks and applies patches."""
    from packages.core.application.maintenance_service import MaintenanceService

    service = MaintenanceService(Config.BASE_DIR)

    console.print("\n [bold yellow]RUNNING MAINTENANCE[/bold yellow]")
    console.print(Rule(style="dim"))

    tasks_to_run = []
    if args.all or not any([args.sql, args.paths, args.cleanup, args.bom]):
        tasks_to_run = [
            "sql_optimization",
            "sql_syntax_fix",
            "profile_integrity",
            "root_cleanup",
            "bom_removal",
            "port_cleanup_fix",
            "path_neutralization",
            "setup_pg_update",
        ]
    else:
        if args.sql:
            tasks_to_run.extend(["sql_optimization", "sql_syntax_fix"])
        if args.paths:
            tasks_to_run.append("path_neutralization")
        if args.cleanup:
            tasks_to_run.append("root_cleanup")
        if args.bom:
            tasks_to_run.append("bom_removal")

    all_results = service.run_all_patches()
    for task in tasks_to_run:
        result = all_results.get(task)
        if result is None: continue

        if isinstance(result, bool):
            status = "[green]OK[/green]" if result else "[yellow]SKIPPED/FAIL[/yellow]"
            console.print(f"  {task:<20} : {status}")
        elif isinstance(result, int):
            status = f"[green]{result} modified[/green]" if result > 0 else "[dim]No action[/dim]"
            console.print(f"  {task:<20} : {status}")
        else:
            console.print(f"  {task:<20} : {result}")

    # 2. Run Health Check
    console.print("\n [bold]System Health Check:[/bold]")
    health = service.get_health_status()
    for check, passed in health.items():
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {check:<20} : {status}")

    console.print(Rule(style="dim"))
    console.print(" [bold green]Maintenance Complete.[/bold green]\n")

# ─────────────────────────────────────────────────────────────────────────────
# Profile Management
# ─────────────────────────────────────────────────────────────────────────────

def manage_profiles() -> None:
    console.print("\n [bold cyan]PROFILE MANAGEMENT[/bold cyan]")
    console.print(Rule(style="dim"))
    console.print("  1. Switch Active Profile")
    console.print("  2. Add New Profile")
    console.print("  0. Back")

    try:
        choice = console.input("\n [bold]Choice >[/bold] ").strip()
        if choice == "1":
            profiles: List[str] = profile_service.get_available_profiles()
            current: str = profile_service.get_active_profile()

            console.print("\n [bold cyan]SWITCH PROFILE[/bold cyan]")
            console.print(Rule(style="dim"))
            for i, p in enumerate(profiles, 1):
                mark = " [bold magenta]>[/bold magenta]" if p == current else "  "
                console.print(f" {mark} {i}. {p.upper()}")

            c = console.input("\n [bold]Choice >[/bold] ").strip()
            if c.isdigit() and 1 <= int(c) <= len(profiles):
                new_p = profiles[int(c)-1]
                profile_service.set_active_profile(new_p)
                Config.reset_cache()
                # Re-initialize repos for new profile
                try:
                    global expense_repo, income_repo, investment_repo
                    expense_repo = SQLiteExpenseRepository(db_path=Config.get_db_path("expense"))
                    income_repo = SQLiteIncomeRepository(db_path=Config.get_db_path("income"))
                    investment_repo = SQLiteInvestmentRepository(db_path=Config.get_db_path("investment"))
                    console.print(f"\n [green]Success:[/green] Switched to {new_p.upper()} profile.")
                except Exception:
                    logger.exception(f"Failed to initialize repositories for profile {new_p}")
                    console.print(f" [red]Error:[/red] Failed to load data for {new_p.upper()}. Check logs.")

        elif choice == "2":
            name = console.input("\n [bold]New Profile Name >[/bold] ").strip()
            if name:
                try:
                    profile_service.add_profile(name)
                    console.print(f" [green]Success:[/green] Profile '{name}' created.")
                except ValueError as ve:
                    logger.exception(f"Validation error adding profile: {ve}")
                    console.print(f" [red]Error:[/red] {ve}")
                except Exception as e:
                    logger.exception(f"Failed to add profile: {e}")
                    console.print(f" [red]Error:[/red] {e}")

    except Exception as e:
        logger.exception("Error in profile management")
        console.print(f"\n [red]Error:[/red] {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Module launcher
# ─────────────────────────────────────────────────────────────────────────────

def run_module(module_dir: str, main_file: str = "main.py") -> None:
    if module_dir.startswith(".."):
        mod_path = (CLI_ROOT / module_dir).resolve()
    else:
        mod_path = CLI_ROOT / module_dir

    main_py: Path = mod_path / main_file

    if str(mod_path) not in sys.path:
        sys.path.insert(0, str(mod_path))
        added_to_path = True
    else:
        added_to_path = False

    module = None
    try:
        # Import the module using its name if possible, or use spec for arbitrary files
        module_name = f"apps.cli.{module_dir.replace('/', '.')}"
        try:
            # Try importing as a proper package member first
            module = importlib.import_module(f"{module_name}.{main_file.replace('.py', '')}")
            importlib.reload(module)
        except (ImportError, ModuleNotFoundError):
            # Fallback to spec-based loading for non-package structures or relative paths
            spec = importlib.util.spec_from_file_location(f"_mod_{module_dir.replace('..', 'ext')}", str(main_py))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

        if module and hasattr(module, "main"):
            module.main()
        elif not module:
            raise ImportError(f"Could not load module {module_dir}")
        else:
            raise AttributeError(f"Module {module_dir} has no 'main' function")
    finally:
        if added_to_path:
            sys.path.remove(str(mod_path))

# ─────────────────────────────────────────────────────────────────────────────
# Dashboard data
# ─────────────────────────────────────────────────────────────────────────────

from prediction_service import PredictionService


def _fetch_dashboard_data() -> Dict[str, Any]:
    now: datetime = datetime.now(timezone.utc)
    y, m = now.year, now.month
    start_date: datetime = datetime(y, m, 1, tzinfo=timezone.utc)
    if m == 12:
        end_date: datetime = datetime(y+1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date: datetime = datetime(y, m+1, 1, tzinfo=timezone.utc)

    # SQLite queries via repositories
    expenses = expense_repo.get_all(start_date=start_date, end_date=end_date)
    exp_this = sum((e.amount for e in expenses), Decimal('0'))

    incomes = income_repo.get_all(start_date=start_date, end_date=end_date)
    inc_this = sum((i.amount for i in incomes), Decimal('0'))

    # Top category
    from collections import Counter
    cat_counts = Counter()
    for e in expenses:
        cat_counts[e.category.value] += e.amount
    top_cat = cat_counts.most_common(1)[0][0] if cat_counts else "-"

    # Totals for savings
    all_inc = sum((i.amount for i in income_repo.get_all()), Decimal('0'))
    all_exp = sum((e.amount for e in expense_repo.get_all()), Decimal('0'))
    bank_savings = max(Decimal('0'), all_inc - all_exp)

    # Investment data
    holdings = investment_repo.get_all_active()

    # Standard USD->IDR conversion
    usd_idr: Decimal = Decimal('16000.0')
    fx_error = None
    try:
        from apps.cli.investment_tracker.services.fx_service import FXService
        usd_idr = Decimal(str(FXService().get_usd_idr()))
    except Exception as e:
        logger.exception(f"Failed to fetch USD/IDR rate from FXService: {e}. Using default 16000.0")
        fx_error = f"FX Rate Error: {e}"

    port_value_idr = sum(h.buy_price * h.remaining_quantity * usd_idr for h in holdings)
    port_pl_pct: float = 0.0

    saving_rate = ((inc_this - exp_this) / inc_this * Decimal('100')) if inc_this > Decimal('0') else Decimal('0')

    # ML Prediction
    top_pred = PredictionService.get_top_prediction()

    # Butterfly Effect Correlation (Macro Insights)
    butterfly_insights = []
    if top_pred:
        try:
            from investment_tracker.services.butterfly_service import ButterflyService
            svc = ButterflyService()
            butterfly_insights = svc.get_risk_map(top_pred['ticker'])
        except Exception:
            logger.exception(f"Failed to fetch butterfly insights for {top_pred['ticker']}")

    return {
        "month_label":  now.strftime("%B %Y").upper(),
        "exp_this":     exp_this,
        "inc_this":     inc_this,
        "saving_rate":  saving_rate,
        "top_cat":      top_cat.upper(),
        "port_value":   port_value_idr,
        "port_pl_pct":  port_pl_pct,
        "bank_savings": bank_savings,
        "top_pred":     top_pred,
        "butterfly":    butterfly_insights[:3],
        "profile":      profile_service.get_active_profile(),
        "error":        fx_error
    }

def _get_dashboard_data() -> Dict[str, Any]:
    try:
        return _fetch_dashboard_data()
    except Exception as e:
        logger.exception("Dashboard data fetch failed")
        return {
            "month_label":  datetime.now().strftime("%B %Y").upper(),
            "exp_this":     0.0,
            "inc_this":     0.0,
            "saving_rate":  0.0,
            "top_cat":      "-",
            "port_value":   0.0,
            "port_pl_pct":  0.0,
            "bank_savings": 0.0,
            "top_pred":     None,
            "butterfly":    [],
            "profile":      profile_service.get_active_profile(),
            "error":        str(e)
        }

def fmt(amount: float) -> str:
    if abs(amount) >= 1_000_000: return f"{amount/1_000_000:.1f}M"
    if abs(amount) >= 1_000:     return f"{amount/1_000:.0f}K"
    return f"{amount:,.0f}"

# ──────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────

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

    if d['port_value'] > 0:
        console.print(f" [dim white]PRT[/dim white] [bold cyan]{fmt(d['port_value'])}[/bold cyan] [dim white]• PORTFOLIO[/dim white]")

    if d.get("top_pred"):
        p = d["top_pred"]
        color = "bold green" if p['pred_return'] > 0 else "bold red"
        console.print(f" [dim white]SNIPER[/dim white] [{color}]{p['ticker']}[/] [dim white]• Target: {p['target_price']:.2f} ({p['pred_return']:+.2f}%) • Conf: {p['confidence']*100:.0f}%[/dim white]")

    if d.get("butterfly"):
        b_text = " ".join([f"[dim]{n.ticker}[/dim] [bold]{n.correlation:+.2f}[/bold]" for n in d["butterfly"]])
        console.print(f" [dim white]BUTTERFLY[/dim white] {b_text} [dim white]• MACRO CORR[/dim white]")

    console.print(Rule(style="dim"))

def get_menu_items(profile: str) -> List[Tuple[str, str, str]]:
    items: List[Tuple[str, str, str]] = [
        ("1", "INVEST",  "Assets"),
        ("2", "EXPENSE", "Spending"),
        ("3", "INCOME",  "Earning"),
        ("4", "SCAN",    "Receipt"),
    ]

    if Config.is_feature_enabled("stocks") and profile != "business":
        items.append(("5", "STOCKS", "Analyzer"))
    if Config.is_feature_enabled("ml") and profile != "business":
        items.append(("6", "ML_STX", "Predict"))
    if Config.is_feature_enabled("behavioral") and profile != "business":
        items.append(("7", "BEH_FIN", "Behavioral"))

    if profile == "business":
        items.append(("7", "REPORT", "Quarterly"))

    items.append(("8", "PROFILE", "Manage"))

    if profile != "business":
        items.append(("9", "WHALE",   "Profiler"))

    items.append(("0", "EXIT",    "Quit"))
    return items

def render_menu(profile: str) -> None:
    items = [f"[bold white]{n}[/bold white] [dim]{l}[/dim]" for n, l, d in get_menu_items(profile)]
    console.print("  " + "   ".join(items) + "\n")

# ──────────────────────────────────────────────────────────────────────────
# Launchers
# ──────────────────────────────────────────────────────────────────────────

def _launch(name: str, fn: Callable) -> None:
    try:
        fn()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Error in {name}: {e}")
        console.print(f"\n[bold red]Error in {name}:[/bold red] {e}")

def _run_subprocess(name: str, cmd: List[str]) -> None:
    import subprocess
    try:
        console.print(f"[bold cyan]Launching {name}...[/bold cyan]")
        env = os.environ.copy()

        # Ensure we use absolute path for python executable
        python_exe = sys.executable
        if cmd[0].lower() in ["python", "python3", "python.exe"]:
            cmd[0] = python_exe

        # Ensure target script is absolute if it exists
        if len(cmd) > 1 and not os.path.isabs(cmd[1]):
            # Try to resolve relative to MONOREPO_ROOT, CLI_ROOT or current dir
            potential_paths = [
                CLI_ROOT / cmd[1],
                MONOREPO_ROOT / cmd[1],
                Path(cmd[1]).resolve()
            ]
            for p in potential_paths:
                if p.exists():
                    cmd[1] = str(p)
                    break

        subprocess.run(cmd, check=True, env=env)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Subprocess Error in {name}: {e}")
        console.print(f"\n[bold red]Subprocess Error in {name}:[/bold red] {e}")

def get_dispatch(profile: str) -> Dict[str, Callable]:
    dispatch: Dict[str, Callable] = {
        "1": lambda: _launch("Investment", lambda: run_module("investment_tracker")),
        "2": lambda: _launch("Expense",    lambda: run_module("expense_tracker")),
        "3": lambda: _launch("Income",     lambda: run_module("income_tracker")),
        "4": lambda: _launch("Receipt",    lambda: run_module("receipt_reader")),
        "8": lambda: manage_profiles(),
    }

    if profile != "business":
        dispatch["9"] = lambda: _launch("Whale", run_whale_profiler)

    if Config.is_feature_enabled("stocks") and profile != "business":
        dispatch["5"] = lambda: _launch("Stocks", lambda: run_module("stock_analyzer"))
    if Config.is_feature_enabled("ml") and profile != "business":
        ml_path = (CLI_ROOT / "stock_ml" / "app.py").resolve()
        dispatch["6"] = lambda: _run_subprocess("ML_Stocks", [sys.executable, str(ml_path)])
    if Config.is_feature_enabled("behavioral") and profile != "business":
        dispatch["7"] = lambda: _launch("Behavioral", lambda: run_module("behavioral_finance"))

    if profile == "business":
        dispatch["7"] = lambda: _launch("Business Report", lambda: run_business_report())

    return dispatch

def run_business_report() -> None:
    from packages.core.application.business_report_service import BusinessReportService
    service = BusinessReportService()
    console.print("\n [bold cyan]GENERATING QUARTERLY REPORT[/bold cyan]")
    try:
        now: datetime = datetime.now()
        q: int = (now.month - 1) // 3 + 1
        path: str = service.generate_quarterly_report(now.year, q)
        console.print(f" [green]Success:[/green] Report saved to {path}")
    except Exception as e:
        logger.exception(f"Failed to generate business report: {e}")
        console.print(f" [red]Error:[/red] {e}")

def run_whale_profiler() -> None:
    mod_path = CLI_ROOT / "investment_tracker"
    if str(mod_path) not in sys.path:
        sys.path.insert(0, str(mod_path))
    from investment_tracker.main import PortfolioApp
    app = PortfolioApp()
    app.whale_profiler()

def main() -> None:
    get_logger("cli")

    parser = argparse.ArgumentParser(description="Alpha CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Profile subcommand
    profile_parser = subparsers.add_parser("profile", help="Manage profiles")
    profile_parser.add_argument("action", choices=["list", "add", "set", "status"], help="Action to perform")
    profile_parser.add_argument("name", nargs="?", help="Profile name for 'add' or 'set' action")

    # Maintain subcommand
    maintain_parser = subparsers.add_parser("maintain", help="Run system maintenance")
    maintain_parser.add_argument("-a", "--all", action="store_true", help="Run all maintenance tasks")
    maintain_parser.add_argument("--sql", action="store_true", help="Run SQL optimizations and syntax fixes")
    maintain_parser.add_argument("--paths", action="store_true", help="Run path neutralization")
    maintain_parser.add_argument("--cleanup", action="store_true", help="Clean up redundant files")
    maintain_parser.add_argument("--bom", action="store_true", help="Remove BOM from files")

    # Workflow subcommand
    workflow_parser = subparsers.add_parser("workflow", help="Manage engineering workflow")
    workflow_parser.add_argument("action", choices=["demo", "status"], help="Action to perform")

    # Parse args
    args, unknown = parser.parse_known_args()

    if args.command == "profile":
        handle_profile_args(args)
        return
    elif args.command == "maintain":
        run_maintenance(args)
        return
    elif args.command == "workflow":
        return

    while True:
        profile: str = profile_service.get_active_profile()
        console.clear()
        render_dashboard(_get_dashboard_data())

        render_menu(profile)
        try:
            choice: str = console.input("[bold]>[/bold] ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = "0"

        if choice == "0":
            console.print("\n [bold green]Exit Safe.[/bold green] Goodbye!\n")
            break

        dispatch: Dict[str, Callable] = get_dispatch(profile)
        if choice in dispatch:
            console.print()
            dispatch[choice]()
            try:
                console.input("\n [dim]Press Enter...[/dim]")
            except Exception as e:
                logger.exception("Failed to wait for user input")
                console.print(f"\n [red]Error:[/red] Interface error: {e}")
        else:
            import time

            time.sleep(0.5)


if __name__ == "__main__":
    main()
