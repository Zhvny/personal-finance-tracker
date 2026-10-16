from pathlib import Path

from test_infrastructure import CLIRunner

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "apps" / "cli" / "main.py"

def probe_menus():
    runner = CLIRunner(ROOT, CLI, "menu_probe_income")
    # Probe INCOME (3)
    runner.run(["3", "0"])
    print(runner.stdout)

if __name__ == "__main__":
    probe_menus()
