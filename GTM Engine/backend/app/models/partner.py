import uuid
from datetime import date
from enum import Enum

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class PartnerType(str, Enum):
    oem = "OEM"
    var_plus = "VAR+"
    var = "VAR"
    referral = "Referral"
    alliance = "Alliance"


class PartnerStatus(str, Enum):
    prospect = "prospect"
    negotiation = "negotiation"
    onboarding = "onboarding"
    active = "active"
    churned = "churned"
    paused = "paused"


class PartnerTier(str, Enum):
    platinum = "Platinum"
    gold = "Gold"
    silver = "Silver"
    bronze = "Bronze"


class Partner(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "partners"

    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("accounts.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default=PartnerTier.bronze
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=PartnerStatus.prospect
    )

    # Capacity dimensions (each 0.0–2.5)
    capacity_commercial: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity_functional: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity_technical: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity_integration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vertical: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Scoring
    icp_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    arr_potential: Mapped[float | None] = mapped_column(Float, nullable=True)
    activation_velocity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # days

    # Contract
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    rappel_structure: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI fields
    fit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    approach_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HubSpot sync
    hubspot_company_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    account: Mapped["Account"] = relationship(  # noqa: F821
        "Account", back_populates="partners", lazy="noload"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        "Opportunity", back_populates="partner", lazy="noload"
    )
    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        "Lead", back_populates="partner", lazy="noload"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(  # noqa: F821
        "Campaign", back_populates="partner", lazy="noload"
    )
    revenue_records: Mapped[list["Revenue"]] = relationship(  # noqa: F821
        "Revenue", back_populates="partner", lazy="noload"
    )
    score_history: Mapped[list["ScoreHistory"]] = relationship(  # noqa: F821
        "ScoreHistory", back_populates="partner", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Partner id={self.id} type={self.type} tier={self.tier} score={self.icp_score}>"


class ScoreHistory(Base, UUIDMixin):
    """Immutable record of a partner's ICP score at a point in time."""

    __tablename__ = "score_history"

    partner_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("partners.id"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    breakdown: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    computed_at: Mapped[str] = mapped_column(String(50), nullable=False)  # ISO datetime string
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    partner: Mapped["Partner"] = relationship("Partner", back_populates="score_history", lazy="noload")

    def __repr__(self) -> str:
        return f"<ScoreHistory partner={self.partner_id} score={self.score} at={self.computed_at}>"
