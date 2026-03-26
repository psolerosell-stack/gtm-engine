"""
WorkflowEngine — Layer 4 orchestration core.

Usage (from a service method):
    from app.services.workflow import workflow_engine
    await workflow_engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=partner.id,
        trigger_data={"partner_id": str(partner.id)},
        db=db,
    )

fire() is non-blocking: it creates execution records and dispatches async tasks.
"""
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import WorkflowActionLog, WorkflowDefinition, WorkflowExecution
from app.services.workflow.triggers import TriggerType, evaluate_trigger_conditions

logger = structlog.get_logger(__name__)


def _idempotency_key(
    workflow_id: UUID,
    entity_id: UUID,
    trigger_type: str,
    day: Optional[str] = None,
) -> str:
    """
    Build an idempotency key for scheduled triggers (one fire per day per entity).
    For event triggers (no day), the key includes a high-resolution timestamp suffix
    to allow multiple firings.
    """
    if day:
        return f"{workflow_id}:{entity_id}:{trigger_type}:{day}"
    return f"{workflow_id}:{entity_id}:{trigger_type}:{datetime.now(timezone.utc).isoformat()}"


class WorkflowEngine:
    """
    Matches incoming triggers against active workflow definitions and
    dispatches executions.
    """

    async def fire(
        self,
        trigger_type: TriggerType,
        entity_type: str,
        entity_id: UUID,
        trigger_data: Dict[str, Any],
        db: AsyncSession,
        idempotency_day: Optional[str] = None,  # e.g. "2026-03-26" for scheduled triggers
    ) -> List[UUID]:
        """
        Evaluate all active workflows matching this trigger_type.
        For each match, create a WorkflowExecution and dispatch it.
        Returns list of execution IDs that were enqueued.
        """
        # Load matching active workflows
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.trigger_type == trigger_type,
                WorkflowDefinition.is_active.is_(True),
            )
        )
        workflows = result.scalars().all()

        execution_ids: List[UUID] = []

        for workflow in workflows:
            try:
                trigger_config = json.loads(workflow.trigger_config or "{}")
            except json.JSONDecodeError:
                trigger_config = {}

            # Check trigger conditions
            if not evaluate_trigger_conditions(trigger_type, trigger_config, trigger_data):
                continue

            actions_raw = json.loads(workflow.actions_json or "[]")

            # Build idempotency key
            ikey = _idempotency_key(
                workflow.id, entity_id, trigger_type, idempotency_day
            )

            # Create execution record inside a savepoint so an IntegrityError
            # (duplicate idempotency key) only rolls back this one insert,
            # not the whole outer transaction.
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_type=trigger_type,
                trigger_data=json.dumps(trigger_data),
                status="pending",
                idempotency_key=ikey,
                actions_total=len(actions_raw),
                actions_completed=0,
            )

            try:
                async with db.begin_nested():
                    db.add(execution)
                    await db.flush()
            except IntegrityError:
                # Duplicate idempotency key — already fired for this entity today
                logger.debug(
                    "workflow_skipped_duplicate",
                    workflow_id=str(workflow.id),
                    entity_id=str(entity_id),
                    ikey=ikey,
                )
                continue

            execution_ids.append(execution.id)
            logger.info(
                "workflow_execution_created",
                workflow_name=workflow.name,
                execution_id=str(execution.id),
                entity_type=entity_type,
                entity_id=str(entity_id),
                trigger_type=trigger_type,
            )

            # Dispatch — prefer Celery, fall back to in-process async
            self._dispatch(execution.id)

        return execution_ids

    def _dispatch(self, execution_id: UUID) -> None:
        """Dispatch execution to Celery task (or mark for in-process run if unavailable)."""
        try:
            from app.tasks.workflow import execute_workflow_task
            execute_workflow_task.delay(str(execution_id))
        except (ImportError, Exception) as exc:
            # Celery not available — schedule in-process execution
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._execute_in_process(execution_id))
            except RuntimeError:
                pass  # No running loop (test environment) — execution is a no-op

    async def _execute_in_process(self, execution_id: UUID) -> None:
        """Fallback: execute workflow in-process (dev mode, no Celery)."""
        from app.database import get_session_factory

        factory = get_session_factory()
        async with factory() as db:
            await self.execute(execution_id, db)

    async def execute(self, execution_id: UUID, db: AsyncSession) -> None:
        """
        Execute all actions for a workflow execution.
        Updates execution status and logs each action result.
        """
        from app.services.workflow.actions import execute_action

        result = await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            logger.warning("workflow_execution_not_found", execution_id=str(execution_id))
            return

        if execution.status not in ("pending",):
            return  # Already running or completed

        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        await db.flush()

        # Load the workflow definition
        wf_result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == execution.workflow_id
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if workflow is None:
            execution.status = "failed"
            execution.error = "Workflow definition not found"
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        try:
            actions_raw = json.loads(workflow.actions_json or "[]")
        except json.JSONDecodeError:
            actions_raw = []

        try:
            trigger_data = json.loads(execution.trigger_data or "{}")
        except json.JSONDecodeError:
            trigger_data = {}

        actions_completed = 0
        global_error = None

        for action_def in sorted(actions_raw, key=lambda x: x.get("sequence", 0)):
            action_type = action_def.get("type", "")
            action_config = action_def.get("config", {})
            sequence = action_def.get("sequence", 0)

            action_log = WorkflowActionLog(
                execution_id=execution.id,
                action_type=action_type,
                action_config=json.dumps(action_config),
                sequence=sequence,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(action_log)
            await db.flush()

            try:
                action_result = await execute_action(
                    action_type=action_type,
                    db=db,
                    entity_type=execution.entity_type,
                    entity_id=execution.entity_id,
                    config=action_config,
                    trigger_data=trigger_data,
                )
                action_log.status = action_result.status
                action_log.result_data = json.dumps(action_result.result)
                action_log.error = action_result.error
                action_log.completed_at = datetime.now(timezone.utc)

                if action_result.status == "completed":
                    actions_completed += 1

                logger.info(
                    "workflow_action_done",
                    execution_id=str(execution.id),
                    action_type=action_type,
                    status=action_result.status,
                )
            except Exception as exc:
                action_log.status = "failed"
                action_log.error = f"{type(exc).__name__}: {exc}"
                action_log.completed_at = datetime.now(timezone.utc)
                global_error = action_log.error
                logger.exception(
                    "workflow_action_exception",
                    execution_id=str(execution.id),
                    action_type=action_type,
                    error=str(exc),
                )

            await db.flush()

        execution.status = "completed" if global_error is None else "failed"
        execution.error = global_error
        execution.actions_completed = actions_completed
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "workflow_execution_done",
            execution_id=str(execution.id),
            status=execution.status,
            actions_completed=actions_completed,
            actions_total=execution.actions_total,
        )

    # ── Seed system workflows ─────────────────────────────────────────────────

    async def seed_system_workflows(self, db: AsyncSession) -> int:
        """
        Insert the 9 system workflow definitions if they don't already exist.
        Returns number of workflows inserted.
        """
        from app.services.workflow.definitions import SYSTEM_WORKFLOWS

        inserted = 0
        for wf in SYSTEM_WORKFLOWS:
            existing = await db.execute(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.name == wf["name"],
                    WorkflowDefinition.is_system.is_(True),
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            definition = WorkflowDefinition(
                name=wf["name"],
                description=wf.get("description"),
                trigger_type=wf["trigger_type"],
                trigger_config=json.dumps(wf.get("trigger_config", {})),
                actions_json=json.dumps(wf["actions"]),
                is_active=True,
                is_system=True,
            )
            db.add(definition)
            inserted += 1

        if inserted:
            await db.commit()
            logger.info("workflow_system_seeded", count=inserted)

        return inserted


# Module-level singleton
workflow_engine = WorkflowEngine()
