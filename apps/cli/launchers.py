#!/usr/bin/env python3
"""
apps/cli/launchers.py
============================
Module launchers and subprocess helpers.
"""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable, List

from rich.console import Console
from packages.core.infrastructure.logging import get_logger

console = Console()
logger = get_logger("cli")

CLI_ROOT = Path(__file__).parent.resolve()

# Monorepo root is the parent of CLI_ROOT's parent (apps/cli -> apps -> root)
MONOREPO_ROOT = CLI_ROOT.parent.parent


def run_module(module_dir: str, main_file: str = "main.py") -> None:
    if module_dir.startswith(".."):
        mod_path = (CLI_ROOT / module_dir).resolve()
    else:
        mod_path = CLI_ROOT / module_dir

    main_py: Path = mod_path / main_file

    if str(mod_path) not in sys.path:
        sys.path.insert(0, str(mod_path))
        added_to_path = True
    else:
        added_to_path = False

    module = None
    try:
        module_name = f"apps.cli.{module_dir.replace('/', '.')}"
        try:
            module = importlib.import_module(f"{module_name}.{main_file.replace('.py', '')}")
            importlib.reload(module)
        except (ImportError, ModuleNotFoundError):
            spec = importlib.util.spec_from_file_location(f"_mod_{module_dir.replace('..', 'ext')}", str(main_py))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

        if module and hasattr(module, "main"):
            module.main()
        elif not module:
            raise ImportError(f"Could not load module {module_dir}")
        else:
            raise AttributeError(f"Module {module_dir} has no 'main' function")
    finally:
        if added_to_path:
            sys.path.remove(str(mod_path))


def _launch(name: str, fn: Callable) -> None:
    try:
        fn()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Error in {name}: {e}")
        console.print(f"\n[bold red]Error in {name}:[/bold red] {e}")


def _run_subprocess(name: str, cmd: List[str]) -> None:
    import subprocess

    try:
        console.print(f"[bold cyan]Launching {name}...[/bold cyan]")
        env = os.environ.copy()

        python_exe = sys.executable
        if cmd[0].lower() in ["python", "python3", "python.exe"]:
            cmd[0] = python_exe

        if len(cmd) > 1 and not os.path.isabs(cmd[1]):
            potential_paths = [
                CLI_ROOT / cmd[1],
                MONOREPO_ROOT / cmd[1],
                Path(cmd[1]).resolve(),
            ]
            for p in potential_paths:
                if p.exists():
                    cmd[1] = str(p)
                    break

        subprocess.run(cmd, check=True, env=env)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Subprocess Error in {name}: {e}")
        console.print(f"\n[bold red]Subprocess Error in {name}:[/bold red] {e}")


def run_business_report() -> None:
    from packages.core.application.business_report_service import BusinessReportService
    from datetime import datetime

    service = BusinessReportService()
    console.print("\n [bold cyan]GENERATING QUARTERLY REPORT[/bold cyan]")
    try:
        now: datetime = datetime.now()
        q: int = (now.month - 1) // 3 + 1
        path: str = service.generate_quarterly_report(now.year, q)
        console.print(f" [green]Success:[/green] Report saved to {path}")
    except Exception as e:
        logger.exception(f"Failed to generate business report: {e}")
        console.print(f" [red]Error:[/red] {e}")


def run_whale_profiler() -> None:
    mod_path = CLI_ROOT / "investment_tracker"
    if str(mod_path) not in sys.path:
        sys.path.insert(0, str(mod_path))
    from investment_tracker.main import PortfolioApp

    app = PortfolioApp()
    app.whale_profiler()
