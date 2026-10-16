from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation as DecimalException
from typing import Dict, List

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table

from packages.core.domain.models import Expense, ExpenseCategory, PaymentMethod

# ─────────────────────────────────────────────────────────────────────────────
# § STYLES (Identical to Stock Analyzer TUI - MarketAnalyzerApp)
# ─────────────────────────────────────────────────────────────────────────────

ACCENT = "#5fafff"       # Light Blue
BG_COLOR = "#0c0d10"     # Dark Gray-Blue
PANEL_BG = "#1a1b1e"    # Slightly Lighter Panel BG
BORDER_COLOR = "#333333" # Subtle Border
BORDER_DETAIL = "#555555" # Detail Border

# ── Payment method display config ───────────────────────────────────────────
PAY_DISPLAY = {
    PaymentMethod.CASH:          "CASH",
    PaymentMethod.DEBIT_CARD:    "DEBIT_CARD",
    PaymentMethod.CREDIT_CARD:   "CREDIT_CARD",
    PaymentMethod.E_WALLET:      "E_WALLET",
    PaymentMethod.BANK_TRANSFER: "BANK_TRANSFER",
    PaymentMethod.OVO:           "OVO",
    PaymentMethod.GOPAY:         "GOPAY",
    PaymentMethod.SHOPEEPAY:     "SHOPEEPAY",
    PaymentMethod.QRIS:          "QRIS",
}

CAT_COLORS = {
    "food": "yellow", "transport": "cyan", "housing": "blue",
    "entertainment": "magenta", "health": "green", "shopping": "red",
    "education": "bright_blue", "investment": "gold1", "other": "dim white",
}


class ExpenseCLIView:
    """All terminal I/O for the Expense Tracker."""

    def __init__(self):
        self.console = Console()

    # ─────────────── Screen Helpers ──────────────────────────────────

    def clear(self):
        self.console.clear()

    def show_header(self, subtitle: str = ""):
        """Standardized Header pattern matching Stock Analyzer."""
        header = Table.grid(expand=True)
        header.add_column()
        header.add_column(justify="right")

        sub_text = f" [dim white]• {subtitle.upper()}[/dim white]" if subtitle else ""
        header.add_row(
            f" [bold {ACCENT}]EXPENSE_TRACKER_CORE[/bold {ACCENT}]{sub_text}",
            f"[bold {ACCENT}]SYSTEM_READY[/] "
        )
        self.console.print(header)
        self.console.print(Rule(style="#222222"))

    def show_status_bar(self, message: str = "READY"):
        """Status bar matching Stock Analyzer's status_panel."""
        self.console.print(Rule(style=f"double {BORDER_COLOR}"))

        status_content = Table.grid(expand=True)
        status_content.add_column()
        status_content.add_row(f" [bold {ACCENT}]{message.upper()}[/]")

        # Subtle progress bar simulation (Textual style)
        bar = f"[{ACCENT}]" + "━" * 40 + "[/][#222222]" + "━" * 20 + "[/]"
        status_content.add_row(f" {bar} [dim]100%[/]")

        self.console.print(Panel(
            status_content,
            box=box.SQUARE,
            border_style="none",
            style=f"on {PANEL_BG}",
            padding=(1, 1)
        ))

    def pause(self, msg: str = "\n Press Enter to continue..."):
        self.console.print(f" [dim]{msg}[/]")
        input()

    def show_info(self, msg: str):
        self.console.print(f"\n [bold {ACCENT}]INFO[/] {msg}")

    def show_success(self, msg: str):
        self.console.print(f"\n [bold green]OK[/] {msg}")

    def show_error(self, msg: str):
        self.console.print(f"\n [bold red]ERR[/] {msg}")
        self.pause()

    def get_input(self, prompt: str, default: str = None) -> str:
        return Prompt.ask(f" [bold {ACCENT}]»[/] {prompt}", default=default)

    def _pay_label(self, pm: PaymentMethod) -> str:
        return PAY_DISPLAY.get(pm, str(pm.value)).upper()

    def _cat_bar(self, amount: float, max_amount: float, width: int = 18) -> str:
        filled = int((amount / max_amount) * width) if max_amount else 0
        return "━" * filled + "·" * (width - filled)

    # ─────────────── Menus ───────────────────────────────────────────

    def show_main_menu(self) -> str:
        self.clear()
        self.show_header("Main Menu")

        menu = [
            ("1", "ADD_EXPENSE",      "Record new spending"),
            ("2", "VIEW_ALL",         "History and logs"),
            ("3", "MONTHLY_STATS",    "Summary by month"),
            ("4", "CATEGORY_VIEW",    "Filter by category"),
            ("5", "BUDGET_CHECK",     "Check budget status"),
            ("6", "DELETE_RECORD",    "Remove entry"),
            ("0", "BACK",             "Return to dashboard"),
        ]

        t = Table.grid(padding=(0, 2))
        for num, title, desc in menu:
            t.add_row(f"[bold {ACCENT}][{num}][/] {title}", f"[dim]{desc}[/]")

        self.console.print("\n")
        self.console.print(Panel(
            t,
            border_style=BORDER_COLOR,
            box=box.SQUARE,
            padding=(1, 4),
            title="[bold cyan]SELECT_OPERATION[/]"
        ))
        self.console.print("\n")
        self.show_status_bar("ORCHESTRATOR_ACTIVE")

        return self.console.input(f"\n [bold {ACCENT}]Command »[/] ").strip()

    # ─────────────── Input Forms ──────────────────────────────────────

    def get_expense_input(self):
        self.clear()
        self.show_header("Add Expense")

        # Select Category
        cats = list(ExpenseCategory)
        cat_table = Table.grid(padding=(0, 2))
        for i, c in enumerate(cats, 1):
            cat_table.add_row(f"[bold {ACCENT}][{i}][/]", c.value.upper())

        self.console.print("\n [bold cyan]CATEGORIES[/]")
        self.console.print(Panel(cat_table, border_style=BORDER_COLOR, box=box.SQUARE, padding=(1, 2)))

        try:
            choice = self.get_input("Category (number)")
            cat_idx = int(choice) - 1
            category = cats[cat_idx]

            # Select Payment Method
            pays = list(PaymentMethod)
            pay_table = Table.grid(padding=(0, 2))
            for i, p in enumerate(pays, 1):
                pay_table.add_row(f"[bold {ACCENT}][{i}][/]", self._pay_label(p))

            self.console.print("\n [bold cyan]PAYMENT_METHODS[/]")
            self.console.print(Panel(pay_table, border_style=BORDER_COLOR, box=box.SQUARE, padding=(1, 2)))

            pay_choice = int(self.get_input("Payment (number)")) - 1
            payment_method = pays[pay_choice]

            description = self.get_input("Description")
            amount_raw = self.get_input("Amount (IDR)")
            amount = Decimal(amount_raw.replace(",", ""))

            date_str = self.get_input("Date (DD-MM-YYYY) [dim]Enter for today[/dim]", default="")
            date = datetime.strptime(date_str, "%d-%m-%Y") if date_str else datetime.now()

            is_recurring = Confirm.ask(f" [bold {ACCENT}]»[/] Recurring expense?", default=False)
            recurring_period = None
            if is_recurring:
                recurring_period = Prompt.ask(f" [bold {ACCENT}]»[/] Period", choices=["monthly", "yearly"], default="monthly")

            # Preview
            self.clear()
            self.show_header("Confirm Entry")

            rows = [
                ("Category", category.value.upper()),
                ("Payment", self._pay_label(payment_method)),
                ("Desc", description),
                ("Amount", f"[bold red]Rp{amount:,.0f}[/]"),
                ("Date", date.strftime('%d-%m-%Y')),
            ]
            if is_recurring:
                rows.append(("Recur", recurring_period.upper()))

            t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
            for l, v in rows: t.add_row(f"[dim]{l}[/]", v)

            self.console.print("\n")
            self.console.print(Align.center(Panel(
                t,
                title="[bold cyan]PREVIEW[/]",
                border_style=BORDER_DETAIL,
                style=f"on {PANEL_BG}",
                box=box.SQUARE,
                padding=(1, 4),
                width=50
            )))

            if not Confirm.ask(f"\n [bold {ACCENT}]»[/] Save record?", default=True):
                return None

            return Expense(
                amount=amount, description=description, category=category,
                payment_method=payment_method, date=date,
                is_recurring=is_recurring, recurring_period=recurring_period,
            )

        except (ValueError, IndexError, DecimalException) as e:
            self.show_error(f"Invalid input: {e}")
            return None

    def show_expense_list(self, expenses: List[Expense]):
        self.clear()
        self.show_header("History")

        if not expenses:
            self.console.print("\n [dim]No records found.[/]")
            self.pause()
            return

        t = Table(
            box=None,
            header_style=f"bold {ACCENT}",
            expand=True,
            title=f"[bold {ACCENT}]EXPENSE_LEDGER[/]",
            padding=(0, 1)
        )
        t.add_column("Sig", width=4, justify="center")
        t.add_column("DATE", justify="center")
        t.add_column("CAT")
        t.add_column("SOURCE")
        t.add_column("PAYMENT", style="dim white")
        t.add_column("AMOUNT", justify="right")

        total = Decimal("0")
        for exp in sorted(expenses, key=lambda x: x.date, reverse=True):
            c = CAT_COLORS.get(exp.category.value, "white")
            t.add_row(
                "[bold red]E[/]",
                f"[dim white]{exp.date.strftime('%d-%m-%y')}[/dim white]",
                f"[{c}]{exp.category.value.upper()[:12]}[/]",
                exp.description[:24],
                f"[dim white]{self._pay_label(exp.payment_method)[:12]}[/dim white]",
                f"[bold red]Rp{exp.amount:,.0f}[/]"
            )
            total += exp.amount

        self.console.print()
        self.console.print(t)
        self.console.print(Rule(style=BORDER_COLOR))
        self.console.print(f" [bold {ACCENT}]TOTAL_SPENT:[/] [bold red]Rp{total:,.0f}[/]")
        self.console.print()
        self.show_status_bar(f"{len(expenses)} RECORDS")
        self.pause()

    def show_monthly_summary(self, summary: Dict, year: int, month: int):
        self.clear()
        self.show_header(f"Summary: {month:02d}/{year}")

        total = Decimal(str(summary['total']))
        avg_day = Decimal(str(summary['average_per_day']))

        # Metrics Panel
        metrics = Table.grid(expand=True, padding=(0, 2))
        metrics.add_row(
            f"[dim]TOTAL_SPENT:[/]\n[bold red]Rp{total:,.0f}[/]",
            f"[dim]Count:[/]\n[bold cyan]{summary['count']}[/]",
            f"[dim]Avg/Day:[/]\n[bold yellow]Rp{avg_day:,.0f}[/]"
        )

        self.console.print("\n")
        self.console.print(Panel(metrics, box=box.SQUARE, border_style=BORDER_COLOR, padding=(1, 2)))

        if summary.get("by_category"):
            max_v = max(summary["by_category"].values()) or 1
            t = Table(box=None, header_style=f"bold {ACCENT}", expand=True)
            t.add_column("CATEGORY")
            t.add_column("INTENSITY", width=22)
            t.add_column("AMOUNT", justify="right")
            t.add_column("PCT", justify="right")

            for cat, amt_val in sorted(summary["by_category"].items(), key=lambda x: x[1], reverse=True):
                amt = Decimal(str(amt_val))
                pct = (amt / total) * Decimal("100") if total else Decimal("0")
                c = CAT_COLORS.get(cat, "white")
                t.add_row(
                    cat.upper(),
                    f"[{c}]{self._cat_bar(float(amt), float(max_v))}[/{c}]",
                    f"Rp{amt:,.0f}",
                    f"{pct:.1f}%"
                )

            self.console.print("\n [bold cyan]BREAKDOWN_BY_CATEGORY[/]")
            self.console.print(t)

        self.console.print()
        self.show_status_bar("ANALYSIS_STABLE")
        self.pause()

    def show_budget_status(self, budget_check: Dict):
        self.clear()
        self.show_header("Budget vs Actual")

        status_cfg = {
            "under":   ("green",  "STABLE"),
            "warning": ("yellow", "WARNING"),
            "over":    ("red",    "CRITICAL"),
        }

        t = Table(box=None, header_style=f"bold {ACCENT}", expand=True, padding=(0, 1))
        t.add_column("CATEGORY")
        t.add_column("UTILIZATION", width=22)
        t.add_column("BUDGET", justify="right")
        t.add_column("ACTUAL", justify="right")
        t.add_column("STATUS", justify="center")

        for cat, data in budget_check.items():
            c, label = status_cfg.get(data["status"], ("white", "UNKNOWN"))
            pct = data["pct_used"]
            blen = min(int(pct / 5), 20)
            bar = f"[{c}]{'━'*blen}[/{c}][dim]{'·'*(20-blen)}[/dim]"

            t.add_row(
                cat.upper(),
                bar,
                f"Rp{data['budget']:,.0f}",
                f"[{c}]Rp{data['actual']:,.0f}[/]",
                f"[{c}]{label}[/]"
            )

        self.console.print()
        self.console.print(t)
        self.console.print(Rule(style=BORDER_COLOR))
        self.show_status_bar("BUDGET_AUDIT_COMPLETE")
        self.pause()
