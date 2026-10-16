# ─── receipt_reader/ui/cli_view.py ────────────────────────────────────────────
# Interface Layer — all terminal I/O for the Receipt Reader.
# UPGRADED: High-Fidelity TUI Edition (Identical to Stock Analyzer Aesthetic).
# ─────────────────────────────────────────────────────────────────────────────

import logging
import re
from datetime import datetime
from typing import List

from rich.console import Console, Group

# Setup logging
logger = logging.getLogger(__name__)

from rich import box
from rich.align import Align
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from apps.cli.receipt_reader.core.interfaces import ExpenseCategory, IUserInterface, Money, ReceiptData, TransactionType

# ─────────────────────────────────────────────────────────────────────────────
# § STYLES (Identical to Stock Analyzer TUI - MarketAnalyzerApp)
# ─────────────────────────────────────────────────────────────────────────────

ACCENT = "#5fafff"       # Light Blue
BG_COLOR = "#0c0d10"     # Dark Gray-Blue
PANEL_BG = "#1a1b1e"    # Slightly Lighter Panel BG
BORDER_COLOR = "#333333" # Subtle Border
BORDER_DETAIL = "#555555" # Detail Border

class RichReceiptView(IUserInterface):
    """All terminal I/O for the Receipt Reader."""

    def __init__(self):
        self.console = Console()

    # ══════════════════════════════════════════════════════════════════
    # § SCREEN HELPERS
    # ══════════════════════════════════════════════════════════════════

    def clear(self):
        self.console.clear()

    def show_header(self, subtitle: str = ""):
        """Standardized Header pattern matching Stock Analyzer."""
        header = Table.grid(expand=True)
        header.add_column()
        header.add_column(justify="right")

        sub_text = f" [dim]• {subtitle.upper()}[/dim]" if subtitle else ""
        header.add_row(
            f" [bold cyan]RECEIPT_SCANNER_CORE[/bold cyan]{sub_text}",
            f"[bold {ACCENT}]ENGINE_ACTIVE[/] "
        )
        # Match Textual Header: Minimalist border
        self.console.print(header)
        self.console.print(Rule(style="#222222"))

    def show_status_bar(self, message: str = "SYSTEM_READY"):
        """Status bar matching Stock Analyzer's status_panel."""
        # Stock Analyzer uses double border top, background #1a1b1e, accent text
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

    def show_success(self, message: str):
        self.console.print(f"\n [bold green]OK[/] {message}")

    def show_error(self, message: str):
        self.console.print(f"\n [bold red]ERR[/] {message}")

    def confirm_action(self, message: str) -> bool:
        return Confirm.ask(f" [bold yellow]?[/] {message}")

    def get_input(self, prompt: str) -> str:
        return Prompt.ask(f" [bold {ACCENT}]»[/] {prompt}")

    # ══════════════════════════════════════════════════════════════════
    # § DISPLAY VIEWS
    # ══════════════════════════════════════════════════════════════════

    def display_receipt(self, receipt: ReceiptData) -> None:
        """Show a single receipt detail — matches 'DetailScreen' look."""
        self.clear()
        self.show_header("Scan Result")

        engine = receipt.metadata.get("engine", "?")
        is_income = receipt.transaction_type == TransactionType.INCOME
        tx_color  = "green" if is_income else "red"
        tx_label  = "INCOME" if is_income else "EXPENSE"
        cat_str   = receipt.category.value if hasattr(receipt.category, "value") else str(receipt.category)

        # Content structure similar to DetailScreen
        rows = [
            ("Merchant", f"[bold white]{receipt.merchant_name or 'Unknown'}[/]"),
            ("Amount", f"[bold {tx_color}]Rp{receipt.total_amount.amount:,.0f}[/]"),
            ("Date", receipt.transaction_date.strftime("%d-%m-%Y")),
            ("Category", f"[bold]{cat_str}[/]"),
            ("Type", f"[{tx_color}]{tx_label}[/]"),
            ("Payment", receipt.payment_method.value.upper() if receipt.payment_method else "-"),
        ]

        if receipt.metadata.get("remarks"):
            rows.append(("Remarks", str(receipt.metadata["remarks"])))

        t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
        for label, val in rows:
            t.add_row(f"[dim]{label}[/]", val)

        # Build items if present
        items_group = None
        if receipt.items:
            it_table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
            for item in receipt.items:
                it_table.add_row(f"• [dim]{item.name[:25]}[/]", f"x{item.quantity:.0f}", f"Rp{item.total_price.amount:,.0f}")
            items_group = Group(Rule(style=BORDER_COLOR), it_table)

        content = Group(
            Text("\nTRANSACTION_DETAIL", style="bold cyan"),
            Rule(style=BORDER_COLOR),
            t,
            items_group if items_group else Text("")
        )

        # Use PANEL_BG and BORDER_DETAIL to match DetailScreen
        self.console.print("\n")
        self.console.print(Align.center(Panel(
            content,
            subtitle=f"[dim]Engine: {engine} ({receipt.confidence_score:.0%})[/dim]",
            border_style=BORDER_DETAIL,
            style=f"on {PANEL_BG}",
            box=box.SQUARE,
            padding=(1, 4),
            width=60
        )))
        self.console.print("\n")
        self.show_status_bar("ANALYSIS_COMPLETE")

    def display_batch_results(self, receipts: List[ReceiptData]) -> None:
        """Render processed receipts as a High-Fidelity Table."""
        if not receipts:
            self.show_error("No receipts to display.")
            return

        # Match DataTable look: No border, specific header style
        table = Table(
            box=None,
            header_style=f"bold {ACCENT}",
            expand=True,
            title="[bold cyan]BATCH_SCAN_RESULTS[/]",
            padding=(0, 1)
        )
        table.add_column("Sig", width=4, justify="center")
        table.add_column("MERCHANT")
        table.add_column("DATE", justify="center")
        table.add_column("AMOUNT", justify="right")
        table.add_column("CAT", justify="center")
        table.add_column("ENGINE", style="dim")

        for i, r in enumerate(receipts, 1):
            cat_str = r.category.value if hasattr(r.category, "value") else str(r.category)
            engine  = r.metadata.get("engine", "?")
            is_inc  = r.transaction_type == TransactionType.INCOME
            color   = "green" if is_inc else "red"
            sig     = "[bold green]I[/]" if is_inc else "[bold red]E[/]"

            table.add_row(
                sig,
                r.merchant_name or "Unknown",
                r.transaction_date.strftime("%d-%m-%y"),
                f"[{color}]Rp{r.total_amount.amount:,.0f}[/]",
                cat_str[:12],
                engine[:10]
            )

        self.console.print()
        self.console.print(table)
        self.console.print(Rule(style=BORDER_COLOR))

    # ══════════════════════════════════════════════════════════════════
    # § INPUT FORMS
    # ══════════════════════════════════════════════════════════════════

    def edit_receipt(self, receipt: ReceiptData) -> ReceiptData:
        """Interactive single-receipt editor."""
        from apps.cli.receipt_reader.core.interfaces import TransactionType

        self.clear()
        self.show_header("Edit Transaction")

        is_inc   = receipt.transaction_type == TransactionType.INCOME
        tx_color = "green" if is_inc else "red"

        self.console.print(f"\n [bold yellow]EDITING:[/] [{tx_color}]{receipt.merchant_name}[/] | Rp{receipt.total_amount.amount:,.0f}")
        self.console.print(" [dim]Press Enter to keep current, 'q' to cancel[/dim]\n")

        def ask_safe(prompt: str, default: str = None, choices: List[str] = None):
            val = Prompt.ask(f"  [bold {ACCENT}]»[/] {prompt}", default=default, choices=choices)
            if val.lower() in ("q", "exit"):
                raise KeyboardInterrupt("Edit cancelled")
            return val

        try:
            receipt.merchant_name = ask_safe("Merchant", default=receipt.merchant_name)

            while True:
                cur_amt = f"{receipt.total_amount.amount:,.0f}".replace(",", "")
                new_amt = ask_safe("Amount (IDR)", default=cur_amt)
                if new_amt == cur_amt: break
                try:
                    val = float(re.sub(r"[^\d.]", "", new_amt))
                    if val > 0:
                        receipt.total_amount = Money(val, "IDR")
                        break
                    else: self.show_error("Amount must be positive.")
                except Exception: self.show_error("Invalid amount format.")

            while True:
                cur_date = receipt.transaction_date.strftime("%d-%m-%Y")
                new_date = ask_safe("Date (DD-MM-YYYY)", default=cur_date)
                if new_date == cur_date: break
                try:
                    d, m, y = [int(x) for x in new_date.split("-")]
                    if y < 100: y += 2000
                    receipt.transaction_date = datetime(y, m, d)
                    break
                except Exception: self.show_error("Invalid date format.")

            new_type = ask_safe("Type", choices=["expense", "income"], default=receipt.transaction_type.value)
            receipt.transaction_type = TransactionType(new_type)

            cats = list(ExpenseCategory)
            cat_choices = [str(i+1) for i in range(len(cats))] + [c.value for c in cats]
            cur_cat = receipt.category.value if hasattr(receipt.category, "value") else str(receipt.category)

            self.console.print(f"  [dim]{'  '.join(f'[{i+1}]{c.value}' for i, c in enumerate(cats))}[/dim]")
            new_cat = ask_safe("Category (name/number)", default=cur_cat)
            if new_cat != cur_cat:
                if new_cat.isdigit():
                    idx = int(new_cat) - 1
                    if 0 <= idx < len(cats): receipt.category = cats[idx]
                else:
                    try: receipt.category = ExpenseCategory(new_cat.lower())
                    except Exception:
                        logger.exception("Failed to parse category: %s", new_cat)
                        pass

        except KeyboardInterrupt:
            self.console.print("\n [bold yellow]![/] Edit cancelled. Changes discarded.")
            return receipt

        self.show_success("Transaction updated.")
        return receipt
