from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.telegram.config import telegram_settings
from src.features.telegram.service import TelegramNotifier
from src.shared.dependencies import get_db, require_perm
from src.shared.permissions import Perm

router = APIRouter(prefix="/telegram", tags=["telegram"])


class SendMessageRequest(BaseModel):
    text: str


class TestTelegramRequest(BaseModel):
    # Which season target to test: "general", "draft" or "alerts".
    target: str = "general"


@router.get("/admin/status")
async def get_telegram_status(
    _admin: dict = Depends(require_perm(Perm.TELEGRAM)),
) -> dict:
    return {
        "enabled": telegram_settings.telegram_enabled,
        "chat_id": telegram_settings.telegram_chat_id or None,
        "bot_configured": bool(telegram_settings.telegram_bot_token),
    }


@router.post("/admin/send-lineup/{lineup_id}")
async def send_lineup(
    lineup_id: int,
    _admin: dict = Depends(require_perm(Perm.TELEGRAM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    notifier = TelegramNotifier(db)
    sent = await notifier.send_lineup_image(lineup_id)
    return {"sent": sent, "lineup_id": lineup_id}


@router.post("/admin/send-message")
async def send_message(
    data: SendMessageRequest,
    _admin: dict = Depends(require_perm(Perm.TELEGRAM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    notifier = TelegramNotifier(db)
    sent = await notifier.send_message(data.text)
    return {"sent": sent}


@router.post("/admin/test/{season_id}")
async def test_telegram(
    season_id: int,
    data: TestTelegramRequest,
    _admin: dict = Depends(require_perm(Perm.TELEGRAM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test message to a season's configured Telegram target."""
    notifier = TelegramNotifier(db)
    return await notifier.send_test(season_id, data.target)
