"""
Analytics router — Layer 6.

Read-only analytics endpoints + daily briefing management.
All endpoints require at least CurrentUser authentication.
"""
import json
import uuid
from datetime import date
from typing import List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession, ManagerUser
from app.models.analytics import DailyBriefing
from app.schemas.analytics import (
    BriefingRead,
    FunnelStage,
    MonthlyARR,
    OverviewKPIs,
    PartnerPerformance,
)
from app.services.analytics import AnalyticsService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewKPIs)
async def get_overview(
    current_user: CurrentUser,
    db: DBSession,
) -> OverviewKPIs:
    """High-level KPIs: partners, ARR, pipeline, leads."""
    svc = AnalyticsService(db)
    return await svc.get_overview_kpis()


@router.get("/funnel", response_model=List[FunnelStage])
async def get_funnel(
    current_user: CurrentUser,
    db: DBSession,
) -> List[FunnelStage]:
    """Opportunity pipeline funnel by stage."""
    svc = AnalyticsService(db)
    return await svc.get_funnel_stats()


@router.get("/partners/performance", response_model=List[PartnerPerformance])
async def get_partner_performance(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=10, ge=1, le=100),
) -> List[PartnerPerformance]:
    """Top partners ranked by attributed revenue."""
    svc = AnalyticsService(db)
    return await svc.get_partner_performance(limit=limit)


@router.get("/revenue/trends", response_model=List[MonthlyARR])
async def get_revenue_trends(
    current_user: CurrentUser,
    db: DBSession,
    months: int = Query(default=12, ge=1, le=36),
) -> List[MonthlyARR]:
    """Monthly ARR/MRR trend for the past N months."""
    svc = AnalyticsService(db)
    return await svc.get_arr_trends(months=months)


@router.get("/briefing/today", response_model=BriefingRead)
async def get_today_briefing(
    current_user: CurrentUser,
    db: DBSession,
) -> BriefingRead:
    """Retrieve today's daily briefing (404 if not yet generated)."""
    svc = AnalyticsService(db)
    briefing = await svc.get_today_briefing()
    if briefing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No briefing generated yet for today",
        )
    return BriefingRead.model_validate(briefing)


@router.post("/briefing/generate", response_model=BriefingRead, status_code=status.HTTP_202_ACCEPTED)
async def generate_briefing(
    current_user: ManagerUser,
    db: DBSession,
) -> BriefingRead:
    """
    Trigger generation of today's daily briefing.
    Idempotent — returns existing briefing if already generated.
    Tries to use Claude AI; falls back to structured JSON if unavailable.
    """
    svc = AnalyticsService(db)

    # Return existing if already generated today
    existing = await svc.get_today_briefing()
    if existing:
        return BriefingRead.model_validate(existing)

    # Collect data
    data = await svc.get_briefing_data()

    # Attempt AI generation
    content: str
    try:
        from app.services.ai import AIService, AIServiceUnavailableError

        ai = AIService(db)
        prompt = _build_briefing_prompt(data)
        narrative = await ai._call_claude(
            prompt=prompt,
            purpose="daily_briefing",
            entity_type="system",
            max_tokens=2000,
        )
        # Wrap narrative + raw data together
        content = json.dumps({"narrative": narrative, "data_snapshot": _data_summary(data)})
        logger.info("briefing_ai_generated", user=current_user.email)
    except Exception as exc:
        logger.warning("briefing_ai_skipped", reason=str(exc), user=current_user.email)
        content = json.dumps({"narrative": None, "data_snapshot": _data_summary(data)})

    # Post to Slack if configured
    posted_to_slack = False
    try:
        from app.config import settings
        if settings.slack_bot_token and not settings.slack_bot_token.startswith("your-"):
            from slack_sdk.web.async_client import AsyncWebClient
            slack = AsyncWebClient(token=settings.slack_bot_token)
            narrative_text = json.loads(content).get("narrative", "Daily GTM briefing generated.")
            await slack.chat_postMessage(
                channel=settings.slack_partnerships_channel,
                text=f"*GTM Daily Briefing — {date.today().isoformat()}*\n{narrative_text}",
            )
            posted_to_slack = True
    except Exception as exc:
        logger.warning("briefing_slack_skipped", reason=str(exc))

    briefing = await svc.save_briefing(content=content, posted_to_slack=posted_to_slack)
    await db.commit()
    await db.refresh(briefing)
    return BriefingRead.model_validate(briefing)


# ── Prompt helpers ────────────────────────────────────────────────────────────

def _data_summary(data: dict) -> dict:
    """Compact summary for embedding in content JSON."""
    kpis = data.get("kpis", {})
    return {
        "total_arr": kpis.get("total_arr", 0),
        "arr_last_30d": kpis.get("arr_last_30d", 0),
        "open_pipeline_arr": kpis.get("open_pipeline_arr", 0),
        "active_partners": kpis.get("active_partners", 0),
        "open_deals": kpis.get("open_deals", 0),
        "urgent_opps_count": len(data.get("urgent_opps", [])),
    }


def _build_briefing_prompt(data: dict) -> str:
    kpis = data.get("kpis", {})
    urgent = data.get("urgent_opps", [])
    top_partners = data.get("top_partners", [])
    trends = data.get("arr_trend_3m", [])

    urgent_text = (
        "\n".join(
            f"  - {o['name']} ({o['stage']}, closes {o['close_date']}, ARR €{o['arr'] or 0:,.0f})"
            for o in urgent[:5]
        )
        or "  None"
    )

    partner_text = (
        "\n".join(
            f"  - {p['partner_name']} (tier={p['tier']}, ARR €{p['total_arr']:,.0f}, {p['active_opportunities']} active deals)"
            for p in top_partners[:3]
        )
        or "  None"
    )

    arr_trend_text = (
        ", ".join(f"{t['month']}: €{t['arr']:,.0f}" for t in trends[-3:]) or "No data"
    )

    return f"""You are the GTM intelligence engine for a B2B SaaS partnerships team.
Generate a concise daily briefing (200-300 words) for the partnerships team based on the data below.

TODAY'S DATA ({data.get('date', 'today')}):

KPIs:
  - Total ARR: €{kpis.get('total_arr', 0):,.0f}
  - ARR closed last 30 days: €{kpis.get('arr_last_30d', 0):,.0f}
  - Open pipeline: €{kpis.get('open_pipeline_arr', 0):,.0f} across {kpis.get('open_deals', 0)} deals
  - Active partners: {kpis.get('active_partners', 0)}
  - Avg ICP score: {kpis.get('avg_icp_score', 0):.1f}

Urgent deals (closing within 14 days):
{urgent_text}

Top partners by revenue:
{partner_text}

ARR trend (last 3 months): {arr_trend_text}

OUTPUT FORMAT (JSON only, no markdown):
{{
  "headline": "one-sentence headline summarizing the most important insight",
  "urgent": ["action item 1", "action item 2"],
  "opportunities": ["opportunity 1", "opportunity 2"],
  "funnel_health": {{"status": "healthy|at_risk|critical", "note": "brief note"}},
  "top_channels": ["channel insight 1"],
  "insights": ["key insight 1", "key insight 2"]
}}

Prompt-version: v1.0"""
