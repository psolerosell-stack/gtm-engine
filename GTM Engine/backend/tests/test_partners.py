import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def seeded_account_id(db_session):
    """Seed a test account and return its id."""
    import uuid
    from app.models.account import Account

    account = Account(
        id=uuid.uuid4(),
        name="Test Corp",
        industry="Manufacturing",
        size=25,
        geography="Spain",
        erp_ecosystem="business_central",
    )
    db_session.add(account)
    await db_session.commit()
    return str(account.id)


@pytest.mark.asyncio
async def test_create_partner(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    resp = await client.post(
        "/api/v1/partners",
        json={
            "account_id": seeded_account_id,
            "type": "VAR",
            "geography": "Spain",
            "vertical": "Manufacturing",
            "capacity_commercial": 2.0,
            "capacity_functional": 1.5,
            "capacity_technical": 2.0,
            "capacity_integration": 1.0,
            "arr_potential": 35000,
            "activation_velocity": 45,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "VAR"
    assert data["icp_score"] > 0
    assert data["tier"] in ("Bronze", "Silver", "Gold", "Platinum")


@pytest.mark.asyncio
async def test_icp_score_computed(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    resp = await client.post(
        "/api/v1/partners",
        json={
            "account_id": seeded_account_id,
            "type": "VAR+",
            "geography": "Spain",
            "vertical": "Manufacturing",
            "capacity_commercial": 2.5,
            "capacity_functional": 2.5,
            "capacity_technical": 2.5,
            "capacity_integration": 2.5,
            "arr_potential": 60000,
            "activation_velocity": 20,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    # High-fit partner should score >= 70 (Gold tier)
    assert data["icp_score"] >= 70


@pytest.mark.asyncio
async def test_get_partner(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/partners",
        json={"account_id": seeded_account_id, "type": "Referral"},
        headers=auth_headers,
    )
    partner_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/partners/{partner_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == partner_id


@pytest.mark.asyncio
async def test_list_partners(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    for i in range(3):
        await client.post(
            "/api/v1/partners",
            json={"account_id": seeded_account_id, "type": "VAR"},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/partners", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert "items" in data


@pytest.mark.asyncio
async def test_update_partner(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/partners",
        json={"account_id": seeded_account_id, "type": "VAR"},
        headers=auth_headers,
    )
    partner_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/partners/{partner_id}",
        json={"status": "active", "notes": "Updated via test"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_delete_partner(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/partners",
        json={"account_id": seeded_account_id, "type": "VAR"},
        headers=auth_headers,
    )
    partner_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/partners/{partner_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/partners/{partner_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_score_breakdown(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/partners",
        json={"account_id": seeded_account_id, "type": "OEM", "geography": "Spain"},
        headers=auth_headers,
    )
    partner_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/partners/{partner_id}/score", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "tier" in data
    assert "dimensions" in data
    assert "erp_ecosystem_fit" in data["dimensions"]
    assert "partner_type_match" in data["dimensions"]


@pytest.mark.asyncio
async def test_score_history(client: AsyncClient, auth_headers: dict, seeded_account_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/partners",
        json={"account_id": seeded_account_id, "type": "VAR"},
        headers=auth_headers,
    )
    partner_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/partners/{partner_id}/score/history", headers=auth_headers)
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1
    assert history[0]["score"] >= 0
