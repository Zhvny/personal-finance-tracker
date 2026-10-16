import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path


class AuditResult:
    def __init__(self, vector_id, success, message="", logs=None):
        self.vector_id = vector_id
        self.success = success
        self.message = message
        self.logs = logs or []

    def __str__(self):
        status = "PASS" if self.success else "FAIL"
        report = f"VECTOR {self.vector_id}: {status}\n"
        if self.message:
            report += f"Error/Info: {self.message}\n"
        if self.logs:
            report += "Logs:\n  - " + "\n  - ".join(self.logs)
        return report

class BaseAuditVector:
    def __init__(self, vector_id):
        self.vector_id = vector_id
        self.logs = []
        self.results = {}

    def log(self, message):
        print(f"[{self.vector_id}] {message}")
        self.logs.append(message)

    def setup(self):
        """Prepare environment for reproduction."""
        pass

    def reproduce(self):
        """Execute the failure vector."""
        pass

    def validate(self) -> bool:
        """Check if DoD is met."""
        return True

    def teardown(self):
        """Cleanup."""
        pass

    def run_command(self, cmd, **kwargs):
        """Helper to run shell commands safely across platforms."""
        # Inject project root into PYTHONPATH for all subprocesses
        root = AuditHarness.get_canonical_root()
        env = kwargs.get("env", os.environ.copy())

        current_pythonpath = env.get("PYTHONPATH", "")
        # Paths to inject
        target_paths = [str(root.resolve()), str((root / "packages").resolve()), str((root / "apps").resolve())]

        existing_paths = [p.strip() for p in current_pythonpath.split(os.pathsep) if p.strip()]
        final_paths = []
        for p in target_paths:
            if p not in final_paths:
                final_paths.append(p)
        for p in existing_paths:
            if p not in final_paths:
                final_paths.append(p)

        env["PYTHONPATH"] = os.pathsep.join(final_paths)
        kwargs["env"] = env

        if isinstance(cmd, list) and len(cmd) > 0:
            # Diagnostics/Resolution: If second argument looks like a script, try to resolve it
            if len(cmd) > 1 and cmd[1].endswith(".py") and not os.path.isabs(cmd[1]):
                try:
                    resolved = AuditHarness.resolve_script_path(cmd[1])
                    self.log(f"Resolved relative script {cmd[1]} to {resolved}")
                    cmd[1] = str(resolved)
                except FileNotFoundError:
                    # Don't crash here, let subprocess try but log the warning
                    self.log(f"WARNING: Script {cmd[1]} not found relative to root.")

            # Fallback for python executable if absolute path is broken/missing
            # Use normcase for robust comparison on Windows
            if os.path.normcase(str(cmd[0])) == os.path.normcase(sys.executable) and not os.path.exists(cmd[0]):
                cmd[0] = "python"

            # On Windows, using list with shell=False is generally more reliable for absolute paths
            res = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
            if res.stderr and not res.stdout:
                # If stdout is empty but stderr has content, "move" stderr to stdout for easier logging in vectors
                # (since many vectors only log .stdout)
                res.stdout = f"STDERR: {res.stderr}"
            return res

        # shell=False: cmd tiba sebagai list; fallback string via shlex
        # (quoting-aware) bila pemanggil masih mengirim string.
        return subprocess.run(
            shlex.split(cmd) if isinstance(cmd, str) else cmd,
            shell=False,
            capture_output=True,
            text=True,
            **kwargs,
        )

    def run(self) -> AuditResult:
        try:
            self.setup()
            self.reproduce()
            success = self.validate()
            self.teardown()
            return AuditResult(self.vector_id, success, logs=self.logs)
        except Exception as e:
            self.log(f"Execution failed: {e}")
            # Ensure failure is captured even on crash
            return AuditResult(self.vector_id, False, message=str(e), logs=self.logs)

class FinancialAuditVector(BaseAuditVector):
    """Specialized vector for financial logic validation."""
    pass

class SecurityAuditVector(BaseAuditVector):
    """Specialized vector for security and vulnerability validation."""
    def check_sql_injection(self, query_template, malicious_input):
        """Helper to check if a query template is vulnerable to injection."""
        query = query_template.replace("?", f"'{malicious_input}'")
        self.log(f"Generated query: {query}")
        return "DROP TABLE" in query.upper() and "--" in query

class AIAuditVector(BaseAuditVector):
    """Specialized vector for AI/ML integrity validation."""
    pass

class AuditHarness:
    """Utilities for executing stability vectors in the Infrastructure Audit."""

    @staticmethod
    def get_canonical_root():
        """Vector 1.1: Returns the absolute canonical root of the project."""
        current = Path(__file__).resolve()
        # Primary Search: Look for GEMINI.md (canonical root marker)
        for parent in [current] + list(current.parents):
            if (parent / "GEMINI.md").exists():
                return parent.resolve()

        # Secondary Search: Fallback to common markers
        for parent in [current] + list(current.parents):
            if (parent / "package.json").exists() or (parent / ".git").exists() or (parent / ".setup_done").exists():
                return parent.resolve()

        # Final fallback
        return current.parent.parent.parent.resolve()

    @staticmethod
    def resolve_script_path(relative_path):
        """Resolves a relative path from the project root to an absolute path."""
        root = AuditHarness.get_canonical_root()
        abs_path = (root / relative_path).resolve()
        if not abs_path.exists():
            raise FileNotFoundError(f"Audit script not found at: {abs_path}")
        return abs_path

    @staticmethod
    def test_thread_safety(target_fn, iterations=100):
        """Vector 1.2: Spawns threads to check for race conditions."""
        threads = []
        results = []
        errors = []

        def wrapper():
            try:
                res = target_fn()
                results.append(res)
            except Exception as e:
                errors.append(e)

        for _ in range(iterations):
            t = threading.Thread(target=wrapper)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        return results, errors

    @staticmethod
    def check_path_truncation(base_path, length=250):
        """Vector 1.5: Verifies file writes with long paths."""
        try:
            long_name = "a" * (length - len(str(base_path)) - 5)
            full_path = Path(base_path) / f"{long_name}.txt"

            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, 'w') as f:
                f.write("test")

            exists = full_path.exists()
            if exists:
                os.remove(full_path)
            return exists, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def verify_pid_cleanup(command, pid_file):
        """Vector 1.6: Verifies process cleanup and PID management."""
        # shell=False + arg array; command list[str] dari pemanggil.
        process = subprocess.Popen(command, shell=False)
        pid = process.pid

        with open(pid_file, 'w') as f:
            f.write(str(pid))

        time.sleep(1)

        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
        else:
            process.kill()

        process.wait()

        try:
            if os.name == 'nt':
                res = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True)
                alive = str(pid) in res.stdout
            else:
                os.kill(pid, 0)
                alive = True
        except OSError:
            alive = False

        return not alive

    @staticmethod
    def ensure_idempotent_sys_path(path):
        """Vector 1.4: Ensures path appears only once in sys.path."""
        target = str(Path(path).resolve())
        new_path = []
        seen = False
        for p in sys.path:
            resolved_p = str(Path(p).resolve()) if p else ""
            if resolved_p == target:
                if not seen:
                    new_path.append(p)
                    seen = True
            else:
                new_path.append(p)
        sys.path[:] = new_path
        return sys.path.count(target) + sys.path.count(path) <= 1

    @staticmethod
    def detect_circular_imports(module_name):
        """Vector 1.7: Checks for circular imports."""
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            __import__(module_name)
            return True, None
        except ImportError as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def test_bom_parsing(file_path, content):
        """Vector 1.8: Verifies BOM-aware parsing."""
        with open(file_path, 'w', encoding='utf-16') as f:
            f.write(content)
        return True

def run_test_vector(vector_id, description, test_fn):
    print(f"Executing Vector {vector_id}: {description}")
    try:
        success, message = test_fn()
        status = "PASS" if success else "FAIL"
        print(f"[{status}] {message if message else ''}")
        return status, message
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return "FAIL", str(e)
