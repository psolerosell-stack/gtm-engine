"""
Celery tasks for workflow execution and scheduled trigger checks — Layer 4.

Tasks:
  execute_workflow_task       — run a single WorkflowExecution by ID
  check_partner_inactivity    — fire partner_inactive triggers (daily)
  check_partners_not_converted — fire partner_not_converted triggers (daily)
"""
import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Execute a single workflow ─────────────────────────────────────────────────

@celery_app.task(
    name="app.tasks.workflow.execute_workflow_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def execute_workflow_task(self, execution_id: str) -> dict:
    """Execute all actions for a WorkflowExecution by ID."""
    import uuid

    async def _run():
        from app.database import get_session_factory
        from app.services.workflow.engine import workflow_engine

        factory = get_session_factory()
        async with factory() as db:
            await workflow_engine.execute(uuid.UUID(execution_id), db)
        return {"status": "done", "execution_id": execution_id}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("execute_workflow_task_failed", execution_id=execution_id, error=str(exc))
        raise self.retry(exc=exc) from exc


# ── Scheduled: check partner inactivity ──────────────────────────────────────

@celery_app.task(
    name="app.tasks.workflow.check_partner_inactivity",
    bind=True,
    max_retries=2,
)
def check_partner_inactivity(self) -> dict:
    """
    Daily task: find partners with no activity in ≥14 days and fire the
    partner_inactive trigger. Uses today's date as idempotency key.
    """
    async def _run():
        from datetime import date, datetime, timedelta, timezone

        from sqlalchemy import func, select

        from app.database import get_session_factory
        from app.models.activity import Activity
        from app.models.partner import Partner
        from app.services.workflow.engine import workflow_engine
        from app.services.workflow.triggers import TriggerType

        factory = get_session_factory()
        today = date.today().isoformat()
        fired = 0

        async with factory() as db:
            # Find all active partners
            result = await db.execute(
                select(Partner.id).where(Partner.deleted_at.is_(None))
            )
            partner_ids = [row[0] for row in result.all()]

        for partner_id in partner_ids:
            async with factory() as db:
                # Find most recent activity for this partner
                result = await db.execute(
                    select(func.max(Activity.date)).where(
                        Activity.entity_type == "partner",
                        Activity.entity_id == partner_id,
                    )
                )
                last_activity = result.scalar_one_or_none()

                now = datetime.now(timezone.utc)
                if last_activity is None:
                    # Never had activity — check partner creation date
                    p_result = await db.execute(select(Partner).where(Partner.id == partner_id))
                    partner = p_result.scalar_one_or_none()
                    if partner is None:
                        continue
                    # Make created_at timezone-aware for comparison
                    created = partner.created_at
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    inactive_days = (now - created).days
                else:
                    if last_activity.tzinfo is None:
                        last_activity = last_activity.replace(tzinfo=timezone.utc)
                    inactive_days = (now - last_activity).days

                if inactive_days >= 14:
                    execution_ids = await workflow_engine.fire(
                        trigger_type=TriggerType.partner_inactive,
                        entity_type="partner",
                        entity_id=partner_id,
                        trigger_data={"inactive_days": inactive_days},
                        db=db,
                        idempotency_day=today,
                    )
                    if execution_ids:
                        fired += 1
                    await db.commit()

        logger.info("check_partner_inactivity_done", fired=fired)
        return {"fired": fired}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("check_partner_inactivity_failed", error=str(exc))
        raise self.retry(exc=exc) from exc


# ── Scheduled: check partners not converted ───────────────────────────────────

@celery_app.task(
    name="app.tasks.workflow.check_partners_not_converted",
    bind=True,
    max_retries=2,
)
def check_partners_not_converted(self) -> dict:
    """
    Daily task: find partners stuck in 'pending' for ≥60 days and fire the
    partner_not_converted trigger.
    """
    async def _run():
        from datetime import date, datetime, timezone

        from sqlalchemy import select

        from app.database import get_session_factory
        from app.models.partner import Partner, PartnerStatus
        from app.services.workflow.engine import workflow_engine
        from app.services.workflow.triggers import TriggerType

        factory = get_session_factory()
        today = date.today().isoformat()
        fired = 0

        async with factory() as db:
            result = await db.execute(
                select(Partner).where(
                    Partner.status == PartnerStatus.pending,
                    Partner.deleted_at.is_(None),
                )
            )
            pending_partners = result.scalars().all()

        for partner in pending_partners:
            async with factory() as db:
                created = partner.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                days_pending = (datetime.now(timezone.utc) - created).days

                if days_pending >= 60:
                    execution_ids = await workflow_engine.fire(
                        trigger_type=TriggerType.partner_not_converted,
                        entity_type="partner",
                        entity_id=partner.id,
                        trigger_data={"days_pending": days_pending, "partner_id": str(partner.id)},
                        db=db,
                        idempotency_day=today,
                    )
                    if execution_ids:
                        fired += 1
                    await db.commit()

        logger.info("check_partners_not_converted_done", fired=fired)
        return {"fired": fired}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("check_partners_not_converted_failed", error=str(exc))
        raise self.retry(exc=exc) from exc
