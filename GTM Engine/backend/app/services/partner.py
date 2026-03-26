import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.partner import Partner, ScoreHistory
from app.models.account import Account
from app.schemas.partner import PartnerCreate, PartnerUpdate
from app.services.audit import AuditService, _model_to_dict
from app.services.scoring import engine as scoring_engine

logger = structlog.get_logger(__name__)


class PartnerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._audit = AuditService(db)

    async def _get_account(self, account_id: uuid.UUID) -> Optional[Account]:
        result = await self.db.execute(
            select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        data: PartnerCreate,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> Partner:
        account = await self._get_account(data.account_id)
        if account is None:
            raise ValueError(f"Account {data.account_id} not found")

        partner = Partner(**data.model_dump())
        weights = await scoring_engine.load_active_weights(self.db)
        score, breakdown = scoring_engine.score(partner, account, weights)
        partner.icp_score = score
        partner.tier = scoring_engine.tier(score)

        self.db.add(partner)
        await self.db.flush()  # get the ID before committing

        # Store initial score history
        history = ScoreHistory(
            partner_id=partner.id,
            score=score,
            tier=partner.tier,
            breakdown=json.dumps(breakdown, default=str),
            computed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(history)

        await self._audit.log(
            table_name="partners",
            record_id=partner.id,
            operation="INSERT",
            new_values=_model_to_dict(partner),
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        await self.db.refresh(partner)
        logger.info("partner_created", partner_id=str(partner.id), score=score, tier=partner.tier)

        await self._fire_trigger(
            "partner_created", "partner", partner.id,
            {"partner_id": str(partner.id), "score": score, "tier": partner.tier},
        )
        return partner

    async def get(self, partner_id: uuid.UUID, load_account: bool = False) -> Optional[Partner]:
        stmt = select(Partner).where(
            Partner.id == partner_id, Partner.deleted_at.is_(None)
        )
        if load_account:
            stmt = stmt.options(selectinload(Partner.account))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        type_filter: Optional[str] = None,
        tier_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        geography_filter: Optional[str] = None,
        min_score: Optional[float] = None,
        load_account: bool = False,
    ) -> Tuple[List[Partner], int]:
        stmt = select(Partner).where(Partner.deleted_at.is_(None))
        count_stmt = select(func.count()).select_from(Partner).where(Partner.deleted_at.is_(None))

        if type_filter:
            stmt = stmt.where(Partner.type == type_filter)
            count_stmt = count_stmt.where(Partner.type == type_filter)
        if tier_filter:
            stmt = stmt.where(Partner.tier == tier_filter)
            count_stmt = count_stmt.where(Partner.tier == tier_filter)
        if status_filter:
            stmt = stmt.where(Partner.status == status_filter)
            count_stmt = count_stmt.where(Partner.status == status_filter)
        if geography_filter:
            stmt = stmt.where(Partner.geography.ilike(f"%{geography_filter}%"))
            count_stmt = count_stmt.where(Partner.geography.ilike(f"%{geography_filter}%"))
        if min_score is not None:
            stmt = stmt.where(Partner.icp_score >= min_score)
            count_stmt = count_stmt.where(Partner.icp_score >= min_score)

        if load_account:
            stmt = stmt.options(selectinload(Partner.account))

        stmt = stmt.order_by(Partner.icp_score.desc()).offset((page - 1) * page_size).limit(page_size)

        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        result = await self.db.execute(stmt)
        partners = list(result.scalars().all())
        return partners, total

    async def update(
        self,
        partner_id: uuid.UUID,
        data: PartnerUpdate,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> Optional[Partner]:
        partner = await self.get(partner_id)
        if partner is None:
            return None

        old_values = _model_to_dict(partner)
        update_dict = data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(partner, field, value)

        partner.updated_at = datetime.now(timezone.utc)

        # Recalculate score after updates
        account = await self._get_account(partner.account_id)
        weights = await scoring_engine.load_active_weights(self.db)
        score, breakdown = scoring_engine.score(partner, account, weights)
        partner.icp_score = score
        partner.tier = scoring_engine.tier(score)

        history = ScoreHistory(
            partner_id=partner.id,
            score=score,
            tier=partner.tier,
            breakdown=json.dumps(breakdown, default=str),
            computed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(history)

        await self._audit.log(
            table_name="partners",
            record_id=partner.id,
            operation="UPDATE",
            old_values=old_values,
            new_values=_model_to_dict(partner),
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        await self.db.refresh(partner)
        logger.info("partner_updated", partner_id=str(partner_id), score=score, tier=partner.tier)

        old_score = float(old_values.get("icp_score") or 0)
        await self._fire_trigger(
            "score_threshold_reached", "partner", partner.id,
            {"score": score, "previous_score": old_score, "tier": partner.tier},
        )
        return partner

    async def delete(
        self,
        partner_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
    ) -> bool:
        partner = await self.get(partner_id)
        if partner is None:
            return False

        old_values = _model_to_dict(partner)
        partner.deleted_at = datetime.now(timezone.utc)

        await self._audit.log(
            table_name="partners",
            record_id=partner.id,
            operation="DELETE",
            old_values=old_values,
            user_id=user_id,
            user_email=user_email,
        )

        await self.db.commit()
        logger.info("partner_soft_deleted", partner_id=str(partner_id))
        return True

    async def _fire_trigger(
        self,
        trigger_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        trigger_data: dict,
    ) -> None:
        """Fire a workflow trigger — never raises; failures are logged and swallowed."""
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

    async def get_score_history(
        self, partner_id: uuid.UUID, limit: int = 50
    ) -> List[ScoreHistory]:
        result = await self.db.execute(
            select(ScoreHistory)
            .where(ScoreHistory.partner_id == partner_id)
            .order_by(ScoreHistory.computed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def recalculate_score(
        self,
        partner_id: uuid.UUID,
        weights: Optional[dict] = None,
    ) -> Optional[Tuple[float, str]]:
        """Force recalculate score. Returns (score, tier) or None if not found.

        Pass pre-loaded `weights` to skip a DB round-trip (useful for batch jobs).
        """
        partner = await self.get(partner_id)
        if partner is None:
            return None
        account = await self._get_account(partner.account_id)
        if weights is None:
            weights = await scoring_engine.load_active_weights(self.db)
        score, breakdown = scoring_engine.score(partner, account, weights)
        partner.icp_score = score
        partner.tier = scoring_engine.tier(score)
        partner.updated_at = datetime.now(timezone.utc)

        history = ScoreHistory(
            partner_id=partner.id,
            score=score,
            tier=partner.tier,
            breakdown=json.dumps(breakdown, default=str),
            computed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(history)
        await self.db.commit()
        return score, partner.tier
