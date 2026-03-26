import uuid
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import Field

from app.models.revenue import RevenueType
from app.schemas.common import BaseSchema


class RevenueCreate(BaseSchema):
    partner_id: Optional[uuid.UUID] = None
    opportunity_id: Optional[uuid.UUID] = None
    arr: float = Field(gt=0)
    mrr: Optional[float] = None  # auto-computed as arr/12 if not provided
    date_closed: date
    type: RevenueType = RevenueType.new
    attribution: Optional[str] = None
    currency: str = Field(default="EUR", max_length=10)


class RevenueRead(BaseSchema):
    id: uuid.UUID
    partner_id: Optional[uuid.UUID] = None
    opportunity_id: Optional[uuid.UUID] = None
    arr: float
    mrr: float
    date_closed: date
    type: str
    attribution: Optional[str] = None
    currency: str
    created_at: datetime
    updated_at: datetime


class MonthlyTrend(BaseSchema):
    month: str   # "YYYY-MM"
    arr: float
    mrr: float
    count: int


class PartnerRevenueBreakdown(BaseSchema):
    partner_id: Optional[uuid.UUID] = None
    account_name: str
    arr: float
    count: int


class RevenueSummary(BaseSchema):
    total_arr: float
    total_mrr: float
    record_count: int
    arr_by_type: Dict[str, float]
    arr_by_currency: Dict[str, float]
    monthly_trends: List[MonthlyTrend]
