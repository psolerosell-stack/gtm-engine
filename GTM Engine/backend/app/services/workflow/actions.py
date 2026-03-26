"""
Action type definitions and execution — Layer 4.

Each action is an async function that accepts an ActionContext and returns
an ActionResult. Actions must be atomic and idempotent.

Integrations (Slack, HubSpot) fail gracefully with status="skipped" when
the relevant API keys are not configured.
"""
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ActionType(str, Enum):
    log_activity = "log_activity"
    create_task = "create_task"
    update_partner_field = "update_partner_field"
    slack_notify = "slack_notify"
    hubspot_create_company = "hubspot_create_company"
    hubspot_update_deal = "hubspot_update_deal"
    create_revenue_record = "create_revenue_record"
    score_recalculate = "score_recalculate"
    generate_ai_intelligence = "generate_ai_intelligence"


class ActionResult:
    def __init__(
        self,
        status: str,  # completed | failed | skipped
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.status = status
        self.result = result or {}
        self.error = error


# ── Action Implementations ────────────────────────────────────────────────────

async def action_log_activity(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Create an Activity record."""
    from app.models.activity import Activity

    notes_template = config.get("notes", "Workflow action: {trigger_type}")
    notes = notes_template.format(**{**trigger_data, "entity_type": entity_type})

    activity = Activity(
        entity_type=entity_type,
        entity_id=entity_id,
        type=config.get("activity_type", "note"),
        date=datetime.now(timezone.utc),
        owner=config.get("owner", "system"),
        notes=notes,
        outcome=config.get("outcome"),
    )
    db.add(activity)
    await db.flush()
    return ActionResult("completed", {"activity_id": str(activity.id)})


async def action_create_task(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Create a task Activity."""
    from app.models.activity import Activity

    title_template = config.get("title", "Task from workflow")
    title = title_template.format(**{**trigger_data, "entity_type": entity_type})

    activity = Activity(
        entity_type=entity_type,
        entity_id=entity_id,
        type="task",
        date=datetime.now(timezone.utc),
        owner=config.get("owner", "system"),
        notes=title,
        outcome=None,
    )
    db.add(activity)
    await db.flush()
    return ActionResult("completed", {"task_id": str(activity.id), "title": title})


async def action_update_partner_field(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Update one or more fields on a Partner record."""
    if entity_type != "partner":
        return ActionResult("skipped", {"reason": f"entity_type={entity_type}, expected partner"})

    from sqlalchemy import select
    from app.models.partner import Partner

    result = await db.execute(
        select(Partner).where(Partner.id == entity_id, Partner.deleted_at.is_(None))
    )
    partner = result.scalar_one_or_none()
    if partner is None:
        return ActionResult("failed", error="Partner not found")

    fields = config.get("fields", {})
    updated = {}
    for field, value in fields.items():
        if hasattr(partner, field):
            # Support dynamic values from trigger_data
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                key = value[1:-1]
                value = trigger_data.get(key, value)
            setattr(partner, field, value)
            updated[field] = value

    await db.flush()
    return ActionResult("completed", {"updated_fields": updated})


async def action_slack_notify(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Send a Slack notification. Skips gracefully if not configured."""
    from app.config import settings

    if not settings.slack_bot_token or settings.slack_bot_token.startswith("your-"):
        logger.info("slack_notify_skipped", reason="not_configured", config=config)
        return ActionResult("skipped", {"reason": "Slack not configured"})

    try:
        from slack_sdk.web.async_client import AsyncWebClient

        message_template = config.get("message", "GTM Engine notification")
        message = message_template.format(**{**trigger_data, "entity_type": entity_type})
        channel = config.get("channel", settings.slack_partnerships_channel)

        client = AsyncWebClient(token=settings.slack_bot_token)
        response = await client.chat_postMessage(channel=channel, text=message)
        return ActionResult("completed", {"ts": response.get("ts"), "channel": channel})
    except ImportError:
        return ActionResult("skipped", {"reason": "slack_sdk not installed"})
    except Exception as exc:
        logger.warning("slack_notify_failed", error=str(exc))
        return ActionResult("failed", error=f"Slack error: {exc}")


async def action_hubspot_create_company(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Create or update a HubSpot company. Skips gracefully if not configured."""
    from app.config import settings

    if not settings.hubspot_api_key or settings.hubspot_api_key.startswith("your-"):
        return ActionResult("skipped", {"reason": "HubSpot not configured"})

    try:
        from sqlalchemy import select
        from app.models.account import Account
        from app.models.partner import Partner

        if entity_type == "partner":
            result = await db.execute(select(Partner).where(Partner.id == entity_id))
            partner = result.scalar_one_or_none()
            if partner is None:
                return ActionResult("failed", error="Partner not found")
            account_result = await db.execute(
                select(Account).where(Account.id == partner.account_id)
            )
            account = account_result.scalar_one_or_none()
        else:
            result = await db.execute(select(Account).where(Account.id == entity_id))
            account = result.scalar_one_or_none()
            partner = None

        if account is None:
            return ActionResult("failed", error="Account not found")

        import hubspot
        from hubspot.crm.companies import SimplePublicObjectInput

        hs = hubspot.Client.create(api_key=settings.hubspot_api_key)
        properties = {
            "name": account.name,
            "domain": account.website or "",
            "industry": account.industry or "",
            "country": account.geography or "",
        }
        if partner:
            properties["gtm_partner_type"] = partner.type
            properties["gtm_icp_score"] = str(partner.icp_score or 0)

        company_input = SimplePublicObjectInput(properties=properties)
        created = hs.crm.companies.basic_api.create(simple_public_object_input=company_input)

        # Save HubSpot ID back
        if partner:
            partner.hubspot_company_id = str(created.id)
        elif account:
            account.hubspot_company_id = str(created.id)
        await db.flush()

        return ActionResult("completed", {"hubspot_company_id": str(created.id)})
    except ImportError:
        return ActionResult("skipped", {"reason": "hubspot package not installed"})
    except Exception as exc:
        logger.warning("hubspot_create_company_failed", error=str(exc))
        return ActionResult("failed", error=f"HubSpot error: {exc}")


async def action_hubspot_update_deal(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Update a HubSpot deal stage. Skips if not configured."""
    from app.config import settings

    if not settings.hubspot_api_key or settings.hubspot_api_key.startswith("your-"):
        return ActionResult("skipped", {"reason": "HubSpot not configured"})

    try:
        from sqlalchemy import select
        from app.models.opportunity import Opportunity

        result = await db.execute(select(Opportunity).where(Opportunity.id == entity_id))
        opp = result.scalar_one_or_none()
        if opp is None or not opp.hubspot_deal_id:
            return ActionResult("skipped", {"reason": "No HubSpot deal ID on opportunity"})

        import hubspot
        from hubspot.crm.deals import SimplePublicObjectInput

        hs = hubspot.Client.create(api_key=settings.hubspot_api_key)
        stage_map = {
            "prospecting": "appointmentscheduled",
            "qualification": "qualifiedtobuy",
            "demo": "presentationscheduled",
            "proposal": "decisionmakerboughtin",
            "negotiation": "contractsent",
            "closed_won": "closedwon",
            "closed_lost": "closedlost",
        }
        hs_stage = stage_map.get(trigger_data.get("new_stage", ""), "appointmentscheduled")
        hs.crm.deals.basic_api.update(
            deal_id=opp.hubspot_deal_id,
            simple_public_object_input=SimplePublicObjectInput(
                properties={"dealstage": hs_stage}
            ),
        )
        return ActionResult("completed", {"hubspot_deal_id": opp.hubspot_deal_id, "stage": hs_stage})
    except ImportError:
        return ActionResult("skipped", {"reason": "hubspot package not installed"})
    except Exception as exc:
        logger.warning("hubspot_update_deal_failed", error=str(exc))
        return ActionResult("failed", error=f"HubSpot error: {exc}")


async def action_create_revenue_record(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Create a Revenue record from a closed-won opportunity."""
    from sqlalchemy import select
    from app.models.opportunity import Opportunity
    from app.models.revenue import Revenue, RevenueType

    opp_id = entity_id if entity_type == "opportunity" else None
    opp = None

    if opp_id:
        result = await db.execute(select(Opportunity).where(Opportunity.id == opp_id))
        opp = result.scalar_one_or_none()

    if opp is None:
        return ActionResult("skipped", {"reason": "Opportunity not found"})

    # Idempotency: don't create duplicate revenue records
    from sqlalchemy import exists, select as sel
    existing = await db.execute(
        sel(Revenue).where(Revenue.opportunity_id == opp.id)
    )
    if existing.scalar_one_or_none():
        return ActionResult("skipped", {"reason": "Revenue record already exists"})

    from datetime import date as _date
    revenue = Revenue(
        partner_id=opp.partner_id,
        opportunity_id=opp.id,
        arr=opp.arr_value or 0.0,
        mrr=(opp.arr_value or 0.0) / 12,
        date_closed=opp.close_date or _date.today(),
        type=RevenueType.new,
        attribution=f"Closed-won: {opp.name}",
    )
    db.add(revenue)
    await db.flush()
    return ActionResult("completed", {"revenue_id": str(revenue.id), "arr": revenue.arr})


async def action_score_recalculate(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Recalculate ICP score for a partner."""
    if entity_type != "partner":
        return ActionResult("skipped", {"reason": f"entity_type={entity_type}"})

    from app.services.partner import PartnerService

    service = PartnerService(db)
    result = await service.recalculate_score(entity_id)
    if result is None:
        return ActionResult("failed", error="Partner not found")
    score, tier = result
    return ActionResult("completed", {"score": score, "tier": tier})


async def action_generate_ai_intelligence(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Queue AI fit summary and approach generation for a partner."""
    if entity_type != "partner":
        return ActionResult("skipped", {"reason": f"entity_type={entity_type}"})

    try:
        from app.tasks.enrichment import generate_partner_intelligence
        generate_partner_intelligence.delay(str(entity_id))
        return ActionResult("completed", {"queued": True})
    except (ImportError, Exception) as exc:
        return ActionResult("skipped", {"reason": f"Celery unavailable: {exc}"})


# ── Dispatcher ────────────────────────────────────────────────────────────────

_ACTION_HANDLERS = {
    ActionType.log_activity: action_log_activity,
    ActionType.create_task: action_create_task,
    ActionType.update_partner_field: action_update_partner_field,
    ActionType.slack_notify: action_slack_notify,
    ActionType.hubspot_create_company: action_hubspot_create_company,
    ActionType.hubspot_update_deal: action_hubspot_update_deal,
    ActionType.create_revenue_record: action_create_revenue_record,
    ActionType.score_recalculate: action_score_recalculate,
    ActionType.generate_ai_intelligence: action_generate_ai_intelligence,
}


async def execute_action(
    action_type: str,
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> ActionResult:
    """Dispatch to the correct action handler."""
    handler = _ACTION_HANDLERS.get(action_type)
    if handler is None:
        return ActionResult("failed", error=f"Unknown action type: {action_type}")
    try:
        return await handler(db, entity_type, entity_id, config, trigger_data)
    except Exception as exc:
        logger.exception("action_execution_error", action_type=action_type, error=str(exc))
        return ActionResult("failed", error=f"{type(exc).__name__}: {exc}")
