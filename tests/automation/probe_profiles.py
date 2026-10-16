from pathlib import Path

from tests.automation.cli_driver import CLIDriver

root = Path(__file__).resolve().parent.parent.parent
driver = CLIDriver(root)
output = driver.run(["8", "0"])
print(output)
