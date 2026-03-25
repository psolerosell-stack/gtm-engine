import uuid
from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class LeadStatus(str, Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    disqualified = "disqualified"
    converted = "converted"


class LeadSource(str, Enum):
    partner_referral = "partner_referral"
    outbound = "outbound"
    inbound = "inbound"
    event = "event"
    linkedin = "linkedin"
    content = "content"
    other = "other"


class Lead(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "leads"

    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("accounts.id"), nullable=False, index=True
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("partners.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, default=LeadSource.other)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=LeadStatus.new)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HubSpot sync
    hubspot_contact_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship(  # noqa: F821
        "Account", back_populates="leads", lazy="noload"
    )
    partner: Mapped["Partner | None"] = relationship(  # noqa: F821
        "Partner", back_populates="leads", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Lead id={self.id} status={self.status} source={self.source}>"
