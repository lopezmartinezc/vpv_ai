from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.base import Base


class BaseRepository[T: Base]:
    def __init__(self, model: type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, entity_id: int) -> T | None:
        return await self.session.get(self.model, entity_id)

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: Any | None = None,
    ) -> list[T]:
        stmt = select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def filter_by(self, **kwargs: Any) -> list[T]:
        stmt = select(self.model).filter_by(**kwargs)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **kwargs: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if kwargs:
            stmt = stmt.filter_by(**kwargs)
        result = await self.session.execute(stmt)
        return result.scalar_one()
