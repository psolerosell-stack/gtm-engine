"""
AnalyticsService — Layer 6: Analytics & Revenue Intelligence.

Aggregates data from Revenue, Opportunities, Partners, Leads, and Activities
to produce KPIs, funnel stats, partner performance rankings, ARR trends,
and the data payload for the daily AI briefing.

All queries are read-only. Avoids dialect-specific SQL by aggregating in Python
where data volumes are small.
"""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.analytics import DailyBriefing
from app.models.lead import Lead
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.partner import Partner
from app.models.revenue import Revenue
from app.schemas.analytics import (
    FunnelStage,
    MonthlyARR,
    OverviewKPIs,
    PartnerPerformance,
)

logger = structlog.get_logger(__name__)

_CLOSED = {OpportunityStage.closed_won.value, OpportunityStage.closed_lost.value}

_STAGE_ORDER = {
    "prospecting": 1,
    "qualification": 2,
    "discovery": 3,
    "demo": 4,
    "proposal": 5,
    "negotiation": 6,
    "closed_won": 7,
    "closed_lost": 8,
}


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_overview_kpis(self) -> OverviewKPIs:
        """Aggregate high-level KPIs across all entity tables."""
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        first_of_month = today.replace(day=1)

        # Partners
        total_partners_res = await self.db.execute(
            select(func.count()).where(Partner.deleted_at.is_(None))
        )
        total_partners = total_partners_res.scalar_one() or 0

        active_partners_res = await self.db.execute(
            select(func.count()).where(
                Partner.deleted_at.is_(None),
                Partner.status == "active",
            )
        )
        active_partners = active_partners_res.scalar_one() or 0

        avg_icp_res = await self.db.execute(
            select(func.avg(Partner.icp_score)).where(Partner.deleted_at.is_(None))
        )
        avg_icp = float(avg_icp_res.scalar_one() or 0.0)

        # Revenue
        total_arr_res = await self.db.execute(
            select(func.sum(Revenue.arr)).where(Revenue.deleted_at.is_(None))
        )
        total_arr = float(total_arr_res.scalar_one() or 0.0)

        arr_30d_res = await self.db.execute(
            select(func.sum(Revenue.arr)).where(
                Revenue.deleted_at.is_(None),
                Revenue.date_closed >= thirty_days_ago,
            )
        )
        arr_last_30d = float(arr_30d_res.scalar_one() or 0.0)

        # Open pipeline
        pipeline_res = await self.db.execute(
            select(
                func.coalesce(func.sum(Opportunity.arr_value), 0.0),
                func.count(Opportunity.id),
            ).where(
                Opportunity.deleted_at.is_(None),
                Opportunity.stage.notin_(list(_CLOSED)),
            )
        )
        pipeline_row = pipeline_res.one()
        open_pipeline_arr = float(pipeline_row[0])
        open_deals = int(pipeline_row[1])

        # Leads this month
        leads_res = await self.db.execute(
            select(func.count()).where(
                Lead.deleted_at.is_(None),
                Lead.created_at >= datetime.combine(first_of_month, datetime.min.time()).replace(
                    tzinfo=timezone.utc
                ),
            )
        )
        leads_this_month = leads_res.scalar_one() or 0

        return OverviewKPIs(
            total_partners=total_partners,
            active_partners=active_partners,
            total_arr=total_arr,
            arr_last_30d=arr_last_30d,
            open_pipeline_arr=open_pipeline_arr,
            open_deals=open_deals,
            leads_this_month=leads_this_month,
            avg_icp_score=round(avg_icp, 1),
        )

    async def get_funnel_stats(self) -> List[FunnelStage]:
        """Pipeline funnel: count + ARR per stage, ordered by funnel position."""
        result = await self.db.execute(
            select(
                Opportunity.stage,
                func.count(Opportunity.id).label("cnt"),
                func.coalesce(func.sum(Opportunity.arr_value), 0.0).label("arr"),
            )
            .where(Opportunity.deleted_at.is_(None))
            .group_by(Opportunity.stage)
        )
        rows = result.all()

        stages = [
            FunnelStage(
                stage=row.stage,
                count=row.cnt,
                arr=float(row.arr),
            )
            for row in rows
        ]
        stages.sort(key=lambda s: _STAGE_ORDER.get(s.stage, 99))
        return stages

    async def get_partner_performance(self, limit: int = 10) -> List[PartnerPerformance]:
        """Top N partners by total attributed revenue + opportunity counts."""
        # Pull partners with their account names
        partners_res = await self.db.execute(
            select(Partner, Account.name.label("account_name"))
            .join(Account, Partner.account_id == Account.id)
            .where(Partner.deleted_at.is_(None))
        )
        partners_with_names = partners_res.all()

        if not partners_with_names:
            return []

        partner_ids = [row.Partner.id for row in partners_with_names]

        # Revenue totals per partner
        rev_res = await self.db.execute(
            select(Revenue.partner_id, func.sum(Revenue.arr).label("total_arr"))
            .where(Revenue.deleted_at.is_(None), Revenue.partner_id.in_(partner_ids))
            .group_by(Revenue.partner_id)
        )
        rev_map: Dict[Any, float] = {
            str(row.partner_id): float(row.total_arr) for row in rev_res.all()
        }

        # Opportunity counts per partner
        opp_res = await self.db.execute(
            select(
                Opportunity.partner_id,
                func.count(Opportunity.id).label("total"),
            )
            .where(
                Opportunity.deleted_at.is_(None),
                Opportunity.partner_id.in_(partner_ids),
            )
            .group_by(Opportunity.partner_id)
        )
        opp_total_map: Dict[Any, int] = {
            str(row.partner_id): int(row.total) for row in opp_res.all()
        }

        active_opp_res = await self.db.execute(
            select(
                Opportunity.partner_id,
                func.count(Opportunity.id).label("active"),
            )
            .where(
                Opportunity.deleted_at.is_(None),
                Opportunity.partner_id.in_(partner_ids),
                Opportunity.stage.notin_(list(_CLOSED)),
            )
            .group_by(Opportunity.partner_id)
        )
        active_opp_map: Dict[Any, int] = {
            str(row.partner_id): int(row.active) for row in active_opp_res.all()
        }

        rows = []
        for row in partners_with_names:
            p = row.Partner
            pid_str = str(p.id)
            rows.append(
                PartnerPerformance(
                    partner_id=p.id,
                    partner_name=row.account_name,
                    tier=p.tier,
                    icp_score=p.icp_score,
                    total_arr=rev_map.get(pid_str, 0.0),
                    opportunity_count=opp_total_map.get(pid_str, 0),
                    active_opportunities=active_opp_map.get(pid_str, 0),
                )
            )

        rows.sort(key=lambda r: r.total_arr, reverse=True)
        return rows[:limit]

    async def get_arr_trends(self, months: int = 12) -> List[MonthlyARR]:
        """Monthly ARR/MRR for the past N months (Python-side aggregation)."""
        cutoff = date.today() - timedelta(days=months * 31)
        result = await self.db.execute(
            select(Revenue.date_closed, Revenue.arr, Revenue.mrr)
            .where(Revenue.deleted_at.is_(None), Revenue.date_closed >= cutoff)
            .order_by(Revenue.date_closed)
        )
        rows = result.all()

        # Group by YYYY-MM
        monthly: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"arr": 0.0, "mrr": 0.0, "count": 0}
        )
        for row in rows:
            key = row.date_closed.strftime("%Y-%m")
            monthly[key]["arr"] += row.arr
            monthly[key]["mrr"] += row.mrr
            monthly[key]["count"] += 1

        return [
            MonthlyARR(month=k, arr=v["arr"], mrr=v["mrr"], count=v["count"])
            for k, v in sorted(monthly.items())
        ]

    async def get_briefing_data(self) -> Dict[str, Any]:
        """Collect all data needed to generate the daily AI briefing."""
        today = date.today()
        two_weeks = today + timedelta(days=14)

        kpis = await self.get_overview_kpis()
        funnel = await self.get_funnel_stats()
        top_partners = await self.get_partner_performance(limit=5)
        arr_trend_3m = await self.get_arr_trends(months=3)

        # Urgent: active deals closing within 14 days
        urgent_res = await self.db.execute(
            select(
                Opportunity.name,
                Opportunity.stage,
                Opportunity.arr_value,
                Opportunity.close_date,
            )
            .where(
                Opportunity.deleted_at.is_(None),
                Opportunity.stage.notin_(list(_CLOSED)),
                Opportunity.close_date <= two_weeks,
                Opportunity.close_date.isnot(None),
            )
            .order_by(Opportunity.close_date)
            .limit(10)
        )
        urgent_opps = [
            {
                "name": row.name,
                "stage": row.stage,
                "arr": row.arr_value,
                "close_date": row.close_date.isoformat() if row.close_date else None,
            }
            for row in urgent_res.all()
        ]

        # Recent revenue
        recent_rev_res = await self.db.execute(
            select(Revenue.arr, Revenue.type, Revenue.date_closed)
            .where(Revenue.deleted_at.is_(None))
            .order_by(Revenue.date_closed.desc())
            .limit(5)
        )
        recent_revenue = [
            {"arr": r.arr, "type": r.type, "date": r.date_closed.isoformat()}
            for r in recent_rev_res.all()
        ]

        return {
            "date": today.isoformat(),
            "kpis": kpis.model_dump(),
            "funnel": [f.model_dump() for f in funnel],
            "top_partners": [p.model_dump() for p in top_partners],
            "arr_trend_3m": [t.model_dump() for t in arr_trend_3m],
            "urgent_opps": urgent_opps,
            "recent_revenue": recent_revenue,
        }

    # ── Briefing helpers ──────────────────────────────────────────────────────

    async def get_today_briefing(self) -> Optional[DailyBriefing]:
        result = await self.db.execute(
            select(DailyBriefing).where(DailyBriefing.date == date.today().isoformat())
        )
        return result.scalar_one_or_none()

    async def save_briefing(self, content: str, posted_to_slack: bool = False) -> DailyBriefing:
        existing = await self.get_today_briefing()
        if existing:
            return existing  # idempotent

        briefing = DailyBriefing(
            date=date.today().isoformat(),
            content=content,
            posted_to_slack=posted_to_slack,
        )
        self.db.add(briefing)
        await self.db.flush()
        return briefing
