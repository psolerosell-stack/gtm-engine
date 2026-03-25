import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import Field

from app.models.opportunity import Currency, OpportunityStage
from app.schemas.common import BaseSchema
from app.schemas.partner import AccountSummary


class OpportunityCreate(BaseSchema):
    account_id: uuid.UUID
    partner_id: Optional[uuid.UUID] = None
    name: str = Field(min_length=1, max_length=255)
    stage: OpportunityStage = OpportunityStage.prospecting
    arr_value: Optional[float] = Field(default=None, ge=0)
    currency: Currency = Currency.eur
    close_date: Optional[date] = None
    owner: Optional[str] = None
    notes: Optional[str] = None


class OpportunityUpdate(BaseSchema):
    partner_id: Optional[uuid.UUID] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    stage: Optional[OpportunityStage] = None
    arr_value: Optional[float] = Field(default=None, ge=0)
    currency: Optional[Currency] = None
    close_date: Optional[date] = None
    owner: Optional[str] = None
    notes: Optional[str] = None
    close_reason: Optional[str] = None


class OpportunityRead(BaseSchema):
    id: uuid.UUID
    account_id: uuid.UUID
    partner_id: Optional[uuid.UUID] = None
    name: str
    stage: str
    arr_value: Optional[float] = None
    currency: str
    close_date: Optional[date] = None
    owner: Optional[str] = None
    notes: Optional[str] = None
    close_reason: Optional[str] = None
    hubspot_deal_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PartnerSummary(BaseSchema):
    id: uuid.UUID
    type: str
    tier: str
    icp_score: float


class OpportunityReadWithRelations(OpportunityRead):
    account: Optional[AccountSummary] = None
    partner: Optional[PartnerSummary] = None
