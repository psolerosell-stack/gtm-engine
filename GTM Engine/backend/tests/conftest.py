import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app as fastapi_app
from app.models.base import Base
import app.models  # noqa: F401 — register all models

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
_session_factory = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create schema once; tear it down after the full session."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def truncate_tables():
    """Wipe all rows after every test so each starts with a clean slate."""
    yield
    async with _test_engine.begin() as conn:
        # Disable FK constraints so we can delete in any order
        await conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys = OFF"))
        for table in Base.metadata.sorted_tables:
            await conn.execute(table.delete())
        await conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys = ON"))


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register a manager user and return Bearer auth headers."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@gtm.io",
            "password": "testpassword123",
            "full_name": "Test User",
            "role": "manager",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@gtm.io", "password": "testpassword123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
