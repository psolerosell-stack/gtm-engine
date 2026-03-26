import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.common import BaseSchema


class OverviewKPIs(BaseSchema):
    total_partners: int
    active_partners: int
    total_arr: float
    arr_last_30d: float
    open_pipeline_arr: float
    open_deals: int
    leads_this_month: int
    avg_icp_score: float


class FunnelStage(BaseSchema):
    stage: str
    count: int
    arr: float


class PartnerPerformance(BaseSchema):
    partner_id: uuid.UUID
    partner_name: str
    tier: str
    icp_score: float
    total_arr: float
    opportunity_count: int
    active_opportunities: int


class MonthlyARR(BaseSchema):
    month: str   # "YYYY-MM"
    arr: float
    mrr: float
    count: int


class BriefingRead(BaseSchema):
    id: uuid.UUID
    date: str
    content: str        # raw JSON string — frontend parses
    generated_at: datetime
    posted_to_slack: bool
