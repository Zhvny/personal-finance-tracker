#!/usr/bin/env python3
"""
apps/cli/menu.py
============================
Menu item definitions and dispatch map.
"""

import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from rich.console import Console

from packages.core.application.profile_service import ProfileService
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.logging import get_logger

from apps.cli.launchers import _launch, _run_subprocess, run_business_report, run_module, run_whale_profiler


def _manage_profiles_wrapper():
    from apps.cli.main import manage_profiles
    return manage_profiles()


console = Console()
logger = get_logger("cli")
profile_service = ProfileService(Config.BASE_DIR)


def get_menu_items(profile: str) -> List[Tuple[str, str, str]]:
    items: List[Tuple[str, str, str]] = [
        ("1", "INVEST", "Assets"),
        ("2", "EXPENSE", "Spending"),
        ("3", "INCOME", "Earning"),
        ("4", "SCAN", "Receipt"),
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
        items.append(("9", "WHALE", "Profiler"))

    items.append(("0", "EXIT", "Quit"))
    return items


def render_menu(profile: str) -> None:
    items = [f"[bold white]{n}[/bold white] [dim]{l}[/dim]" for n, l, d in get_menu_items(profile)]
    console.print("  " + "   ".join(items) + "\n")


def get_dispatch(profile: str) -> Dict[str, Callable]:
    dispatch: Dict[str, Callable] = {
        "1": lambda: _launch("Investment", lambda: run_module("investment_tracker")),
        "2": lambda: _launch("Expense", lambda: run_module("expense_tracker")),
        "3": lambda: _launch("Income", lambda: run_module("income_tracker")),
        "4": lambda: _launch("Receipt", lambda: run_module("receipt_reader")),
        "8": lambda: _manage_profiles_wrapper(),
    }

    if profile != "business":
        dispatch["9"] = lambda: _launch("Whale", run_whale_profiler)

    if Config.is_feature_enabled("stocks") and profile != "business":
        dispatch["5"] = lambda: _launch("Stocks", lambda: run_module("stock_analyzer"))
    if Config.is_feature_enabled("ml") and profile != "business":
        ml_path = (Path(__file__).parent / "stock_ml" / "app.py").resolve()
        dispatch["6"] = lambda: _run_subprocess("ML_Stocks", [sys.executable, str(ml_path)])
    if Config.is_feature_enabled("behavioral") and profile != "business":
        dispatch["7"] = lambda: _launch("Behavioral", lambda: run_module("behavioral_finance"))

    if profile == "business":
        dispatch["7"] = lambda: _launch("Business Report", lambda: run_business_report())

    return dispatch
