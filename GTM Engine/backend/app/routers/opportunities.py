import math
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DBSession, ManagerUser
from app.schemas.common import PaginatedResponse
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityRead,
    OpportunityReadWithRelations,
    OpportunityUpdate,
)
from app.services.opportunity import OpportunityService

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=PaginatedResponse[OpportunityRead])
async def list_opportunities(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    stage: Optional[str] = Query(default=None),
    partner_id: Optional[uuid.UUID] = Query(default=None),
    account_id: Optional[uuid.UUID] = Query(default=None),
    owner: Optional[str] = Query(default=None),
) -> PaginatedResponse[OpportunityRead]:
    service = OpportunityService(db)
    opps, total = await service.list(
        page=page,
        page_size=page_size,
        stage_filter=stage,
        partner_id_filter=partner_id,
        account_id_filter=account_id,
        owner_filter=owner,
    )
    return PaginatedResponse(
        items=[OpportunityRead.model_validate(o) for o in opps],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=OpportunityRead, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    data: OpportunityCreate,
    current_user: ManagerUser,
    db: DBSession,
) -> OpportunityRead:
    service = OpportunityService(db)
    try:
        opp = await service.create(data, user_id=current_user.id, user_email=current_user.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return OpportunityRead.model_validate(opp)


@router.get("/pipeline/summary")
async def pipeline_summary(
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """Stage-by-stage count and total ARR — used by Pipeline Review view."""
    service = OpportunityService(db)
    return await service.get_pipeline_summary()


@router.get("/{opp_id}", response_model=OpportunityReadWithRelations)
async def get_opportunity(
    opp_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> OpportunityReadWithRelations:
    service = OpportunityService(db)
    opp = await service.get(opp_id, load_relations=True)
    if opp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return OpportunityReadWithRelations.model_validate(opp)


@router.put("/{opp_id}", response_model=OpportunityRead)
async def update_opportunity(
    opp_id: uuid.UUID,
    data: OpportunityUpdate,
    current_user: ManagerUser,
    db: DBSession,
) -> OpportunityRead:
    service = OpportunityService(db)
    opp = await service.update(opp_id, data, user_id=current_user.id, user_email=current_user.email)
    if opp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return OpportunityRead.model_validate(opp)


@router.delete("/{opp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opp_id: uuid.UUID,
    current_user: ManagerUser,
    db: DBSession,
) -> None:
    service = OpportunityService(db)
    deleted = await service.delete(opp_id, user_id=current_user.id, user_email=current_user.email)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")


@router.post("/{opp_id}/enrich")
async def enrich_opportunity(
    opp_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    AI-enrich an opportunity: generates a deal summary, fit analysis, signals,
    and suggested next action using Claude.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.opportunity import Opportunity
    from app.models.account import Account
    from app.models.partner import Partner
    from app.services.ai import AIService, AIServiceUnavailableError
    import json

    # Load opp with relations
    result = await db.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.account), selectinload(Opportunity.partner))
        .where(Opportunity.id == opp_id, Opportunity.deleted_at.is_(None))
    )
    opp = result.scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    account = opp.account if hasattr(opp, "account") else None
    partner = opp.partner if hasattr(opp, "partner") else None

    # Load partner account if needed
    partner_account = None
    if partner:
        pa_result = await db.execute(select(Account).where(Account.id == partner.account_id))
        partner_account = pa_result.scalar_one_or_none()

    # Build context
    context_parts = [
        f"Deal: {opp.name}",
        f"Stage: {opp.stage}",
        f"ARR: {opp.arr_value or 'unknown'}",
        f"Close date: {opp.close_date or 'unknown'}",
        f"Owner: {opp.owner or 'unassigned'}",
    ]
    if account:
        context_parts.append(f"Account: {account.name} ({account.industry or 'unknown industry'}, {account.geography or 'unknown geo'})")
        if account.erp_ecosystem:
            context_parts.append(f"ERP ecosystem: {account.erp_ecosystem}")
    if partner and partner_account:
        context_parts.append(f"Partner: {partner_account.name} ({partner.type}, tier {partner.tier}, ICP score {partner.icp_score:.0f})")
    if opp.notes:
        context_parts.append(f"Notes: {opp.notes}")

    context = "\n".join(context_parts)

    prompt = f"""Analyze this sales opportunity and return a JSON object with exactly these fields:
- summary: 2-3 sentence deal summary (what, who, why it matters)
- fit_analysis: 1-2 sentences on how well this opportunity fits our ideal customer profile
- signals: array of 2-4 short strings identifying positive or negative signals
- next_action: one specific, actionable next step to advance the deal

Opportunity context:
{context}

Return only valid JSON, no markdown fences."""

    try:
        svc = AIService(db)
        response_text = await svc._call_claude(
            prompt=prompt,
            purpose="opportunity_enrichment",
            entity_type="opportunity",
            entity_id=opp_id,
        )
        try:
            enrichment = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # Try to extract JSON
            import re
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            enrichment = json.loads(match.group()) if match else {"summary": response_text}

        # Persist summary to notes if empty
        if enrichment.get("summary") and not opp.notes:
            opp.notes = enrichment["summary"]
            await db.commit()

        return {"status": "enriched", "enrichment": enrichment}

    except AIServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI enrichment failed: {exc}")
