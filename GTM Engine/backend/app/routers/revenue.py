"""
Revenue router — Layer 6.

Endpoints for CRUD on Revenue records and aggregated reporting.
Route ordering: /summary and /trends MUST appear before /{revenue_id}
to prevent FastAPI matching string literals as UUID path params.
"""
import math
import uuid
from collections import defaultdict
from datetime import date as _date, timedelta
from typing import List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import AdminUser, CurrentUser, DBSession, ManagerUser
from app.models.account import Account
from app.models.partner import Partner
from app.models.revenue import Revenue
from app.schemas.common import PaginatedResponse
from app.schemas.revenue import (
    MonthlyTrend,
    PartnerRevenueBreakdown,
    RevenueCreate,
    RevenueRead,
    RevenueSummary,
)
from app.services.audit import AuditService, _model_to_dict

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/revenue", tags=["revenue"])


# ── Summary (must be before /{revenue_id}) ────────────────────────────────────

@router.get("/summary", response_model=RevenueSummary)
async def get_revenue_summary(
    current_user: CurrentUser,
    db: DBSession,
) -> RevenueSummary:
    """Aggregated ARR/MRR stats with breakdowns."""
    # Totals
    totals_res = await db.execute(
        select(
            func.coalesce(func.sum(Revenue.arr), 0.0),
            func.coalesce(func.sum(Revenue.mrr), 0.0),
            func.count(Revenue.id),
        ).where(Revenue.deleted_at.is_(None))
    )
    row = totals_res.one()
    total_arr, total_mrr, record_count = float(row[0]), float(row[1]), int(row[2])

    # By type
    by_type_res = await db.execute(
        select(Revenue.type, func.sum(Revenue.arr))
        .where(Revenue.deleted_at.is_(None))
        .group_by(Revenue.type)
    )
    arr_by_type: dict = {}
    for r in by_type_res.all():
        arr_by_type[r[0]] = float(r[1] or 0.0)

    # By currency
    by_cur_res = await db.execute(
        select(Revenue.currency, func.sum(Revenue.arr))
        .where(Revenue.deleted_at.is_(None))
        .group_by(Revenue.currency)
    )
    arr_by_currency: dict = {}
    for r in by_cur_res.all():
        arr_by_currency[r[0]] = float(r[1] or 0.0)

    # Monthly trends (12 months, Python-side aggregation)
    cutoff = _date.today() - timedelta(days=366)
    trend_res = await db.execute(
        select(Revenue.date_closed, Revenue.arr, Revenue.mrr)
        .where(Revenue.deleted_at.is_(None), Revenue.date_closed >= cutoff)
        .order_by(Revenue.date_closed)
    )
    monthly: dict = defaultdict(lambda: {"arr": 0.0, "mrr": 0.0, "count": 0})
    for r in trend_res.all():
        key = r.date_closed.strftime("%Y-%m")
        monthly[key]["arr"] += r.arr
        monthly[key]["mrr"] += r.mrr
        monthly[key]["count"] += 1

    monthly_trends = [
        MonthlyTrend(month=k, arr=v["arr"], mrr=v["mrr"], count=v["count"])
        for k, v in sorted(monthly.items())
    ]

    return RevenueSummary(
        total_arr=total_arr,
        total_mrr=total_mrr,
        record_count=record_count,
        arr_by_type=arr_by_type,
        arr_by_currency=arr_by_currency,
        monthly_trends=monthly_trends,
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[RevenueRead])
async def list_revenue(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    partner_id: Optional[uuid.UUID] = Query(default=None),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    date_from: Optional[_date] = Query(default=None),
    date_to: Optional[_date] = Query(default=None),
) -> PaginatedResponse[RevenueRead]:
    filters = [Revenue.deleted_at.is_(None)]
    if partner_id:
        filters.append(Revenue.partner_id == partner_id)
    if type_filter:
        filters.append(Revenue.type == type_filter)
    if date_from:
        filters.append(Revenue.date_closed >= date_from)
    if date_to:
        filters.append(Revenue.date_closed <= date_to)

    total_res = await db.execute(select(func.count(Revenue.id)).where(*filters))
    total = total_res.scalar_one()

    items_res = await db.execute(
        select(Revenue)
        .where(*filters)
        .order_by(Revenue.date_closed.desc(), Revenue.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = items_res.scalars().all()

    return PaginatedResponse(
        items=[RevenueRead.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=RevenueRead, status_code=status.HTTP_201_CREATED)
async def create_revenue(
    data: RevenueCreate,
    current_user: ManagerUser,
    db: DBSession,
) -> RevenueRead:
    if data.partner_id:
        exists = await db.execute(
            select(Partner.id).where(
                Partner.id == data.partner_id, Partner.deleted_at.is_(None)
            )
        )
        if exists.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Partner {data.partner_id} not found",
            )

    mrr = data.mrr if data.mrr is not None else round(data.arr / 12, 4)
    record = Revenue(
        partner_id=data.partner_id,
        opportunity_id=data.opportunity_id,
        arr=data.arr,
        mrr=mrr,
        date_closed=data.date_closed,
        type=data.type.value,
        attribution=data.attribution,
        currency=data.currency,
    )
    db.add(record)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        table_name="revenue",
        record_id=record.id,
        operation="INSERT",
        new_values=_model_to_dict(record),
        user_id=current_user.id,
        user_email=current_user.email,
    )
    await db.commit()

    logger.info(
        "revenue_created",
        revenue_id=str(record.id),
        arr=record.arr,
        user=current_user.email,
    )
    await db.refresh(record)
    return RevenueRead.model_validate(record)


# ── Get by ID (after static routes) ──────────────────────────────────────────

@router.get("/{revenue_id}", response_model=RevenueRead)
async def get_revenue(
    revenue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> RevenueRead:
    result = await db.execute(
        select(Revenue).where(
            Revenue.id == revenue_id, Revenue.deleted_at.is_(None)
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revenue record not found")
    return RevenueRead.model_validate(record)


# ── Delete (admin only) ────────────────────────────────────────────────────────

@router.delete("/{revenue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_revenue(
    revenue_id: uuid.UUID,
    current_user: AdminUser,
    db: DBSession,
) -> None:
    from datetime import datetime, timezone

    result = await db.execute(
        select(Revenue).where(
            Revenue.id == revenue_id, Revenue.deleted_at.is_(None)
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revenue record not found")

    record.deleted_at = datetime.now(timezone.utc)

    audit = AuditService(db)
    await audit.log(
        table_name="revenue",
        record_id=record.id,
        operation="DELETE",
        old_values=_model_to_dict(record),
        user_id=current_user.id,
        user_email=current_user.email,
    )
    await db.commit()
    logger.info("revenue_deleted", revenue_id=str(revenue_id), user=current_user.email)
