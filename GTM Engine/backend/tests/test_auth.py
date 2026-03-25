import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    # Register
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@test.io", "password": "password123", "role": "viewer"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "user@test.io"
    assert data["role"] == "viewer"

    # Login
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.io", "password": "password123"},
    )
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "secure@test.io", "password": "rightpass1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "secure@test.io", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@gtm.io"


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    payload = {"email": "dup@test.io", "password": "password123"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@test.io", "password": "password123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@test.io", "password": "password123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
