"""Initial schema — all entities

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── accounts ─────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("geography", sa.String(100), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("erp_ecosystem", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fit_summary", sa.Text(), nullable=True),
        sa.Column("enrichment_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("enrichment_data", sa.Text(), nullable=True),
        sa.Column("hubspot_company_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_accounts_name", "accounts", ["name"])
    op.create_index("ix_accounts_hubspot_company_id", "accounts", ["hubspot_company_id"])

    # ── partners ─────────────────────────────────────────────────────────────
    op.create_table(
        "partners",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("account_id", sa.CHAR(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("tier", sa.String(50), nullable=False, server_default="Bronze"),
        sa.Column("status", sa.String(50), nullable=False, server_default="prospect"),
        sa.Column("capacity_commercial", sa.Float(), nullable=False, server_default="0"),
        sa.Column("capacity_functional", sa.Float(), nullable=False, server_default="0"),
        sa.Column("capacity_technical", sa.Float(), nullable=False, server_default="0"),
        sa.Column("capacity_integration", sa.Float(), nullable=False, server_default="0"),
        sa.Column("geography", sa.String(100), nullable=True),
        sa.Column("vertical", sa.String(100), nullable=True),
        sa.Column("icp_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("arr_potential", sa.Float(), nullable=True),
        sa.Column("activation_velocity", sa.Integer(), nullable=True),
        sa.Column("contract_start", sa.Date(), nullable=True),
        sa.Column("contract_end", sa.Date(), nullable=True),
        sa.Column("rappel_structure", sa.Text(), nullable=True),
        sa.Column("fit_summary", sa.Text(), nullable=True),
        sa.Column("approach_suggestion", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("hubspot_company_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_partners_account_id", "partners", ["account_id"])
    op.create_index("ix_partners_hubspot_company_id", "partners", ["hubspot_company_id"])

    # ── score_history ─────────────────────────────────────────────────────────
    op.create_table(
        "score_history",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("partner_id", sa.CHAR(36), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("tier", sa.String(50), nullable=False),
        sa.Column("breakdown", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.String(50), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=True),
    )
    op.create_index("ix_score_history_partner_id", "score_history", ["partner_id"])

    # ── leads ─────────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("account_id", sa.CHAR(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("partner_id", sa.CHAR(36), sa.ForeignKey("partners.id"), nullable=True),
        sa.Column("source", sa.String(100), nullable=False, server_default="other"),
        sa.Column("status", sa.String(50), nullable=False, server_default="new"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("hubspot_contact_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_leads_account_id", "leads", ["account_id"])
    op.create_index("ix_leads_partner_id", "leads", ["partner_id"])

    # ── opportunities ─────────────────────────────────────────────────────────
    op.create_table(
        "opportunities",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("account_id", sa.CHAR(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("partner_id", sa.CHAR(36), sa.ForeignKey("partners.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False, server_default="prospecting"),
        sa.Column("arr_value", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("hubspot_deal_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_opportunities_account_id", "opportunities", ["account_id"])
    op.create_index("ix_opportunities_partner_id", "opportunities", ["partner_id"])
    op.create_index("ix_opportunities_hubspot_deal_id", "opportunities", ["hubspot_deal_id"])

    # ── contacts ──────────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("account_id", sa.CHAR(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin", sa.String(512), nullable=True),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("hubspot_contact_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contacts_account_id", "contacts", ["account_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])
    op.create_index("ix_contacts_hubspot_contact_id", "contacts", ["hubspot_contact_id"])

    # ── campaigns ─────────────────────────────────────────────────────────────
    op.create_table(
        "campaigns",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(100), nullable=True),
        sa.Column("partner_id", sa.CHAR(36), sa.ForeignKey("partners.id"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("leads_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("arr_attributed", sa.Float(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_campaigns_name", "campaigns", ["name"])
    op.create_index("ix_campaigns_partner_id", "campaigns", ["partner_id"])

    # ── activities ────────────────────────────────────────────────────────────
    op.create_table(
        "activities",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.CHAR(36), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(255), nullable=True),
        sa.Column("reply_received", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_activities_entity_type", "activities", ["entity_type"])
    op.create_index("ix_activities_entity_id", "activities", ["entity_id"])
    op.create_index("ix_activities_message_id", "activities", ["message_id"])

    # ── revenue ───────────────────────────────────────────────────────────────
    op.create_table(
        "revenue",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("partner_id", sa.CHAR(36), sa.ForeignKey("partners.id"), nullable=True),
        sa.Column("opportunity_id", sa.CHAR(36), sa.ForeignKey("opportunities.id"), nullable=True),
        sa.Column("arr", sa.Float(), nullable=False),
        sa.Column("mrr", sa.Float(), nullable=False),
        sa.Column("date_closed", sa.Date(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False, server_default="new"),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_revenue_partner_id", "revenue", ["partner_id"])
    op.create_index("ix_revenue_opportunity_id", "revenue", ["opportunity_id"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.CHAR(36), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("old_values", sa.Text(), nullable=True),
        sa.Column("new_values", sa.Text(), nullable=True),
        sa.Column("user_id", sa.CHAR(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(50), nullable=True),
    )
    op.create_index("ix_audit_logs_table_name", "audit_logs", ["table_name"])
    op.create_index("ix_audit_logs_record_id", "audit_logs", ["record_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    # ── analytics_events ──────────────────────────────────────────────────────
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.CHAR(36), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])
    op.create_index("ix_analytics_events_entity_type", "analytics_events", ["entity_type"])
    op.create_index("ix_analytics_events_entity_id", "analytics_events", ["entity_id"])
    op.create_index("ix_analytics_events_timestamp", "analytics_events", ["timestamp"])

    # ── scoring_weight_versions ───────────────────────────────────────────────
    op.create_table(
        "scoring_weight_versions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scoring_weight_versions_version", "scoring_weight_versions", ["version"])

    # ── daily_briefings ───────────────────────────────────────────────────────
    op.create_table(
        "daily_briefings",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("date", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("posted_to_slack", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_daily_briefings_date", "daily_briefings", ["date"])


def downgrade() -> None:
    op.drop_table("daily_briefings")
    op.drop_table("scoring_weight_versions")
    op.drop_table("analytics_events")
    op.drop_table("audit_logs")
    op.drop_table("revenue")
    op.drop_table("activities")
    op.drop_table("campaigns")
    op.drop_table("contacts")
    op.drop_table("opportunities")
    op.drop_table("leads")
    op.drop_table("score_history")
    op.drop_table("partners")
    op.drop_table("accounts")
    op.drop_table("users")
