import uuid
from datetime import date
from enum import Enum

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class RevenueType(str, Enum):
    new = "new"
    expansion = "expansion"
    renewal = "renewal"
    churn = "churn"


class Revenue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "revenue"

    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("partners.id"), nullable=True, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("opportunities.id"), nullable=True, index=True
    )
    arr: Mapped[float] = mapped_column(Float, nullable=False)
    mrr: Mapped[float] = mapped_column(Float, nullable=False)
    date_closed: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default=RevenueType.new)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="EUR")

    # Relationships
    partner: Mapped["Partner | None"] = relationship(  # noqa: F821
        "Partner", back_populates="revenue_records", lazy="noload"
    )
    opportunity: Mapped["Opportunity | None"] = relationship(  # noqa: F821
        "Opportunity", back_populates="revenue_records", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Revenue id={self.id} arr={self.arr} type={self.type}>"
