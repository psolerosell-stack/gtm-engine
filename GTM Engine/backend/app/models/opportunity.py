import uuid
from datetime import date
from enum import Enum

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class OpportunityStage(str, Enum):
    prospecting = "prospecting"
    qualification = "qualification"
    discovery = "discovery"
    demo = "demo"
    proposal = "proposal"
    negotiation = "negotiation"
    closed_won = "closed_won"
    closed_lost = "closed_lost"


class Currency(str, Enum):
    eur = "EUR"
    usd = "USD"
    gbp = "GBP"


class Opportunity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "opportunities"

    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("accounts.id"), nullable=False, index=True
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("partners.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(
        String(50), nullable=False, default=OpportunityStage.prospecting
    )
    arr_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=Currency.eur)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HubSpot sync
    hubspot_deal_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    account: Mapped["Account"] = relationship(  # noqa: F821
        "Account", back_populates="opportunities", lazy="noload"
    )
    partner: Mapped["Partner | None"] = relationship(  # noqa: F821
        "Partner", back_populates="opportunities", lazy="noload"
    )
    revenue_records: Mapped[list["Revenue"]] = relationship(  # noqa: F821
        "Revenue", back_populates="opportunity", lazy="noload"
    )
    activities: Mapped[list["Activity"]] = relationship(  # noqa: F821
        "Activity",
        primaryjoin="and_(Activity.entity_type=='opportunity', foreign(Activity.entity_id)==Opportunity.id)",
        lazy="noload",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Opportunity id={self.id} name={self.name} stage={self.stage}>"
