"""send_test reports a clear reason instead of sending when unconfigured.

The "draft" target has no fallback: when the season has no
``draft_telegram_chat_id`` the test send must short-circuit (no network, no
TelegramClient) and return a reason the admin can act on.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.telegram.service import TelegramNotifier
from src.shared.models.season import Season


@pytest.mark.asyncio
async def test_draft_test_without_chat_id_reports_reason(db_session: AsyncSession) -> None:
    season = Season(
        name="2026-2027", matchday_start=1, kind="league", draft_telegram_chat_id=None
    )
    db_session.add(season)
    await db_session.flush()

    result = await TelegramNotifier(db_session).send_test(season.id, "draft")

    assert result["sent"] is False
    assert result["target"] == "draft"
    assert "chat_id" in (result.get("reason") or "").lower()
