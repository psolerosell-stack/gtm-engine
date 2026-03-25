"""
Scoring Weight Versioning API — Layer 2.

Endpoints:
  GET    /api/v1/scoring/weights           — list all weight versions
  POST   /api/v1/scoring/weights           — create a new version
  GET    /api/v1/scoring/weights/active    — get currently active version
  GET    /api/v1/scoring/weights/{id}      — get a specific version
  POST   /api/v1/scoring/weights/{id}/activate — activate a version
"""
import json
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from app.dependencies import CurrentUser, DBSession, ManagerUser
from app.models.analytics import ScoringWeightVersion
from app.schemas.account import ScoringWeightVersionCreate, ScoringWeightVersionRead
from app.services.scoring import DEFAULT_WEIGHTS

router = APIRouter(prefix="/scoring", tags=["scoring"])


async def _get_next_version(db) -> int:
    from sqlalchemy import func
    result = await db.execute(
        select(func.max(ScoringWeightVersion.version))
    )
    current_max = result.scalar_one_or_none()
    return (current_max or 0) + 1


@router.get("/weights", response_model=list[ScoringWeightVersionRead])
async def list_weight_versions(
    db: DBSession,
    current_user: CurrentUser,
) -> list[ScoringWeightVersionRead]:
    result = await db.execute(
        select(ScoringWeightVersion).order_by(ScoringWeightVersion.version.desc())
    )
    versions = list(result.scalars().all())
    return [
        ScoringWeightVersionRead(
            id=v.id,
            version=v.version,
            weights=json.loads(v.weights),
            rationale=v.rationale,
            is_active=v.is_active,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/weights/active", response_model=ScoringWeightVersionRead | None)
async def get_active_weight_version(
    db: DBSession,
    current_user: CurrentUser,
) -> ScoringWeightVersionRead | None:
    result = await db.execute(
        select(ScoringWeightVersion)
        .where(ScoringWeightVersion.is_active.is_(True))
        .order_by(ScoringWeightVersion.version.desc())
        .limit(1)
    )
    version = result.scalar_one_or_none()
    if version is None:
        return None
    return ScoringWeightVersionRead(
        id=version.id,
        version=version.version,
        weights=json.loads(version.weights),
        rationale=version.rationale,
        is_active=version.is_active,
        created_at=version.created_at,
    )


@router.post("/weights", response_model=ScoringWeightVersionRead, status_code=status.HTTP_201_CREATED)
async def create_weight_version(
    body: ScoringWeightVersionCreate,
    db: DBSession,
    current_user: ManagerUser,
) -> ScoringWeightVersionRead:
    next_version = await _get_next_version(db)

    # If activating, deactivate all existing active versions first
    if body.activate:
        await db.execute(
            update(ScoringWeightVersion)
            .where(ScoringWeightVersion.is_active.is_(True))
            .values(is_active=False)
        )

    version = ScoringWeightVersion(
        version=next_version,
        weights=json.dumps(body.weights),
        rationale=body.rationale,
        is_active=body.activate,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    return ScoringWeightVersionRead(
        id=version.id,
        version=version.version,
        weights=json.loads(version.weights),
        rationale=version.rationale,
        is_active=version.is_active,
        created_at=version.created_at,
    )


@router.get("/weights/{version_id}", response_model=ScoringWeightVersionRead)
async def get_weight_version(
    version_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> ScoringWeightVersionRead:
    result = await db.execute(
        select(ScoringWeightVersion).where(ScoringWeightVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weight version not found")
    return ScoringWeightVersionRead(
        id=version.id,
        version=version.version,
        weights=json.loads(version.weights),
        rationale=version.rationale,
        is_active=version.is_active,
        created_at=version.created_at,
    )


@router.post("/weights/{version_id}/activate", response_model=ScoringWeightVersionRead)
async def activate_weight_version(
    version_id: uuid.UUID,
    db: DBSession,
    current_user: ManagerUser,
) -> ScoringWeightVersionRead:
    result = await db.execute(
        select(ScoringWeightVersion).where(ScoringWeightVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weight version not found")

    # Deactivate all others, activate this one
    await db.execute(
        update(ScoringWeightVersion)
        .where(ScoringWeightVersion.is_active.is_(True))
        .values(is_active=False)
    )
    version.is_active = True
    await db.commit()
    await db.refresh(version)

    return ScoringWeightVersionRead(
        id=version.id,
        version=version.version,
        weights=json.loads(version.weights),
        rationale=version.rationale,
        is_active=version.is_active,
        created_at=version.created_at,
    )


@router.get("/weights/defaults/current", response_model=dict)
async def get_default_weights(current_user: CurrentUser) -> dict:
    """Return the hardcoded default weights (used when no active version exists)."""
    return DEFAULT_WEIGHTS
