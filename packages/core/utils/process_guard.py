import os
import threading
import time


class ProcessGuard:
    """
    Monitors parent process and terminates child if parent dies (orphan protection).
    Useful for background workers started by a main app.
    """
    def __init__(self, check_interval=2):
        self.parent_pid = os.getppid()
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _monitor(self):
        while not self._stop_event.is_set():
            if not self._is_parent_alive():
                # Parent is gone, terminate self immediately
                # Using os._exit to skip cleanup and ensure termination
                os._exit(1)
            time.sleep(self.check_interval)

    def _is_parent_alive(self):
        if self.parent_pid == 1: # Init process on Unix
            return True

        try:
            # os.kill(pid, 0) check existence without sending signal
            os.kill(self.parent_pid, 0)
            return True
        except OSError:
            return False

def protect_orphan(interval=2):
    """
    Convenience function to start a daemon thread that reaps the current process if parent dies.
    """
    guard = ProcessGuard(check_interval=interval)
    guard.start()
    return guard
