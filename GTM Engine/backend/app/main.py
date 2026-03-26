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
