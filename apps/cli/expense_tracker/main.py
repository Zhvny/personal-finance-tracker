#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add monorepo root to sys.path to access shared packages
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.core.domain.models import ExpenseCategory

# Initialize DatabaseManager for Postgres redirection
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    DatabaseManager.initialize()
except Exception:
    pass

from rich import box
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from apps.cli.expense_tracker.core.calculator import ExpenseCalculator
from apps.cli.expense_tracker.ui.cli_view import ExpenseCLIView
from packages.core.application.expense_service import ExpenseService
from packages.core.application.expense_tracker.budget_service import BudgetService
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.expense_tracker.repository import SQLiteExpenseRepository as ExpenseRepository
from packages.database.index import run_query

# Identical to cli_view.py for consistency
ACCENT = "#5fafff"

class ExpenseTrackerApp:
    """Orchestrates the Expense Tracker workflow.
    
    - High Cohesion: only routing / coordination logic lives here.
    - Low Coupling: depends on abstract interfaces, not concrete implementations.
    """

    def __init__(self):
        # Ensure Config is initialized to get correct profile paths
        Config.initialize()
        db_path = Config.get_db_path("expense")
        self.repo    = ExpenseRepository(db_path=db_path)
        self.service = ExpenseService(self.repo)
        self.view    = ExpenseCLIView()
        self.calc    = ExpenseCalculator()
        self.budget  = BudgetService()
        self.running = True

    def run(self):
        handlers = {
            "1": self.add_expense,
            "2": self.view_all,
            "3": self.monthly_summary,
            "4": self.by_category,
            "5": self.budget_status,
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

    def add_expense(self):
        exp_obj = self.view.get_expense_input()
        if exp_obj:
            result = run_query(self.service.record_expense(
                amount=exp_obj.amount,
                description=exp_obj.description,
                category=exp_obj.category.value,
                payment_method=exp_obj.payment_method.value,
                date=exp_obj.date,
                is_recurring=exp_obj.is_recurring,
                recurring_period=exp_obj.recurring_period
            ))
            self.view.show_success(f"Record saved. ID: {result['id']}")

            # Show newly unlocked rewards
            for reward in result.get("newly_unlocked", []):
                self.view.show_success(f"🏆 REWARD UNLOCKED: {reward['description']}")
            self.view.pause()

    def view_all(self):
        self.view.show_expense_list(run_query(self.service.get_expenses()))

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
        for i, c in enumerate(ExpenseCategory, 1):
            type_table.add_row(f"[bold {ACCENT}][{i}][/]", c.value.upper())
        self.view.console.print("\n [bold white]SELECT_CATEGORY[/]")
        self.view.console.print(Panel(type_table, border_style="#333333", box=box.SQUARE, padding=(1, 2)))
        try:
            choice_str = self.view.get_input("Selection (1-9)")
            choice   = int(choice_str) - 1
            category = list(ExpenseCategory)[choice].value
            self.view.show_expense_list(run_query(self.service.get_expenses(category=category)))
        except (ValueError, IndexError):
            self.view.show_error("Invalid selection")

    def budget_status(self):
        self.view.show_info("Budget check not fully implemented for SQLite in this phase.")
        self.view.pause()

    def delete_record(self):
        expenses = run_query(self.service.get_expenses())
        if not expenses:
            self.view.show_error("No records found for deletion")
            return

        self.view.show_expense_list(expenses)
        try:
            id_str = self.view.get_input("ID to remove (0 to cancel)")
            id_to_delete = int(id_str)
            if id_to_delete == 0: return

            if Confirm.ask(f" [bold red]![/] Confirm deletion of ID {id_to_delete}?", default=False):
                if run_query(self.service.delete_expense(id_to_delete)):
                    self.view.show_success(f"Record {id_to_delete} purged")
                else:
                    self.view.show_error("Deletion failed (ID not found)")
            self.view.pause()
        except ValueError:
            self.view.show_error("Invalid ID format")

    def _exit(self):
        self.running = False


def main():
    app = ExpenseTrackerApp()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
()
