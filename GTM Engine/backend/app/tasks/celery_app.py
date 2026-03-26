from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "gtm_engine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.scoring", "app.tasks.briefing", "app.tasks.workflow", "app.tasks.enrichment"],
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
        # Check partner inactivity daily at 7am
        "check-partner-inactivity": {
            "task": "app.tasks.workflow.check_partner_inactivity",
            "schedule": crontab(hour=7, minute=0),
        },
        # Check partners not converted daily at 7:05am
        "check-partners-not-converted": {
            "task": "app.tasks.workflow.check_partners_not_converted",
            "schedule": crontab(hour=7, minute=5),
        },
    },
)
