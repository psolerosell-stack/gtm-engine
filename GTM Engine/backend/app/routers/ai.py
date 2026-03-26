"""
AI Intelligence router — Layer 3.

Endpoints:
  POST /accounts/{id}/enrich           Queue background enrichment
  GET  /accounts/{id}/enrichment       Get enrichment status + results
  POST /accounts/{id}/signals          Detect signals (synchronous, fast)
  POST /partners/{id}/intelligence     Queue fit summary + approach
  POST /ai/discover                    Discover target companies
  GET  /ai/usage                       Usage stats (manager+)
  GET  /ai/logs                        Recent call log (admin)
"""
import json
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import AdminUser, CurrentUser, DBSession, ManagerUser
from app.models.account import Account
from app.models.ai_log import AICallLog
from app.models.partner import Partner
from app.schemas.ai import (
    AICallLogRead,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveredCompany,
    EnrichmentStatusResponse,
    EnrichRequest,
    IntelligenceRequest,
    IntelligenceResponse,
    SignalItem,
    SignalsResponse,
    UsageStatsResponse,
)
from app.services.ai import AIService, AIServiceUnavailableError

router = APIRouter(tags=["ai"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unavailable_error(exc: AIServiceUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"AI service unavailable: {exc}",
    )


# ── Account Enrichment ────────────────────────────────────────────────────────

@router.post(
    "/accounts/{account_id}/enrich",
    response_model=EnrichmentStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enrich_account(
    account_id: uuid.UUID,
    body: EnrichRequest,
    db: DBSession,
    _current_user: ManagerUser,
) -> EnrichmentStatusResponse:
    """
    Queue an AI enrichment job for an account.

    - If `force=False` and status is already 'done', returns current data without re-queuing.
    - Otherwise, sets status to 'pending' and dispatches a Celery task.
    """
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.enrichment_status == "done" and not body.force:
        enrichment_data = None
        if account.enrichment_data:
            try:
                enrichment_data = json.loads(account.enrichment_data)
            except json.JSONDecodeError:
                pass
        return EnrichmentStatusResponse(
            account_id=account_id,
            enrichment_status=account.enrichment_status,
            enrichment_data=enrichment_data,
            fit_summary=account.fit_summary,
            queued=False,
        )

    # Queue enrichment
    account.enrichment_status = "pending"
    await db.commit()

    try:
        from app.tasks.enrichment import enrich_account_task
        enrich_account_task.delay(str(account_id))
    except (ImportError, Exception):
        # Celery not available in local dev — skip background dispatch
        pass

    return EnrichmentStatusResponse(
        account_id=account_id,
        enrichment_status="pending",
        queued=True,
    )


@router.get(
    "/accounts/{account_id}/enrichment",
    response_model=EnrichmentStatusResponse,
)
async def get_enrichment_status(
    account_id: uuid.UUID,
    db: DBSession,
    _current_user: CurrentUser,
) -> EnrichmentStatusResponse:
    """Get the current enrichment status and results for an account."""
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    enrichment_data = None
    if account.enrichment_data:
        try:
            enrichment_data = json.loads(account.enrichment_data)
        except json.JSONDecodeError:
            pass

    return EnrichmentStatusResponse(
        account_id=account_id,
        enrichment_status=account.enrichment_status,
        enrichment_data=enrichment_data,
        fit_summary=account.fit_summary,
        queued=False,
    )


# ── Signal Detection (synchronous) ────────────────────────────────────────────

@router.post(
    "/accounts/{account_id}/signals",
    response_model=SignalsResponse,
)
async def detect_signals(
    account_id: uuid.UUID,
    db: DBSession,
    _current_user: ManagerUser,
) -> SignalsResponse:
    """Run synchronous signal detection for an account using Claude."""
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        service = AIService(db)
        signals = await service.detect_signals(account)
        await db.commit()
    except AIServiceUnavailableError as exc:
        raise _unavailable_error(exc)

    return SignalsResponse(
        account_id=account_id,
        signals=[SignalItem(**s) for s in signals],
    )


# ── Partner Intelligence ──────────────────────────────────────────────────────

@router.post(
    "/partners/{partner_id}/intelligence",
    response_model=IntelligenceResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_partner_intelligence(
    partner_id: uuid.UUID,
    body: IntelligenceRequest,
    db: DBSession,
    _current_user: ManagerUser,
) -> IntelligenceResponse:
    """
    Queue AI-generated fit summary and approach suggestion for a partner.

    - If `force=False` and fit_summary already exists, returns current data.
    - Otherwise dispatches a Celery background task.
    """
    result = await db.execute(
        select(Partner).where(Partner.id == partner_id, Partner.deleted_at.is_(None))
    )
    partner = result.scalar_one_or_none()
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")

    if partner.fit_summary and not body.force:
        return IntelligenceResponse(
            partner_id=partner_id,
            fit_summary=partner.fit_summary,
            approach_suggestion=partner.approach_suggestion,
            queued=False,
        )

    try:
        from app.tasks.enrichment import generate_partner_intelligence as gpi_task
        gpi_task.delay(str(partner_id))
    except (ImportError, Exception):
        pass  # Celery optional in local dev

    return IntelligenceResponse(
        partner_id=partner_id,
        fit_summary=partner.fit_summary,
        approach_suggestion=partner.approach_suggestion,
        queued=True,
    )


# ── Account Discovery ─────────────────────────────────────────────────────────

@router.post(
    "/ai/discover",
    response_model=DiscoverResponse,
)
async def discover_accounts(
    body: DiscoverRequest,
    db: DBSession,
    _current_user: ManagerUser,
) -> DiscoverResponse:
    """
    Given a natural language partner profile description, return a list of
    10-20 suggested companies to research as potential partners.
    """
    try:
        service = AIService(db)
        companies = await service.discover_accounts(body.profile, count=body.count)
        await db.commit()
    except AIServiceUnavailableError as exc:
        raise _unavailable_error(exc)

    return DiscoverResponse(
        profile=body.profile,
        count_requested=body.count,
        companies=[DiscoveredCompany(**c) for c in companies],
    )


# ── Usage Stats ───────────────────────────────────────────────────────────────

@router.get(
    "/ai/usage",
    response_model=UsageStatsResponse,
)
async def get_usage_stats(
    db: DBSession,
    _current_user: ManagerUser,
    days: int = Query(default=30, ge=1, le=365),
) -> UsageStatsResponse:
    """Return aggregated Claude API usage stats for the last N days."""
    service = AIService(db)
    stats = await service.get_usage_stats(days=days)
    return UsageStatsResponse(**stats)


# ── Call Log (admin) ──────────────────────────────────────────────────────────

@router.get(
    "/ai/logs",
    response_model=List[AICallLogRead],
)
async def get_call_logs(
    db: DBSession,
    _current_user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[AICallLogRead]:
    """List recent AI call log entries (admin only)."""
    result = await db.execute(
        select(AICallLog)
        .order_by(AICallLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    return [AICallLogRead.model_validate(r) for r in rows]
