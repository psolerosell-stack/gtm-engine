"""
Activities router — Layer 5.

Endpoints:
  GET  /activities          List activities (filterable by entity_type + entity_id)
  POST /activities          Create an activity (log a call, note, task, etc.)
  GET  /activities/{id}     Get a single activity
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession, ManagerUser
from app.models.activity import Activity
from app.schemas.activity import ActivityCreate, ActivityRead

router = APIRouter(tags=["activities"])


@router.get("/activities", response_model=List[ActivityRead])
async def list_activities(
    db: DBSession,
    _current_user: CurrentUser,
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[UUID] = Query(default=None),
    activity_type: Optional[str] = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[ActivityRead]:
    stmt = (
        select(Activity)
        .order_by(Activity.date.desc())
        .limit(limit)
        .offset(offset)
    )
    if entity_type:
        stmt = stmt.where(Activity.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(Activity.entity_id == entity_id)
    if activity_type:
        stmt = stmt.where(Activity.type == activity_type)

    result = await db.execute(stmt)
    return [ActivityRead.model_validate(a) for a in result.scalars().all()]


@router.post("/activities", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
async def create_activity(
    body: ActivityCreate,
    db: DBSession,
    current_user: ManagerUser,
) -> ActivityRead:
    activity = Activity(
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        type=body.type,
        date=body.date,
        owner=body.owner or current_user.email,
        notes=body.notes,
        outcome=body.outcome,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return ActivityRead.model_validate(activity)


@router.get("/activities/{activity_id}", response_model=ActivityRead)
async def get_activity(
    activity_id: UUID,
    db: DBSession,
    _current_user: CurrentUser,
) -> ActivityRead:
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityRead.model_validate(activity)
