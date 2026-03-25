import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from app.models.partner import PartnerStatus, PartnerTier, PartnerType
from app.schemas.common import BaseSchema


class CapacityFields(BaseSchema):
    capacity_commercial: float = Field(default=0.0, ge=0.0, le=2.5)
    capacity_functional: float = Field(default=0.0, ge=0.0, le=2.5)
    capacity_technical: float = Field(default=0.0, ge=0.0, le=2.5)
    capacity_integration: float = Field(default=0.0, ge=0.0, le=2.5)


class PartnerCreate(CapacityFields):
    account_id: uuid.UUID
    type: PartnerType
    status: PartnerStatus = PartnerStatus.prospect
    geography: Optional[str] = None
    vertical: Optional[str] = None
    arr_potential: Optional[float] = Field(default=None, ge=0)
    activation_velocity: Optional[int] = Field(default=None, ge=0)
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    rappel_structure: Optional[str] = None
    notes: Optional[str] = None


class PartnerUpdate(BaseSchema):
    type: Optional[PartnerType] = None
    status: Optional[PartnerStatus] = None
    tier: Optional[PartnerTier] = None
    capacity_commercial: Optional[float] = Field(default=None, ge=0.0, le=2.5)
    capacity_functional: Optional[float] = Field(default=None, ge=0.0, le=2.5)
    capacity_technical: Optional[float] = Field(default=None, ge=0.0, le=2.5)
    capacity_integration: Optional[float] = Field(default=None, ge=0.0, le=2.5)
    geography: Optional[str] = None
    vertical: Optional[str] = None
    arr_potential: Optional[float] = Field(default=None, ge=0)
    activation_velocity: Optional[int] = Field(default=None, ge=0)
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    rappel_structure: Optional[str] = None
    notes: Optional[str] = None
    fit_summary: Optional[str] = None
    approach_suggestion: Optional[str] = None


class PartnerRead(CapacityFields):
    id: uuid.UUID
    account_id: uuid.UUID
    type: str
    tier: str
    status: str
    geography: Optional[str] = None
    vertical: Optional[str] = None
    icp_score: float
    arr_potential: Optional[float] = None
    activation_velocity: Optional[int] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    rappel_structure: Optional[str] = None
    fit_summary: Optional[str] = None
    approach_suggestion: Optional[str] = None
    notes: Optional[str] = None
    hubspot_company_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AccountSummary(BaseSchema):
    id: uuid.UUID
    name: str
    industry: Optional[str] = None
    geography: Optional[str] = None
    erp_ecosystem: Optional[str] = None
    website: Optional[str] = None


class PartnerReadWithAccount(PartnerRead):
    account: Optional[AccountSummary] = None


class ScoreBreakdown(BaseSchema):
    total: float
    tier: str
    dimensions: Dict[str, Dict[str, Any]]
    # e.g. {"erp_ecosystem_fit": {"weight": 0.20, "raw": 9, "weighted": 1.8, "label": "Sage 200"}}


class ScoreHistoryRead(BaseSchema):
    id: uuid.UUID
    partner_id: uuid.UUID
    score: float
    tier: str
    breakdown: Dict[str, Any]
    computed_at: str
