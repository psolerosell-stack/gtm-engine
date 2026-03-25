import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.audit import AuditService, _model_to_dict

logger = structlog.get_logger(__name__)


class AccountService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._audit = AuditService(db)

    async def create(
        self,
        data: AccountCreate,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> Account:
        account = Account(**data.model_dump())
        self.db.add(account)
        await self.db.flush()

        await self._audit.log(
            table_name="accounts",
            record_id=account.id,
            operation="INSERT",
            new_values=_model_to_dict(account),
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        await self.db.refresh(account)
        logger.info("account_created", account_id=str(account.id), name=account.name)
        return account

    async def get(self, account_id: uuid.UUID) -> Optional[Account]:
        result = await self.db.execute(
            select(Account).where(
                Account.id == account_id, Account.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        name_search: Optional[str] = None,
        industry: Optional[str] = None,
        erp_ecosystem: Optional[str] = None,
        geography: Optional[str] = None,
    ) -> Tuple[List[Account], int]:
        stmt = select(Account).where(Account.deleted_at.is_(None))
        count_stmt = (
            select(func.count())
            .select_from(Account)
            .where(Account.deleted_at.is_(None))
        )

        if name_search:
            stmt = stmt.where(Account.name.ilike(f"%{name_search}%"))
            count_stmt = count_stmt.where(Account.name.ilike(f"%{name_search}%"))
        if industry:
            stmt = stmt.where(Account.industry.ilike(f"%{industry}%"))
            count_stmt = count_stmt.where(Account.industry.ilike(f"%{industry}%"))
        if erp_ecosystem:
            stmt = stmt.where(Account.erp_ecosystem == erp_ecosystem)
            count_stmt = count_stmt.where(Account.erp_ecosystem == erp_ecosystem)
        if geography:
            stmt = stmt.where(Account.geography.ilike(f"%{geography}%"))
            count_stmt = count_stmt.where(Account.geography.ilike(f"%{geography}%"))

        stmt = stmt.order_by(Account.name).offset((page - 1) * page_size).limit(page_size)

        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        result = await self.db.execute(stmt)
        accounts = list(result.scalars().all())
        return accounts, total

    async def update(
        self,
        account_id: uuid.UUID,
        data: AccountUpdate,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> Optional[Account]:
        account = await self.get(account_id)
        if account is None:
            return None

        old_values = _model_to_dict(account)
        update_dict = data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(account, field, value)

        account.updated_at = datetime.now(timezone.utc)

        await self._audit.log(
            table_name="accounts",
            record_id=account.id,
            operation="UPDATE",
            old_values=old_values,
            new_values=_model_to_dict(account),
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        await self.db.refresh(account)
        logger.info("account_updated", account_id=str(account_id))
        return account

    async def delete(
        self,
        account_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> bool:
        account = await self.get(account_id)
        if account is None:
            return False

        old_values = _model_to_dict(account)
        account.deleted_at = datetime.now(timezone.utc)

        await self._audit.log(
            table_name="accounts",
            record_id=account.id,
            operation="DELETE",
            old_values=old_values,
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        logger.info("account_soft_deleted", account_id=str(account_id))
        return True
