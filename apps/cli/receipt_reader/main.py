#!/usr/bin/env python3
"""
Receipt Reader — Main Entry Point

Features:
  - Ensemble OCR: Tesseract + EasyOCR + PaddleOCR (runs all, picks best)
  - Universal parser: BCA QRIS, BCA Transfer, BCA m-Info single & bulk, generic
  - Export menu: to expense_tracker / income_tracker / JSON
  - Bulk mode: process an entire folder automatically
"""

import logging
import os
import sys
import warnings
from typing import List

# Setup logging
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env dari project root agar GEMINI_API_KEY dan variabel lain tersedia
try:
    import pathlib as _pathlib

    from dotenv import load_dotenv as _load_dotenv

    # Cari .env di project root (naik 4 level dari apps/cli/receipt_reader/main.py)
    _env_candidates = [
        _pathlib.Path(__file__).resolve().parent.parent.parent.parent / ".env",  # project root
        _pathlib.Path(__file__).resolve().parent.parent.parent / ".env",  # Alpha/
    ]
    for _env_path in _env_candidates:
        if _env_path.exists():
            _load_dotenv(_env_path, override=False)
            break
except ImportError:
    pass  # python-dotenv tidak terinstall, lanjut pakai os.environ

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from apps.cli.receipt_reader.ui.cli_view import RichReceiptView
from apps.cli.receipt_reader.services.categorizer import CategorizerService
from packages.core.application.receipt_reader.exporters.expense_exporter import ExpenseExporter
from packages.core.application.receipt_reader.exporters.income_exporter import IncomeExporter
from packages.core.application.receipt_reader.exporters.json_exporter import JSONExporter
from packages.core.application.receipt_reader.interfaces import Money, ReceiptData, TransactionType
from packages.core.application.receipt_reader.ocr_ensemble import OCREnsemble
from packages.core.infrastructure.config import Config
from packages.core.application.receipt_reader.parser import ReceiptParser

console = Console()


# ─────────────────────── Screen Helper ───────────────────────────────


def _cls():
    """Clear terminal screen."""
    console.clear()


# ─────────────────────── App ─────────────────────────────────────────

# Identical to cli_view.py for consistency
ACCENT = "#5fafff"
BORDER_COLOR = "#333333"


class ReceiptReaderApp:
    """
    Orchestrates OCR, parsing, categorization, and export.

    - High Cohesion: each private method handles a single workflow stage.
    - Low Coupling: OCR, parsing, categorization, export are independent modules.
    - Abstraction: callers interact via `run()` only.
    """

    def __init__(self):
        # Profile- and FINANCE_DATA_ROOT-aware export root (was hardcoded to the
        # apps/cli source dir, which ignored the active profile and test isolation).
        self.base_path = str(Config.get_cli_data_root())
        self.ensemble = OCREnsemble(language="id", use_gpu=False)
        self.parser = ReceiptParser()
        self.categorizer = CategorizerService()
        self.ui = RichReceiptView()
        self.exporters = self._build_exporters()

        console.print(f" [dim]OCR engines available: {', '.join(self.ensemble.available_engines)}[/dim]")

    def _build_exporters(self) -> dict:
        export_dir = os.path.join(self.base_path, "receipt_reader", "exports")
        return {
            "expense": ExpenseExporter(self.base_path),
            "income": IncomeExporter(self.base_path),
            "json": JSONExporter(export_dir),
        }

    # ─────────────── Main Loop ───────────────────────────────────────

    def run(self):
        while True:
            self.ui.clear()
            self.ui.show_header("Main Menu")

            menu = Table.grid(padding=(0, 2))
            menu.add_row(f"[bold {ACCENT}][1][/] SINGLE", "[dim]Process one image[/]")
            menu.add_row(f"[bold {ACCENT}][2][/] BULK", "[dim]Process entire folder[/]")
            menu.add_row(f"[bold {ACCENT}][0][/] BACK", "[dim]Return to dashboard[/]")

            self.ui.console.print("\n")
            self.ui.console.print(
                Panel(
                    menu, border_style=BORDER_COLOR, box=box.SQUARE, padding=(1, 4), title="[bold cyan]SELECT_MODE[/]"
                )
            )
            self.ui.console.print("\n")
            self.ui.show_status_bar("READY")

            choice = self.ui.console.input(f"\n [bold {ACCENT}]Select Mode »[/] ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self._run_single()
            elif choice == "2":
                self._run_bulk()
            else:
                self.ui.show_error("Invalid choice")

    # ─────────────── Single Mode ─────────────────────────────────────

    def _run_single(self):
        while True:
            self.ui.clear()
            self.ui.show_header("Single Scan")
            path = self.ui.get_input("Image path (or 'q' to go back)")

            if path.lower() in ("q", "quit", "exit"):
                break
            if not os.path.exists(path):
                self.ui.show_error(f"File not found: {path}")
                continue

            receipts = self._process_image(path, verbose=True)
            if not receipts:
                self.ui.show_error("No data could be parsed")
                continue

            if len(receipts) == 1:
                self._handle_single_receipt(receipts[0])
            else:
                self.ui.show_success(f"Found {len(receipts)} transactions")
                self._handle_bulk_receipts(receipts)

    # ─────────────── Bulk Mode ───────────────────────────────────────

    def _run_bulk(self):
        self.ui.clear()
        self.ui.show_header("Bulk Scan")
        folder = self.ui.get_input("Folder path")
        if not os.path.isdir(folder):
            self.ui.show_error("Folder not found")
            return

        EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        seen = set()
        images = []
        try:
            entries = os.listdir(folder)
        except PermissionError as e:
            self.ui.show_error(f"Access denied: {e}")
            return

        for name in sorted(entries, key=str.lower):
            if os.path.splitext(name)[1].lower() not in EXTS:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            images.append(os.path.join(folder, name))

        if not images:
            self.ui.show_error(f"No images found in {folder}")
            return

        self.ui.show_success(f"Processing {len(images)} images...")

        all_receipts: List[ReceiptData] = []
        for i, img in enumerate(images, 1):
            self.ui.console.print(f" [dim][{i}/{len(images)}] {os.path.basename(img)}[/dim]")
            try:
                receipts = self._process_image(img, verbose=False)
                if receipts:
                    all_receipts.extend(receipts)
                    for r in receipts:
                        cat = r.category.value if hasattr(r.category, "value") else str(r.category)
                        color = "green" if r.transaction_type == TransactionType.INCOME else "red"
                        self.ui.console.print(
                            f"   [bold {color}]●[/] {r.merchant_name[:20]:<20} | Rp{r.total_amount.amount:>10,.0f} | {cat}"
                        )
                else:
                    self.ui.console.print("   [yellow]![/] No data extracted")
            except Exception as e:
                self.ui.show_error(f"   [red]FAILED[/] {os.path.basename(img)}: {e}")

        if all_receipts:
            self.ui.show_success(f"Total: {len(all_receipts)} transactions found")
            self._handle_bulk_receipts(all_receipts)

    # ─────────────── Processing ──────────────────────────────────────

    def _process_image(self, image_path: str, verbose: bool = False) -> List[ReceiptData]:
        """OCR + parse → List[ReceiptData]."""
        if verbose:
            self.ui.console.print(" [dim]Running Ensemble OCR...[/dim]")

        result = self.ensemble.run(image_path, verbose=verbose)
        if not result.best_text.strip():
            return []

        receipts = self.parser.parse_all(result.best_text)

        # Patch results using Ensemble Field-Level Voting
        votes = result.field_votes

        for r in receipts:
            r.confidence_score = result.confidence
            r.metadata["engine"] = result.best_engine
            r.metadata["engine_ranking"] = result.engine_ranking

            # Apply votes to minimize manual corrections
            if votes.get("total") and (r.total_amount.amount == 0):
                try:
                    val = float(votes["total"])
                    r.total_amount = Money(val, "IDR")
                    r.metadata["voted_total"] = True
                except Exception:
                    logger.exception("Failed to parse voted total: %s", votes.get("total"))

            if votes.get("merchant") and not r.merchant_name:
                r.merchant_name = votes["merchant"]
                r.metadata["voted_merchant"] = True

            if votes.get("date") and (not r.transaction_date or r.transaction_date.year < 2020):
                try:
                    from datetime import datetime

                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                        try:
                            r.transaction_date = datetime.strptime(votes["date"], fmt)
                            r.metadata["voted_date"] = True
                            break
                        except (ValueError, TypeError):
                            continue
                except Exception:
                    logger.exception("Failed to parse voted date: %s", votes.get("date"))

            # Use persistent CategorizerService (Merchant Memory)
            clf = self.categorizer.categorize(r)
            r.category = clf.category
            r.metadata["cat_method"] = clf.method

            if not r.metadata.get("tx_type_from_parser"):
                # Access internal smart categorizer for type detection if needed
                r.transaction_type = self.categorizer._categorizer._detect_transaction_type(r)

        return receipts

    # ─────────────── Receipt Handlers ────────────────────────────────

    def _handle_single_receipt(self, receipt: ReceiptData):
        self.ui.display_receipt(receipt)

        if self.ui.confirm_action("Edit data?"):
            old_cat = receipt.category
            receipt = self.ui.edit_receipt(receipt)

            # Record correction if category changed
            if receipt.category != old_cat:
                cat_val = receipt.category.value if hasattr(receipt.category, "value") else str(receipt.category)
                self.categorizer.record_correction(receipt, cat_val)

            self.ui.display_receipt(receipt)

        self._export_menu(receipt)

    def _handle_bulk_receipts(self, receipts: List[ReceiptData]):
        while True:
            self.ui.clear()
            self.ui.show_header("Bulk Summary")
            self._show_bulk_summary(receipts)

            menu = Table.grid(padding=(0, 2))
            menu.add_row(f"[bold {ACCENT}][E][/] EDIT", "[dim]Correct transactions[/]")
            menu.add_row(f"[bold {ACCENT}][X][/] EXPORT", "[dim]Save all to database[/]")
            menu.add_row(f"[bold {ACCENT}][0][/] CANCEL", "[dim]Discard results[/]")

            self.ui.console.print("\n")
            self.ui.console.print(
                Panel(menu, box=box.SQUARE, border_style=BORDER_COLOR, title="[bold cyan]ACTIONS[/]", padding=(1, 4))
            )
            self.ui.show_status_bar(f"{len(receipts)} Transactions Found")

            choice = self.ui.console.input(f"\n [bold {ACCENT}]Action »[/] ").strip().upper()

            if choice == "E":
                receipts = self._edit_bulk_menu(receipts)
            elif choice == "X":
                self._bulk_export(receipts)
                break
            elif choice == "0":
                break

    def _edit_bulk_menu(self, receipts: List[ReceiptData]) -> List[ReceiptData]:
        self.ui.display_batch_results(receipts)

        raw = self.ui.get_input("Transaction # to edit (e.g. 1,3 | 'all' | 0 cancel)")

        if raw == "0":
            return receipts
        indices = (
            list(range(len(receipts)))
            if raw.lower() == "all"
            else [int(p) - 1 for p in raw.split(",") if p.strip().isdigit() and 0 <= int(p.strip()) - 1 < len(receipts)]
        )
        for idx in indices:
            old_cat = receipts[idx].category
            receipts[idx] = self.ui.edit_receipt(receipts[idx])

            # Record correction if category changed
            if receipts[idx].category != old_cat:
                cat_val = (
                    receipts[idx].category.value
                    if hasattr(receipts[idx].category, "value")
                    else str(receipts[idx].category)
                )
                self.categorizer.record_correction(receipts[idx], cat_val)

        return receipts

    # ─────────────── Export ──────────────────────────────────────────

    def _export_menu(self, receipt: ReceiptData):
        tx_type = receipt.transaction_type
        self.ui.console.print("\n [bold cyan]EXPORT_DESTINATION[/]")
        self.ui.console.print(Rule(style=BORDER_COLOR))

        options = []
        if tx_type == TransactionType.EXPENSE:
            options.append(("1", "Expense Tracker", "expense"))
        else:
            options.append(("1", "Income Tracker", "income"))
        options += [
            ("2", "JSON (backup)", "json"),
            ("3", "Expense Tracker (force)", "expense"),
            ("4", "Income Tracker (force)", "income"),
            ("0", "Skip", None),
        ]

        for num, label, _ in options:
            self.ui.console.print(f"  [bold {ACCENT}][{num}][/] {label}")

        choice = self.ui.console.input(f"\n [bold {ACCENT}]Select »[/] ").strip()
        target = next((t for n, _, t in options if n == choice and t), None)
        if target:
            self._do_export(receipt, target)
        else:
            self.ui.console.print(" [dim]Skipped[/dim]")

    def _do_export(self, receipt: ReceiptData, target: str) -> bool:
        exporter = self.exporters.get(target)
        if not exporter:
            self.ui.show_error(f"Exporter '{target}' not found")
            return False
        try:
            ok = exporter.export(receipt)
            if ok:
                self.ui.show_success(f"Exported to {target}")
            else:
                self.ui.show_error(f"Export failed: {target}")
            return ok
        except Exception as e:
            self.ui.show_error(f"Export Error: {e}")
            return False

    def _bulk_export(self, receipts: List[ReceiptData]):
        ok_count = 0
        for r in receipts:
            target = "expense" if r.transaction_type == TransactionType.EXPENSE else "income"
            if self._do_export(r, target):
                ok_count += 1
            self._do_export(r, "json")
        self.ui.show_success(f"Exported {ok_count}/{len(receipts)} transactions")

    # ─────────────── Display Helpers ─────────────────────────────────

    def _make_tx_table(self, receipts, is_income_table: bool, start_idx: int):
        color = "green" if is_income_table else "red"
        # Match DataTable look: No box, specific header
        t = Table(box=None, show_header=True, header_style=f"bold {color}", padding=(0, 1), expand=True)
        t.add_column("Sig", width=4, justify="center")
        t.add_column("MERCHANT", width=24)
        t.add_column("DATE", width=12, justify="center")
        t.add_column("AMOUNT", width=14, justify="right")
        t.add_column("CAT", width=14, justify="center")
        t.add_column("ENGINE", width=11, style="dim")

        total = 0.0
        sig = "[bold green]I[/]" if is_income_table else "[bold red]E[/]"
        for i, r in enumerate(receipts, start_idx):
            cat_str = r.category.value if hasattr(r.category, "value") else str(r.category)
            t.add_row(
                sig,
                r.merchant_name[:23],
                r.transaction_date.strftime("%d-%m-%y"),
                f"[{color}]Rp{r.total_amount.amount:,.0f}[/]",
                cat_str[:10],
                r.metadata.get("engine", "?")[:10],
            )
            total += r.total_amount.amount

        return t, total

    def _show_bulk_summary(self, receipts: List[ReceiptData]):
        expenses = [r for r in receipts if r.transaction_type != TransactionType.INCOME]
        incomes = [r for r in receipts if r.transaction_type == TransactionType.INCOME]

        total_expense = total_income = 0.0

        if expenses:
            exp_table, total_expense = self._make_tx_table(expenses, False, 1)
            self.ui.console.print(exp_table)
            self.ui.console.print(f"  [bold red]Total_EXP:[/] Rp{total_expense:,.0f}\n")

        if incomes:
            inc_table, total_income = self._make_tx_table(incomes, True, 1)
            self.ui.console.print(inc_table)
            self.ui.console.print(f"  [bold green]Total_INC:[/] Rp{total_income:,.0f}\n")

        net = total_income - total_expense
        nc = "bold green" if net >= 0 else "bold red"

        summary = Table.grid(expand=True, padding=(0, 2))
        summary.add_row(
            f" [bold cyan]TOTAL:[/] {len(receipts)} TX",
            f"[bold green]INC:[/] Rp{total_income:,.0f}",
            f"[bold red]EXP:[/] Rp{total_expense:,.0f}",
            f"[bold {nc}]NET:[/] Rp{net:+,.0f}",
        )
        self.ui.console.print(Panel(summary, box=box.SQUARE, border_style=BORDER_COLOR))


def main():
    app = ReceiptReaderApp()
    try:
        app.run()
    except KeyboardInterrupt:
        console.print("\n[cyan]Goodbye! [/cyan]")


if __name__ == "__main__":
    main()
