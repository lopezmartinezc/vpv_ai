from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.base.repository import BaseRepository
from src.shared.models.season import ValidFormation


class TestBaseRepository:
    @pytest.fixture
    def repo(self, db_session: AsyncSession) -> BaseRepository[ValidFormation]:
        return BaseRepository(ValidFormation, db_session)

    async def test_list_returns_empty_when_no_data(
        self, repo: BaseRepository[ValidFormation],
    ) -> None:
        result = await repo.list()
        assert isinstance(result, list)

    async def test_get_by_id_returns_none_for_missing(
        self, repo: BaseRepository[ValidFormation],
    ) -> None:
        result = await repo.get_by_id(9999)
        assert result is None

    async def test_get_by_id_returns_entity(
        self, db_session: AsyncSession, repo: BaseRepository[ValidFormation],
    ) -> None:
        formation = ValidFormation(
            formation="1-4-4-2", defenders=4, midfielders=4, forwards=2,
        )
        db_session.add(formation)
        await db_session.flush()

        result = await repo.get_by_id(formation.id)
        assert result is not None
        assert result.formation == "1-4-4-2"

    async def test_filter_by_returns_matching(
        self, db_session: AsyncSession, repo: BaseRepository[ValidFormation],
    ) -> None:
        db_session.add(ValidFormation(formation="1-3-4-3", defenders=3, midfielders=4, forwards=3))
        db_session.add(ValidFormation(formation="1-5-3-2", defenders=5, midfielders=3, forwards=2))
        await db_session.flush()

        result = await repo.filter_by(defenders=3)
        assert len(result) == 1
        assert result[0].formation == "1-3-4-3"

    async def test_count_returns_total(
        self, db_session: AsyncSession, repo: BaseRepository[ValidFormation],
    ) -> None:
        db_session.add(ValidFormation(formation="1-4-3-3", defenders=4, midfielders=3, forwards=3))
        db_session.add(ValidFormation(formation="1-5-4-1", defenders=5, midfielders=4, forwards=1))
        await db_session.flush()

        total = await repo.count()
        assert total == 2

    async def test_list_with_offset_and_limit(
        self, db_session: AsyncSession, repo: BaseRepository[ValidFormation],
    ) -> None:
        for i, f in enumerate(["1-3-4-3", "1-4-4-2", "1-5-3-2"]):
            db_session.add(ValidFormation(formation=f, defenders=3 + i, midfielders=4, forwards=3))
        await db_session.flush()

        result = await repo.list(offset=1, limit=1)
        assert len(result) == 1
