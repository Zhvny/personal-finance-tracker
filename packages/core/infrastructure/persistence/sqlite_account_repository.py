from typing import List, Optional

from packages.core.domain.models.account import VirtualAccount
from packages.core.domain.repositories.account_repository import IVirtualAccountRepository
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database


class SqliteVirtualAccountRepository(IVirtualAccountRepository):
    def __init__(self, db_path: Optional[str] = None):
        # Use Config.get_db_path("goals") which is where accounts are stored
        self.db_path = db_path or Config.get_db_path("goals")
        self._init_db()

    def _init_db(self):
        script = """
            CREATE TABLE IF NOT EXISTS virtual_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_account_id INTEGER,
                balance REAL DEFAULT 0,
                target_amount REAL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                profile_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_va_profile ON virtual_accounts(profile_id);
        """
        Database.execute_script(self.db_path, script)

    def save(self, account: VirtualAccount) -> int:
        sql = """
            INSERT INTO virtual_accounts (name, parent_account_id, balance, target_amount, currency, profile_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (account.name, account.parent_account_id, float(account.balance),
                  0.0, "IDR", account.profile_id) # Mapping to existing model fields
        result = Database.execute(self.db_path, sql, params)
        if result:
            account.id = str(result)
            return result
        return 0

    def get_all(self, profile_id: str) -> List[VirtualAccount]:
        sql = "SELECT * FROM virtual_accounts WHERE profile_id = ?"
        rows = Database.query(self.db_path, sql, (profile_id,))
        return [self._row_to_account(row) for row in rows]

    def get_by_id(self, account_id: int, profile_id: str) -> Optional[VirtualAccount]:
        sql = "SELECT * FROM virtual_accounts WHERE id = ? AND profile_id = ?"
        rows = Database.query(self.db_path, sql, (account_id, profile_id))
        if rows:
            return self._row_to_account(rows[0])
        return None

    def delete(self, account_id: int, profile_id: str) -> bool:
        sql = "DELETE FROM virtual_accounts WHERE id = ? AND profile_id = ?"
        result = Database.execute(self.db_path, sql, (account_id, profile_id))
        return bool(result)

    def update_balance(self, account_id: int, profile_id: str, new_balance: float) -> bool:
        sql = "UPDATE virtual_accounts SET balance = ? WHERE id = ? AND profile_id = ?"
        result = Database.execute(self.db_path, sql, (new_balance, account_id, profile_id))
        return bool(result)

    def _row_to_account(self, row: dict) -> VirtualAccount:
        return VirtualAccount(
            id=str(row["id"]),
            name=row["name"],
            balance=row["balance"],
            target_amount=row.get("target_amount") or 0.0,
        )

