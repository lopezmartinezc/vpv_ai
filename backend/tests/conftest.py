from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from src.app import create_app
from src.core.config import settings
from src.shared.dependencies import get_db
from src.shared.models import Base

# The fixture below creates and DROPS every table of the database it is given,
# so it must never be pointed at a real one. The URL comes from TEST_DATABASE_URL
# when set; otherwise it is derived from the app's, and either way the database
# name has to end in "_test" or no test touches it.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or settings.database_url.replace(
    "/ligavpv", "/ligavpv_test"
)


def _database_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


@pytest_asyncio.fixture
async def test_engine():
    if not _database_name(TEST_DATABASE_URL).endswith("_test"):
        pytest.fail(
            f"Refusing to run DB tests against {_database_name(TEST_DATABASE_URL)!r}: "
            "the test engine drops every table. Set TEST_DATABASE_URL to a *_test database."
        )
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    conn = await test_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)

    yield session

    await session.close()
    await trans.rollback()
    await conn.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
