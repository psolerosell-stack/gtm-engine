import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import create_all_tables, dispose_engine

# Configure structlog before anything else
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if settings.is_development else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(settings.log_level),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def _seed_defaults() -> None:
    """Seed default pipeline stages and app settings (idempotent)."""
    import json
    from sqlalchemy import select
    from app.database import get_session_factory
    from app.models.settings import AppSetting, PipelineStage, OnboardingStep

    DEFAULT_STAGES = [
        {"name": "Prospecting",   "slug": "prospecting",   "probability": 10, "color": "#6B7280", "rotting_days": 30,  "is_won": False, "is_lost": False},
        {"name": "Qualification", "slug": "qualification", "probability": 25, "color": "#3B82F6", "rotting_days": 21,  "is_won": False, "is_lost": False},
        {"name": "Discovery",     "slug": "discovery",     "probability": 40, "color": "#8B5CF6", "rotting_days": 21,  "is_won": False, "is_lost": False},
        {"name": "Demo",          "slug": "demo",          "probability": 60, "color": "#F59E0B", "rotting_days": 14,  "is_won": False, "is_lost": False},
        {"name": "Proposal",      "slug": "proposal",      "probability": 75, "color": "#EF4444", "rotting_days": 14,  "is_won": False, "is_lost": False},
        {"name": "Negotiation",   "slug": "negotiation",   "probability": 90, "color": "#EC4899", "rotting_days": 10,  "is_won": False, "is_lost": False},
        {"name": "Closed Won",    "slug": "closed_won",    "probability": 100,"color": "#10B981", "rotting_days": None,"is_won": True,  "is_lost": False},
        {"name": "Closed Lost",   "slug": "closed_lost",   "probability": 0,  "color": "#374151", "rotting_days": None,"is_won": False, "is_lost": True},
    ]

    DEFAULT_SETTINGS = {
        "icp_weights": {
            "erp_ecosystem_fit": 0.20,
            "partner_type_match": 0.15,
            "capacity_score": 0.15,
            "geography_match": 0.10,
            "vertical_fit": 0.10,
            "company_size": 0.10,
            "arr_potential": 0.10,
            "activation_velocity": 0.10,
        },
        "company_context": "",
        "tier_thresholds": {"platinum": 85, "gold": 70, "silver": 50},
        "partner_types": ["Referral", "Reseller", "VAR", "Delivery"],
        "alerts": {
            "rotting_deal": {"enabled": True, "channel": "in_app"},
            "score_drop": {"enabled": True, "threshold": 10, "channel": "in_app"},
            "tier_change": {"enabled": True, "channel": "in_app"},
            "onboarding_stalled": {"enabled": True, "days": 7, "channel": "in_app"},
        },
    }

    DEFAULT_ONBOARDING_STEPS = [
        {"name": "Contrato firmado",          "description": "El acuerdo de partner está firmado y archivado.", "position": 0},
        {"name": "Acceso al portal",          "description": "Partner tiene acceso al portal de partners.",       "position": 1},
        {"name": "Sesión de kickoff",         "description": "Primera reunión de alineación completada.",         "position": 2},
        {"name": "Formación de producto",     "description": "El partner ha completado la formación inicial.",   "position": 3},
        {"name": "Demo técnica validada",     "description": "El partner puede realizar una demo autónoma.",     "position": 4},
        {"name": "Primera oportunidad abierta","description": "Al menos una oportunidad registrada en el CRM.",  "position": 5},
    ]

    factory = get_session_factory()
    async with factory() as db:
        # Seed pipeline stages
        for i, s in enumerate(DEFAULT_STAGES):
            result = await db.execute(select(PipelineStage).where(PipelineStage.slug == s["slug"]))
            if result.scalar_one_or_none() is None:
                db.add(PipelineStage(position=i, required_fields="[]", **s))

        # Seed default settings (only if key doesn't exist)
        for key, value in DEFAULT_SETTINGS.items():
            result = await db.execute(select(AppSetting).where(AppSetting.key == key))
            if result.scalar_one_or_none() is None:
                db.add(AppSetting(key=key, value=json.dumps(value)))

        # Seed default onboarding steps
        for s in DEFAULT_ONBOARDING_STEPS:
            result = await db.execute(select(OnboardingStep).where(OnboardingStep.name == s["name"]))
            if result.scalar_one_or_none() is None:
                db.add(OnboardingStep(is_required=True, is_active=True, **s))

        await db.commit()
    logger.info("defaults_seeded")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("gtm_engine_starting", env=settings.app_env, version=settings.app_version)

    # In dev / SQLite mode, auto-create tables (Alembic handles Postgres migrations)
    if "sqlite" in settings.database_url:
        await create_all_tables()
        logger.info("sqlite_tables_created")

    # Seed the 9 system workflow definitions (idempotent)
    try:
        from app.database import get_session_factory
        from app.services.workflow.engine import workflow_engine as wf_engine
        factory = get_session_factory()
        async with factory() as db:
            seeded = await wf_engine.seed_system_workflows(db)
            if seeded:
                logger.info("workflow_system_seeded", count=seeded)
    except Exception as exc:
        logger.warning("workflow_seed_failed", error=str(exc))

    # Seed default pipeline stages and settings (idempotent)
    try:
        from app.database import get_session_factory
        await _seed_defaults()
    except Exception as exc:
        logger.warning("defaults_seed_failed", error=str(exc))

    # Run initial alert evaluation
    try:
        from app.database import get_session_factory
        from app.services.alerts import evaluate_alerts
        factory = get_session_factory()
        async with factory() as db:
            await evaluate_alerts(db)
    except Exception as exc:
        logger.warning("alerts_evaluation_failed", error=str(exc))

    yield

    await dispose_engine()
    logger.info("gtm_engine_stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="GTM Engine — B2B SaaS Partnerships Intelligence Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ───────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        method=request.method,
        path=request.url.path,
    )
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info(
        "http_request",
        status_code=response.status_code,
        duration_ms=round(elapsed, 2),
    )
    return response


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Routers ──────────────────────────────────────────────────────────────────
from app.routers.auth import router as auth_router
from app.routers.partners import router as partners_router
from app.routers.opportunities import router as opportunities_router
from app.routers.accounts import router as accounts_router
from app.routers.scoring import router as scoring_router
from app.routers.ai import router as ai_router
from app.routers.workflows import router as workflows_router
from app.routers.activities import router as activities_router
from app.routers.revenue import router as revenue_router
from app.routers.analytics import router as analytics_router
from app.routers.leads import router as leads_router
from app.routers.contacts import router as contacts_router
from app.routers.campaigns import router as campaigns_router
from app.routers.integrations import router as integrations_router
from app.routers.settings import router as settings_router
from app.routers.notifications import router as notifications_router

API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(accounts_router, prefix=API_PREFIX)
app.include_router(partners_router, prefix=API_PREFIX)
app.include_router(opportunities_router, prefix=API_PREFIX)
app.include_router(scoring_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(workflows_router, prefix=API_PREFIX)
app.include_router(activities_router, prefix=API_PREFIX)
app.include_router(revenue_router, prefix=API_PREFIX)
app.include_router(analytics_router, prefix=API_PREFIX)
app.include_router(leads_router, prefix=API_PREFIX)
app.include_router(contacts_router, prefix=API_PREFIX)
app.include_router(campaigns_router, prefix=API_PREFIX)
app.include_router(integrations_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": settings.app_version,
        "env": settings.app_env,
    }


@app.get("/api/v1/health", tags=["system"])
async def api_health_check() -> dict:
    from app.database import get_engine
    from sqlalchemy import text

    db_status = "ok"
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.app_version,
        "env": settings.app_env,
        "database": db_status,
    }
