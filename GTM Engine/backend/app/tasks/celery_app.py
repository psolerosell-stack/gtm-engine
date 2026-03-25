from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "gtm_engine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.scoring", "app.tasks.briefing"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        # Recalculate all partner scores every hour
        "recalculate-all-scores": {
            "task": "app.tasks.scoring.recalculate_all_scores",
            "schedule": crontab(minute=0),
        },
        # Generate daily briefing at 8am Madrid time
        "generate-daily-briefing": {
            "task": "app.tasks.briefing.generate_daily_briefing",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)
