from pathlib import Path

from test_infrastructure import CLIRunner

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "apps" / "cli" / "main.py"

def probe_menus():
    runner = CLIRunner(ROOT, CLI, "menu_probe")
    # Probe INVEST (1), EXPENSE (2), INCOME (3)
    # We enter each and exit immediately
    runner.run(["1", "0", "2", "0", "3", "0"])
    print(runner.stdout)

if __name__ == "__main__":
    probe_menus()
