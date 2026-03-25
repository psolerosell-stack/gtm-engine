import uuid
from enum import Enum

from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ERPEcosystem(str, Enum):
    business_central = "business_central"
    navision = "navision"
    sage_200 = "sage_200"
    sage_x3 = "sage_x3"
    sap_b1 = "sap_b1"
    netsuite = "netsuite"
    holded = "holded"
    other = "other"


class Account(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # number of employees
    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    erp_ecosystem: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI enrichment fields
    fit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending / running / done / failed
    enrichment_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    # HubSpot sync
    hubspot_company_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    partners: Mapped[list["Partner"]] = relationship(  # noqa: F821
        "Partner", back_populates="account", lazy="noload"
    )
    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        "Lead", back_populates="account", lazy="noload"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        "Opportunity", back_populates="account", lazy="noload"
    )
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        "Contact", back_populates="account", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} name={self.name}>"
