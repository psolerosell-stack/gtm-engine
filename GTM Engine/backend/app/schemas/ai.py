from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── Enrichment ────────────────────────────────────────────────────────────────

class EnrichRequest(BaseSchema):
    """Trigger AI enrichment for an account."""
    force: bool = Field(
        default=False,
        description="Re-enrich even if status is already 'done'",
    )


class EnrichmentStatusResponse(BaseSchema):
    account_id: UUID
    enrichment_status: str  # pending / running / done / failed
    enrichment_data: Optional[Dict[str, Any]] = None
    fit_summary: Optional[str] = None
    queued: bool = False


# ── Partner Intelligence ──────────────────────────────────────────────────────

class IntelligenceRequest(BaseSchema):
    """Trigger AI fit summary + approach suggestion for a partner."""
    force: bool = Field(
        default=False,
        description="Regenerate even if fit_summary already exists",
    )


class IntelligenceResponse(BaseSchema):
    partner_id: UUID
    fit_summary: Optional[str] = None
    approach_suggestion: Optional[str] = None
    queued: bool = False


# ── Signal Detection ──────────────────────────────────────────────────────────

class SignalItem(BaseSchema):
    type: str
    description: str
    confidence: float
    action_recommended: Optional[str] = None


class SignalsResponse(BaseSchema):
    account_id: UUID
    signals: List[SignalItem]


# ── Discovery ─────────────────────────────────────────────────────────────────

class DiscoverRequest(BaseSchema):
    profile: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Natural language description of the ideal partner profile",
    )
    count: int = Field(default=15, ge=5, le=30)


class DiscoveredCompany(BaseSchema):
    name: str
    country: Optional[str] = None
    erp_ecosystem: Optional[str] = None
    company_type: Optional[str] = None
    reasoning: str
    fit_score_estimate: Optional[int] = None
    website_hint: Optional[str] = None


class DiscoverResponse(BaseSchema):
    profile: str
    count_requested: int
    companies: List[DiscoveredCompany]


# ── Usage Stats ───────────────────────────────────────────────────────────────

class UsagePurposeBreakdown(BaseSchema):
    purpose: str
    calls: int
    tokens: int
    cost_usd: float


class UsageStatsResponse(BaseSchema):
    period_days: int
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    failed_calls: int
    by_purpose: List[UsagePurposeBreakdown]


# ── AI Call Log ───────────────────────────────────────────────────────────────

class AICallLogRead(BaseSchema):
    id: UUID
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    purpose: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    success: bool
    error: Optional[str] = None
    created_at: datetime
