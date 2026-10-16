import os
import sys
from pathlib import Path

# Fix sys.path for monorepo imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from packages.core.domain.models.account import VirtualAccount
from packages.core.infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository


def test_va_flow():
    # Use a name that doesn't trigger Postgres redirection (avoid 'goals.db' etc)
    test_db = str(_PROJECT_ROOT / "test_va_mock.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    repo = SqliteVirtualAccountRepository(test_db)

    # 1. Save
    va = VirtualAccount(name="New Car", target_amount=20000.0, profile_id="test_user")
    repo.save(va)
    print(f"Saved VA with ID: {va.id}")

    # 2. Retrieve
    retrieved = repo.get_by_id(va.id, "test_user")
    assert retrieved.name == "New Car"
    print("Retrieval successful")

    # 3. Update
    repo.update_balance(va.id, "test_user", 500.0)
    updated = repo.get_by_id(va.id, "test_user")
    assert updated.balance == 500.0
    print(f"Progress: {updated.progress_pct}%")

    # 4. List
    all_va = repo.get_all("test_user")
    assert len(all_va) >= 1
    print(f"Total virtual accounts: {len(all_va)}")

    # 5. Delete
    repo.delete(va.id, "test_user")
    assert repo.get_by_id(va.id, "test_user") is None
    print("Delete successful")

    if os.path.exists(test_db):
        os.remove(test_db)
    print("Test passed!")

if __name__ == "__main__":
    test_va_flow()
