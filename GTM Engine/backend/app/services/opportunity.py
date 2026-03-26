import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.partner import Partner
from app.schemas.opportunity import OpportunityCreate, OpportunityUpdate
from app.services.audit import AuditService, _model_to_dict

logger = structlog.get_logger(__name__)


class OpportunityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._audit = AuditService(db)

    async def _assert_account_exists(self, account_id: uuid.UUID) -> Account:
        result = await self.db.execute(
            select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")
        return account

    async def _assert_partner_exists(self, partner_id: uuid.UUID) -> Partner:
        result = await self.db.execute(
            select(Partner).where(Partner.id == partner_id, Partner.deleted_at.is_(None))
        )
        partner = result.scalar_one_or_none()
        if partner is None:
            raise ValueError(f"Partner {partner_id} not found")
        return partner

    async def create(
        self,
        data: OpportunityCreate,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> Opportunity:
        await self._assert_account_exists(data.account_id)
        if data.partner_id:
            await self._assert_partner_exists(data.partner_id)

        opp = Opportunity(**data.model_dump())
        self.db.add(opp)
        await self.db.flush()

        await self._audit.log(
            table_name="opportunities",
            record_id=opp.id,
            operation="INSERT",
            new_values=_model_to_dict(opp),
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        await self.db.refresh(opp)
        logger.info("opportunity_created", opp_id=str(opp.id), stage=opp.stage)
        return opp

    async def get(
        self,
        opp_id: uuid.UUID,
        load_relations: bool = False,
    ) -> Optional[Opportunity]:
        stmt = select(Opportunity).where(
            Opportunity.id == opp_id, Opportunity.deleted_at.is_(None)
        )
        if load_relations:
            stmt = stmt.options(
                selectinload(Opportunity.account),
                selectinload(Opportunity.partner),
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        stage_filter: Optional[str] = None,
        partner_id_filter: Optional[uuid.UUID] = None,
        account_id_filter: Optional[uuid.UUID] = None,
        owner_filter: Optional[str] = None,
        load_relations: bool = False,
    ) -> Tuple[List[Opportunity], int]:
        stmt = select(Opportunity).where(Opportunity.deleted_at.is_(None))
        count_stmt = (
            select(func.count())
            .select_from(Opportunity)
            .where(Opportunity.deleted_at.is_(None))
        )

        if stage_filter:
            stmt = stmt.where(Opportunity.stage == stage_filter)
            count_stmt = count_stmt.where(Opportunity.stage == stage_filter)
        if partner_id_filter:
            stmt = stmt.where(Opportunity.partner_id == partner_id_filter)
            count_stmt = count_stmt.where(Opportunity.partner_id == partner_id_filter)
        if account_id_filter:
            stmt = stmt.where(Opportunity.account_id == account_id_filter)
            count_stmt = count_stmt.where(Opportunity.account_id == account_id_filter)
        if owner_filter:
            stmt = stmt.where(Opportunity.owner.ilike(f"%{owner_filter}%"))
            count_stmt = count_stmt.where(Opportunity.owner.ilike(f"%{owner_filter}%"))

        if load_relations:
            stmt = stmt.options(
                selectinload(Opportunity.account),
                selectinload(Opportunity.partner),
            )

        stmt = (
            stmt.order_by(Opportunity.close_date.asc().nullslast(), Opportunity.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        result = await self.db.execute(stmt)
        opps = list(result.scalars().all())
        return opps, total

    async def update(
        self,
        opp_id: uuid.UUID,
        data: OpportunityUpdate,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> Optional[Opportunity]:
        opp = await self.get(opp_id)
        if opp is None:
            return None

        if data.partner_id and data.partner_id != opp.partner_id:
            await self._assert_partner_exists(data.partner_id)

        old_values = _model_to_dict(opp)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(opp, field, value)

        opp.updated_at = datetime.now(timezone.utc)

        await self._audit.log(
            table_name="opportunities",
            record_id=opp.id,
            operation="UPDATE",
            old_values=old_values,
            new_values=_model_to_dict(opp),
            user_id=user_id,
            user_email=user_email,
        )

        old_stage = old_values.get("stage")
        new_stage = opp.stage

        await self.db.commit()
        await self.db.refresh(opp)
        logger.info("opportunity_updated", opp_id=str(opp_id), stage=opp.stage)

        if old_stage != new_stage:
            base_data = {
                "opportunity_id": str(opp.id),
                "opportunity_name": opp.name,
                "previous_stage": old_stage,
                "new_stage": new_stage,
                "arr_value": opp.arr_value or 0,
                "close_reason": opp.close_reason or "",
                "partner_id": str(opp.partner_id) if opp.partner_id else "",
            }
            await self._fire_trigger("opportunity_stage_changed", "opportunity", opp.id, base_data)
            if new_stage == OpportunityStage.closed_won:
                await self._fire_trigger("deal_closed_won", "opportunity", opp.id, base_data)
            elif new_stage == OpportunityStage.closed_lost:
                await self._fire_trigger("deal_closed_lost", "opportunity", opp.id, base_data)

        return opp

    async def delete(
        self,
        opp_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> bool:
        opp = await self.get(opp_id)
        if opp is None:
            return False

        old_values = _model_to_dict(opp)
        opp.deleted_at = datetime.now(timezone.utc)

        await self._audit.log(
            table_name="opportunities",
            record_id=opp.id,
            operation="DELETE",
            old_values=old_values,
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        logger.info("opportunity_soft_deleted", opp_id=str(opp_id))
        return True

    async def _fire_trigger(
        self,
        trigger_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        trigger_data: dict,
    ) -> None:
        try:
            from app.services.workflow.engine import workflow_engine
            from app.services.workflow.triggers import TriggerType as TT
            await workflow_engine.fire(
                trigger_type=TT(trigger_type),
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_data=trigger_data,
                db=self.db,
            )
            await self.db.commit()
        except Exception as exc:
            logger.warning("workflow_trigger_failed", trigger_type=trigger_type, error=str(exc))

    async def get_pipeline_summary(self) -> dict:
        """Return stage distribution and total ARR per stage."""
        result = await self.db.execute(
            select(Opportunity.stage, func.count().label("count"), func.sum(Opportunity.arr_value).label("total_arr"))
            .where(Opportunity.deleted_at.is_(None))
            .group_by(Opportunity.stage)
        )
        rows = result.all()
        summary = {}
        for row in rows:
            summary[row.stage] = {
                "count": row.count,
                "total_arr": float(row.total_arr or 0),
            }
        return summary
