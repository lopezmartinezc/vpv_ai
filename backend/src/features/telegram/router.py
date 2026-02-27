from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.telegram.config import telegram_settings
from src.features.telegram.service import TelegramNotifier
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/telegram", tags=["telegram"])


class SendMessageRequest(BaseModel):
    text: str


@router.get("/admin/status")
async def get_telegram_status(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    return {
        "enabled": telegram_settings.telegram_enabled,
        "chat_id": telegram_settings.telegram_chat_id or None,
        "bot_configured": bool(telegram_settings.telegram_bot_token),
    }


@router.post("/admin/send-lineup/{lineup_id}")
async def send_lineup(
    lineup_id: int,
    _admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    notifier = TelegramNotifier(db)
    sent = await notifier.send_lineup_image(lineup_id)
    return {"sent": sent, "lineup_id": lineup_id}


@router.post("/admin/send-message")
async def send_message(
    data: SendMessageRequest,
    _admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    notifier = TelegramNotifier(db)
    sent = await notifier.send_message(data.text)
    return {"sent": sent}
