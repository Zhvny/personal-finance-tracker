"""
Unified Binance-style TUI components for Finance Tracker.
Follows DESIGN.md: Yellow (#FCD535) and Dark (#0B0E11) theme.
"""

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# Binance Design Tokens
BINANCE_YELLOW = "#FCD535"
BINANCE_DARK = "#0B0E11"
BINANCE_SURFACE = "#1E2329"
TRADING_UP = "#0ECB81"
TRADING_DOWN = "#F6465D"

binance_theme = Theme({
    "primary": BINANCE_YELLOW,
    "background": BINANCE_DARK,
    "surface": BINANCE_SURFACE,
    "up": TRADING_UP,
    "down": TRADING_DOWN,
    "muted": "#707A8A"
})

console = Console(theme=binance_theme)

class BinanceTUI:
    @staticmethod
    def render_task_summary(
        task_name: str,
        completed_work: list,
        validation_results: str,
        docs_updated: list,
        risks: list,
        next_task: str
    ):
        """
        Renders a structured task report in Binance style.
        """
        content = []

        # Completed Work Section
        work_table = Table(box=None, header_style=f"bold {BINANCE_YELLOW}", padding=(0, 1))
        work_table.add_column("COMPLETED WORK")
        for item in completed_work:
            work_table.add_row(f"• {item}")
        content.append(work_table)
        content.append("")

        # Validation Section
        content.append(Panel(
            validation_results,
            title="[bold up]VALIDATION SUCCESS[/]",
            border_style=TRADING_UP,
            box=box.ROUNDED
        ))
        content.append("")

        # Documentation Section
        docs_table = Table(box=None, header_style="bold white", padding=(0, 1))
        docs_table.add_column("HUB UPDATES")
        for doc in docs_updated:
            docs_table.add_row(f"[primary]✓[/] {doc}")
        content.append(docs_table)
        content.append("")

        # Next Task
        content.append(Panel(
            f"[bold white]NEXT:[/] {next_task}",
            border_style=BINANCE_YELLOW,
            box=box.SIMPLE
        ))

        # Main Container
        console.print(Panel(
            Group(*content),
            title=f"[bold primary] {task_name.upper()} [/]",
            subtitle="[muted]Alpha Structured Workflow[/]",
            border_style=BINANCE_YELLOW,
            padding=(1, 2)
        ))

    @staticmethod
    def render_lifecycle_progress(current_step: int):
        """
        Renders the 7-step lifecycle progress bar.
        """
        steps = ["Analyze", "Plan", "Execute", "Validate", "Document", "Verify", "Next"]

        table = Table(box=None, show_header=False, padding=(0, 1))
        row = []
        for i, step in enumerate(steps, 1):
            if i < current_step:
                row.append(f"[up]✓ {step}[/]")
            elif i == current_step:
                row.append(f"[bold primary]▶ {step.upper()}[/]")
            else:
                row.append(f"[muted]{step}[/]")

        table.add_row(*row)
        console.print(table)
