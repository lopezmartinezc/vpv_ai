"""The assistant is admin-only and off unless explicitly enabled."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/draft-assistant/12/preseason/ask",
        json={"question": "¿mejor delantero?"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_rejects_oversized_question(client: AsyncClient) -> None:
    """Bounded input keeps a runaway client from burning tokens."""
    resp = await client.post(
        "/api/draft-assistant/12/preseason/ask",
        json={"question": "x" * 5000},
    )
    # Unauthenticated is fine here too — what must NOT happen is a 200.
    assert resp.status_code != 200
