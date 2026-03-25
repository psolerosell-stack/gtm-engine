import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_account(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Acme Corp",
            "industry": "Manufacturing",
            "size": 40,
            "geography": "Spain",
            "erp_ecosystem": "sage_200",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert data["erp_ecosystem"] == "sage_200"
    assert data["enrichment_status"] == "pending"


@pytest.mark.asyncio
async def test_list_accounts(client: AsyncClient, auth_headers: dict) -> None:
    for i in range(3):
        await client.post(
            "/api/v1/accounts",
            json={"name": f"Company {i}", "industry": "Distribution"},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/accounts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert "items" in data


@pytest.mark.asyncio
async def test_filter_accounts_by_erp(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/accounts",
        json={"name": "SAP Corp", "erp_ecosystem": "sap_b1"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/accounts",
        json={"name": "BC Corp", "erp_ecosystem": "business_central"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/accounts?erp_ecosystem=sap_b1", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(a["erp_ecosystem"] == "sap_b1" for a in items)


@pytest.mark.asyncio
async def test_get_account(client: AsyncClient, auth_headers: dict) -> None:
    create_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Get Me Corp"},
        headers=auth_headers,
    )
    account_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == account_id


@pytest.mark.asyncio
async def test_update_account(client: AsyncClient, auth_headers: dict) -> None:
    create_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Update Me Corp", "size": 10},
        headers=auth_headers,
    )
    account_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/accounts/{account_id}",
        json={"size": 50, "erp_ecosystem": "holded"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["size"] == 50
    assert resp.json()["erp_ecosystem"] == "holded"


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient, auth_headers: dict) -> None:
    create_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Delete Me Corp"},
        headers=auth_headers,
    )
    account_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_account_not_found(client: AsyncClient, auth_headers: dict) -> None:
    import uuid
    resp = await client.get(f"/api/v1/accounts/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
