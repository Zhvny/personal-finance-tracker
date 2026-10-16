import os
import re
import sys
import tempfile
import time
from pathlib import Path

from harness import AuditHarness, BaseAuditVector


class AuditVector_1_10(BaseAuditVector):
    """
    Failure Vector 1.10: Orphan Process Reaper
    Verify that a child process terminates if its parent exits.
    """
    def setup(self):
        # Use a proper temporary file for signaling
        fd, self.temp_file_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        self.temp_file = Path(self.temp_file_path)
        self.log(f"Temp file: {self.temp_file}")

        self.root = AuditHarness.get_canonical_root()

        # Script for the child process
        self.child_script = f"""
import time
import os
import sys
# Add root to sys.path so packages.core is importable
sys.path.append(r'{self.root}')
from packages.core.utils.process_guard import protect_orphan

# Small interval for testing
protect_orphan(interval=0.5)

# Signal we are running
with open(sys.argv[1], 'w') as f:
    f.write('running')

# Loop forever
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
"""
        cfd, self.child_py_path = tempfile.mkstemp(suffix=".py")
        os.close(cfd)
        self.child_py = Path(self.child_py_path).resolve()
        with open(self.child_py, 'w') as f:
            f.write(self.child_script)

    def reproduce(self):
        # Determine valid python executable to pass to wrapper
        python_exe = sys.executable
        if not os.path.exists(python_exe):
            python_exe = "python"

        # Wrapper script that starts child and then exits
        wrapper_script = f"""
import subprocess
import sys
import time
import os

# Start child
# On Windows, use DETACHED_PROCESS to fully decouple from parent pipes
creation_flags = 0x00000008 if os.name == 'nt' else 0
child = subprocess.Popen(
    [r'{python_exe}', r'{self.child_py}', r'{self.temp_file}'], 
    stdout=subprocess.DEVNULL, 
    stderr=subprocess.DEVNULL,
    creationflags=creation_flags
)
print(f"CHILD_PID:{{child.pid}}")
# Wait a bit for child to start
time.sleep(1)
# Exit wrapper
sys.exit(0)
"""
        wfd, self.wrapper_py_path = tempfile.mkstemp(suffix=".py")
        os.close(wfd)
        self.wrapper_py = Path(self.wrapper_py_path)
        with open(self.wrapper_py, 'w') as f:
            f.write(wrapper_script)

        self.log("Starting wrapper process...")
        res = self.run_command([sys.executable, str(self.wrapper_py)])

        # Extract Child PID
        match = re.search(r"CHILD_PID:(\d+)", res.stdout)
        if not match:
            self.log(f"Failed to get child PID. Output: {res.stdout}")
            self.child_pid = None
            return

        self.child_pid = int(match.group(1))
        self.log(f"Child process started with PID: {self.child_pid}")

        # Verify child started by checking if file was written
        # Wait up to 5s for start signal
        started = False
        for _ in range(10):
            if self.temp_file.exists() and self.temp_file.stat().st_size > 0:
                started = True
                break
            time.sleep(0.5)

        if not started:
            self.log("Child did not signal start.")
            self.is_alive = False # Not even started
            return

        # Wait for reaper to kick in (interval is 0.5s, let's wait 3s)
        self.log("Waiting for reaper to terminate child...")
        time.sleep(3)

        # Check if child is alive
        try:
            # os.kill(pid, 0) checks if process exists
            os.kill(self.child_pid, 0)
            self.is_alive = True
            self.log("Child is still alive (FAILURE).")
        except OSError:
            self.is_alive = False
            self.log("Child is terminated (SUCCESS).")

    def validate(self) -> bool:
        return self.child_pid is not None and not self.is_alive

    def teardown(self):
        if hasattr(self, 'child_pid') and getattr(self, 'is_alive', False):
            try:
                os.kill(self.child_pid, 9)
            except:
                pass

        # Clean up temp files
        for f_path in [self.temp_file_path, self.child_py_path, self.wrapper_py_path]:
            if f_path and os.path.exists(f_path):
                try: os.remove(f_path)
                except: pass
