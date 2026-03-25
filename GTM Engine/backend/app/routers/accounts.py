import math
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DBSession, ManagerUser
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.schemas.common import PaginatedResponse
from app.services.account import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    db: DBSession,
    current_user: ManagerUser,
) -> AccountRead:
    service = AccountService(db)
    account = await service.create(body, user_id=current_user.id, user_email=current_user.email)
    return AccountRead.model_validate(account)


@router.get("", response_model=PaginatedResponse[AccountRead])
async def list_accounts(
    db: DBSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    name: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    erp_ecosystem: str | None = Query(default=None),
    geography: str | None = Query(default=None),
) -> PaginatedResponse[AccountRead]:
    service = AccountService(db)
    accounts, total = await service.list(
        page=page,
        page_size=page_size,
        name_search=name,
        industry=industry,
        erp_ecosystem=erp_ecosystem,
        geography=geography,
    )
    return PaginatedResponse(
        items=[AccountRead.model_validate(a) for a in accounts],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> AccountRead:
    service = AccountService(db)
    account = await service.get(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return AccountRead.model_validate(account)


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    db: DBSession,
    current_user: ManagerUser,
) -> AccountRead:
    service = AccountService(db)
    account = await service.update(account_id, body, user_id=current_user.id, user_email=current_user.email)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return AccountRead.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    db: DBSession,
    current_user: ManagerUser,
) -> None:
    service = AccountService(db)
    deleted = await service.delete(account_id, user_id=current_user.id, user_email=current_user.email)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
