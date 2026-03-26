"""
AIService — Layer 3: AI Intelligence and Research.

Wraps the Claude API for five capabilities:
  1. enrich_account      — extract company profile from name + website
  2. generate_fit_summary — 3-sentence ICP fit explanation
  3. suggest_approach     — GTM motion + first outreach suggestion
  4. detect_signals       — flag partnership-relevant signals
  5. discover_accounts    — suggest 10-20 target companies

All calls are logged to ai_call_logs with token counts + cost estimates.
Works without an API key configured: raises ServiceUnavailableError.
"""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.account import Account
from app.models.ai_log import AICallLog
from app.models.partner import Partner

logger = structlog.get_logger(__name__)

# Cost per million tokens (claude-sonnet-4 pricing)
_INPUT_COST_PER_MTOK = 3.0   # $3 / MTok
_OUTPUT_COST_PER_MTOK = 15.0  # $15 / MTok

# Prompt version tag embedded in every prompt (bump when prompts change)
PROMPT_VERSION = "v1.0"


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    input_cost = (prompt_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
    output_cost = (completion_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
    return round(input_cost + output_cost, 6)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_json(text: str) -> Any:
    """
    Extract JSON from Claude's response text.
    Handles fenced code blocks (```json ... ```) and bare JSON.
    """
    text = text.strip()
    if text.startswith("```"):
        start = text.find("\n") + 1
        end = text.rfind("```")
        text = text[start:end].strip()
    return json.loads(text)


class AIServiceUnavailableError(Exception):
    """Raised when the Anthropic API key is not configured."""


class AIService:
    """
    Stateless service class for all Claude-powered capabilities.

    Usage:
        service = AIService(db)
        result = await service.enrich_account(account)
    """

    def __init__(
        self,
        db: AsyncSession,
        client=None,  # anthropic.AsyncAnthropic — injected for testing
    ) -> None:
        self.db = db
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as e:
            raise AIServiceUnavailableError("anthropic package not installed") from e
        if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("your-"):
            raise AIServiceUnavailableError(
                "ANTHROPIC_API_KEY not configured. Set it in .env to use AI features."
            )
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def _call_claude(
        self,
        prompt: str,
        purpose: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Make a Claude API call, log it to ai_call_logs, and return the text response.
        """
        client = self._get_client()
        prompt_hash = _sha256(f"{PROMPT_VERSION}:{prompt}")
        start_ms = time.monotonic()
        success = True
        error_msg = None
        response_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
        except Exception as exc:
            success = False
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(
                "claude_api_error",
                purpose=purpose,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                error=error_msg,
            )
            raise
        finally:
            latency_ms = int((time.monotonic() - start_ms) * 1000)
            total_tokens = prompt_tokens + completion_tokens
            cost = _estimate_cost(prompt_tokens, completion_tokens)

            log_entry = AICallLog(
                entity_type=entity_type,
                entity_id=entity_id,
                purpose=purpose,
                model=settings.claude_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                success=success,
                error=error_msg,
                prompt_hash=prompt_hash,
            )
            self.db.add(log_entry)
            try:
                await self.db.flush()
            except Exception:
                pass  # Don't fail the call because logging failed

            logger.info(
                "claude_api_call",
                purpose=purpose,
                entity_type=entity_type,
                tokens=total_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                success=success,
            )

        return response_text

    # ── 1. Account Enrichment ─────────────────────────────────────────────────

    async def enrich_account(self, account: Account) -> Dict[str, Any]:
        """
        Use Claude to enrich an account record with structured company intelligence.
        Returns a dict with extracted fields; caller is responsible for persisting.
        """
        prompt = f"""You are a B2B SaaS partnerships analyst. Your company sells AP/AR automation software that integrates with ERP systems (Sage 200, Sage X3, SAP Business One, Business Central, Holded, Netsuite).

Analyze the following company and extract structured information. Respond ONLY with valid JSON, no commentary.

Company name: {account.name}
Website: {account.website or "unknown"}
Known industry: {account.industry or "unknown"}
Known geography: {account.geography or "unknown"}

Extract and return this exact JSON structure:
{{
  "size_estimate": <integer employees or null>,
  "industry": "<primary industry>",
  "geography": "<primary country or region>",
  "erp_ecosystem": "<one of: business_central, navision, sage_200, sage_x3, sap_b1, netsuite, holded, other, or null if unknown>",
  "description": "<2-3 sentence company description>",
  "product_portfolio": "<brief description of their main products/services>",
  "market_positioning": "<brief description of market position and target customers>",
  "signals": [
    {{"type": "<signal_type>", "description": "<what was detected>", "confidence": <0.0-1.0>}}
  ],
  "fit_summary": "<2-3 sentences explaining why this company is or isn't a good partner fit for AP/AR automation with ERP integrations>",
  "data_sources": ["analysis based on company name and provided context"]
}}

Signal types to look for: erp_focus, automation_interest, target_market_match, integration_capability, competitive_risk.
If you cannot determine a field from the available information, use null.
Prompt-version: {PROMPT_VERSION}"""

        response_text = await self._call_claude(
            prompt=prompt,
            purpose="enrich",
            entity_type="account",
            entity_id=account.id,
            max_tokens=1500,
        )

        try:
            data = _extract_json(response_text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("enrich_account_parse_error", account_id=str(account.id), error=str(exc))
            data = {"raw_response": response_text, "parse_error": str(exc)}

        return data

    # ── 2. Fit Summary ────────────────────────────────────────────────────────

    async def generate_fit_summary(
        self,
        partner: Partner,
        account: Account,
        score_breakdown: Dict[str, Any],
    ) -> str:
        """
        Generate a 3-sentence natural language explanation of why this partner
        matches (or doesn't) the ICP. Returns plain text.
        """
        top_dims = sorted(
            score_breakdown.items(),
            key=lambda x: x[1].get("weighted", 0),
            reverse=True,
        )[:3]
        top_summary = ", ".join(
            f"{k} ({v.get('label', '')} → {v.get('weighted', 0):.2f})"
            for k, v in top_dims
        )

        prompt = f"""You are a B2B SaaS partnerships analyst for an AP/AR automation company that integrates with ERPs (Sage 200, Sage X3, SAP B1, Business Central, Holded).

Write exactly 3 sentences explaining why this partner is or isn't a strong fit for a partnership. Be specific, concrete, and actionable. Use the score data to support your reasoning.

Partner type: {partner.type}
Account name: {account.name}
Industry: {account.industry or 'unknown'}
ERP ecosystem: {account.erp_ecosystem or 'unknown'}
Geography: {partner.geography or account.geography or 'unknown'}
Vertical: {partner.vertical or 'unknown'}
ICP Score: {partner.icp_score:.1f}/100 (Tier: {partner.tier})
Top scoring dimensions: {top_summary}
ARR potential: {partner.arr_potential or 'unknown'}
Activation velocity: {f"{partner.activation_velocity} days" if partner.activation_velocity else 'unknown'}

Respond with exactly 3 sentences. No headers, no bullet points, no JSON.
Prompt-version: {PROMPT_VERSION}"""

        return await self._call_claude(
            prompt=prompt,
            purpose="fit_summary",
            entity_type="partner",
            entity_id=partner.id,
            max_tokens=300,
        )

    # ── 3. Approach Suggestion ────────────────────────────────────────────────

    async def suggest_approach(
        self,
        partner: Partner,
        account: Account,
        score_breakdown: Dict[str, Any],
    ) -> str:
        """
        Suggest the correct GTM motion and first outreach approach for this partner.
        Returns plain text (1-2 paragraphs).
        """
        prompt = f"""You are a GTM strategy expert for a B2B SaaS company selling AP/AR automation software integrated with ERPs (Sage 200, Sage X3, SAP B1, Business Central, Holded). Target customers are mid-market companies with 10-200 employees.

Based on this partner profile, suggest the optimal GTM motion and a specific first outreach approach. Be highly specific — name the ERP, the use case, the value proposition angle.

Partner type: {partner.type}
Account name: {account.name}
Industry: {account.industry or 'unknown'}
ERP ecosystem: {account.erp_ecosystem or 'unknown'}
Geography: {partner.geography or account.geography or 'unknown'}
Vertical: {partner.vertical or 'unknown'}
ICP Score: {partner.icp_score:.1f}/100 (Tier: {partner.tier})
Capacity: commercial={partner.capacity_commercial}, functional={partner.capacity_functional}, technical={partner.capacity_technical}, integration={partner.capacity_integration}
ARR potential: {partner.arr_potential or 'unknown'}

Format your response as:
GTM Motion: <one of: co-sell, resell, referral, OEM-embed, technology-alliance>
Approach: <2-4 sentences describing the specific first outreach>
Key hook: <1 sentence — the single most compelling reason for them to engage>
Prompt-version: {PROMPT_VERSION}"""

        return await self._call_claude(
            prompt=prompt,
            purpose="approach",
            entity_type="partner",
            entity_id=partner.id,
            max_tokens=400,
        )

    # ── 4. Signal Detection ───────────────────────────────────────────────────

    async def detect_signals(self, account: Account) -> List[Dict[str, Any]]:
        """
        Analyze the account and return a list of partnership-relevant signals.
        Each signal: {type, description, confidence, action_recommended}.
        """
        prompt = f"""You are a B2B SaaS partnership intelligence analyst. Analyze this company for signals that indicate they could be a strong partner for an AP/AR automation company (Sage 200, Sage X3, SAP B1, Business Central, Holded integrations).

Company: {account.name}
Website: {account.website or 'unknown'}
Industry: {account.industry or 'unknown'}
Geography: {account.geography or 'unknown'}
ERP ecosystem: {account.erp_ecosystem or 'unknown'}
Description: {account.description or 'none provided'}
Existing fit summary: {account.fit_summary or 'none'}

Detect signals and respond ONLY with valid JSON array (no commentary):
[
  {{
    "type": "<erp_focus | automation_interest | target_market_match | integration_capability | competitive_risk | hiring_signal | content_signal>",
    "description": "<specific observation>",
    "confidence": <0.0-1.0>,
    "action_recommended": "<what to do with this signal>"
  }}
]

Return between 1 and 5 signals. If no signals are detectable from available data, return a single low-confidence signal.
Prompt-version: {PROMPT_VERSION}"""

        response_text = await self._call_claude(
            prompt=prompt,
            purpose="signals",
            entity_type="account",
            entity_id=account.id,
            max_tokens=800,
        )

        try:
            signals = _extract_json(response_text)
            if not isinstance(signals, list):
                signals = [{"type": "unknown", "description": response_text, "confidence": 0.5}]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("detect_signals_parse_error", account_id=str(account.id), error=str(exc))
            signals = [{"type": "parse_error", "description": response_text[:200], "confidence": 0.0}]

        return signals

    # ── 5. Account Discovery ──────────────────────────────────────────────────

    async def discover_accounts(
        self,
        profile_description: str,
        count: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Given a target profile description, suggest companies to research as
        potential partners. Returns list of {name, country, erp_ecosystem,
        reasoning, fit_score_estimate, website_hint}.
        """
        prompt = f"""You are a B2B partnerships researcher. Your company sells AP/AR automation SaaS integrated with: Sage 200, Sage X3, SAP Business One, Microsoft Business Central, Holded, and Netsuite.

Based on the following ideal partner profile, suggest {count} real companies (primarily ERP resellers, VARs, implementation partners, or technology alliances) that match the profile. Focus on companies in Spain and LATAM unless the profile specifies otherwise.

Target profile:
{profile_description}

Respond ONLY with valid JSON array (no commentary):
[
  {{
    "name": "<company name>",
    "country": "<country>",
    "erp_ecosystem": "<primary ERP they work with>",
    "company_type": "<VAR | OEM | Referral | Alliance | Distributor>",
    "reasoning": "<1-2 sentences why this company matches the profile>",
    "fit_score_estimate": <integer 0-100>,
    "website_hint": "<domain.com or null if unknown>"
  }}
]

Return exactly {count} suggestions, ordered by estimated fit score descending.
Prompt-version: {PROMPT_VERSION}"""

        response_text = await self._call_claude(
            prompt=prompt,
            purpose="discover",
            entity_type=None,
            entity_id=None,
            max_tokens=3000,
        )

        try:
            companies = _extract_json(response_text)
            if not isinstance(companies, list):
                raise ValueError("Expected JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("discover_accounts_parse_error", error=str(exc))
            companies = []

        return companies

    # ── Usage Stats ───────────────────────────────────────────────────────────

    async def get_usage_stats(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Return aggregated usage stats for the last N days."""
        from datetime import timedelta

        from sqlalchemy import func, select

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.count(AICallLog.id).label("total_calls"),
                func.sum(AICallLog.total_tokens).label("total_tokens"),
                func.sum(AICallLog.cost_usd).label("total_cost_usd"),
                func.avg(AICallLog.latency_ms).label("avg_latency_ms"),
                func.sum(
                    (AICallLog.success == False).cast(  # noqa: E712
                        __import__("sqlalchemy").Integer
                    )
                ).label("failed_calls"),
            ).where(AICallLog.created_at >= cutoff)
        )
        row = result.one()

        # Per-purpose breakdown
        breakdown_result = await self.db.execute(
            select(
                AICallLog.purpose,
                func.count(AICallLog.id).label("calls"),
                func.sum(AICallLog.total_tokens).label("tokens"),
                func.sum(AICallLog.cost_usd).label("cost"),
            )
            .where(AICallLog.created_at >= cutoff)
            .group_by(AICallLog.purpose)
        )

        return {
            "period_days": days,
            "total_calls": row.total_calls or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost_usd": round(row.total_cost_usd or 0.0, 4),
            "avg_latency_ms": round(row.avg_latency_ms or 0.0, 1),
            "failed_calls": row.failed_calls or 0,
            "by_purpose": [
                {
                    "purpose": r.purpose,
                    "calls": r.calls,
                    "tokens": r.tokens or 0,
                    "cost_usd": round(r.cost or 0.0, 4),
                }
                for r in breakdown_result.all()
            ],
        }
