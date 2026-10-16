"""
behavioral-finance/interface/cli.py
=====================================
Interface Layer — Command-Line Interface for Behavioral Finance analysis.
ULTIMATE: Pixel-Perfect Stock Analyzer Aesthetic.
"""

import argparse
from datetime import date
from typing import List

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..application.use_cases import (
    AnalyseFBSUseCase,
    AnalyseFragilityUseCase,
    ListImpulseTransactionsUseCase,
    MonthlyReportUseCase,
)
from ..domain.models import FBSResult, FragilityResult, ImpulseTransaction

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# § STYLES (Identical to Stock Analyzer TUI)
# ─────────────────────────────────────────────────────────────────────────────

ACCENT = "#5fafff"  # The specific "Stock Analyzer" Blue
BORDER_COLOR = "#333333"
BG_PANEL = "#1a1b1e"

def _get_grade_color(grade: str) -> str:
    return {
        "A": "bright_green",
        "B": "green",
        "C": "yellow",
        "D": "orange3",
        "E": "red",
        "F": "bright_red",
    }.get(grade, "white")

def _fmt_idr(amount: float) -> str:
    if abs(amount) >= 1_000_000: return f"Rp{amount/1_000_000:.1f}M"
    if abs(amount) >= 1_000:     return f"Rp{amount/1_000:.0f}K"
    return f"Rp{amount:,.0f}"

# ─────────────────────────────────────────────────────────────────────────────
# § COMPONENTS (Stock Analyzer Patterns)
# ─────────────────────────────────────────────────────────────────────────────

def _make_score_panel(title: str, score: float, label: str, grade: str, details_table: Table) -> Panel:
    """Matches the 'DetailScreen' aesthetic of Stock Analyzer."""
    color = _get_grade_color(grade)

    # Progress Bar matches TUI style
    bar_width = 25
    filled = int(score / 100 * bar_width)
    bar = Text.assemble(("█" * filled, color), ("█" * (bar_width - filled), "#222"))

    content = Group(
        Align.center(Text(f"{title}", style="bold dim")),
        Align.center(Text(f"{score:.1f}", style=f"bold {color} size 20")),
        Align.center(bar),
        Text(f"\n{label.upper()}", style=f"bold {color}", justify="center"),
        Rule(style=BORDER_COLOR),
        details_table
    )

    return Panel(
        content,
        border_style=BORDER_COLOR,
        padding=(1, 2),
        box=box.SQUARE
    )

def present_fbs(result: FBSResult) -> Panel:
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    for name, score in result.component_scores.items():
        label = name.replace("_", " ").title()
        comp_color = "green" if score > 70 else ("yellow" if score > 40 else "red")
        table.add_row(f"[dim]{label}[/]", f"[bold {comp_color}]{score:>5.1f}[/]")

    table.add_row(Rule(style=BORDER_COLOR), Rule(style=BORDER_COLOR))
    table.add_row("[dim]Saving Rate[/]", f"[bold]{result.saving_rate:.1f}%[/]")
    table.add_row("[dim]Impulse Idx[/]", f"[bold]{result.impulse_index:.1f}%[/]")

    return _make_score_panel("BEHAVIORAL SCORE", result.score, result.label, result.grade, table)

def present_fragility(result: FragilityResult) -> Panel:
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_row("[dim]Income Sources[/]", f"[bold]{result.income_sources}[/]")
    table.add_row("[dim]Emergency Buff[/]", f"[bold]{result.emergency_months:.1f} mo[/]")

    conc_pct = result.asset_concentration * 100
    conc_color = "green" if conc_pct < 40 else ("yellow" if conc_pct < 70 else "red")
    table.add_row("[dim]Concentration[/]", f"[bold {conc_color}]{conc_pct:.1f}%[/]")

    table.add_row(Rule(style=BORDER_COLOR), Rule(style=BORDER_COLOR))
    table.add_row(Text("Liquidity Risk Analysis", style="dim italic", justify="center"), "")

    return _make_score_panel("RISK FRAGILITY", result.score, result.label, result.grade, table)

def present_impulse(transactions: List[ImpulseTransaction]) -> None:
    """Matches Stock Analyzer's DataTable aesthetic."""
    table = Table(
        box=box.SIMPLE,
        header_style=f"bold {ACCENT}",
        expand=True,
        border_style=BORDER_COLOR
    )
    table.add_column("DATE", style="dim")
    table.add_column("CATEGORY")
    table.add_column("AMOUNT", justify="right")
    table.add_column("SCORE", justify="center")
    table.add_column("BIAS", style="italic")

    for itx in transactions:
        t = itx.transaction
        score = itx.impulse_score * 100
        color = "red" if score > 70 else ("yellow" if score > 40 else "green")
        table.add_row(
            t.date[5:],
            t.category.upper(),
            _fmt_idr(t.amount),
            f"[{color}]● {score:.0f}%[/]",
            itx.bias_applied.replace("_", " ").title()
        )

    console.print(table)

def present_report(report: dict) -> None:
    """Full immersive report."""
    totals = report["totals"]

    # 1. Header Panel
    header_content = Table.grid(expand=True)
    header_content.add_column()
    header_content.add_column(justify="right")
    header_content.add_row(
        f" [bold cyan]BEHAVIORAL PSYCHOLOGY AUDIT[/] [dim]• {report['period'].upper()}[/]",
        f"[bold {ACCENT}]SESSION ACTIVE[/] "
    )
    console.print(Panel(header_content, box=box.SQUARE, border_style=BORDER_COLOR, padding=(0, 1)))

    # 2. Financial Overview
    inc_val = totals['income_this']
    exp_val = totals['expense_this']
    net = inc_val - exp_val
    net_color = "bright_green" if net >= 0 else "bright_red"

    overview = Table.grid(expand=True, padding=1)
    overview.add_column(ratio=1); overview.add_column(ratio=1); overview.add_column(ratio=1)

    overview.add_row(
        Panel(f" [bold green]{_fmt_idr(inc_val)}[/]\n [dim]Prev: {_fmt_idr(totals['income_prev'])}[/]", title="[bold]INC[/]", border_style="green", box=box.SQUARE),
        Panel(f" [bold red]{_fmt_idr(exp_val)}[/]\n [dim]Prev: {_fmt_idr(totals['expense_prev'])}[/]", title="[bold]EXP[/]", border_style="red", box=box.SQUARE),
        Panel(f" [bold {net_color}]{_fmt_idr(net)}[/]\n [dim]{'SURPLUS' if net >= 0 else 'DEFICIT'}[/]", title="[bold]NET[/]", border_style=net_color, box=box.SQUARE)
    )
    console.print(overview)

    # 3. Scores (Side-by-Side)
    console.print(Columns([present_fbs(report["fbs"]), present_fragility(report["fragility"])], expand=True, equal=True))

    # 4. Impulse Table
    if report["top_impulse_transactions"]:
        present_impulse(report["top_impulse_transactions"][:5])

    # 5. Status Panel (The Bottom Bar)
    status_content = Table.grid(expand=True)
    status_content.add_row(f"[bold {ACCENT}]ANALYSIS COMPLETE[/]")
    status_content.add_row("[bright_green]██████████████████████████████████████████████████████████████████████████████[/]")

    console.print(Panel(status_content, box=box.SQUARE, border_style=BORDER_COLOR, padding=(0, 1)))
    console.print()

# ─────────────────────────────────────────────────────────────────────────────
# § CLI
# ─────────────────────────────────────────────────────────────────────────────

def _default_year()  -> int: return date.today().year
def _default_month() -> int: return date.today().month

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="behavioral-finance")
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--year",      type=int, default=_default_year())
    parent.add_argument("--month",     type=int, default=_default_month())
    parent.add_argument("--emergency", type=float, default=0.0)

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report", parents=[parent])
    sub.add_parser("fbs", parents=[parent])
    sub.add_parser("fragility", parents=[parent])
    imp = sub.add_parser("impulse", parents=[parent])
    imp.add_argument("--top", type=int, default=10)

    return parser

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    year, month = args.year, args.month
    emergency = getattr(args, "emergency", 0.0)

    if args.command == "report":
        present_report(MonthlyReportUseCase().execute(year, month, emergency))
    elif args.command == "fbs":
        console.print(present_fbs(AnalyseFBSUseCase().execute(year, month, emergency)))
    elif args.command == "fragility":
        console.print(present_fragility(AnalyseFragilityUseCase().execute(year, month, emergency)))
    elif args.command == "impulse":
        present_impulse(ListImpulseTransactionsUseCase().execute(year, month, top_n=args.top))

if __name__ == "__main__":
    main()
