import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, UUIDMixin


class AICallLog(Base, UUIDMixin):
    """
    Immutable record of every Claude API call made by the system.
    Used for cost tracking, debugging, and prompt versioning.
    """

    __tablename__ = "ai_call_logs"

    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # enrich | fit_summary | approach | signals | discover

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Store prompt hash for deduplication / caching analysis
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AICallLog purpose={self.purpose} entity={self.entity_type}:{self.entity_id} "
            f"tokens={self.total_tokens} cost=${self.cost_usd:.4f}>"
        )
