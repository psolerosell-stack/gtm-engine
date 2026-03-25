import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, UUIDMixin


class AuditLog(Base, UUIDMixin):
    """Immutable audit trail for all entity writes."""

    __tablename__ = "audit_logs"

    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)  # INSERT / UPDATE / DELETE
    old_values: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON string
    new_values: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON string
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True, index=True
    )
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
    )
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog op={self.operation} table={self.table_name} "
            f"record={self.record_id} at={self.timestamp}>"
        )
