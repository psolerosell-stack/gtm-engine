"""
Workflow Orchestrator router — Layer 4.

Endpoints:
  GET    /workflows                        List all workflow definitions
  POST   /workflows                        Create a custom workflow
  GET    /workflows/{id}                   Get a workflow definition
  PUT    /workflows/{id}                   Update a workflow definition
  DELETE /workflows/{id}                   Deactivate (soft) a workflow
  POST   /workflows/seed                   Seed the 9 system workflows
  POST   /workflows/trigger                Manual trigger (for testing)
  GET    /workflows/executions             List recent executions
  GET    /workflows/executions/{id}        Get execution detail with action logs
"""
import json
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import AdminUser, CurrentUser, DBSession, ManagerUser
from app.models.workflow import WorkflowActionLog, WorkflowDefinition, WorkflowExecution
from app.schemas.workflow import (
    ManualTriggerRequest,
    ManualTriggerResponse,
    SeedResponse,
    WorkflowActionLogRead,
    WorkflowCreate,
    WorkflowExecutionRead,
    WorkflowRead,
    WorkflowUpdate,
)
from app.services.workflow.engine import workflow_engine
from app.services.workflow.triggers import TriggerType

router = APIRouter(tags=["workflows"])


def _parse_json_field(raw: str, default):
    try:
        return json.loads(raw) if raw else default
    except json.JSONDecodeError:
        return default


def _wf_to_read(wf: WorkflowDefinition) -> WorkflowRead:
    return WorkflowRead(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        trigger_type=wf.trigger_type,
        trigger_config=_parse_json_field(wf.trigger_config, {}),
        actions=_parse_json_field(wf.actions_json, []),
        is_active=wf.is_active,
        is_system=wf.is_system,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


def _exec_to_read(ex: WorkflowExecution) -> WorkflowExecutionRead:
    action_logs = []
    for log in (ex.action_logs or []):
        action_logs.append(WorkflowActionLogRead(
            id=log.id,
            action_type=log.action_type,
            action_config=_parse_json_field(log.action_config, {}),
            sequence=log.sequence,
            status=log.status,
            result_data=_parse_json_field(log.result_data, None),
            error=log.error,
            started_at=log.started_at,
            completed_at=log.completed_at,
            created_at=log.created_at,
        ))
    return WorkflowExecutionRead(
        id=ex.id,
        workflow_id=ex.workflow_id,
        entity_type=ex.entity_type,
        entity_id=ex.entity_id,
        trigger_type=ex.trigger_type,
        trigger_data=_parse_json_field(ex.trigger_data, {}),
        status=ex.status,
        started_at=ex.started_at,
        completed_at=ex.completed_at,
        error=ex.error,
        actions_total=ex.actions_total,
        actions_completed=ex.actions_completed,
        created_at=ex.created_at,
        action_logs=action_logs,
    )


# ── Static sub-routes MUST be registered before /{workflow_id} ───────────────
# FastAPI matches routes in registration order; static segments must come first.

# ── Seed ──────────────────────────────────────────────────────────────────────

@router.post("/workflows/seed", response_model=SeedResponse)
async def seed_workflows(
    db: DBSession,
    _current_user: AdminUser,
) -> SeedResponse:
    """Seed the 9 system workflow definitions (idempotent)."""
    inserted = await workflow_engine.seed_system_workflows(db)
    return SeedResponse(
        inserted=inserted,
        message=f"Seeded {inserted} workflow(s). Already existing workflows were skipped.",
    )


# ── Manual Trigger ────────────────────────────────────────────────────────────

@router.post("/workflows/trigger", response_model=ManualTriggerResponse)
async def manual_trigger(
    body: ManualTriggerRequest,
    db: DBSession,
    _current_user: ManagerUser,
) -> ManualTriggerResponse:
    """Manually fire a workflow trigger for testing."""
    try:
        trigger_type = TriggerType(body.trigger_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type '{body.trigger_type}'",
        )
    execution_ids = await workflow_engine.fire(
        trigger_type=trigger_type,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        trigger_data=body.trigger_data,
        db=db,
    )
    await db.commit()
    return ManualTriggerResponse(
        execution_ids=[str(eid) for eid in execution_ids],
        workflows_fired=len(execution_ids),
    )


# ── Execution History ─────────────────────────────────────────────────────────

@router.get("/workflows/executions", response_model=List[WorkflowExecutionRead])
async def list_executions(
    db: DBSession,
    _current_user: ManagerUser,
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[WorkflowExecutionRead]:
    """List recent workflow executions with optional filters."""
    stmt = (
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.action_logs))
        .order_by(WorkflowExecution.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if entity_type:
        stmt = stmt.where(WorkflowExecution.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(WorkflowExecution.entity_id == entity_id)
    if status_filter:
        stmt = stmt.where(WorkflowExecution.status == status_filter)
    result = await db.execute(stmt)
    return [_exec_to_read(ex) for ex in result.scalars().all()]


@router.get("/workflows/executions/{execution_id}", response_model=WorkflowExecutionRead)
async def get_execution(
    execution_id: UUID,
    db: DBSession,
    _current_user: CurrentUser,
) -> WorkflowExecutionRead:
    """Get full execution detail including action logs."""
    result = await db.execute(
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.action_logs))
        .where(WorkflowExecution.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _exec_to_read(ex)


# ── Workflow Definitions CRUD ─────────────────────────────────────────────────

@router.get("/workflows", response_model=List[WorkflowRead])
async def list_workflows(
    db: DBSession,
    _current_user: CurrentUser,
    active_only: bool = Query(default=False),
) -> List[WorkflowRead]:
    """List all workflow definitions."""
    stmt = select(WorkflowDefinition).order_by(
        WorkflowDefinition.is_system.desc(),
        WorkflowDefinition.created_at.asc(),
    )
    if active_only:
        stmt = stmt.where(WorkflowDefinition.is_active.is_(True))
    result = await db.execute(stmt)
    return [_wf_to_read(w) for w in result.scalars().all()]


@router.post("/workflows", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    db: DBSession,
    _current_user: ManagerUser,
) -> WorkflowRead:
    """Create a custom workflow definition."""
    try:
        TriggerType(body.trigger_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type '{body.trigger_type}'. Valid: {[t.value for t in TriggerType]}",
        )
    wf = WorkflowDefinition(
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        trigger_config=json.dumps(body.trigger_config),
        actions_json=json.dumps([a.model_dump() for a in body.actions]),
        is_active=body.is_active,
        is_system=False,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return _wf_to_read(wf)


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(
    workflow_id: UUID,
    db: DBSession,
    _current_user: CurrentUser,
) -> WorkflowRead:
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _wf_to_read(wf)


@router.put("/workflows/{workflow_id}", response_model=WorkflowRead)
async def update_workflow(
    workflow_id: UUID,
    body: WorkflowUpdate,
    db: DBSession,
    _current_user: ManagerUser,
) -> WorkflowRead:
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.trigger_config is not None:
        wf.trigger_config = json.dumps(body.trigger_config)
    if body.actions is not None:
        wf.actions_json = json.dumps([a.model_dump() for a in body.actions])
    if body.is_active is not None:
        wf.is_active = body.is_active

    await db.commit()
    await db.refresh(wf)
    return _wf_to_read(wf)


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_workflow(
    workflow_id: UUID,
    db: DBSession,
    _current_user: AdminUser,
) -> None:
    """Deactivate a workflow (system workflows cannot be hard-deleted)."""
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if wf.is_system:
        # For system workflows: deactivate instead of delete
        wf.is_active = False
        await db.commit()
        return

    await db.delete(wf)
    await db.commit()
