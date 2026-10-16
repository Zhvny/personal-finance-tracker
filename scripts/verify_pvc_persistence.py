#!/usr/bin/env python3
"""
scripts/verify_pvc_persistence.py
============================
Automated Kubernetes PVC Persistence Verification.
Tests:
1. Write-Delete-Verify: Marker table data survives pod deletion.
2. Backup-Restore: Data can be recovered from pg_dump.
"""

import argparse
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

# Project Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Ensure project root is in path
BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

try:
    from packages.core.infrastructure.config import Config
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError as e:
    print(f"{RED}[ERROR]{RESET} Missing dependencies: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pvc_verification")

class PVCVerifier:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        Config.initialize()
        DatabaseManager.initialize()

        self.host = Config.POSTGRES_HOST
        self.port = Config.POSTGRES_PORT
        self.user = Config.POSTGRES_USER
        self.password = Config.POSTGRES_PASSWORD
        self.db_name = Config.POSTGRES_DB

        # Test parameters
        self.schema = "financials"
        self.table = "pvc_test"
        self.full_table = f"{self.schema}.{self.table}"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.schema) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.table):
            raise ValueError(f"Invalid schema/table name: {self.schema}.{self.table}")
        self.temp_dir = tempfile.gettempdir()
        self.backup_path = os.path.join(self.temp_dir, "pvc_backup.sql")

    def check_tools(self):
        """Verify necessary CLI tools are installed."""
        tools = ["kubectl", "pg_dump", "psql"]
        missing = []
        for tool in tools:
            if not shutil.which(tool):
                missing.append(tool)

        if missing:
            print(f"{YELLOW}[WARN]{RESET} Missing CLI tools: {missing}")
            print("       Tests involving these tools will likely fail.")
        return len(missing) == 0

    def run_cmd(self, cmd, capture=True, check=True, stdout=None, stdin=None):
        """Execute a command with shell=False. Caller passes arg array.

        Redirect shell (`>`, `<`) diganti file handle stdout/stdin eksplisit
        di test_backup_restore — input path/tools internal tetap,
        tidak ada interpolasi user input.
        """
        env = os.environ.copy()
        env["PGPASSWORD"] = self.password

        argv = shlex.split(cmd) if isinstance(cmd, str) else cmd
        try:
            if capture:
                result = subprocess.run(
                    argv,
                    shell=False,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=check,
                    **({"stdout": stdout} if stdout is not None else {}),
                    **({"stdin": stdin} if stdin is not None else {}),
                )
                return (result.stdout or "").strip()
            else:
                subprocess.run(
                    argv,
                    shell=False,
                    env=env,
                    check=check,
                    **({"stdout": stdout} if stdout is not None else {}),
                    **({"stdin": stdin} if stdin is not None else {}),
                )
                return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {argv}\nError: {e.stderr}")
            if check:
                raise
            return None

    def check_connectivity(self):
        print(f"[*] Checking connectivity to {self.host}:{self.port}...")
        try:
            res = DatabaseManager.query("SELECT 1 as health;")
            if res and res[0]['health'] == 1:
                print(f"{GREEN}[PASS]{RESET} Connected to Postgres.")
                return True
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} Connection failed: {e}")
            return False

    def setup_marker(self):
        marker_id = f"PVC-TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        print(f"[*] Setting up marker: {marker_id}...")

        setup_sql = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};
        CREATE TABLE IF NOT EXISTS {self.full_table} (
            id SERIAL PRIMARY KEY,
            marker VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO {self.full_table} (marker) VALUES (%s);
        """
        try:
            DatabaseManager.execute(setup_sql, (marker_id,))
            print(f"{GREEN}[PASS]{RESET} Marker created in {self.full_table}.")
            return marker_id
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} Failed to setup marker: {e}")
            raise

    def verify_marker(self, marker_id, stage="post-deletion"):
        print(f"[*] Verifying marker ({stage}): {marker_id}...")
        query = f"SELECT marker FROM {self.full_table} WHERE marker = %s;"
        try:
            res = DatabaseManager.query(query, (marker_id,))
            if res and res[0]['marker'] == marker_id:
                print(f"{GREEN}[PASS]{RESET} Marker verified ({stage}). Persistence confirmed.")
                return True
            else:
                print(f"{RED}[FAIL]{RESET} Marker NOT found ({stage})!")
                return False
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} Verification error ({stage}): {e}")
            return False

    def delete_pod(self):
        pod_name = "postgres-db-0"
        print(f"[*] Deleting pod {pod_name}...")
        if self.dry_run:
            print(f"{YELLOW}[DRY-RUN]{RESET} Skipping kubectl delete pod.")
            return True

        try:
            self.run_cmd(["kubectl", "delete", "pod", pod_name])
            print(f"{GREEN}[PASS]{RESET} Pod deletion triggered.")
            return True
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} Failed to delete pod: {e}")
            return False

    def wait_for_pod(self):
        pod_name = "postgres-db-0"
        print(f"[*] Waiting for pod {pod_name} to be Ready...")
        if self.dry_run:
            print(f"{YELLOW}[DRY-RUN]{RESET} Skipping wait.")
            return True

        try:
            # Wait for pod to disappear (optional) and then reappear and be ready
            self.run_cmd(["kubectl", "wait", "--for=condition=Ready", f"pod/{pod_name}", "--timeout=120s"])
            print(f"{GREEN}[PASS]{RESET} Pod {pod_name} is Ready.")
            return True
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} Pod failed to become ready: {e}")
            return False

    def test_backup_restore(self, marker_id):
        print("[*] Testing Backup/Restore lifecycle...")

        # 1. Backup (redirect ">" diganti file handle — shell kompleks terdokumentasi di run_cmd)
        print(f"  [1] Backing up table {self.full_table}...")
        backup_argv = [
            "pg_dump",
            "-h",
            self.host,
            "-p",
            str(self.port),
            "-U",
            self.user,
            "-d",
            self.db_name,
            "-t",
            self.full_table,
        ]
        try:
            with open(self.backup_path, "w") as f:
                self.run_cmd(backup_argv, stdout=f)
            print(f"      {GREEN}Backup saved to {self.backup_path}{RESET}")
        except Exception as e:
            print(f"      {RED}Backup failed: {e}{RESET}")
            return False

        # 2. Drop table
        print(f"  [2] Dropping table {self.full_table}...")
        try:
            DatabaseManager.execute(f"DROP TABLE {self.full_table};")
            print(f"      {GREEN}Table dropped.{RESET}")
        except Exception as e:
            print(f"      {RED}Drop failed: {e}{RESET}")
            return False

        # 3. Restore ("<" diganti file handle)
        print("  [3] Restoring from backup...")
        restore_argv = ["psql", "-h", self.host, "-p", str(self.port), "-U", self.user, "-d", self.db_name]
        try:
            with open(self.backup_path) as f:
                self.run_cmd(restore_argv, stdin=f)
            print(f"      {GREEN}Restore completed.{RESET}")
        except Exception as e:
            print(f"      {RED}Restore failed: {e}{RESET}")
            return False

        # 4. Verify
        return self.verify_marker(marker_id, stage="post-restore")

    def cleanup(self):
        print("[*] Cleaning up test artifacts...")
        try:
            DatabaseManager.execute(f"DROP TABLE IF EXISTS {self.full_table};")
            if os.path.exists(self.backup_path):
                os.remove(self.backup_path)
            print(f"{GREEN}[PASS]{RESET} Cleanup complete.")
        except Exception as e:
            print(f"{YELLOW}[WARN]{RESET} Cleanup error: {e}")

    def run(self):
        print("=== PVC PERSISTENCE VERIFICATION ===\n")

        self.check_tools()

        if not self.check_connectivity():
            sys.exit(1)

        try:
            # Phase 1: Persistence Test
            marker_id = self.setup_marker()

            if not self.delete_pod():
                sys.exit(1)

            if not self.wait_for_pod():
                sys.exit(1)

            # Allow a small buffer for connection pool to recover if needed
            import time
            time.sleep(2)

            if not self.verify_marker(marker_id, stage="post-deletion"):
                print(f"{RED}PERSISTENCE CHECK FAILED!{RESET}")
                sys.exit(1)

            print(f"\n{GREEN}PHASE 1 (Persistence) SUCCESSFUL{RESET}\n")

            # Phase 2: Backup/Restore Test
            if not self.test_backup_restore(marker_id):
                print(f"{RED}BACKUP/RESTORE CHECK FAILED!{RESET}")
                sys.exit(1)

            print(f"\n{GREEN}PHASE 2 (Backup/Restore) SUCCESSFUL{RESET}\n")

            print(f"{GREEN}ALL PVC VERIFICATION TESTS PASSED{RESET}")

        finally:
            self.cleanup()

def main():
    parser = argparse.ArgumentParser(description="Verify K8s PVC Persistence")
    parser.add_argument("--dry-run", action="store_true", help="Skip destructive kubectl deletion")
    args = parser.parse_args()

    verifier = PVCVerifier(dry_run=args.dry_run)
    verifier.run()

if __name__ == "__main__":
    main()
