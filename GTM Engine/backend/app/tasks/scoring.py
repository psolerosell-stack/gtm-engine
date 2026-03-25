import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Helper to run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _recalculate_all_async() -> dict:
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.partner import Partner
    from app.services.partner import PartnerService

    factory = get_session_factory()
    results = {"success": 0, "failed": 0, "skipped": 0}

    async with factory() as db:
        result = await db.execute(
            select(Partner.id).where(Partner.deleted_at.is_(None))
        )
        partner_ids = [row[0] for row in result.all()]

    for partner_id in partner_ids:
        try:
            async with factory() as db:
                service = PartnerService(db)
                await service.recalculate_score(partner_id)
            results["success"] += 1
        except Exception as exc:
            logger.error("score_recalc_failed", partner_id=str(partner_id), error=str(exc))
            results["failed"] += 1

    logger.info("score_recalc_complete", **results)
    return results


@celery_app.task(name="app.tasks.scoring.recalculate_all_scores", bind=True, max_retries=3)
def recalculate_all_scores(self) -> dict:
    """Idempotent task: recalculate ICP scores for all active partners."""
    try:
        return _run_async(_recalculate_all_async())
    except Exception as exc:
        logger.exception("recalculate_all_scores_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60) from exc


@celery_app.task(name="app.tasks.scoring.recalculate_partner_score", bind=True, max_retries=3)
def recalculate_partner_score(self, partner_id: str) -> dict:
    """Recalculate score for a single partner (triggered on update)."""
    import uuid

    async def _run():
        from app.database import get_session_factory
        from app.services.partner import PartnerService

        factory = get_session_factory()
        async with factory() as db:
            service = PartnerService(db)
            result = await service.recalculate_score(uuid.UUID(partner_id))
            if result is None:
                return {"status": "not_found", "partner_id": partner_id}
            score, tier = result
            return {"status": "ok", "partner_id": partner_id, "score": score, "tier": tier}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("recalculate_partner_score_failed", partner_id=partner_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc
