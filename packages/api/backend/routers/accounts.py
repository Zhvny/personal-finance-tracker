from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.api.backend.security.core import require_scope
from packages.core.domain.models.account import VirtualAccount
from packages.core.infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository

from .deps import get_active_profile

router = APIRouter(
    prefix="/api/accounts",
    tags=["accounts"],
    dependencies=[Depends(require_scope("write"))]
)

class VirtualAccountCreate(BaseModel):
    name: str
    target_amount: float
    balance: float = 0.0
    currency: str = "USD"
    parent_account_id: int = None

class VirtualAccountUpdate(BaseModel):
    balance: float = None
    target_amount: float = None

@router.get("/virtual", response_model=List[VirtualAccount])
def list_virtual_accounts(profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    return repo.get_all(profile_id)

@router.post("/virtual")
def create_virtual_account(account_in: VirtualAccountCreate, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    account = VirtualAccount(
        name=account_in.name,
        target_amount=account_in.target_amount,
        balance=account_in.balance,
        currency=account_in.currency,
        parent_account_id=account_in.parent_account_id,
        profile_id=profile_id
    )
    repo.save(account)
    return account

@router.get("/virtual/{id}")
def get_virtual_account(id: int, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    account = repo.get_by_id(id, profile_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.put("/virtual/{id}")
def update_virtual_account(id: int, update: VirtualAccountUpdate, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    account = repo.get_by_id(id, profile_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if update.balance is not None:
        repo.update_balance(id, profile_id, update.balance)

    # Reload and return
    return repo.get_by_id(id, profile_id)

@router.delete("/virtual/{id}")
def delete_virtual_account(id: int, profile_id: str = Depends(get_active_profile)):
    repo = SqliteVirtualAccountRepository()
    if repo.delete(id, profile_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Account not found")
