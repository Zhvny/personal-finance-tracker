import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple


class CLIDriver:
    """
    A simple subprocess-based driver for interacting with the Finance Tracker CLI.
    Supports both blocking batch-input runs (run/run_scenario) and basic start/stop.
    """
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
        self.project_root = project_root
        self.cli_path = project_root / "apps" / "cli" / "main.py"
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(project_root)
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.env["TERM"] = "xterm-256color"
        self._process = None
        self.stdout = ""
        self.stderr = ""

    def run(self, inputs: list, timeout=30) -> str:
        """Batch-input run: send all inputs at once, return combined stdout."""
        input_str = "\n".join(str(i) for i in inputs) + "\n0\n0\n0\n0\n"
        process = subprocess.Popen(
            [sys.executable, str(self.cli_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env=self.env,
            cwd=str(self.project_root),
            shell=False
        )
        try:
            stdout, _ = process.communicate(input=input_str, timeout=timeout)
            return stdout or ""
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate()
            return stdout or ""
        except Exception as e:
            if process.poll() is None:
                process.kill()
            return f"Error: {str(e)}"

    def run_scenario(self, inputs: list, wait_after_input: float = 1.0,
                     timeout: int = 30) -> Tuple[str, str]:
        """
        Run a scenario with batch inputs. Returns (stdout, stderr) tuple.
        `wait_after_input` is ignored (kept for API compatibility).
        """
        input_str = "\n".join(str(i) for i in inputs) + "\n0\n0\n0\n0\n"
        process = subprocess.Popen(
            [sys.executable, str(self.cli_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=self.env,
            cwd=str(self.project_root),
            shell=False
        )
        try:
            stdout, stderr = process.communicate(input=input_str, timeout=timeout)
            self.stdout = stdout or ""
            self.stderr = stderr or ""
            return self.stdout, self.stderr
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            self.stdout = stdout or ""
            self.stderr = stderr or ""
            return self.stdout, self.stderr
        except Exception as e:
            if process.poll() is None:
                process.kill()
            return f"Error: {str(e)}", ""

    def start(self, args: list = None):
        """Start CLI as a subprocess (non-interactive helper for simple subcommands)."""
        cmd = [sys.executable, str(self.cli_path)]
        if args:
            cmd.extend(args)
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=self.env,
            cwd=str(self.project_root),
            shell=False
        )

    def stop(self):
        """Terminate the running CLI process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def is_running(self) -> bool:
        """Returns True if the CLI process is still running."""
        return self._process is not None and self._process.poll() is None

    def read_output(self, timeout: float = 5) -> str:
        """Read available stdout from the started process."""
        if not self._process:
            return ""
        try:
            stdout, _ = self._process.communicate(timeout=timeout)
            return stdout or ""
        except subprocess.TimeoutExpired:
            self._process.kill()
            stdout, _ = self._process.communicate()
            return stdout or ""

    def read_error(self, timeout: float = 2) -> str:
        """Read available stderr from the started process."""
        if not self._process:
            return ""
        # stderr was already captured in communicate
        return ""
