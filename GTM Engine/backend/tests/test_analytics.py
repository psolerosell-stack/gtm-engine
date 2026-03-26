"""
Tests for Layer 6: Revenue CRUD + Analytics endpoints.
"""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_account(db_session):
    from app.models.account import Account
    acc = Account(
        id=uuid.uuid4(),
        name="Analytics Corp",
        industry="Technology",
        size=100,
        geography="Spain",
        erp_ecosystem="business_central",
    )
    db_session.add(acc)
    await db_session.commit()
    return acc


@pytest_asyncio.fixture
async def seeded_partner(db_session, seeded_account):
    from app.models.partner import Partner
    p = Partner(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        type="VAR",
        tier="Silver",
        status="active",
        geography="Spain",
        vertical="Technology",
        icp_score=72.0,
        capacity_commercial=2.0,
        capacity_functional=2.0,
        capacity_technical=2.0,
        capacity_integration=1.5,
        arr_potential=50000,
        activation_velocity=30,
    )
    db_session.add(p)
    await db_session.commit()
    return p


@pytest_asyncio.fixture
async def seeded_revenue(db_session, seeded_partner):
    from app.models.revenue import Revenue
    records = [
        Revenue(
            id=uuid.uuid4(),
            partner_id=seeded_partner.id,
            arr=12000.0,
            mrr=1000.0,
            date_closed=date.today() - timedelta(days=10),
            type="new",
            currency="EUR",
        ),
        Revenue(
            id=uuid.uuid4(),
            partner_id=seeded_partner.id,
            arr=6000.0,
            mrr=500.0,
            date_closed=date.today() - timedelta(days=45),
            type="expansion",
            currency="EUR",
        ),
    ]
    for r in records:
        db_session.add(r)
    await db_session.commit()
    return records


# ── Revenue CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_revenue(client: AsyncClient, auth_headers: dict, seeded_partner) -> None:
    resp = await client.post(
        "/api/v1/revenue",
        json={
            "partner_id": str(seeded_partner.id),
            "arr": 24000.0,
            "date_closed": date.today().isoformat(),
            "type": "new",
            "currency": "EUR",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["arr"] == 24000.0
    assert data["mrr"] == pytest.approx(2000.0, rel=1e-3)
    assert data["type"] == "new"
    assert data["currency"] == "EUR"
    assert data["partner_id"] == str(seeded_partner.id)


@pytest.mark.asyncio
async def test_create_revenue_mrr_auto(client: AsyncClient, auth_headers: dict) -> None:
    """MRR is auto-computed as arr/12 when not provided."""
    resp = await client.post(
        "/api/v1/revenue",
        json={
            "arr": 36000.0,
            "date_closed": date.today().isoformat(),
            "type": "renewal",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["mrr"] == pytest.approx(3000.0, rel=1e-3)


@pytest.mark.asyncio
async def test_create_revenue_invalid_partner(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/v1/revenue",
        json={
            "partner_id": str(uuid.uuid4()),
            "arr": 1000.0,
            "date_closed": date.today().isoformat(),
            "type": "new",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_revenue(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    resp = await client.get("/api/v1/revenue", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_list_revenue_filter_by_type(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    resp = await client.get("/api/v1/revenue?type=new", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["type"] == "new"


@pytest.mark.asyncio
async def test_get_revenue_by_id(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    rev_id = str(seeded_revenue[0].id)
    resp = await client.get(f"/api/v1/revenue/{rev_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == rev_id


@pytest.mark.asyncio
async def test_get_revenue_not_found(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get(f"/api/v1/revenue/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revenue_summary(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    resp = await client.get("/api/v1/revenue/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_arr" in data
    assert "total_mrr" in data
    assert "arr_by_type" in data
    assert "arr_by_currency" in data
    assert "monthly_trends" in data
    assert data["total_arr"] >= 18000.0  # 12000 + 6000


@pytest.mark.asyncio
async def test_delete_revenue_requires_admin(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    """Manager-role user cannot delete — admin required."""
    rev_id = str(seeded_revenue[0].id)
    resp = await client.delete(f"/api/v1/revenue/{rev_id}", headers=auth_headers)
    assert resp.status_code == 403


# ── Analytics endpoints ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_overview(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    resp = await client.get("/api/v1/analytics/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_arr" in data
    assert "active_partners" in data
    assert "open_pipeline_arr" in data
    assert "leads_this_month" in data
    assert "avg_icp_score" in data


@pytest.mark.asyncio
async def test_analytics_funnel(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/analytics/funnel", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_analytics_partner_performance(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    resp = await client.get("/api/v1/analytics/partners/performance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "partner_id" in data[0]
        assert "total_arr" in data[0]
        assert "tier" in data[0]


@pytest.mark.asyncio
async def test_analytics_revenue_trends(client: AsyncClient, auth_headers: dict, seeded_revenue) -> None:
    resp = await client.get("/api/v1/analytics/revenue/trends?months=6", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "month" in data[0]
        assert "arr" in data[0]


@pytest.mark.asyncio
async def test_briefing_today_not_found(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/analytics/briefing/today", headers=auth_headers)
    # Either 404 (not generated) or 200 (already generated in another test)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_generate_briefing(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post("/api/v1/analytics/briefing/generate", headers=auth_headers)
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert "id" in data
    assert "date" in data
    assert "content" in data
    # content is valid JSON
    import json
    content = json.loads(data["content"])
    assert "data_snapshot" in content


@pytest.mark.asyncio
async def test_generate_briefing_idempotent(client: AsyncClient, auth_headers: dict) -> None:
    """Calling generate twice returns the same briefing id."""
    r1 = await client.post("/api/v1/analytics/briefing/generate", headers=auth_headers)
    r2 = await client.post("/api/v1/analytics/briefing/generate", headers=auth_headers)
    assert r1.status_code in (200, 202)
    assert r2.status_code in (200, 202)
    assert r1.json()["id"] == r2.json()["id"]
