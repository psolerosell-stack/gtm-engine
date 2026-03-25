import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field, HttpUrl, field_validator

from app.models.account import ERPEcosystem
from app.schemas.common import BaseSchema


class AccountCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=100)
    size: Optional[int] = Field(default=None, ge=1)
    geography: Optional[str] = Field(default=None, max_length=100)
    website: Optional[str] = Field(default=None, max_length=512)
    erp_ecosystem: Optional[ERPEcosystem] = None
    description: Optional[str] = None
    hubspot_company_id: Optional[str] = Field(default=None, max_length=100)


class AccountUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=100)
    size: Optional[int] = Field(default=None, ge=1)
    geography: Optional[str] = Field(default=None, max_length=100)
    website: Optional[str] = Field(default=None, max_length=512)
    erp_ecosystem: Optional[ERPEcosystem] = None
    description: Optional[str] = None
    hubspot_company_id: Optional[str] = Field(default=None, max_length=100)
    fit_summary: Optional[str] = None


class AccountRead(BaseSchema):
    id: uuid.UUID
    name: str
    industry: Optional[str] = None
    size: Optional[int] = None
    geography: Optional[str] = None
    website: Optional[str] = None
    erp_ecosystem: Optional[str] = None
    description: Optional[str] = None
    fit_summary: Optional[str] = None
    enrichment_status: str
    hubspot_company_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScoringWeightVersionCreate(BaseSchema):
    """Create a new scoring weight version."""
    weights: dict = Field(
        ...,
        description="Dict mapping dimension names to float weights (must sum to 1.0)",
    )
    rationale: Optional[str] = None
    activate: bool = Field(
        default=False,
        description="If true, immediately activate this version.",
    )

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: dict) -> dict:
        required = {
            "erp_ecosystem_fit", "partner_type_match", "capacity_score",
            "geography_match", "vertical_fit", "company_size",
            "arr_potential", "activation_velocity",
        }
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"Missing weight dimensions: {missing}")
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        return v


class ScoringWeightVersionRead(BaseSchema):
    id: uuid.UUID
    version: int
    weights: dict
    rationale: Optional[str] = None
    is_active: bool
    created_at: datetime
