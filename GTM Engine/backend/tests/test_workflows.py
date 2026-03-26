"""
Layer 4 tests — Workflow Orchestrator.

Tests cover:
- Trigger condition evaluation
- Engine.fire() creating executions
- Engine.execute() running actions and updating logs
- Action implementations (log_activity, create_task, update_partner_field, create_revenue_record)
- HTTP endpoints (CRUD, seed, manual trigger, execution list)
- Integration: partner_created fires after PartnerService.create()
- Integration: deal_closed_won fires after OpportunityService.update()
"""
import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.partner import Partner
from app.models.workflow import WorkflowActionLog, WorkflowDefinition, WorkflowExecution
from app.services.workflow.engine import WorkflowEngine, workflow_engine
from app.services.workflow.triggers import TriggerType, evaluate_trigger_conditions


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_account(db_session: AsyncSession) -> Account:
    account = Account(
        name="Workflow Test Account",
        industry="Manufacturing",
        geography="Spain",
        erp_ecosystem="sage_200",
        size=20,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def seeded_partner(db_session: AsyncSession, seeded_account: Account) -> Partner:
    partner = Partner(
        account_id=seeded_account.id,
        type="VAR",
        geography="Spain",
        vertical="Manufacturing",
        capacity_commercial=2.0,
        capacity_functional=2.0,
        capacity_technical=1.5,
        capacity_integration=1.0,
        arr_potential=25000.0,
        activation_velocity=45,
        icp_score=60.0,
        tier="silver",
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)
    return partner


@pytest_asyncio.fixture
async def seeded_opportunity(
    db_session: AsyncSession, seeded_account: Account, seeded_partner: Partner
) -> Opportunity:
    opp = Opportunity(
        account_id=seeded_account.id,
        partner_id=seeded_partner.id,
        name="Test Opportunity",
        stage=OpportunityStage.prospecting,
        arr_value=20000.0,
        currency="EUR",
        owner="test@gtm.io",
    )
    db_session.add(opp)
    await db_session.commit()
    await db_session.refresh(opp)
    return opp


@pytest_asyncio.fixture
async def simple_workflow(db_session: AsyncSession) -> WorkflowDefinition:
    """A minimal workflow with one log_activity action."""
    wf = WorkflowDefinition(
        name="Test: Partner Created",
        description="Test workflow",
        trigger_type="partner_created",
        trigger_config="{}",
        actions_json=json.dumps([
            {
                "sequence": 1,
                "type": "log_activity",
                "config": {
                    "activity_type": "note",
                    "notes": "Workflow fired for entity_type={entity_type}",
                },
            }
        ]),
        is_active=True,
        is_system=False,
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf


@pytest_asyncio.fixture
async def score_threshold_workflow(db_session: AsyncSession) -> WorkflowDefinition:
    wf = WorkflowDefinition(
        name="Test: Score Threshold",
        trigger_type="score_threshold_reached",
        trigger_config=json.dumps({"threshold": 70}),
        actions_json=json.dumps([
            {"sequence": 1, "type": "create_task", "config": {"title": "Activate partner!"}}
        ]),
        is_active=True,
        is_system=False,
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf


# ── Unit tests: trigger evaluation ────────────────────────────────────────────

def test_score_threshold_fires_when_crossing_upward():
    result = evaluate_trigger_conditions(
        TriggerType.score_threshold_reached,
        {"threshold": 70},
        {"score": 75, "previous_score": 65},
    )
    assert result is True


def test_score_threshold_no_fire_already_above():
    result = evaluate_trigger_conditions(
        TriggerType.score_threshold_reached,
        {"threshold": 70},
        {"score": 80, "previous_score": 72},  # was already above 70
    )
    assert result is False


def test_score_threshold_no_fire_below():
    result = evaluate_trigger_conditions(
        TriggerType.score_threshold_reached,
        {"threshold": 70},
        {"score": 65, "previous_score": 60},
    )
    assert result is False


def test_stage_change_specific_stage_match():
    result = evaluate_trigger_conditions(
        TriggerType.opportunity_stage_changed,
        {"stage": "closed_won"},
        {"new_stage": "closed_won"},
    )
    assert result is True


def test_stage_change_specific_stage_no_match():
    result = evaluate_trigger_conditions(
        TriggerType.opportunity_stage_changed,
        {"stage": "closed_won"},
        {"new_stage": "demo"},
    )
    assert result is False


def test_stage_change_any_stage():
    result = evaluate_trigger_conditions(
        TriggerType.opportunity_stage_changed,
        {},
        {"new_stage": "demo"},
    )
    assert result is True


def test_partner_inactive_threshold():
    assert evaluate_trigger_conditions(
        TriggerType.partner_inactive, {"days": 14}, {"inactive_days": 15}
    ) is True
    assert evaluate_trigger_conditions(
        TriggerType.partner_inactive, {"days": 14}, {"inactive_days": 10}
    ) is False


def test_partner_not_converted_threshold():
    assert evaluate_trigger_conditions(
        TriggerType.partner_not_converted, {"days": 60}, {"days_pending": 61}
    ) is True
    assert evaluate_trigger_conditions(
        TriggerType.partner_not_converted, {"days": 60}, {"days_pending": 30}
    ) is False


def test_unconditional_triggers_always_true():
    for tt in [TriggerType.partner_created, TriggerType.deal_closed_won,
               TriggerType.deal_closed_lost, TriggerType.lead_from_partner,
               TriggerType.onboarding_completed]:
        assert evaluate_trigger_conditions(tt, {}, {}) is True


# ── Unit tests: engine.fire() ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fire_creates_execution(
    db_session: AsyncSession,
    simple_workflow: WorkflowDefinition,
    seeded_partner: Partner,
):
    """engine.fire() creates a WorkflowExecution record."""
    engine = WorkflowEngine()
    execution_ids = await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"partner_id": str(seeded_partner.id)},
        db=db_session,
    )
    await db_session.commit()

    assert len(execution_ids) == 1
    result = await db_session.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_ids[0])
    )
    ex = result.scalar_one()
    assert ex.entity_type == "partner"
    assert ex.status == "pending"
    assert ex.workflow_id == simple_workflow.id


@pytest.mark.asyncio
async def test_fire_skips_inactive_workflow(
    db_session: AsyncSession,
    seeded_partner: Partner,
):
    """Inactive workflows are not executed."""
    wf = WorkflowDefinition(
        name="Inactive Workflow",
        trigger_type="partner_created",
        trigger_config="{}",
        actions_json="[]",
        is_active=False,
    )
    db_session.add(wf)
    await db_session.commit()

    engine = WorkflowEngine()
    execution_ids = await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={},
        db=db_session,
    )
    assert len(execution_ids) == 0


@pytest.mark.asyncio
async def test_fire_respects_trigger_conditions(
    db_session: AsyncSession,
    score_threshold_workflow: WorkflowDefinition,
    seeded_partner: Partner,
):
    """score_threshold_reached only fires when score crosses threshold upward."""
    engine = WorkflowEngine()

    # Score goes from 65 to 75 — should fire
    ids = await engine.fire(
        trigger_type=TriggerType.score_threshold_reached,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"score": 75, "previous_score": 65},
        db=db_session,
    )
    assert len(ids) == 1

    # Score was already above 70 — should NOT fire
    ids = await engine.fire(
        trigger_type=TriggerType.score_threshold_reached,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"score": 80, "previous_score": 72},
        db=db_session,
    )
    assert len(ids) == 0


# ── Unit tests: engine.execute() ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_log_activity_action(
    db_session: AsyncSession,
    simple_workflow: WorkflowDefinition,
    seeded_partner: Partner,
):
    """Executing a log_activity action creates an Activity and logs the action."""
    from app.models.activity import Activity

    engine = WorkflowEngine()
    ids = await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"entity_type": "partner"},
        db=db_session,
    )
    await db_session.commit()

    execution_id = ids[0]
    await engine.execute(execution_id, db_session)

    # Check execution is completed
    result = await db_session.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    )
    ex = result.scalar_one()
    assert ex.status == "completed"
    assert ex.actions_completed == 1

    # Check action log
    log_result = await db_session.execute(
        select(WorkflowActionLog).where(WorkflowActionLog.execution_id == execution_id)
    )
    log = log_result.scalar_one()
    assert log.status == "completed"
    assert log.action_type == "log_activity"

    # Check Activity was created
    act_result = await db_session.execute(
        select(Activity).where(
            Activity.entity_type == "partner",
            Activity.entity_id == seeded_partner.id,
        )
    )
    activity = act_result.scalar_one()
    assert activity.type == "note"
    assert "partner" in activity.notes


@pytest.mark.asyncio
async def test_execute_create_task_action(
    db_session: AsyncSession,
    seeded_partner: Partner,
):
    """create_task action creates a task-type Activity."""
    from app.models.activity import Activity

    wf = WorkflowDefinition(
        name="Test: Create Task",
        trigger_type="partner_created",
        trigger_config="{}",
        actions_json=json.dumps([
            {"sequence": 1, "type": "create_task", "config": {"title": "Test task {entity_type}"}}
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    engine = WorkflowEngine()
    ids = await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"entity_type": "partner"},
        db=db_session,
    )
    await db_session.commit()
    await engine.execute(ids[0], db_session)

    result = await db_session.execute(
        select(Activity).where(
            Activity.entity_type == "partner",
            Activity.entity_id == seeded_partner.id,
            Activity.type == "task",
        )
    )
    task = result.scalar_one()
    assert "partner" in task.notes


@pytest.mark.asyncio
async def test_execute_update_partner_field(
    db_session: AsyncSession,
    seeded_partner: Partner,
):
    """update_partner_field action sets partner fields."""
    wf = WorkflowDefinition(
        name="Test: Update Partner Field",
        trigger_type="onboarding_completed",
        trigger_config="{}",
        actions_json=json.dumps([
            {
                "sequence": 1,
                "type": "update_partner_field",
                "config": {"fields": {"status": "active"}},
            }
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    engine = WorkflowEngine()
    ids = await engine.fire(
        trigger_type=TriggerType.onboarding_completed,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={},
        db=db_session,
    )
    await db_session.commit()
    await engine.execute(ids[0], db_session)

    await db_session.refresh(seeded_partner)
    assert seeded_partner.status == "active"


@pytest.mark.asyncio
async def test_execute_creates_revenue_record(
    db_session: AsyncSession,
    seeded_opportunity: Opportunity,
):
    """create_revenue_record action creates a Revenue entry from an opportunity."""
    from app.models.revenue import Revenue

    wf = WorkflowDefinition(
        name="Test: Revenue Record",
        trigger_type="deal_closed_won",
        trigger_config="{}",
        actions_json=json.dumps([
            {"sequence": 1, "type": "create_revenue_record", "config": {}}
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    engine = WorkflowEngine()
    ids = await engine.fire(
        trigger_type=TriggerType.deal_closed_won,
        entity_type="opportunity",
        entity_id=seeded_opportunity.id,
        trigger_data={"opportunity_id": str(seeded_opportunity.id)},
        db=db_session,
    )
    await db_session.commit()
    await engine.execute(ids[0], db_session)

    result = await db_session.execute(
        select(Revenue).where(Revenue.opportunity_id == seeded_opportunity.id)
    )
    revenue = result.scalar_one()
    assert revenue.arr == 20000.0


@pytest.mark.asyncio
async def test_execute_slack_skipped_when_not_configured(
    db_session: AsyncSession,
    seeded_partner: Partner,
):
    """slack_notify action marks as 'skipped' when Slack is not configured."""
    wf = WorkflowDefinition(
        name="Test: Slack",
        trigger_type="partner_created",
        trigger_config="{}",
        actions_json=json.dumps([
            {"sequence": 1, "type": "slack_notify", "config": {"message": "Hello!"}}
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    engine = WorkflowEngine()
    ids = await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={},
        db=db_session,
    )
    await db_session.commit()
    await engine.execute(ids[0], db_session)

    log_result = await db_session.execute(
        select(WorkflowActionLog).where(
            WorkflowActionLog.execution_id == ids[0],
            WorkflowActionLog.action_type == "slack_notify",
        )
    )
    log = log_result.scalar_one()
    # Should be skipped (no key) or completed — either is acceptable
    assert log.status in ("skipped", "completed")


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate_daily_execution(
    db_session: AsyncSession,
    seeded_partner: Partner,
):
    """Firing the same scheduled trigger twice with the same day key only creates one execution."""
    wf = WorkflowDefinition(
        name="Test: Idempotent",
        trigger_type="partner_inactive",
        trigger_config=json.dumps({"days": 14}),
        actions_json=json.dumps([
            {"sequence": 1, "type": "log_activity", "config": {"notes": "Inactive alert"}}
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    engine = WorkflowEngine()
    today = "2026-03-26"

    ids1 = await engine.fire(
        trigger_type=TriggerType.partner_inactive,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"inactive_days": 15},
        db=db_session,
        idempotency_day=today,
    )
    await db_session.commit()

    ids2 = await engine.fire(
        trigger_type=TriggerType.partner_inactive,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"inactive_days": 15},
        db=db_session,
        idempotency_day=today,
    )
    await db_session.commit()

    assert len(ids1) == 1
    assert len(ids2) == 0  # deduplicated


# ── Integration tests: trigger wiring ────────────────────────────────────────

@pytest.mark.asyncio
async def test_partner_service_fires_partner_created_trigger(
    db_session: AsyncSession,
    seeded_account: Account,
    simple_workflow: WorkflowDefinition,
):
    """PartnerService.create() fires the partner_created trigger."""
    from app.schemas.partner import PartnerCreate
    from app.services.partner import PartnerService

    service = PartnerService(db_session)
    partner = await service.create(
        PartnerCreate(
            account_id=seeded_account.id,
            type="VAR",
            geography="Spain",
            capacity_commercial=1.0,
            capacity_functional=1.0,
            capacity_technical=1.0,
            capacity_integration=1.0,
        )
    )

    # Give the trigger a moment to flush
    result = await db_session.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.entity_id == partner.id,
            WorkflowExecution.trigger_type == "partner_created",
        )
    )
    ex = result.scalar_one_or_none()
    assert ex is not None, "partner_created execution was not created"


@pytest.mark.asyncio
async def test_opportunity_service_fires_stage_changed_trigger(
    db_session: AsyncSession,
    seeded_opportunity: Opportunity,
):
    """OpportunityService.update() fires opportunity_stage_changed trigger when stage changes."""
    wf = WorkflowDefinition(
        name="Stage Changed WF",
        trigger_type="opportunity_stage_changed",
        trigger_config="{}",
        actions_json=json.dumps([
            {"sequence": 1, "type": "log_activity", "config": {"notes": "Stage changed"}}
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    from app.schemas.opportunity import OpportunityUpdate
    from app.services.opportunity import OpportunityService

    service = OpportunityService(db_session)
    await service.update(seeded_opportunity.id, OpportunityUpdate(stage="demo"))

    result = await db_session.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.entity_id == seeded_opportunity.id,
            WorkflowExecution.trigger_type == "opportunity_stage_changed",
        )
    )
    ex = result.scalar_one_or_none()
    assert ex is not None


@pytest.mark.asyncio
async def test_opportunity_service_fires_deal_closed_won(
    db_session: AsyncSession,
    seeded_opportunity: Opportunity,
):
    """OpportunityService fires deal_closed_won trigger on closed_won transition."""
    wf = WorkflowDefinition(
        name="Closed Won WF",
        trigger_type="deal_closed_won",
        trigger_config="{}",
        actions_json=json.dumps([
            {"sequence": 1, "type": "log_activity", "config": {"notes": "Deal won!"}}
        ]),
        is_active=True,
    )
    db_session.add(wf)
    await db_session.commit()

    from app.schemas.opportunity import OpportunityUpdate
    from app.services.opportunity import OpportunityService

    service = OpportunityService(db_session)
    await service.update(seeded_opportunity.id, OpportunityUpdate(stage="closed_won"))

    result = await db_session.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.entity_id == seeded_opportunity.id,
            WorkflowExecution.trigger_type == "deal_closed_won",
        )
    )
    ex = result.scalar_one_or_none()
    assert ex is not None


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_workflows_endpoint(client: AsyncClient, auth_headers: dict):
    """POST /workflows/seed creates the 9 system workflows (admin required)."""
    # First register an admin user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@gtm.io",
            "password": "adminpassword123",
            "full_name": "Admin User",
            "role": "admin",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@gtm.io", "password": "adminpassword123"},
    )
    admin_token = resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post("/api/v1/workflows/seed", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 9

    # Calling again is idempotent
    resp2 = await client.post("/api/v1/workflows/seed", headers=admin_headers)
    assert resp2.json()["inserted"] == 0


@pytest.mark.asyncio
async def test_list_workflows(client: AsyncClient, auth_headers: dict, simple_workflow):
    resp = await client.get("/api/v1/workflows", headers=auth_headers)
    assert resp.status_code == 200
    workflows = resp.json()
    assert len(workflows) >= 1
    assert any(w["name"] == "Test: Partner Created" for w in workflows)


@pytest.mark.asyncio
async def test_create_workflow(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/workflows",
        json={
            "name": "My Custom Workflow",
            "trigger_type": "partner_created",
            "trigger_config": {},
            "actions": [
                {"sequence": 1, "type": "log_activity", "config": {"notes": "Custom note"}}
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Custom Workflow"
    assert data["is_system"] is False


@pytest.mark.asyncio
async def test_create_workflow_invalid_trigger(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Bad Workflow",
            "trigger_type": "nonexistent_trigger",
            "trigger_config": {},
            "actions": [{"sequence": 1, "type": "log_activity", "config": {}}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_manual_trigger(
    client: AsyncClient,
    auth_headers: dict,
    simple_workflow: WorkflowDefinition,
    seeded_partner: Partner,
):
    """POST /workflows/trigger manually fires a workflow."""
    resp = await client.post(
        "/api/v1/workflows/trigger",
        json={
            "trigger_type": "partner_created",
            "entity_type": "partner",
            "entity_id": str(seeded_partner.id),
            "trigger_data": {"entity_type": "partner"},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflows_fired"] >= 1
    assert len(data["execution_ids"]) >= 1


@pytest.mark.asyncio
async def test_list_executions(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    simple_workflow: WorkflowDefinition,
    seeded_partner: Partner,
):
    # Create an execution
    engine = WorkflowEngine()
    await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={},
        db=db_session,
    )
    await db_session.commit()

    resp = await client.get("/api/v1/workflows/executions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["entity_type"] == "partner"


@pytest.mark.asyncio
async def test_get_execution_detail(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    simple_workflow: WorkflowDefinition,
    seeded_partner: Partner,
):
    """GET /workflows/executions/{id} returns action logs."""
    engine = WorkflowEngine()
    ids = await engine.fire(
        trigger_type=TriggerType.partner_created,
        entity_type="partner",
        entity_id=seeded_partner.id,
        trigger_data={"entity_type": "partner"},
        db=db_session,
    )
    await db_session.commit()
    await engine.execute(ids[0], db_session)

    resp = await client.get(f"/api/v1/workflows/executions/{ids[0]}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["action_logs"]) == 1
    assert data["action_logs"][0]["status"] == "completed"
