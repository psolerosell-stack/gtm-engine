"""
Celery tasks for background AI enrichment — Layer 3.

Tasks:
  enrich_account_task        — enrich a single account (status: pending→running→done/failed)
  generate_partner_intelligence — fit summary + approach for a single partner
"""
import asyncio
import json

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Account Enrichment ────────────────────────────────────────────────────────

async def _enrich_account_async(account_id: str) -> dict:
    import uuid

    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.account import Account
    from app.services.ai import AIService, AIServiceUnavailableError

    pid = uuid.UUID(account_id)
    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(
            select(Account).where(Account.id == pid, Account.deleted_at.is_(None))
        )
        account = result.scalar_one_or_none()
        if account is None:
            return {"status": "not_found", "account_id": account_id}

        # Mark as running
        account.enrichment_status = "running"
        await db.commit()

    async with factory() as db:
        result = await db.execute(
            select(Account).where(Account.id == pid)
        )
        account = result.scalar_one()

        try:
            service = AIService(db)
            enrichment = await service.enrich_account(account)

            # Apply extracted fields back to the account
            if isinstance(enrichment, dict) and "parse_error" not in enrichment:
                if enrichment.get("size_estimate") is not None:
                    account.size = int(enrichment["size_estimate"])
                if enrichment.get("industry"):
                    account.industry = enrichment["industry"]
                if enrichment.get("geography"):
                    account.geography = enrichment["geography"]
                if enrichment.get("erp_ecosystem"):
                    account.erp_ecosystem = enrichment["erp_ecosystem"]
                if enrichment.get("description"):
                    account.description = enrichment["description"]
                if enrichment.get("fit_summary"):
                    account.fit_summary = enrichment["fit_summary"]

            account.enrichment_data = json.dumps(enrichment)
            account.enrichment_status = "done"
            await db.commit()

            logger.info("account_enrichment_done", account_id=account_id)
            return {"status": "done", "account_id": account_id}

        except AIServiceUnavailableError as exc:
            account.enrichment_status = "failed"
            account.enrichment_data = json.dumps({"error": str(exc)})
            await db.commit()
            logger.warning("account_enrichment_unavailable", account_id=account_id, error=str(exc))
            return {"status": "failed", "error": str(exc), "account_id": account_id}

        except Exception as exc:
            account.enrichment_status = "failed"
            account.enrichment_data = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
            await db.commit()
            logger.error("account_enrichment_failed", account_id=account_id, error=str(exc))
            raise


@celery_app.task(
    name="app.tasks.enrichment.enrich_account_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def enrich_account_task(self, account_id: str) -> dict:
    """Background task: enrich an account with Claude AI."""
    try:
        return _run_async(_enrich_account_async(account_id))
    except Exception as exc:
        logger.exception("enrich_account_task_failed", account_id=account_id, error=str(exc))
        raise self.retry(exc=exc) from exc


# ── Partner Intelligence ──────────────────────────────────────────────────────

async def _partner_intelligence_async(partner_id: str) -> dict:
    import uuid

    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.account import Account
    from app.models.partner import Partner
    from app.services.ai import AIService, AIServiceUnavailableError
    from app.services.scoring import engine as scoring_engine

    pid = uuid.UUID(partner_id)
    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(
            select(Partner).where(Partner.id == pid, Partner.deleted_at.is_(None))
        )
        partner = result.scalar_one_or_none()
        if partner is None:
            return {"status": "not_found", "partner_id": partner_id}

        account_result = await db.execute(
            select(Account).where(Account.id == partner.account_id)
        )
        account = account_result.scalar_one_or_none()
        if account is None:
            return {"status": "account_not_found", "partner_id": partner_id}

        try:
            weights = await scoring_engine.load_active_weights(db)
            _score, score_breakdown = scoring_engine.score(partner, account, weights)

            service = AIService(db)

            fit_summary = await service.generate_fit_summary(partner, account, score_breakdown)
            approach = await service.suggest_approach(partner, account, score_breakdown)

            partner.fit_summary = fit_summary.strip()
            partner.approach_suggestion = approach.strip()
            await db.commit()

            logger.info("partner_intelligence_done", partner_id=partner_id)
            return {"status": "done", "partner_id": partner_id}

        except AIServiceUnavailableError as exc:
            logger.warning("partner_intelligence_unavailable", partner_id=partner_id, error=str(exc))
            return {"status": "failed", "error": str(exc), "partner_id": partner_id}

        except Exception as exc:
            logger.error("partner_intelligence_failed", partner_id=partner_id, error=str(exc))
            raise


@celery_app.task(
    name="app.tasks.enrichment.generate_partner_intelligence",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_partner_intelligence(self, partner_id: str) -> dict:
    """Background task: generate fit summary and approach for a partner."""
    try:
        return _run_async(_partner_intelligence_async(partner_id))
    except Exception as exc:
        logger.exception(
            "generate_partner_intelligence_failed", partner_id=partner_id, error=str(exc)
        )
        raise self.retry(exc=exc) from exc
