from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineups.repository import LineupRepository
from src.features.telegram.client import TelegramClient
from src.features.telegram.config import telegram_settings
from src.features.telegram.image_generator import generate_lineup_image
from src.shared.models.season import Season

logger = logging.getLogger(__name__)


async def resolve_chat_id(session: AsyncSession, season_id: int | None = None) -> str:
    """Resolve Telegram chat_id with per-season override.

    Kept for backwards compatibility — new code should prefer
    :func:`resolve_chat_target` which also returns the thread_id.
    """
    chat_id, _ = await resolve_chat_target(session, season_id)
    return chat_id


async def resolve_chat_target(
    session: AsyncSession, season_id: int | None = None
) -> tuple[str, int | None]:
    """Resolve (chat_id, thread_id) with per-season override.

    Returns the season-specific Telegram chat + thread when set, otherwise
    falls back to the global ``TELEGRAM_CHAT_ID`` (with no thread). The
    thread is only honoured when the season also overrides the chat — a
    season's ``telegram_thread_id`` is meaningless against the global chat.
    """
    if season_id is not None:
        season = await session.get(Season, season_id)
        if season is not None and season.telegram_chat_id:
            return season.telegram_chat_id, season.telegram_thread_id
    return telegram_settings.telegram_chat_id, None


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

        # Send to Telegram — resolve chat/thread with per-season override
        chat_id, thread_id = await resolve_chat_target(self.repo.session, data.get("season_id"))
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
                    message_thread_id=thread_id,
                )
            sent = result.get("ok", False)
        except Exception:
            logger.exception("Failed to send Telegram photo for lineup %d", lineup_id)
            sent = False

        if sent:
            await self.repo.mark_telegram_sent(lineup_id, image_rel)
            logger.info("Telegram photo sent for lineup %d", lineup_id)

        return sent

    async def send_message(self, text: str, season_id: int | None = None) -> bool:
        """Send a text message to the Telegram group.

        If ``season_id`` is given and that season has a custom telegram_chat_id,
        it is used; otherwise the global chat_id is used.
        """
        if not telegram_settings.telegram_enabled:
            return False

        chat_id, thread_id = await resolve_chat_target(self.repo.session, season_id)

        try:
            async with TelegramClient() as client:
                result = await client.send_message(
                    chat_id=chat_id, text=text, message_thread_id=thread_id
                )
            return result.get("ok", False)
        except Exception:
            logger.exception("Failed to send Telegram message")
            return False

    async def send_alert(self, text: str, season_id: int | None = None) -> bool:
        """Send a message to the alerts chat (deadline reminders, etc.).

        Resolution order:
        1. season.telegram_chat_id (if season_id provided + season has it)
        2. settings.telegram_alerts_chat_id (dedicated alerts chat)
        3. telegram_settings.telegram_chat_id (global default)
        """
        if not telegram_settings.telegram_enabled:
            return False

        from src.core.config import settings

        # Try per-season chat first (with its thread); otherwise alerts chat
        # (no thread) or global default.
        thread_id: int | None = None
        if season_id is not None:
            season = await self.repo.session.get(Season, season_id)
            if season is not None and season.telegram_chat_id:
                chat_id = season.telegram_chat_id
                thread_id = season.telegram_thread_id
            else:
                chat_id = settings.telegram_alerts_chat_id or telegram_settings.telegram_chat_id
        else:
            chat_id = settings.telegram_alerts_chat_id or telegram_settings.telegram_chat_id

        try:
            async with TelegramClient() as client:
                result = await client.send_message(
                    chat_id=chat_id, text=text, message_thread_id=thread_id
                )
            return result.get("ok", False)
        except Exception:
            logger.exception("Failed to send Telegram alert")
            return False
