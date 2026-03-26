"""
Layer 3 tests — AI Intelligence and Research.

All Claude API calls are mocked via a fake anthropic client injected into AIService.
No real API calls are made; no key is required.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.ai_log import AICallLog
from app.models.partner import Partner, PartnerTier
from app.services.ai import AIService, AIServiceUnavailableError, _extract_json


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_message(text: str, input_tokens: int = 100, output_tokens: int = 50):
    """Build a fake anthropic.types.Message-like object."""
    content_block = SimpleNamespace(text=text)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[content_block], usage=usage)


def _fake_client(response_text: str) -> MagicMock:
    """Return a mock anthropic.AsyncAnthropic client that returns the given text."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(
        return_value=_fake_message(response_text)
    )
    return client


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_account(db_session: AsyncSession) -> Account:
    account = Account(
        name="Acme ERP Partners SL",
        industry="Manufacturing",
        geography="Spain",
        website="https://acme-erp.es",
        erp_ecosystem="sage_200",
        size=25,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def seeded_partner(db_session: AsyncSession, seeded_account: Account) -> Partner:
    partner = Partner(
        account_id=seeded_account.id,
        type="VAR",
        geography="Spain",
        vertical="Manufacturing",
        capacity_commercial=2.0,
        capacity_functional=2.0,
        capacity_technical=1.5,
        capacity_integration=1.0,
        arr_potential=35000.0,
        activation_velocity=45,
    )
    from app.services.scoring import engine as scoring_engine

    weights = None  # use defaults
    score, _ = scoring_engine.score(partner, seeded_account, weights)
    partner.icp_score = score
    partner.tier = scoring_engine.tier(score)
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)
    return partner


# ── Unit tests: _extract_json ─────────────────────────────────────────────────

def test_extract_json_bare():
    data = _extract_json('{"key": "value"}')
    assert data == {"key": "value"}


def test_extract_json_fenced():
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_fenced_no_lang():
    text = '```\n[1, 2, 3]\n```'
    assert _extract_json(text) == [1, 2, 3]


# ── Unit tests: AIService unavailable ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_service_unavailable_no_key(db_session: AsyncSession):
    """AIService raises when ANTHROPIC_API_KEY is not set (no injected client)."""
    with patch("app.services.ai.settings") as mock_settings:
        mock_settings.anthropic_api_key = None
        mock_settings.claude_model = "claude-sonnet-4-20250514"
        service = AIService(db_session)
        with pytest.raises(AIServiceUnavailableError):
            service._get_client()


# ── Unit tests: enrich_account ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrich_account_returns_parsed_json(
    db_session: AsyncSession,
    seeded_account: Account,
):
    enrichment_payload = {
        "size_estimate": 30,
        "industry": "Manufacturing",
        "geography": "Spain",
        "erp_ecosystem": "sage_200",
        "description": "A leading Sage 200 VAR in Spain.",
        "product_portfolio": "ERP implementations and support",
        "market_positioning": "Mid-market industrial companies",
        "signals": [
            {"type": "erp_focus", "description": "Sage 200 specialist", "confidence": 0.95}
        ],
        "fit_summary": "Strong ERP ecosystem fit.",
        "data_sources": ["analysis"],
    }
    client = _fake_client(json.dumps(enrichment_payload))
    service = AIService(db_session, client=client)

    result = await service.enrich_account(seeded_account)
    await db_session.commit()

    assert result["erp_ecosystem"] == "sage_200"
    assert result["size_estimate"] == 30
    assert "signals" in result
    assert len(result["signals"]) == 1

    # Check that a call log was written
    log_result = await db_session.execute(select(AICallLog).where(AICallLog.purpose == "enrich"))
    log = log_result.scalar_one()
    assert log.success is True
    assert log.entity_type == "account"
    assert log.total_tokens == 150


@pytest.mark.asyncio
async def test_enrich_account_handles_malformed_json(
    db_session: AsyncSession,
    seeded_account: Account,
):
    """When Claude returns non-JSON text, enrich_account stores raw response without crashing."""
    client = _fake_client("Sorry, I cannot help with that.")
    service = AIService(db_session, client=client)

    result = await service.enrich_account(seeded_account)
    await db_session.commit()

    assert "parse_error" in result or "raw_response" in result


# ── Unit tests: generate_fit_summary ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_fit_summary(
    db_session: AsyncSession,
    seeded_partner: Partner,
    seeded_account: Account,
):
    from app.services.scoring import engine as scoring_engine

    _score, breakdown = scoring_engine.score(seeded_partner, seeded_account)

    expected = (
        "Acme ERP Partners is a strong fit due to their Sage 200 specialization. "
        "Their manufacturing focus aligns with our ICP. Recommend co-sell motion."
    )
    client = _fake_client(expected)
    service = AIService(db_session, client=client)

    summary = await service.generate_fit_summary(seeded_partner, seeded_account, breakdown)
    await db_session.commit()

    assert "Sage 200" in summary or "Acme" in summary or len(summary) > 10
    log_result = await db_session.execute(
        select(AICallLog).where(AICallLog.purpose == "fit_summary")
    )
    log = log_result.scalar_one()
    assert log.entity_type == "partner"


# ── Unit tests: suggest_approach ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suggest_approach(
    db_session: AsyncSession,
    seeded_partner: Partner,
    seeded_account: Account,
):
    from app.services.scoring import engine as scoring_engine

    _score, breakdown = scoring_engine.score(seeded_partner, seeded_account)
    expected_text = (
        "GTM Motion: co-sell\n"
        "Approach: Partner with them on Sage 200 integrations.\n"
        "Key hook: Immediate AP automation value."
    )
    client = _fake_client(expected_text)
    service = AIService(db_session, client=client)

    result = await service.suggest_approach(seeded_partner, seeded_account, breakdown)
    await db_session.commit()

    assert len(result) > 5
    log_result = await db_session.execute(
        select(AICallLog).where(AICallLog.purpose == "approach")
    )
    log = log_result.scalar_one()
    assert log.success is True


# ── Unit tests: detect_signals ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_signals_returns_list(
    db_session: AsyncSession,
    seeded_account: Account,
):
    signals_json = json.dumps([
        {"type": "erp_focus", "description": "Sage specialist", "confidence": 0.9,
         "action_recommended": "Prioritize for outreach"},
        {"type": "target_market_match", "description": "Industrial clients", "confidence": 0.8,
         "action_recommended": "Use manufacturing use case in pitch"},
    ])
    client = _fake_client(signals_json)
    service = AIService(db_session, client=client)

    signals = await service.detect_signals(seeded_account)
    await db_session.commit()

    assert isinstance(signals, list)
    assert len(signals) == 2
    assert signals[0]["type"] == "erp_focus"
    assert signals[0]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_detect_signals_handles_bad_json(
    db_session: AsyncSession,
    seeded_account: Account,
):
    client = _fake_client("No signals detected.")
    service = AIService(db_session, client=client)

    signals = await service.detect_signals(seeded_account)
    await db_session.commit()

    assert isinstance(signals, list)
    assert len(signals) >= 1


# ── Unit tests: discover_accounts ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_accounts(db_session: AsyncSession):
    companies = [
        {
            "name": "ERP Solutions SL",
            "country": "Spain",
            "erp_ecosystem": "sage_200",
            "company_type": "VAR",
            "reasoning": "Sage 200 specialist with manufacturing clients",
            "fit_score_estimate": 88,
            "website_hint": "erpsolutions.es",
        }
    ] * 5

    client = _fake_client(json.dumps(companies))
    service = AIService(db_session, client=client)

    results = await service.discover_accounts(
        "VAR partners that implement Sage 200 for manufacturing companies in Spain",
        count=5,
    )
    await db_session.commit()

    assert isinstance(results, list)
    assert len(results) == 5
    assert results[0]["erp_ecosystem"] == "sage_200"


# ── Integration tests: HTTP endpoints ────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrich_endpoint_queues_job(
    client: AsyncClient,
    auth_headers: dict,
    seeded_account: Account,
):
    """POST /accounts/{id}/enrich returns 202 and sets status to 'pending'."""
    resp = await client.post(
        f"/api/v1/accounts/{seeded_account.id}/enrich",
        json={"force": False},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["enrichment_status"] in ("pending", "done")
    assert data["account_id"] == str(seeded_account.id)


@pytest.mark.asyncio
async def test_enrich_endpoint_no_requeue_if_done(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    seeded_account: Account,
):
    """If enrichment_status is 'done' and force=False, returns cached data immediately."""
    seeded_account.enrichment_status = "done"
    seeded_account.enrichment_data = json.dumps({"erp_ecosystem": "sage_200"})
    seeded_account.fit_summary = "Great fit."
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/accounts/{seeded_account.id}/enrich",
        json={"force": False},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["enrichment_status"] == "done"
    assert data["queued"] is False
    assert data["fit_summary"] == "Great fit."


@pytest.mark.asyncio
async def test_get_enrichment_status(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    seeded_account: Account,
):
    seeded_account.enrichment_status = "done"
    seeded_account.enrichment_data = json.dumps({"size_estimate": 25})
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/accounts/{seeded_account.id}/enrichment",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enrichment_status"] == "done"
    assert data["enrichment_data"]["size_estimate"] == 25


@pytest.mark.asyncio
async def test_signals_endpoint_unavailable_without_key(
    client: AsyncClient,
    auth_headers: dict,
    seeded_account: Account,
):
    """When no API key configured, signals endpoint returns 503."""
    with patch("app.routers.ai.AIService") as MockService:
        mock_instance = MockService.return_value
        mock_instance.detect_signals = AsyncMock(
            side_effect=AIServiceUnavailableError("ANTHROPIC_API_KEY not configured")
        )
        resp = await client.post(
            f"/api/v1/accounts/{seeded_account.id}/signals",
            headers=auth_headers,
        )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_discover_endpoint(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """POST /ai/discover with a mocked AI service returns a list of companies."""
    companies = [
        {
            "name": f"Partner {i}",
            "country": "Spain",
            "erp_ecosystem": "sage_200",
            "company_type": "VAR",
            "reasoning": "Good fit",
            "fit_score_estimate": 80,
            "website_hint": f"partner{i}.es",
        }
        for i in range(10)
    ]
    with patch("app.routers.ai.AIService") as MockService:
        mock_instance = MockService.return_value
        mock_instance.discover_accounts = AsyncMock(return_value=companies)
        resp = await client.post(
            "/api/v1/ai/discover",
            json={"profile": "VAR partners implementing Sage 200 in Spain for manufacturing", "count": 10},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count_requested"] == 10
    assert len(data["companies"]) == 10
    assert data["companies"][0]["erp_ecosystem"] == "sage_200"


@pytest.mark.asyncio
async def test_usage_stats_endpoint(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET /ai/usage returns usage stats (zero if no calls made)."""
    resp = await client.get("/api/v1/ai/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_calls" in data
    assert "total_cost_usd" in data
    assert data["period_days"] == 30


@pytest.mark.asyncio
async def test_partner_intelligence_endpoint(
    client: AsyncClient,
    auth_headers: dict,
    seeded_partner: Partner,
):
    """POST /partners/{id}/intelligence queues the job and returns 202."""
    resp = await client.post(
        f"/api/v1/partners/{seeded_partner.id}/intelligence",
        json={"force": False},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["partner_id"] == str(seeded_partner.id)
    assert "queued" in data
