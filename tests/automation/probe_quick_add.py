from pathlib import Path

from test_infrastructure import CLIRunner

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "apps" / "cli" / "main.py"

def probe_quick_add():
    runner = CLIRunner(ROOT, CLI, "probe_quick_add")
    # INVEST (1) -> QUICK_ADD (1) -> AAPL -> crypto -> 10 -> 100 -> "" -> 0 -> "test" -> y (Save)
    runner.run(["1", "1", "AAPL", "crypto", "10", "100", "", "0", "test", "y"])
    print(runner.stdout)

if __name__ == "__main__":
    probe_quick_add()
