from pathlib import Path

from test_infrastructure import CLIRunner

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "apps" / "cli" / "main.py"

def probe_add_expense():
    runner = CLIRunner(ROOT, CLI, "probe_add_expense")
    # EXPENSE (2) -> ADD_EXPENSE (1) -> Amount -> Desc -> Category -> Payment -> Date -> Recurring -> Save
    runner.run(["2", "1", "100", "test", "1", "1", "", "n", "y"])
    print(runner.stdout)

if __name__ == "__main__":
    probe_add_expense()
