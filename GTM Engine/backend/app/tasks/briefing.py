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


@celery_app.task(name="app.tasks.briefing.generate_daily_briefing", bind=True, max_retries=2)
def generate_daily_briefing(self) -> dict:
    """Generate and store the daily GTM briefing. Idempotent — skips if already generated today."""

    async def _run():
        from datetime import date

        from sqlalchemy import select

        from app.database import get_session_factory
        from app.models.analytics import DailyBriefing

        today = date.today().isoformat()
        factory = get_session_factory()

        async with factory() as db:
            existing = await db.execute(
                select(DailyBriefing).where(DailyBriefing.date == today)
            )
            if existing.scalar_one_or_none():
                logger.info("daily_briefing_already_exists", date=today)
                return {"status": "skipped", "date": today}

        import json

        async with factory() as db:
            from app.services.analytics import AnalyticsService
            svc = AnalyticsService(db)
            data = await svc.get_briefing_data()

            content: str
            try:
                from app.services.ai import AIService
                from app.routers.analytics import _build_briefing_prompt, _data_summary
                ai = AIService(db)
                prompt = _build_briefing_prompt(data)
                narrative = await ai._call_claude(
                    prompt=prompt,
                    purpose="daily_briefing",
                    entity_type="system",
                    max_tokens=2000,
                )
                content = json.dumps({"narrative": narrative, "data_snapshot": _data_summary(data)})
            except Exception as ai_exc:
                logger.warning("briefing_task_ai_skipped", reason=str(ai_exc))
                from app.routers.analytics import _data_summary
                content = json.dumps({"narrative": None, "data_snapshot": _data_summary(data)})

            briefing = DailyBriefing(date=today, content=content)
            db.add(briefing)
            await db.commit()

        logger.info("daily_briefing_generated", date=today)
        return {"status": "ok", "date": today}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("generate_daily_briefing_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300) from exc
