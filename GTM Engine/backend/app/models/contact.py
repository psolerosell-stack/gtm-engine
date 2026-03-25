import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class Contact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contacts"

    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("accounts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HubSpot sync
    hubspot_contact_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    account: Mapped["Account"] = relationship(  # noqa: F821
        "Account", back_populates="contacts", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Contact id={self.id} name={self.name} email={self.email}>"
