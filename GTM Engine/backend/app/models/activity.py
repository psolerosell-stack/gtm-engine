import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class ActivityType(str, Enum):
    email = "email"
    call = "call"
    meeting = "meeting"
    demo = "demo"
    contract = "contract"
    onboarding = "onboarding"
    note = "note"
    task = "task"
    linkedin = "linkedin"


class ActivityEntityType(str, Enum):
    account = "account"
    partner = "partner"
    lead = "lead"
    opportunity = "opportunity"
    contact = "contact"


class Activity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "activities"

    # Polymorphic FK — stores entity_type + entity_id rather than separate FKs
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Email tracking (from Gmail/HubSpot webhooks)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reply_received: Mapped[bool | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"<Activity id={self.id} type={self.type} entity={self.entity_type}:{self.entity_id}>"
