"""
Import all models here so that SQLAlchemy's mapper registry
and Alembic's autogenerate can discover them.
"""

from app.models.base import Base, TimestampMixin, UUIDMixin  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.account import Account, ERPEcosystem  # noqa: F401
from app.models.partner import Partner, PartnerType, PartnerTier, PartnerStatus, ScoreHistory  # noqa: F401
from app.models.lead import Lead, LeadSource, LeadStatus  # noqa: F401
from app.models.opportunity import Opportunity, OpportunityStage, Currency  # noqa: F401
from app.models.contact import Contact  # noqa: F401
from app.models.campaign import Campaign, CampaignType  # noqa: F401
from app.models.activity import Activity, ActivityType, ActivityEntityType  # noqa: F401
from app.models.revenue import Revenue, RevenueType  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.analytics import AnalyticsEvent, ScoringWeightVersion, DailyBriefing  # noqa: F401
from app.models.ai_log import AICallLog  # noqa: F401
from app.models.workflow import WorkflowDefinition, WorkflowExecution, WorkflowActionLog  # noqa: F401

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "UserRole",
    "Account",
    "ERPEcosystem",
    "Partner",
    "PartnerType",
    "PartnerTier",
    "PartnerStatus",
    "ScoreHistory",
    "Lead",
    "LeadSource",
    "LeadStatus",
    "Opportunity",
    "OpportunityStage",
    "Currency",
    "Contact",
    "Campaign",
    "CampaignType",
    "Activity",
    "ActivityType",
    "ActivityEntityType",
    "Revenue",
    "RevenueType",
    "AuditLog",
    "AnalyticsEvent",
    "ScoringWeightVersion",
    "DailyBriefing",
    "AICallLog",
    "WorkflowDefinition",
    "WorkflowExecution",
    "WorkflowActionLog",
]
