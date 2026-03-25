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
