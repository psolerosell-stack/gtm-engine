"""Add workflow tables — Layer 4

Revision ID: 003
Revises: 002
Create Date: 2026-03-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # workflow_definitions
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(100), nullable=False),
        sa.Column("trigger_config", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("actions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_definitions_trigger_type", "workflow_definitions", ["trigger_type"])

    # workflow_executions
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("trigger_type", sa.String(100), nullable=False),
        sa.Column("trigger_data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("actions_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actions_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
    op.create_index("ix_workflow_executions_entity_type", "workflow_executions", ["entity_type"])
    op.create_index("ix_workflow_executions_entity_id", "workflow_executions", ["entity_id"])
    op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])
    op.create_index("ix_workflow_executions_created_at", "workflow_executions", ["created_at"])
    op.create_index(
        "ix_workflow_executions_idempotency_key",
        "workflow_executions",
        ["idempotency_key"],
        unique=True,
    )

    # workflow_action_logs
    op.create_table(
        "workflow_action_logs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("action_config", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("result_data", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["workflow_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_action_logs_execution_id", "workflow_action_logs", ["execution_id"]
    )


def downgrade() -> None:
    op.drop_table("workflow_action_logs")
    op.drop_table("workflow_executions")
    op.drop_table("workflow_definitions")
