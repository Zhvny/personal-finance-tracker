import os
import sqlite3
import tempfile

from harness import FinancialAuditVector


class AuditVector_2_8(FinancialAuditVector):
    """
    Failure Vector 2.8: Double-Entry Leakage (Non-Atomic)
    Verify that if a transaction fails halfway, no partial data remains.
    """
    def setup(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.log(f"Temp DB: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self.cursor.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, amount REAL)")
        self.cursor.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, msg TEXT)")
        self.conn.commit()

    def reproduce(self):
        self.log("Starting atomic transaction...")
        try:
            self.conn.execute("BEGIN TRANSACTION")

            # Step 1: Write to audit_log
            self.cursor.execute("INSERT INTO audit_log (msg) VALUES (?)", ("Transfer 100",))
            self.log("Wrote to audit_log.")

            # Step 2: Crash/Fail before writing to transactions
            self.log("Simulating crash before transaction table write.")
            raise Exception("DB_WRITE_FAILURE")

            # This line would normally be:
            # self.cursor.execute("INSERT INTO transactions (amount) VALUES (?)", (100,))
            # self.conn.commit()

        except Exception as e:
            self.log(f"Caught expected failure: {e}")
            self.conn.rollback()
            self.log("Rolled back transaction.")

    def validate(self) -> bool:
        # DoD: Both tables MUST be empty if the transaction was rolled back.
        self.cursor.execute("SELECT count(*) FROM audit_log")
        audit_count = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT count(*) FROM transactions")
        tx_count = self.cursor.fetchone()[0]

        self.log(f"Audit log count: {audit_count}")
        self.log(f"Transaction count: {tx_count}")

        return audit_count == 0 and tx_count == 0

    def teardown(self):
        self.conn.close()
        os.close(self.db_fd)
        os.remove(self.db_path)
