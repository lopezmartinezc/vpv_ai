from __future__ import annotations

import logging
from typing import Self

import httpx

from src.features.telegram.config import telegram_settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org"


class TelegramClient:
    """Async client for the Telegram Bot API using httpx."""

    def __init__(self) -> None:
        self._token = telegram_settings.telegram_bot_token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _url(self, method: str) -> str:
        return f"{_BASE_URL}/bot{self._token}/{method}"

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        message_thread_id: int | None = None,
    ) -> dict:
        """Send a text message to a Telegram chat.

        When *message_thread_id* is provided the message is delivered to that
        topic of a forum-enabled supergroup. Otherwise it goes to the chat's
        default thread (the "General" topic, or the regular chat in groups
        without topics).
        """
        assert self._client is not None
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        resp = await self._client.post(self._url("sendMessage"), json=payload)
        data = resp.json()
        if not data.get("ok"):
            logger.error("Telegram sendMessage failed: %s", data)
        return data

    async def send_photo(
        self,
        chat_id: str,
        photo_bytes: bytes,
        caption: str | None = None,
        filename: str = "lineup.png",
        message_thread_id: int | None = None,
    ) -> dict:
        """Send a photo (as bytes) to a Telegram chat.

        See :meth:`send_message` for *message_thread_id* semantics.
        """
        assert self._client is not None
        files = {"photo": (filename, photo_bytes, "image/png")}
        data: dict[str, str] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = "HTML"
        if message_thread_id is not None:
            data["message_thread_id"] = str(message_thread_id)
        resp = await self._client.post(
            self._url("sendPhoto"),
            data=data,
            files=files,
        )
        result = resp.json()
        if not result.get("ok"):
            logger.error("Telegram sendPhoto failed: %s", result)
        return result
