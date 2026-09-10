"""Opt-in integration test: ONLY an ephemeral container, never configured application DB."""

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from .. import history
from ..errors import AssistantError
from ..models import ChatState
from ..schemas import Exchange
from .factories import request
from .test_stream_service import answer

pytestmark = pytest.mark.skipif(
    os.environ.get("VPV_V2_CONTAINER_TESTS") != "1", reason="Opt-in ephemeral PostgreSQL"
)


@pytest.fixture
async def database(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    with (
        DockerContainer("postgres:16-alpine")
        .with_env("POSTGRES_PASSWORD", "test-only")
        .with_exposed_ports(5432) as container
    ):
        wait_for_logs(container, "database system is ready to accept connections", timeout=60)
        host, port = container.get_container_host_ip(), container.get_exposed_port(5432)
        engine = create_async_engine(
            f"postgresql+asyncpg://postgres:test-only@{host}:{port}/postgres"
        )
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            await conn.execute(
                text("""CREATE TABLE drafts (
                id INTEGER PRIMARY KEY, season_id INTEGER NOT NULL, draft_type VARCHAR(20),
                phase VARCHAR(20), status VARCHAR(20), current_round SMALLINT,
                current_pick SMALLINT, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now())""")
            )
            table = ChatState.__table__
            assert isinstance(table, Table)
            await conn.run_sync(table.create)
            await conn.execute(text("INSERT INTO users VALUES (11), (12)"))
            await conn.execute(text("INSERT INTO drafts (id,season_id) VALUES (1,1)"))
        monkeypatch.setattr(
            history,
            "AsyncSessionLocal",
            async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False),
        )
        try:
            yield
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_history_lease_isolation_and_clear(database: None) -> None:
    outcomes = await asyncio.gather(
        history.acquire(11, 1), history.acquire(11, 1), return_exceptions=True
    )
    leases = [result for result in outcomes if isinstance(result, str)]
    assert len(leases) == 1
    assert any(
        isinstance(result, AssistantError) and result.code == "CHAT_BUSY" for result in outcomes
    )
    lease = leases[0]
    with pytest.raises(AssistantError, match="Cancela"):
        await history.clear(11, 1)
    await history.save(11, 1, lease, Exchange(question=request().question, answer=answer()))
    assert len((await history.read_history(11, 1)).exchanges) == 1
    assert (await history.read_history(12, 1)).exchanges == []
    await history.release(11, 1, "wrong-lease")
    with pytest.raises(AssistantError):
        await history.acquire(11, 1)
    await history.release(11, 1, lease)
    await history.clear(11, 1)
    assert (await history.read_history(11, 1)).exchanges == []
    with pytest.raises(AssistantError):
        await history.save(11, 1, lease, Exchange(question="old", answer=answer()))
    with pytest.raises(AssistantError) as error:
        await history.acquire(11, 999)
    assert error.value.status == 404
