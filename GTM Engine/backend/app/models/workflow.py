import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, UUIDMixin


class WorkflowDefinition(Base, UUIDMixin):
    """
    A configured workflow: one trigger + ordered list of actions.
    System workflows are pre-seeded and cannot be deleted (only deactivated).
    """

    __tablename__ = "workflow_definitions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON
    actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")   # JSON list
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="workflow", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<WorkflowDef id={self.id} trigger={self.trigger_type} active={self.is_active}>"


class WorkflowExecution(Base, UUIDMixin):
    """
    A single run of a workflow for a specific entity.
    """

    __tablename__ = "workflow_executions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_data: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON snapshot

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )  # pending | running | completed | failed | skipped

    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True, unique=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    actions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actions_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), default=datetime.utcnow, index=True,
    )

    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition", back_populates="executions", lazy="noload"
    )
    action_logs: Mapped[list["WorkflowActionLog"]] = relationship(
        "WorkflowActionLog", back_populates="execution", lazy="noload",
        order_by="WorkflowActionLog.sequence",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowExecution id={self.id} status={self.status} "
            f"entity={self.entity_type}:{self.entity_id}>"
        )


class WorkflowActionLog(Base, UUIDMixin):
    """
    Immutable record of a single action step within a workflow execution.
    """

    __tablename__ = "workflow_action_logs"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workflow_executions.id"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending | completed | failed | skipped

    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), default=datetime.utcnow,
    )

    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution", back_populates="action_logs", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowActionLog id={self.id} action={self.action_type} "
            f"seq={self.sequence} status={self.status}>"
        )
