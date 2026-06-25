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
from app.services.partner import PartnerService
from app.services.scoring import compute_icp_score, tier_from_score

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("", response_model=PaginatedResponse[PartnerReadWithAccount])
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
) -> PaginatedResponse[PartnerReadWithAccount]:
    service = PartnerService(db)
    partners, total = await service.list(
        page=page,
        page_size=page_size,
        type_filter=type,
        tier_filter=tier,
        status_filter=status,
        geography_filter=geography,
        min_score=min_score,
        load_account=True,
    )
    return PaginatedResponse(
        items=[PartnerReadWithAccount.model_validate(p) for p in partners],
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
    from app.services.scoring import engine as scoring_engine

    service = PartnerService(db)
    weights = await scoring_engine.load_active_weights(db)
    result = await service.recalculate_score(partner_id, weights=weights)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")

    partner = await service.get(partner_id, load_account=True)
    account = partner.account if hasattr(partner, "account") else None
    score, breakdown = scoring_engine.score(partner, account, weights)
    tier = scoring_engine.tier(score)
    return ScoreBreakdown(total=score, tier=tier, dimensions=breakdown)


@router.get("/{partner_id}/onboarding")
async def get_partner_onboarding(
    partner_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Return all active onboarding steps with completion status for this partner."""
    from sqlalchemy import select, or_
    from app.models.settings import OnboardingStep, PartnerOnboardingProgress
    from app.models.partner import Partner

    # Verify partner exists
    service = PartnerService(db)
    partner = await service.get(partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Load active steps (all types + partner-specific)
    steps_result = await db.execute(
        select(OnboardingStep)
        .where(
            OnboardingStep.is_active.is_(True),
            or_(OnboardingStep.partner_type == partner.type, OnboardingStep.partner_type.is_(None)),
        )
        .order_by(OnboardingStep.position)
    )
    steps = steps_result.scalars().all()

    # Load completions for this partner
    completions_result = await db.execute(
        select(PartnerOnboardingProgress).where(
            PartnerOnboardingProgress.partner_id == partner_id
        )
    )
    completions = {str(c.step_id): c for c in completions_result.scalars().all()}

    items = []
    for step in steps:
        completion = completions.get(str(step.id))
        items.append({
            "step_id": str(step.id),
            "name": step.name,
            "description": step.description,
            "partner_type": step.partner_type,
            "position": step.position,
            "is_required": step.is_required,
            "completed": completion is not None and completion.completed_at is not None,
            "completed_at": completion.completed_at.isoformat() if completion and completion.completed_at else None,
            "completed_by": completion.completed_by if completion else None,
        })

    completed_count = sum(1 for i in items if i["completed"])
    return {
        "partner_id": str(partner_id),
        "steps": items,
        "total": len(items),
        "completed": completed_count,
        "progress_pct": round(completed_count / len(items) * 100) if items else 0,
    }


@router.post("/{partner_id}/onboarding/{step_id}")
async def complete_onboarding_step(
    partner_id: uuid.UUID,
    step_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Mark an onboarding step as completed for this partner."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.settings import PartnerOnboardingProgress

    service = PartnerService(db)
    if await service.get(partner_id) is None:
        raise HTTPException(status_code=404, detail="Partner not found")

    result = await db.execute(
        select(PartnerOnboardingProgress).where(
            PartnerOnboardingProgress.partner_id == partner_id,
            PartnerOnboardingProgress.step_id == step_id,
        )
    )
    progress = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if progress:
        progress.completed_at = now
        progress.completed_by = current_user.email
    else:
        db.add(PartnerOnboardingProgress(
            partner_id=partner_id,
            step_id=step_id,
            completed_at=now,
            completed_by=current_user.email,
        ))

    await db.commit()
    return {"status": "completed", "step_id": str(step_id)}


@router.delete("/{partner_id}/onboarding/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uncomplete_onboarding_step(
    partner_id: uuid.UUID,
    step_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Unmark a completed onboarding step."""
    from sqlalchemy import select
    from app.models.settings import PartnerOnboardingProgress

    result = await db.execute(
        select(PartnerOnboardingProgress).where(
            PartnerOnboardingProgress.partner_id == partner_id,
            PartnerOnboardingProgress.step_id == step_id,
        )
    )
    progress = result.scalar_one_or_none()
    if progress:
        progress.completed_at = None
        progress.completed_by = None
        await db.commit()


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
