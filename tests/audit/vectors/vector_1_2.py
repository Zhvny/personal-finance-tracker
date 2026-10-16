import threading

from harness import BaseAuditVector

from packages.core.infrastructure.config import Config


class AuditVector_1_2(BaseAuditVector):
    """
    Failure Vector 1.2: Thread-Safe Config Singleton
    Spawn 100 threads accessing Config.BASE_DIR simultaneously.
    """
    def setup(self):
        self.num_threads = 100
        self.results = []
        self.errors = []

    def reproduce(self):
        def access_config():
            try:
                # Accessing a class attribute is atomic in Python,
                # but we want to simulate simultaneous access to trigger any init logic.
                val = Config.BASE_DIR
                self.results.append(val)
            except Exception as e:
                self.errors.append(e)

        threads = []
        for _ in range(self.num_threads):
            t = threading.Thread(target=access_config)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

    def validate(self) -> bool:
        self.log(f"Threads: {self.num_threads}, Results: {len(self.results)}, Errors: {len(self.errors)}")

        if self.errors:
            for err in self.errors:
                self.log(f"Error: {err}")
            return False

        # Check if all results are the same
        if len(set(self.results)) > 1:
            self.log("Detected inconsistent BASE_DIR values!")
            return False

        return len(self.results) == self.num_threads

    def teardown(self):
        pass
