from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineups.repository import LineupRepository
from src.features.telegram.client import TelegramClient
from src.features.telegram.config import telegram_settings
from src.features.telegram.image_generator import generate_lineup_image

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parents[3] / "static"
_LINEUPS_DIR = _STATIC_DIR / "lineups"


class TelegramNotifier:
    """Generates lineup images and sends them to the Telegram group."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = LineupRepository(session)

    async def send_lineup_image(self, lineup_id: int) -> bool:
        """Generate and send a lineup image to the Telegram group.

        Returns True if sent successfully, False otherwise.
        """
        if not telegram_settings.telegram_enabled:
            return False

        data = await self.repo.get_lineup_for_image(lineup_id)
        if data is None:
            logger.warning("Lineup %d not found for image generation", lineup_id)
            return False

        # Generate image
        try:
            png_bytes = generate_lineup_image(
                display_name=data["user_display_name"],
                matchday_number=data["matchday_number"],
                formation=data["formation"],
                players=data["players"],
            )
        except Exception:
            logger.exception("Failed to generate image for lineup %d", lineup_id)
            return False

        # Save to disk
        _LINEUPS_DIR.mkdir(parents=True, exist_ok=True)
        image_rel = f"lineups/{lineup_id}.png"
        image_path = _STATIC_DIR / image_rel
        image_path.write_bytes(png_bytes)

        # Send to Telegram
        chat_id = telegram_settings.telegram_chat_id
        caption = (
            f"<b>{data['user_display_name']}</b> — "
            f"Jornada {data['matchday_number']} "
            f"({data['formation']})"
        )

        try:
            async with TelegramClient() as client:
                result = await client.send_photo(
                    chat_id=chat_id,
                    photo_bytes=png_bytes,
                    caption=caption,
                )
            sent = result.get("ok", False)
        except Exception:
            logger.exception("Failed to send Telegram photo for lineup %d", lineup_id)
            sent = False

        if sent:
            await self.repo.mark_telegram_sent(lineup_id, image_rel)
            logger.info("Telegram photo sent for lineup %d", lineup_id)

        return sent

    async def send_message(self, text: str) -> bool:
        """Send a text message to the Telegram group."""
        if not telegram_settings.telegram_enabled:
            return False

        try:
            async with TelegramClient() as client:
                result = await client.send_message(
                    chat_id=telegram_settings.telegram_chat_id,
                    text=text,
                )
            return result.get("ok", False)
        except Exception:
            logger.exception("Failed to send Telegram message")
            return False
