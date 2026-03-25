import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.partner import Partner, PartnerTier, ScoreHistory
from app.models.account import Account
from app.schemas.partner import PartnerCreate, PartnerUpdate, ScoreBreakdown
from app.services.audit import AuditService, _model_to_dict

logger = structlog.get_logger(__name__)

# ── Scoring weights (Layer 2 — can be replaced by ScoringWeightVersion) ─────

DEFAULT_WEIGHTS: Dict[str, float] = {
    "erp_ecosystem_fit": 0.20,
    "partner_type_match": 0.15,
    "capacity_score": 0.15,
    "geography_match": 0.10,
    "vertical_fit": 0.10,
    "company_size": 0.10,
    "arr_potential": 0.10,
    "activation_velocity": 0.10,
}

ERP_SCORES: Dict[str, float] = {
    "business_central": 10,
    "navision": 10,
    "sage_200": 9,
    "sage_x3": 9,
    "sap_b1": 8,
    "netsuite": 8,
    "holded": 7,
    "other": 5,
}

PARTNER_TYPE_SCORES: Dict[str, float] = {
    "OEM": 10,
    "VAR+": 9,
    "VAR": 8,
    "Referral": 6,
    "Alliance": 7,
}

GEOGRAPHY_SCORES: Dict[str, float] = {
    "spain": 10,
    "españa": 10,
}
LATAM_COUNTRIES = {"mexico", "colombia", "argentina", "chile", "peru", "latam"}

VERTICAL_SCORES: Dict[str, float] = {
    "manufacturing": 10,
    "distribution": 10,
    "wholesale": 9,
    "logistics": 8,
    "services": 7,
}


def compute_icp_score(
    partner: Partner,
    account: Optional[Account],
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute weighted ICP score (0–100) for a partner.
    Returns (score, breakdown_dict).
    """
    w = weights or DEFAULT_WEIGHTS
    breakdown: Dict[str, Any] = {}

    # 1. ERP ecosystem fit
    erp_raw = 5.0
    erp_label = "unknown"
    if account and account.erp_ecosystem:
        key = account.erp_ecosystem.lower().replace(" ", "_").replace("-", "_")
        erp_raw = ERP_SCORES.get(key, 5.0)
        erp_label = account.erp_ecosystem
    breakdown["erp_ecosystem_fit"] = {
        "weight": w["erp_ecosystem_fit"],
        "raw": erp_raw,
        "weighted": round(erp_raw * w["erp_ecosystem_fit"], 4),
        "label": erp_label,
    }

    # 2. Partner type match
    type_raw = PARTNER_TYPE_SCORES.get(partner.type, 5.0)
    breakdown["partner_type_match"] = {
        "weight": w["partner_type_match"],
        "raw": type_raw,
        "weighted": round(type_raw * w["partner_type_match"], 4),
        "label": partner.type,
    }

    # 3. Capacity score (sum of four dimensions, each 0–2.5 → max 10)
    capacity_sum = (
        partner.capacity_commercial
        + partner.capacity_functional
        + partner.capacity_technical
        + partner.capacity_integration
    )
    capacity_raw = min(capacity_sum, 10.0)
    breakdown["capacity_score"] = {
        "weight": w["capacity_score"],
        "raw": round(capacity_raw, 2),
        "weighted": round(capacity_raw * w["capacity_score"], 4),
        "label": f"commercial={partner.capacity_commercial} functional={partner.capacity_functional} "
                 f"technical={partner.capacity_technical} integration={partner.capacity_integration}",
    }

    # 4. Geography match
    geo_raw = 5.0
    geo_label = partner.geography or "unknown"
    if partner.geography:
        geo_lower = partner.geography.lower()
        if geo_lower in ("spain", "españa", "es"):
            geo_raw = 10.0
        elif geo_lower in LATAM_COUNTRIES or "latam" in geo_lower:
            geo_raw = 7.0
        else:
            geo_raw = 5.0
    breakdown["geography_match"] = {
        "weight": w["geography_match"],
        "raw": geo_raw,
        "weighted": round(geo_raw * w["geography_match"], 4),
        "label": geo_label,
    }

    # 5. Vertical fit
    vert_raw = 5.0
    vert_label = partner.vertical or "unknown"
    if partner.vertical:
        vert_lower = partner.vertical.lower()
        vert_raw = next(
            (v for k, v in VERTICAL_SCORES.items() if k in vert_lower),
            5.0,
        )
    breakdown["vertical_fit"] = {
        "weight": w["vertical_fit"],
        "raw": vert_raw,
        "weighted": round(vert_raw * w["vertical_fit"], 4),
        "label": vert_label,
    }

    # 6. Company size
    size_raw = 5.0
    size_label = "unknown"
    if account and account.size:
        size = account.size
        size_label = str(size)
        if 10 <= size <= 50:
            size_raw = 10.0
        elif 5 <= size < 10:
            size_raw = 8.0
        else:
            size_raw = 6.0
    breakdown["company_size"] = {
        "weight": w["company_size"],
        "raw": size_raw,
        "weighted": round(size_raw * w["company_size"], 4),
        "label": size_label,
    }

    # 7. ARR potential
    arr_raw = 4.0
    arr_label = "unknown"
    if partner.arr_potential is not None:
        arr_label = f"{partner.arr_potential:.0f}"
        if partner.arr_potential >= 50000:
            arr_raw = 10.0
        elif partner.arr_potential >= 20000:
            arr_raw = 7.0
        else:
            arr_raw = 4.0
    breakdown["arr_potential"] = {
        "weight": w["arr_potential"],
        "raw": arr_raw,
        "weighted": round(arr_raw * w["arr_potential"], 4),
        "label": arr_label,
    }

    # 8. Activation velocity
    vel_raw = 4.0
    vel_label = "unknown"
    if partner.activation_velocity is not None:
        vel_label = f"{partner.activation_velocity} days"
        if partner.activation_velocity < 30:
            vel_raw = 10.0
        elif partner.activation_velocity <= 90:
            vel_raw = 7.0
        else:
            vel_raw = 4.0
    breakdown["activation_velocity"] = {
        "weight": w["activation_velocity"],
        "raw": vel_raw,
        "weighted": round(vel_raw * w["activation_velocity"], 4),
        "label": vel_label,
    }

    # Total (sum of weighted values × 10 to normalise to 0–100)
    total = sum(dim["weighted"] for dim in breakdown.values()) * 10
    total = min(round(total, 2), 100.0)

    return total, breakdown


def tier_from_score(score: float) -> str:
    if score >= 85:
        return PartnerTier.platinum
    if score >= 70:
        return PartnerTier.gold
    if score >= 50:
        return PartnerTier.silver
    return PartnerTier.bronze


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
        score, breakdown = compute_icp_score(partner, account)
        partner.icp_score = score
        partner.tier = tier_from_score(score)

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
        score, breakdown = compute_icp_score(partner, account)
        partner.icp_score = score
        partner.tier = tier_from_score(score)

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

    async def recalculate_score(self, partner_id: uuid.UUID) -> Optional[Tuple[float, str]]:
        """Force recalculate score. Returns (score, tier) or None if not found."""
        partner = await self.get(partner_id)
        if partner is None:
            return None
        account = await self._get_account(partner.account_id)
        score, breakdown = compute_icp_score(partner, account)
        partner.icp_score = score
        partner.tier = tier_from_score(score)
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
