import json
import math
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DBSession, ManagerUser
from app.schemas.common import PaginatedResponse
from app.schemas.partner import (
    PartnerCreate,
    PartnerRead,
    PartnerReadWithAccount,
    PartnerUpdate,
    ScoreBreakdown,
    ScoreHistoryRead,
)
from app.services.partner import PartnerService, compute_icp_score, tier_from_score

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("", response_model=PaginatedResponse[PartnerRead])
async def list_partners(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    type: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    geography: Optional[str] = Query(default=None),
    min_score: Optional[float] = Query(default=None, ge=0, le=100),
) -> PaginatedResponse[PartnerRead]:
    service = PartnerService(db)
    partners, total = await service.list(
        page=page,
        page_size=page_size,
        type_filter=type,
        tier_filter=tier,
        status_filter=status,
        geography_filter=geography,
        min_score=min_score,
        load_account=False,
    )
    return PaginatedResponse(
        items=[PartnerRead.model_validate(p) for p in partners],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=PartnerRead, status_code=status.HTTP_201_CREATED)
async def create_partner(
    data: PartnerCreate,
    current_user: ManagerUser,
    db: DBSession,
) -> PartnerRead:
    service = PartnerService(db)
    try:
        partner = await service.create(data, user_id=current_user.id, user_email=current_user.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return PartnerRead.model_validate(partner)


@router.get("/{partner_id}", response_model=PartnerReadWithAccount)
async def get_partner(
    partner_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> PartnerReadWithAccount:
    service = PartnerService(db)
    partner = await service.get(partner_id, load_account=True)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return PartnerReadWithAccount.model_validate(partner)


@router.put("/{partner_id}", response_model=PartnerRead)
async def update_partner(
    partner_id: uuid.UUID,
    data: PartnerUpdate,
    current_user: ManagerUser,
    db: DBSession,
) -> PartnerRead:
    service = PartnerService(db)
    partner = await service.update(
        partner_id, data, user_id=current_user.id, user_email=current_user.email
    )
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return PartnerRead.model_validate(partner)


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partner(
    partner_id: uuid.UUID,
    current_user: ManagerUser,
    db: DBSession,
) -> None:
    service = PartnerService(db)
    deleted = await service.delete(
        partner_id, user_id=current_user.id, user_email=current_user.email
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")


@router.get("/{partner_id}/score", response_model=ScoreBreakdown)
async def get_partner_score(
    partner_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ScoreBreakdown:
    """Return full ICP score breakdown with dimension-level explainability."""
    service = PartnerService(db)
    partner = await service.get(partner_id, load_account=True)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")

    account = partner.account if hasattr(partner, "account") else None
    score, breakdown = compute_icp_score(partner, account)
    tier = tier_from_score(score)
    return ScoreBreakdown(total=score, tier=tier, dimensions=breakdown)


@router.post("/{partner_id}/score/recalculate", response_model=ScoreBreakdown)
async def recalculate_partner_score(
    partner_id: uuid.UUID,
    current_user: ManagerUser,
    db: DBSession,
) -> ScoreBreakdown:
    """Force-recalculate and persist the ICP score."""
    service = PartnerService(db)
    result = await service.recalculate_score(partner_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")

    partner = await service.get(partner_id, load_account=True)
    account = partner.account if hasattr(partner, "account") else None
    score, breakdown = compute_icp_score(partner, account)
    tier = tier_from_score(score)
    return ScoreBreakdown(total=score, tier=tier, dimensions=breakdown)


@router.get("/{partner_id}/score/history", response_model=list[ScoreHistoryRead])
async def get_score_history(
    partner_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ScoreHistoryRead]:
    service = PartnerService(db)
    history = await service.get_score_history(partner_id, limit=limit)
    results = []
    for h in history:
        breakdown_dict = json.loads(h.breakdown) if h.breakdown else {}
        results.append(
            ScoreHistoryRead(
                id=h.id,
                partner_id=h.partner_id,
                score=h.score,
                tier=h.tier,
                breakdown=breakdown_dict,
                computed_at=h.computed_at,
            )
        )
    return results
