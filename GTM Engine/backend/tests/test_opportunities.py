import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def seeded_account_id(db_session):
    from app.models.account import Account

    account = Account(
        id=uuid.uuid4(),
        name="Opp Test Corp",
        industry="Distribution",
        size=30,
        geography="Spain",
        erp_ecosystem="sage_200",
    )
    db_session.add(account)
    await db_session.commit()
    return str(account.id)


@pytest.mark.asyncio
async def test_create_opportunity(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    resp = await client.post(
        "/api/v1/opportunities",
        json={
            "account_id": seeded_account_id,
            "name": "Sage 200 AP Automation Deal",
            "stage": "discovery",
            "arr_value": 18000,
            "currency": "EUR",
            "owner": "pol@company.io",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sage 200 AP Automation Deal"
    assert data["stage"] == "discovery"
    assert data["arr_value"] == 18000


@pytest.mark.asyncio
async def test_list_opportunities(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    for i in range(3):
        await client.post(
            "/api/v1/opportunities",
            json={"account_id": seeded_account_id, "name": f"Deal {i}", "stage": "prospecting"},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/opportunities", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_filter_by_stage(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    await client.post(
        "/api/v1/opportunities",
        json={"account_id": seeded_account_id, "name": "Demo Deal", "stage": "demo"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/opportunities?stage=demo", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(o["stage"] == "demo" for o in data["items"])


@pytest.mark.asyncio
async def test_update_stage(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/opportunities",
        json={"account_id": seeded_account_id, "name": "Stage Move Deal", "stage": "discovery"},
        headers=auth_headers,
    )
    opp_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/opportunities/{opp_id}",
        json={"stage": "proposal", "arr_value": 25000},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "proposal"
    assert resp.json()["arr_value"] == 25000


@pytest.mark.asyncio
async def test_pipeline_summary(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    stages = ["prospecting", "demo", "proposal"]
    for stage in stages:
        await client.post(
            "/api/v1/opportunities",
            json={"account_id": seeded_account_id, "name": f"{stage} deal", "stage": stage, "arr_value": 10000},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/opportunities/pipeline/summary", headers=auth_headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert "prospecting" in summary or "demo" in summary


@pytest.mark.asyncio
async def test_delete_opportunity(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/opportunities",
        json={"account_id": seeded_account_id, "name": "To Delete", "stage": "prospecting"},
        headers=auth_headers,
    )
    opp_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/opportunities/{opp_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/opportunities/{opp_id}", headers=auth_headers)
    assert get_resp.status_code == 404
