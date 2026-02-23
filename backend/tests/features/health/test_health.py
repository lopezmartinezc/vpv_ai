from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_healthy(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] is True


@pytest.mark.asyncio
async def test_health_check_includes_version(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    data = response.json()
    assert data["version"] == "0.1.0"
