from datetime import datetime
from decimal import Decimal
from typing import List

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table

from packages.core.domain.models import Income, IncomeType

# ─────────────────────────────────────────────────────────────────────────────
# § STYLES (Identical to Stock Analyzer TUI - MarketAnalyzerApp)
# ─────────────────────────────────────────────────────────────────────────────

ACCENT = "#5fafff"       # Light Blue
BG_COLOR = "#0c0d10"     # Dark Gray-Blue
PANEL_BG = "#1a1b1e"    # Slightly Lighter Panel BG
BORDER_COLOR = "#333333" # Subtle Border
BORDER_DETAIL = "#555555" # Detail Border

class IncomeCLIView:
    """All terminal I/O for the Income Tracker.
    
    - High Cohesion: each method manages exactly one screen.
    - Low Coupling: no service/repository references; depends only on core.models.
    """

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

        sub_text = f" [dim]• {subtitle.upper()}[/dim]" if subtitle else ""
        header.add_row(
            f" [bold cyan]INCOME_TRACKER_CORE[/bold cyan]{sub_text}",
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

    def show_success(self, msg: str):
        self.console.print(f"\n [bold green]OK[/] {msg}")

    def show_error(self, msg: str):
        self.console.print(f"\n [bold red]ERR[/] {msg}")
        self.pause()

    def get_input(self, prompt: str, default: str = None) -> str:
        return Prompt.ask(f" [bold {ACCENT}]»[/] {prompt}", default=default)

    # ─────────────── Menus ───────────────────────────────────────────

    def show_main_menu(self) -> str:
        self.clear()
        self.show_header("Main Menu")

        menu = [
            ("1", "ADD_INCOME",      "Record new earnings"),
            ("2", "VIEW_ALL",        "History and logs"),
            ("3", "MONTHLY_STATS",   "Summary by month"),
            ("4", "CATEGORY_VIEW",   "Filter by type"),
            ("5", "TAX_ESTIMATE",    "PPh 21 projection"),
            ("6", "DELETE_RECORD",   "Remove entry"),
            ("0", "BACK",            "Return to dashboard"),
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

    def get_income_input(self):
        self.clear()
        self.show_header("Add Income")

        # Select Type
        type_table = Table.grid(padding=(0, 2))
        for i, t in enumerate(IncomeType, 1):
            type_table.add_row(f"[bold {ACCENT}][{i}][/]", t.value.upper())

        self.console.print("\n [bold cyan]INCOME_TYPES[/]")
        self.console.print(Panel(type_table, border_style=BORDER_COLOR, box=box.SQUARE, padding=(1, 2)))

        try:
            choice = self.get_input("Type (number)")
            type_idx = int(choice) - 1
            income_type = list(IncomeType)[type_idx]

            source = self.get_input("Source (e.g. Salary)")
            amount_raw = self.get_input("Amount (IDR)")
            amount = Decimal(amount_raw.replace(",", ""))

            date_str = self.get_input("Date (DD-MM-YYYY) [dim]Enter for today[/dim]", default="")
            date = datetime.strptime(date_str, "%d-%m-%Y") if date_str else datetime.now()

            description = self.get_input("Description [dim]Optional[/dim]", default="")
            is_taxed = Confirm.ask(f" [bold {ACCENT}]»[/] Already taxed?", default=False)

            # Confirmation View
            self.clear()
            self.show_header("Confirm Entry")

            rows = [
                ("Type", income_type.value.upper()),
                ("Source", source),
                ("Amount", f"[bold green]Rp{amount:,.0f}[/]"),
                ("Date", date.strftime('%d-%m-%Y')),
                ("Taxed", "YES" if is_taxed else "NO")
            ]

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

            return Income(
                amount=amount,
                source=source,
                income_type=income_type,
                date=date,
                description=description or None,
                is_taxed=is_taxed,
            )

        except Exception as e:
            self.show_error(f"Invalid input: {e}")
            return None

    # ─────────────── Display Views ────────────────────────────────────

    def show_income_list(self, incomes: List[Income]):
        self.clear()
        self.show_header("History")

        if not incomes:
            self.console.print("\n [dim]No records found.[/]")
            self.pause()
            return

        # DataTable style
        t = Table(
            box=None,
            header_style=f"bold {ACCENT}",
            expand=True,
            title="[bold cyan]INCOME_LEDGER[/]",
            padding=(0, 1)
        )
        t.add_column("Sig", width=4, justify="center")
        t.add_column("DATE", justify="center")
        t.add_column("TYPE")
        t.add_column("SOURCE")
        t.add_column("AMOUNT", justify="right")

        total = Decimal("0")
        for inc in incomes:
            t.add_row(
                "[bold green]I[/]",
                inc.date.strftime("%d-%m-%y"),
                inc.income_type.value.upper(),
                inc.source[:25],
                f"[bold green]Rp{inc.amount:,.0f}[/]"
            )
            total += inc.amount

        self.console.print()
        self.console.print(t)
        self.console.print(Rule(style=BORDER_COLOR))
        self.console.print(f" [bold cyan]TOTAL_CUMULATIVE:[/] [bold green]Rp{total:,.0f}[/]")
        self.console.print()
        self.show_status_bar(f"{len(incomes)} RECORDS")
        self.pause()

    def show_monthly_summary(self, summary: dict, year: int, month: int):
        self.clear()
        self.show_header(f"Summary: {month:02d}/{year}")

        total = Decimal(str(summary['total']))
        average = Decimal(str(summary['average']))

        # Metrics Panel
        metrics = Table.grid(expand=True, padding=(0, 2))
        metrics.add_row(
            f"[dim]Total:[/]\n[bold green]Rp{total:,.0f}[/]",
            f"[dim]Count:[/]\n[bold white]{summary['count']}[/]",
            f"[dim]Average:[/]\n[bold cyan]Rp{average:,.0f}[/]"
        )

        self.console.print("\n")
        self.console.print(Panel(metrics, box=box.SQUARE, border_style=BORDER_COLOR, padding=(1, 2)))

        if summary["by_type"]:
            t = Table(box=None, header_style=f"bold {ACCENT}", expand=True)
            t.add_column("TYPE")
            t.add_column("AMOUNT", justify="right")
            t.add_column("PERCENT", justify="right")

            for type_name, amount_val in summary["by_type"].items():
                amount = Decimal(str(amount_val))
                pct = (amount / total) * Decimal("100") if total else Decimal("0")
                t.add_row(type_name.upper(), f"Rp{amount:,.0f}", f"{pct:.1f}%")

            self.console.print("\n [bold cyan]BREAKDOWN_BY_TYPE[/]")
            self.console.print(t)

        self.console.print()
        self.show_status_bar("SUMMARY_COMPLETE")
        self.pause()

    def show_tax_estimate(self, annual_income: Decimal, tax: Decimal):
        self.clear()
        self.show_header("Tax Projection")

        effective_rate = (tax / annual_income) * Decimal('100') if annual_income > 0 else Decimal('0')
        monthly_net = (annual_income - tax) / Decimal('12')

        rows = [
            ("Gross Annual", f"Rp{annual_income:,.0f}"),
            ("PPh 21 Est.", f"[bold red]Rp{tax:,.0f}[/]"),
            ("Effective Rate", f"{effective_rate:.1f}%"),
            ("Monthly Net", f"[bold green]Rp{monthly_net:,.0f}[/]")
        ]

        t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
        for l, v in rows: t.add_row(f"[dim]{l}[/]", v)

        self.console.print("\n")
        self.console.print(Align.center(Panel(
            t,
            title="[bold cyan]TAX_ANALYSIS[/]",
            border_style="yellow",
            style=f"on {PANEL_BG}",
            box=box.SQUARE,
            padding=(1, 4),
            width=50
        )))

        self.console.print("\n [dim]Calculation based on standard PPh 21 progressive rates.[/]")
        self.show_status_bar("PROJECTION_STABLE")
        self.pause()
