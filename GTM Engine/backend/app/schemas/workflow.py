from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── Action step (used in create/read) ────────────────────────────────────────

class WorkflowActionStep(BaseSchema):
    sequence: int
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)


# ── Workflow Definition ───────────────────────────────────────────────────────

class WorkflowCreate(BaseSchema):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    actions: List[WorkflowActionStep] = Field(..., min_length=1)
    is_active: bool = True


class WorkflowUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    actions: Optional[List[WorkflowActionStep]] = None
    is_active: Optional[bool] = None


class WorkflowRead(BaseSchema):
    id: UUID
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any]
    actions: List[WorkflowActionStep]
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime


# ── Workflow Execution ────────────────────────────────────────────────────────

class WorkflowActionLogRead(BaseSchema):
    id: UUID
    action_type: str
    action_config: Dict[str, Any]
    sequence: int
    status: str
    result_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class WorkflowExecutionRead(BaseSchema):
    id: UUID
    workflow_id: UUID
    entity_type: str
    entity_id: UUID
    trigger_type: str
    trigger_data: Dict[str, Any]
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    actions_total: int
    actions_completed: int
    created_at: datetime
    action_logs: List[WorkflowActionLogRead] = Field(default_factory=list)


# ── Manual Trigger ────────────────────────────────────────────────────────────

class ManualTriggerRequest(BaseSchema):
    trigger_type: str
    entity_type: str
    entity_id: UUID
    trigger_data: Dict[str, Any] = Field(default_factory=dict)


class ManualTriggerResponse(BaseSchema):
    execution_ids: List[str]
    workflows_fired: int


# ── Seed response ─────────────────────────────────────────────────────────────

class SeedResponse(BaseSchema):
    inserted: int
    message: str
