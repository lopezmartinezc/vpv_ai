from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.shared.models.draft import Draft

from .config import config
from .errors import AssistantError
from .models import ChatState
from .schemas import Exchange, History


def chat_key(user_id: int, draft_id: int) -> tuple[int, int]:
    return user_id, draft_id


async def configure(session: AsyncSession) -> None:
    await session.execute(text("SET LOCAL statement_timeout = '5000ms'"))


async def read_history(user_id: int, draft_id: int) -> History:
    async with AsyncSessionLocal() as session, session.begin():
        await configure(session)
        row = await session.get(ChatState, chat_key(user_id, draft_id))
        return (
            History(exchanges=[Exchange.model_validate(e) for e in row.exchanges])
            if row
            else History()
        )


async def acquire(user_id: int, draft_id: int) -> str:
    now, lease = datetime.now(UTC), str(uuid4())
    async with AsyncSessionLocal() as session, session.begin():
        await configure(session)
        if await session.get(Draft, draft_id) is None:
            raise AssistantError("DRAFT_NOT_FOUND", "Draft no encontrado.", 404)
        await session.execute(
            insert(ChatState)
            .values(user_id=user_id, draft_id=draft_id, exchanges=[])
            .on_conflict_do_nothing()
        )
        stmt = (
            update(ChatState)
            .where(
                ChatState.user_id == user_id,
                ChatState.draft_id == draft_id,
                or_(ChatState.lease_until.is_(None), ChatState.lease_until < now),
            )
            .values(
                lease_id=lease, lease_until=now + timedelta(seconds=config.timeout_seconds + 30)
            )
        )
        result = await session.scalar(stmt.returning(ChatState.lease_id))
        if result is None:
            raise AssistantError("CHAT_BUSY", "Ya hay una consulta activa para este draft.", 409)
    return lease


async def release(user_id: int, draft_id: int, lease: str) -> None:
    async with AsyncSessionLocal() as session, session.begin():
        await configure(session)
        await session.execute(
            update(ChatState)
            .where(
                ChatState.user_id == user_id,
                ChatState.draft_id == draft_id,
                ChatState.lease_id == lease,
            )
            .values(lease_id=None, lease_until=None)
        )


async def save(user_id: int, draft_id: int, lease: str, exchange: Exchange) -> None:
    async with AsyncSessionLocal() as session, session.begin():
        await configure(session)
        row = await session.scalar(
            select(ChatState)
            .where(
                ChatState.user_id == user_id,
                ChatState.draft_id == draft_id,
                ChatState.lease_id == lease,
            )
            .with_for_update()
        )
        if row is None:
            raise AssistantError(
                "CHAT_CHANGED", "La conversación cambió; vuelve a consultar.", 409
            )
        row.exchanges = [*row.exchanges[-39:], exchange.model_dump(mode="json")]


async def clear(user_id: int, draft_id: int) -> None:
    async with AsyncSessionLocal() as session, session.begin():
        await configure(session)
        row = await session.get(ChatState, chat_key(user_id, draft_id), with_for_update=True)
        if row is None:
            return
        if row.lease_until is not None and row.lease_until > datetime.now(UTC):
            raise AssistantError(
                "CHAT_BUSY", "Cancela la consulta antes de borrar el historial.", 409
            )
        await session.delete(row)
