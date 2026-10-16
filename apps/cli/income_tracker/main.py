#!/usr/bin/env python3
import sys
from datetime import datetime
from pathlib import Path

# Add monorepo root to sys.path to access shared packages
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rich import box
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from apps.cli.income_tracker.core.calculator import IncomeCalculator
from apps.cli.income_tracker.ui.cli_view import IncomeCLIView
from packages.core.application.income_service import IncomeService
from packages.core.domain.models import IncomeType
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.income_tracker.repository import SQLiteIncomeRepository as IncomeRepository
from packages.database.index import run_query

# Identical to cli_view.py for consistency
ACCENT = "#5fafff"

class IncomeTrackerApp:
    """Orchestrates the Income Tracker workflow.
    
    - High Cohesion: only routing / coordination logic lives here.
    - Low Coupling: depends on repository/view interfaces.
    """

    def __init__(self):
        Config.initialize()
        db_path = Config.get_db_path("income")
        self.repo    = IncomeRepository(db_path=db_path)
        self.service = IncomeService(self.repo)
        self.view    = IncomeCLIView()
        self.calc    = IncomeCalculator()
        self.running = True

    def run(self):
        handlers = {
            "1": self.add_income,
            "2": self.view_all,
            "3": self.monthly_summary,
            "4": self.by_category,
            "5": self.tax_estimate,
            "6": self.delete_record,
            "0": self._exit,
        }
        while self.running:
            choice  = self.view.show_main_menu()
            handler = handlers.get(choice)
            if handler:
                handler()
            else:
                self.view.show_error("Invalid choice")

    # ─────────────── Actions ─────────────────────────────────────────

    def add_income(self):
        income_obj = self.view.get_income_input()
        if income_obj:
            result = run_query(self.service.record_income(
                amount=income_obj.amount,
                source=income_obj.source,
                income_type=income_obj.income_type.value,
                date=income_obj.date,
                description=income_obj.description,
                is_taxed=income_obj.is_taxed
            ))
            self.view.show_success(f"Record saved. ID: {result['income_id']}")

            # Show newly unlocked rewards
            for reward in result.get("newly_unlocked", []):
                self.view.show_success(f"🏆 REWARD UNLOCKED: {reward['description']}")
            self.view.pause()

    def view_all(self):
        self.view.show_income_list(run_query(self.service.get_incomes()))

    def monthly_summary(self):
        self.view.clear()
        self.view.show_header("Monthly Summary")
        try:
            year_str  = self.view.get_input("Year (YYYY)", default=str(datetime.now().year))
            month_str = self.view.get_input("Month (MM)", default=f"{datetime.now().month:02d}")
            year, month = int(year_str), int(month_str)
            self.view.show_monthly_summary(run_query(self.service.get_monthly_summary(year, month)), year, month)
        except ValueError:
            self.view.show_error("Invalid date parameters")

    def by_category(self):
        self.view.clear()
        self.view.show_header("Category View")

        type_table = Table.grid(padding=(0, 2))
        for i, t in enumerate(IncomeType, 1):
            type_table.add_row(f"[bold {ACCENT}][{i}][/]", t.value.upper())
        self.view.console.print("\n [bold white]SELECT_TYPE[/]")
        self.view.console.print(Panel(type_table, border_style="#333333", box=box.SQUARE, padding=(1, 2)))

        try:
            choice_str = self.view.get_input("Selection (1-5)")
            choice      = int(choice_str) - 1
            income_type = list(IncomeType)[choice]
            incomes = run_query(self.service.get_incomes())
            filtered = [i for i in incomes if i.income_type == income_type]
            self.view.show_income_list(filtered)
        except (ValueError, IndexError):
            self.view.show_error("Invalid selection")

    def tax_estimate(self):
        self.view.clear()
        self.view.show_header("Tax Estimate")
        try:
            year_str = self.view.get_input("Target Year (YYYY)", default=str(datetime.now().year))
            year    = int(year_str)
            incomes = run_query(self.service.get_incomes(datetime(year, 1, 1), datetime(year, 12, 31)))
            annual  = self.calc.total_income(incomes)
            tax     = self.calc.tax_estimate(annual)
            self.view.show_tax_estimate(annual, tax)
        except ValueError:
            self.view.show_error("Invalid year provided")

    def delete_record(self):
        incomes = run_query(self.service.get_incomes())
        if not incomes:
            self.view.show_error("No records found for deletion")
            return

        self.view.show_income_list(incomes)
        try:
            id_str = self.view.get_input("ID to remove (0 to cancel)")
            id_to_delete = int(id_str)
            if id_to_delete == 0: return

            if Confirm.ask(f" [bold red]![/] Confirm deletion of ID {id_to_delete}?", default=False):
                if run_query(self.service.delete_income(id_to_delete)):
                    self.view.show_success(f"Record {id_to_delete} purged")
                else:
                    self.view.show_error("Deletion failed (ID not found)")
            self.view.pause()
        except ValueError:
            self.view.show_error("Invalid ID format")

    def _exit(self):
        self.running = False


def main():
    app = IncomeTrackerApp()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
