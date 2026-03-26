from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class ActivityCreate(BaseSchema):
    entity_type: str = Field(..., description="account | partner | lead | opportunity | contact")
    entity_id: UUID
    type: str = Field(..., description="email | call | meeting | demo | contract | onboarding | note | task | linkedin")
    date: datetime = Field(default_factory=datetime.utcnow)
    owner: Optional[str] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None


class ActivityRead(BaseSchema):
    id: UUID
    entity_type: str
    entity_id: UUID
    type: str
    date: datetime
    owner: Optional[str] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None
    message_id: Optional[str] = None
    reply_received: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
