import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict

from packages.core.infrastructure.config import Config

logger = logging.getLogger(__name__)

class MaintenanceService:
    """
    Internal maintenance service for Finance-Tracker.
    Handles SQL patching, system health checks, and environment cleanup.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        # Initialize Config to ensure BASE_DIR is set
        Config.initialize()
        self.db_paths = Config.get_db_paths()
        self.application_dir = self.project_root / "packages" / "core" / "application"

    def run_all_patches(self) -> Dict[str, Any]:
        """Runs all registered system patches."""
        results = {
            "sql_optimization": self.apply_sql_optimization(),
            "sql_syntax_fix": self.patch_sql_syntax(),
            "profile_integrity": self.check_profile_structure(),
            "root_cleanup": self.cleanup_root(),
            "bom_removal": self.remove_bom(),
            "port_cleanup_fix": self.fix_port_and_startup(),
            "path_neutralization": self.neutralize_paths(),
            "setup_pg_update": self.update_setup_pg()
        }
        return results

    def neutralize_paths(self) -> bool:
        """Neutralizes hardcoded paths across the codebase."""
        try:
            from scripts.health_check import check_hardcoded_paths
            return check_hardcoded_paths(fix=True)
        except ImportError:
            logger.error("Could not import check_hardcoded_paths from scripts.health_check")
            return False

    def apply_sql_optimization(self) -> bool:
        """Ensures databases are optimized and using WAL mode."""
        logger.info("Running SQL optimizations...")
        success = True
        for name, path in self.db_paths.items():
            if not path.exists(): continue
            try:
                # Use a timeout to avoid locking issues during maintenance
                with sqlite3.connect(path, timeout=10) as conn:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA optimize;")
                logger.info(f" Optimized {name} database.")
            except Exception as e:
                logger.error(f" Failed to optimize {name} ({path}): {e}")
                success = False
        return success

    def patch_sql_syntax(self) -> bool:
        """Applies generic and service-specific Postgres syntax alignment."""
        logger.info("Patching SQL syntax for Postgres alignment...")
        fix_map = {
            "income_service.py": self._fix_income_sql,
            "expense_service.py": self._fix_expenses_sql,
            "investment_service.py": self._fix_analytics_sql,
            "wealth_service.py": self._fix_balances_sql,
            "whale_service.py": self._fix_ai_sql
        }

        success = True
        for fname, fix_func in fix_map.items():
            path = self.application_dir / fname
            if not path.exists(): continue

            try:
                content = path.read_text(encoding="utf-8")
                # 1. Apply service-specific fix
                content = fix_func(content)
                # 2. Apply generic Postgres alignment
                new_content = self._fix_generic_sql(content)

                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    logger.info(f" Patched SQL syntax in {fname}")
            except Exception as e:
                logger.error(f" Failed to patch {fname}: {e}")
                success = False
        return success

    def _fix_generic_sql(self, content: str) -> str:
        """Generic Postgres syntax alignment: ? -> %s, strftime -> to_char."""
        # Replace SQLite placeholders with Postgres
        content = re.sub(r'(?<![\'"])\?(?![\'"])', '%s', content)

        # Replace strftime with to_char
        content = re.sub(r"strftime\s*\(\s*'%Y-%m'\s*,\s*(\w+)\s*\)", r"to_char(\1, 'YYYY-MM')", content)
        content = re.sub(r"strftime\s*\(\s*'%Y-%m-%d'\s*,\s*(\w+)\s*\)", r"to_char(\1, 'YYYY-MM-DD')", content)
        return content

    def _fix_balances_sql(self, content: str) -> str:
        return content

    def _fix_ai_sql(self, content: str) -> str:
        return re.sub(
            r'_query\(_balances_db\(\),\s*"SELECT value FROM manual_balances WHERE key=\'emergency_fund\'"\)',
            r'_query(_balances_db(), "SELECT value FROM manual_balances WHERE key=%s", ("emergency_fund",))',
            content
        )

    def _fix_analytics_sql(self, content: str) -> str:
        pattern = r'(holdings = _query\(db, """\s+SELECT.*?FROM investments i\s+WHERE i\.status != )\'sold\'(\s+AND COALESCE\(i\.remaining_quantity, i\.quantity\) > )0(\s+"""\s*\))'
        return re.sub(pattern, r'\1%s\2%s\3, ("sold", 0)', content, flags=re.DOTALL)

    def _fix_income_sql(self, content: str) -> str:
        content = re.sub(r'(_query\(bal_db,\s*"SELECT value FROM manual_balances WHERE key=)\'emergency_fund\'("\))',
                         r'\1%s\2, ("emergency_fund",)', content)
        content = re.sub(r'(INSERT INTO manual_balances \(key, value, updated_at\) VALUES \()\'emergency_fund\'(,%s,%s\))',
                         r'\1%s,%s,%s\2', content)
        return content.replace('(ef_cur + db_writes["emergency_fund"], now_iso))',
                               '("emergency_fund", ef_cur + db_writes["emergency_fund"], now_iso))')

    def _fix_expenses_sql(self, content: str) -> str:
        return content.replace("WHERE is_recurring=TRUE", "WHERE is_recurring=%s")

    def update_setup_pg(self) -> bool:
        """Add investment.fx_rates to setup_postgres.py."""
        path = self.project_root / "scripts" / "setup_postgres.py"
        if not path.exists(): return False

        try:
            content = path.read_text(encoding="utf-8")
            ddl = """
        cur.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS investment.fx_rates (
                pair TEXT NOT NULL,
                rate_date DATE NOT NULL,
                rate DECIMAL(20, 8) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (pair, rate_date)
            );
        \"\"\")
"""
            if 'investment.fx_rates' not in content:
                insertion_point = '        # 5. Market Tables'
                if insertion_point in content:
                    content = content.replace(insertion_point, ddl + "\n" + insertion_point)
                    path.write_text(content, encoding="utf-8")
                    logger.info("Added investment.fx_rates to setup_postgres.py")
                    return True
        except Exception as e:
            logger.error(f"Failed to update setup_postgres.py: {e}")

        return False

    def cleanup_root(self) -> int:
        """Delete redundant fix_*.py and tmp_patch_*.py files from root."""
        redundant_files = [
            "apply_final_patches_v2.py",
            "apply_final_patches.py",
            "apply_task2_fix.py",
            "check_agent_locks.py",
            "check_all_data_v2.py",
            "check_all_data.py",
            "verify_totals.py",
            "audit_postgres.py",
            "fix_balances.py",
            "fix_deps.py",
            "fix_script.py",
            "fix_sql_2.py",
            "fix_sql.py",
            "tmp_patch_advanced.py",
            "tmp_patch_behavioral.py",
            "tmp_patch_exporter_service.py",
            "tmp_patch_merchant.py",
            "update_setup_pg.py"
        ]

        count = 0
        for f in redundant_files:
            p = self.project_root / f
            if p.exists():
                try:
                    p.unlink()
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {f}: {e}")

        logger.info(f"Cleaned up {count} redundant files from root.")
        return count

    def cleanup_redundant_files(self) -> int:
        """Alias for cleanup_root."""
        return self.cleanup_root()

    def remove_bom(self) -> int:
        """Remove UTF-8 BOM from project files."""
        count = 0
        for root, _, files in os.walk(self.project_root):
            if any(x in root for x in ["__pycache__", ".git", ".pytest_cache", "node_modules"]):
                continue
            for f in files:
                if f.endswith((".py", ".bat", ".md", ".json")):
                    p = Path(root) / f
                    try:
                        raw = p.read_bytes()
                        if raw.startswith(b'\xef\xbb\xbf'):
                            p.write_bytes(raw[3:])
                            count += 1
                    except Exception:
                        logger.warning("Failed to running maintenance task", exc_info=True)
                        pass
        logger.info(f"Removed BOM from {count} files.")
        return count

    def fix_port_and_startup(self) -> bool:
        """Updates run-gui.bat to target port 8501 for cleanup."""
        bat_path = self.project_root / "run-gui.bat"
        if not bat_path.exists():
            return False

        try:
            content = bat_path.read_text(encoding="utf-8")

            # Look for the port cleanup section
            old_cleanup_marker = 'echo [*] Ensuring ports 8443 and 8444 are free...'
            if old_cleanup_marker in content:
                # Add 8501 to the loop
                new_cleanup_marker = 'echo [*] Ensuring ports 8443, 8444 and 8501 are free...'
                content = content.replace(old_cleanup_marker, new_cleanup_marker)
                content = content.replace('for %%p in (8443 8444) do (', 'for %%p in (8443 8444 8501) do (')

                bat_path.write_text(content, encoding="utf-8")
                logger.info("Updated run-gui.bat with port 8501 cleanup logic")
                return True
        except Exception as e:
            logger.error(f"Failed to update run-gui.bat: {e}")

        return False

    def check_profile_structure(self) -> bool:
        """Ensures all mandatory profile directories exist."""
        try:
            from scripts.health_check import check_profiles
            return check_profiles()
        except ImportError:
            logger.error("Could not import check_profiles from scripts.health_check")
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """Executes a full suite of health checks."""
        try:
            from scripts.health_check import (
                check_hardcoded_paths,
                check_postgres,
                check_profiles,
                check_stray_databases,
            )
            return {
                "hardcoded_paths": check_hardcoded_paths(),
                "stray_databases": check_stray_databases(),
                "profiles_exist": check_profiles(),
                "postgres_conn": check_postgres()
            }
        except Exception as e:
            logger.error(f"Health check execution failed: {e}")
            return {"error": False}
