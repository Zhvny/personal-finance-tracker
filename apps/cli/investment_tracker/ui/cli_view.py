from datetime import datetime
from typing import Dict, List, Optional

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table

from apps.cli.investment_tracker.core.calculator import ProfitCalculator
from apps.cli.investment_tracker.services.sell_service import SellResult
from packages.core.domain.models import Investment, InvestmentStatus, SellTransaction

# ─────────────────────────────────────────────────────────────────────────────
# § STYLES (Identical to Stock Analyzer TUI - MarketAnalyzerApp)
# ─────────────────────────────────────────────────────────────────────────────

ACCENT = "#5fafff"       # Light Blue
BG_COLOR = "#0c0d10"     # Dark Gray-Blue
PANEL_BG = "#1a1b1e"    # Slightly Lighter Panel BG
BORDER_COLOR = "#333333" # Subtle Border
BORDER_DETAIL = "#555555" # Detail Border

class CLIView:
    """All terminal I/O for the Investment Tracker.
    
    - High Cohesion: each method handles exactly one screen or form.
    - Low Coupling: no business logic; depends only on models/sell_service interfaces.
    """

    def __init__(self):
        self.console = Console()
        self.calc    = ProfitCalculator()

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
            f" [bold cyan]INVESTMENT_CORE[/bold cyan]{sub_text}",
            f"[bold {ACCENT}]SYSTEM_READY[/] "
        )
        self.console.print(header)
        self.console.print(Rule(style="#222222"))

    def show_status_bar(self, message: str = "READY", lust_stats: Optional[dict] = None):
        """Status bar matching Stock Analyzer's status_panel."""
        self.console.print(Rule(style=f"double {BORDER_COLOR}"))

        status_content = Table.grid(expand=True)
        status_content.add_column()
        status_content.add_column(justify="right")

        msg_line = f" [bold {ACCENT}]{message.upper()}[/]"
        lust_line = ""
        if lust_stats:
            pts = lust_stats['points']
            rank = lust_stats['rank']
            color = "green" if pts >= 100 else "red"
            lust_line = f"[dim]LUST_POINTS:[/] [bold {color}]{pts:.0f}[/] | [bold]{rank}[/] "

        status_content.add_row(msg_line, lust_line)

        # Subtle progress bar simulation (Textual style)
        bar = f"[{ACCENT}]" + "━" * 40 + "[/][#222222]" + "━" * 20 + "[/]"
        status_content.add_row(f" {bar} [dim]100%[/]", "")

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

    def show_info(self, msg: str):
        self.console.print(f"\n [bold {ACCENT}]INFO[/] {msg}")

    def get_input(self, prompt: str, default: str = None) -> str:
        return Prompt.ask(f" [bold {ACCENT}]»[/] {prompt}", default=default)

    # ─────────────── Menus ───────────────────────────────────────────

    def show_main_menu(self, lust_stats: Optional[dict] = None) -> str:
        self.clear()
        self.show_header("Main Menu")

        menu = [
            ("1", "QUICK_ADD",      "Add & save to database"),
            ("2", "QUICK_CHECK",    "Check price without saving"),
            ("3", "VIEW_PORTFOLIO", "List all investments"),
            ("4", "PL_ANALYSIS",    "Weekly profit/loss chart"),
            ("5", "SNIPER_ADVICE",  "ML price target & risk sizing"),
            ("10", "AGENT_SENATE",  "Multi-AI voting & consensus"),
            ("11", "BUTTERFLY_MAP", "Cross-market systemic risk"),
            ("12", "WHALE_PROFILER", "Detect institutional absorption"),
            ("6", "EDIT_DELETE",    "Manage investments"),
            ("7", "SELL_ASSET",     "Record sale & realized P/L"),
            ("8", "REALIZED_PL",    "View closed positions history"),
            ("9", "CLEAN_DB",       "Remove fully-sold entries"),
            ("0", "BACK",           "Return to dashboard"),
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
        self.show_status_bar("ORCHESTRATOR_ACTIVE", lust_stats)

        return self.console.input(f"\n [bold {ACCENT}]Command »[/] ").strip()

    # ─────────────── Input Forms ──────────────────────────────────────

    def get_investment_input(self, mode: str = "ADD") -> Optional[Investment]:
        self.clear()
        self.show_header("Add Investment" if mode == "ADD" else "Quick Price Check")

        try:
            type_table = Table.grid(padding=(0, 2))
            type_table.add_row(f"[bold {ACCENT}][1][/]", "STOCK")
            type_table.add_row(f"[bold {ACCENT}][2][/]", "CRYPTO")
            type_table.add_row(f"[bold {ACCENT}][3][/]", "GOLD")

            self.console.print("\n [bold cyan]ASSET_TYPES[/]")
            self.console.print(Panel(type_table, border_style=BORDER_COLOR, box=box.SQUARE, padding=(1, 2)))

            at = self.get_input("Type (1-3)", default="1")
            asset_type = {"1": "stock", "2": "crypto", "3": "gold"}.get(at, "stock")

            hints = {"stock": "AAPL, TLKM.JK", "crypto": "BTC, ETH", "gold": "XAU, XAG"}
            ticker = self.get_input(f"Ticker [dim]({hints[asset_type]})[/dim]").upper()

            qty = float(self.get_input("Quantity"))
            price = float(self.get_input("Buy Price (per unit)"))

            curr = self.get_input("Currency [1] IDR [2] USD", default="1")
            currency = "IDR" if curr == "1" else "USD"

            date_str = self.get_input("Date (DD-MM-YYYY) [dim]Enter for today[/dim]", default="")
            buy_date = datetime.strptime(date_str, "%d-%m-%Y") if date_str else datetime.now()

            # Preview
            self.clear()
            self.show_header("Confirm Entry" if mode == "ADD" else "Entry Details")

            rows = [
                ("Asset", asset_type.upper()),
                ("Ticker", ticker),
                ("Qty", f"{qty:,.4f}"),
                ("Price", f"{price:,.2f} {currency}"),
                ("Date", buy_date.strftime('%d-%m-%Y')),
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

            if mode == "ADD":
                if not Confirm.ask(f"\n [bold {ACCENT}]»[/] Save record?", default=True):
                    return None

            return Investment(
                asset_type=asset_type, ticker=ticker, quantity=float(qty),
                buy_price=float(price), buy_currency=currency, buy_date=buy_date)

        except Exception as e:
            self.show_error(f"Invalid input: {e}")
            return None

    def get_sell_input(self, investment: Investment) -> Optional[SellTransaction]:
        self.clear()
        self.show_header(f"Sell Asset: {investment.ticker}")

        print(f"\n [dim]Holdings:[/] {investment.remaining_quantity:.4f} units")
        print(f" [dim]Cost Basis:[/] {investment.buy_price:,.2f} {investment.buy_currency}")

        try:
            qty = float(self.get_input("Quantity to sell"))
            if qty > investment.remaining_quantity:
                self.show_error("Cannot sell more than you own!")
                return None

            price = float(self.get_input("Sell Price (per unit)"))

            curr = self.get_input("Currency [1] IDR [2] USD", default="1")
            currency = "IDR" if curr == "1" else "USD"

            date_str = self.get_input("Date (DD-MM-YYYY) [dim]Enter for today[/dim]", default="")
            sell_date = datetime.strptime(date_str, "%d-%m-%Y") if date_str else datetime.now()

            fees = float(self.get_input("Fees (IDR)", default="0"))

            return SellTransaction(sell_date=sell_date, quantity=qty, sell_price=price,
                                   sell_currency=currency, fees=fees)

        except Exception as e:
            self.show_error(f"Invalid input: {e}")
            return None

    def select_ticker(self, tickers: List[Dict]) -> Optional[Dict]:
        self.clear()
        self.show_header("Select Ticker to Sell")

        t = Table(box=box.SQUARE, border_style=BORDER_COLOR, header_style=f"bold {ACCENT}", expand=True)
        t.add_column("No", width=4, justify="center")
        t.add_column("Asset")
        t.add_column("Ticker")
        t.add_column("Total Holding", justify="right")

        for i, row in enumerate(tickers, 1):
            t.add_row(
                str(i),
                row["asset_type"].upper(),
                row["ticker"],
                f"{row['total_qty']:.4f}"
            )

        self.console.print()
        self.console.print(t)

        try:
            choice = int(self.get_input(f"Selection (1-{len(tickers)})")) - 1
            return tickers[choice] if 0 <= choice < len(tickers) else None
        except (ValueError, IndexError):
            return None

    def get_fifo_sell_input(self, ticker: str, total_holding: float) -> Optional[SellTransaction]:
        self.clear()
        self.show_header(f"FIFO Sell: {ticker}")

        print(f"\n [dim]Total Holdings:[/] {total_holding:.4f} units")

        try:
            qty = float(self.get_input("Quantity to sell"))
            if qty > total_holding:
                self.show_error("Cannot sell more than you own!")
                return None

            price = float(self.get_input("Sell Price (per unit)"))

            curr = self.get_input("Currency [1] IDR [2] USD", default="1")
            currency = "IDR" if curr == "1" else "USD"

            date_str = self.get_input("Date (DD-MM-YYYY) [dim]Enter for today[/dim]", default="")
            sell_date = datetime.strptime(date_str, "%d-%m-%Y") if date_str else datetime.now()

            fees = float(self.get_input("Total Fees (IDR)", default="0"))

            return SellTransaction(sell_date=sell_date, quantity=qty, sell_price=price,
                                   sell_currency=currency, fees=fees)

        except Exception as e:
            self.show_error(f"Invalid input: {e}")
            return None

    def select_investment(self, invs: List[Investment], action: str) -> Optional[int]:
        self.clear()
        self.show_header(f"Select: {action.upper()}")

        t = Table(box=box.SQUARE, border_style=BORDER_COLOR, header_style=f"bold {ACCENT}", expand=True)
        t.add_column("No", width=4, justify="center")
        t.add_column("Asset")
        t.add_column("Ticker")
        t.add_column("Qty", justify="right")
        t.add_column("Status")

        for i, inv in enumerate(invs, 1):
            t.add_row(
                str(i),
                inv.asset_type.upper(),
                inv.ticker,
                f"{inv.remaining_quantity:.4f}",
                inv.status.value.upper()
            )

        self.console.print()
        self.console.print(t)

        try:
            choice = int(self.get_input(f"Selection (1-{len(invs)})")) - 1
            return invs[choice].id if 0 <= choice < len(invs) else None
        except (ValueError, IndexError):
            return None

    # ─────────────── Display Views ────────────────────────────────────

    def show_portfolio_list(self, invs: List[Investment], prices: Dict):
        # This is handled by Live in main.py, but we define the table generator here
        pass

    def get_portfolio_table(self, invs: List[Investment], prices: Dict, last_updated: Optional[datetime] = None) -> Table:
        status_text = ""
        if last_updated:
            diff = (datetime.now() - last_updated).total_seconds()
            if diff < 60: status = "[bold green]● LIVE[/]"
            elif diff < 600: status = "[bold yellow]● UPDATED[/]"
            else: status = "[bold red]● STALE[/]"
            status_text = f"  {status} [dim]({last_updated.strftime('%H:%M:%S')})[/dim]"

        t = Table(
            box=box.SQUARE,
            header_style=f"bold {ACCENT}",
            border_style=BORDER_COLOR,
            title=f" [bold cyan]PORTFOLIO_STATUS[/bold cyan]{status_text}",
            expand=True
        )
        t.add_column("ST", width=3, justify="center")
        t.add_column("ID", width=4, justify="center")
        t.add_column("ASSET", width=8)
        t.add_column("TICKER", width=10)
        t.add_column("QTY", justify="right")
        t.add_column("BUY_PRICE", justify="right")
        t.add_column("CURR_VAL", justify="right")
        t.add_column("TOTAL_P/L", justify="right")
        t.add_column("P/L %", justify="right")

        for inv in invs:
            p = prices.get(inv.id)
            fav_star = "[yellow]★[/yellow]" if inv.is_favorite else "[dim]☆[/dim]"

            if not p:
                t.add_row(fav_star, str(inv.id), inv.asset_type.upper()[:6], inv.ticker, *["—"] * 5)
                continue

            ticker_disp = inv.ticker
            if p.get("stale"):
                ticker_disp = f"[yellow]{inv.ticker}![/]"

            qty_for_calc = (inv.remaining_quantity
                            if inv.status == InvestmentStatus.PARTIAL_SOLD
                            else inv.quantity)
            res = self.calc.calculate(p["buy_price_idr"], p["current_price_idr"], qty_for_calc)
            color, emoji = self._pl_style(res.percent)

            t.add_row(fav_star, str(inv.id), inv.asset_type.upper()[:6], ticker_disp,
                      f"{qty_for_calc:.4f}".rstrip("0").rstrip("."),
                      f"{res.buy_value:,.0f}", f"{res.current_value:,.0f}",
                      f"[{color}]{res.profit:+,.0f}[/{color}]",
                      f"[{color}]{res.percent:+.1f}%[/{color}]")
        return t

    def show_sell_history(self, sells: List):
        self.console.print("\n [bold cyan]SELL_TRANSACTION_HISTORY[/]")
        t = Table(box=box.SQUARE, border_style=BORDER_COLOR, header_style=f"bold {ACCENT}", expand=True)
        t.add_column("DATE", justify="center")
        t.add_column("TICKER")
        t.add_column("QTY", justify="right")
        t.add_column("SELL_PRICE", justify="right")
        t.add_column("REALIZED_P/L", justify="right")
        t.add_column("P/L %", justify="right")

        for sell in sells:
            # Support both SellTransaction dataclasses and legacy dict format
            if hasattr(sell, 'realized_pl'):
                pl = float(sell.realized_pl)
                pct = float(sell.realized_pl_pct)
                curr = getattr(sell, 'sell_currency', 'IDR') or 'IDR'
                ticker = getattr(sell, 'ticker', '-') or '-'
                qty = float(sell.quantity)
                sell_price = float(sell.sell_price)
                sell_date = sell.sell_date
                if isinstance(sell_date, str):
                    sell_date = datetime.fromisoformat(sell_date.replace(" ", "T"))
            else:
                pl = sell.get("realized_pl_idr", sell.get("realized_pl", 0))
                pct = sell.get("realized_pl_pct", 0)
                curr = sell.get("sell_currency", "IDR")
                ticker = sell.get("ticker", "-")
                qty = sell.get("quantity", 0)
                sell_price = sell.get("sell_price", 0)
                sell_date = datetime.fromisoformat(sell["sell_date"])

            curr_disp = "Rp" if str(curr).upper() == "IDR" else f"{curr} "
            c = "bold green" if pl >= 0 else "bold red"
            date_str = sell_date.strftime('%d-%m-%Y') if hasattr(sell_date, 'strftime') else str(sell_date)
            t.add_row(
                f"[dim white]{date_str}[/dim white]",
                str(ticker),
                f"{qty:.4f}",
                f"{curr_disp}{sell_price:,.2f}",
                f"[{c}]Rp{pl:+,.2f}[/{c}]",
                f"[{c}]{pct:+.2f}%[/{c}]")

        self.console.print(t)


    def show_sell_confirmation(self, result: SellResult):
        self.clear()
        self.show_header("Sell Executed")

        rows = [
            ("Quantity Sold", f"{result.quantity_sold:.4f}"),
            ("Sell Value", f"Rp{result.sell_value_idr:,.2f}"),
            ("Cost Basis", f"Rp{result.buy_value_idr:,.2f}"),
            ("Realized P/L (IDR)", f"[bold {'green' if result.realized_pl >= 0 else 'red'}]Rp{result.realized_pl:+,.2f} ({result.realized_pl_pct:+.2f}%)[/]"),
            ("Remaining", f"{result.remaining:.4f}")
        ]

        # Show USD P/L when the sell was denominated in USD
        if result.realized_pl_usd is not None:
            usd_color = 'green' if result.realized_pl_usd >= 0 else 'red'
            rows.insert(4, ("Realized P/L (USD)", f"[bold {usd_color}]USD {result.realized_pl_usd:+,.2f}[/]"))

        t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
        for l, v in rows: t.add_row(f"[dim]{l}[/]", v)

        self.console.print("\n")
        self.console.print(Align.center(Panel(
            t,
            title="[bold cyan]TRANSACTION_SUMMARY[/]",             border_style="green",
            style=f"on {PANEL_BG}",
            box=box.SQUARE,
            padding=(1, 4),
            width=50
        )))

        if result.is_fully_sold:
            self.console.print("\n [yellow]! Asset fully sold — position closed[/yellow]")

    def show_realized_pl_summary(self, summary: dict):
        self.clear()
        self.show_header("Realized P/L Report")

        pc = "green" if summary["total_realized_pl"] >= 0 else "red"
        rows = [
            ("Total Realized P/L", f"[bold {pc}]Rp{summary['total_realized_pl']:+,.2f}[/]"),
            ("Total Sells", str(summary["total_sells"])),
            ("Wins / Losses", f"[green]{summary['wins']}[/] / [red]{summary['losses']}[/]"),
            ("Win Rate", f"{summary['win_rate']:.1f}%")
        ]

        t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
        for l, v in rows: t.add_row(f"[dim]{l}[/]", v)

        self.console.print("\n")
        self.console.print(Align.center(Panel(
            t,
            title="[bold cyan]CUMULATIVE_PERFORMANCE[/]",             border_style=ACCENT,
            style=f"on {PANEL_BG}",
            box=box.SQUARE,
            padding=(1, 4),
            width=50
        )))

    def show_senate_advice(self, ticker: str, res):
        from apps.cli.investment_tracker.services.senate_service import Vote
        color_map = {Vote.BUY: "green", Vote.SELL: "red", Vote.HOLD: "yellow"}
        consensus_color = color_map.get(res.consensus, "white")

        self.clear()
        self.show_header(f"Senate: {ticker}")

        conf_pct = res.confidence * 100
        self.console.print(f"\n Consensus: [bold {consensus_color}]{res.consensus.value}[/] ({conf_pct:.0f}% confidence)")

        t = Table(box=box.SQUARE, border_style=BORDER_COLOR, header_style=f"bold {ACCENT}", expand=True)
        t.add_column("Persona", width=20)
        t.add_column("Vote", width=10, justify="center")
        t.add_column("Conf %", width=10, justify="right")
        t.add_column("Rationale")

        for op in res.opinions:
            v_color = color_map.get(op.vote, "white")
            t.add_row(op.agent_name, f"[{v_color}]{op.vote.value}[/]", f"{op.confidence*100:.0f}%", op.rationale)

        self.console.print(t)
        self.show_status_bar("SENATE_ANALYSIS_COMPLETE")

    def show_discipline_events(self, events: List[tuple]):
        if not events: return
        self.console.print("\n [bold cyan]DISCIPLINE_FEEDBACK[/]")
        for delta, reason in events:
            color = "bold green" if delta > 0 else "bold red"
            self.console.print(f"  [{color}]{delta:+d}[/] {reason}")

    def show_butterfly_map(self, ticker: str, nodes: List):
        self.clear()
        self.show_header(f"Butterfly Effect: {ticker}")

        t = Table(box=box.SQUARE, border_style=BORDER_COLOR, header_style=f"bold {ACCENT}", expand=True)
        t.add_column("Driver", width=20)
        t.add_column("Corr", width=10, justify="center")
        t.add_column("Impact", width=10, justify="center")
        t.add_column("Market Context")

        for n in nodes:
            c = n.correlation
            abs_c = abs(c)

            color = "green" if abs_c < 0.3 else "yellow" if abs_c < 0.6 else "red"
            imp_color = "dim" if n.impact_level == "Low" else "yellow" if n.impact_level == "Medium" else "bold red"

            # High Impact Highlighting (> 0.7)
            driver_text = n.ticker
            if abs_c > 0.7:
                driver_text = f"[bold white on red] {n.ticker} [/] [bold red]![/]"
                imp_color = "bold blink red"

            t.add_row(
                driver_text,
                f"[{color}]{c:+.2f}[/]",
                f"[{imp_color}]{n.impact_level}[/]",
                n.description
            )

        self.console.print(t)
        self.show_status_bar("SYSTEMIC_RISK_MAPPED")

    def show_prune_result(self, result: dict):
        d = result.get("deleted", 0)
        self.console.print(f"\n [bold green]CLEANUP_COMPLETE[/] Removed {d} stale records.")

    def show_whale_analysis(self, result: Dict):
        self.clear()

        if "error" in result:
            self.show_header("Whale Profiler: ERROR")
            self.show_error(result["error"])
            return

        self.show_header(f"Whale Profiler: {result['ticker']}")

        signal = result["signal"]
        color = "white"
        if "ACCUMULATION" in signal: color = "bold green"
        elif "DISTRIBUTION" in signal: color = "bold red"
        elif "HIGH" in signal: color = "bold yellow"

        self.console.print(f"\n [dim]Date:[/] {result['date']}")
        self.console.print(f" [dim]Status:[/] [{color}]{signal}[/]\n")

        # Metrics Table
        t = Table(box=box.SQUARE, border_style=BORDER_COLOR, padding=(0, 2))
        t.add_column("Metric", style=f"bold {ACCENT}")
        t.add_column("Value")
        t.add_column("Insight")

        t.add_row("Volume Ratio", f"{result['vol_ratio']:.2f}x",
                  "[green]Institutional[/]" if result['vol_ratio'] > 1.5 else "[dim]Retail-level[/]")
        t.add_row("Price Range", f"{result['price_range_pct']:.2f}%",
                  "[yellow]Absorption[/]" if result['price_range_pct'] < 0.5 else "[dim]Normal[/]")
        t.add_row("Body Movement", f"{result['body_move_pct']:.2f}%",
                  "[yellow]Tight[/]" if result['body_move_pct'] < 0.3 else "[dim]Active[/]")

        self.console.print(t)
        self.console.print("\n" + result["description"])

        self.show_status_bar("SMART_MONEY_PROFILED")

    def _pl_style(self, percent: float):
        if percent >= 0: return "bold green", "(+)"
        return "bold red", "(-)"
