import uuid
from datetime import date
from enum import Enum

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class CampaignType(str, Enum):
    co_marketing = "co_marketing"
    webinar = "webinar"
    email_sequence = "email_sequence"
    event = "event"
    content = "content"
    paid = "paid"
    partner_enablement = "partner_enablement"


class Campaign(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("partners.id"), nullable=True, index=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    leads_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    arr_attributed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    partner: Mapped["Partner | None"] = relationship(  # noqa: F821
        "Partner", back_populates="campaigns", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name} type={self.type}>"
