from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.achievements.models import Achievement, AchievementDefinition
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.user import User

logger = logging.getLogger(__name__)


class AchievementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_achievements(self, achievements: list[Achievement]) -> int:
        """Bulk insert achievements with ON CONFLICT DO NOTHING.

        Returns the number of rows actually inserted.
        """
        if not achievements:
            return 0

        rows = [
            {
                "season_id": a.season_id,
                "participant_id": a.participant_id,
                "matchday_id": a.matchday_id,
                "achievement_key": a.achievement_key,
                "tier": a.tier,
                "metadata": a.metadata_,
                "created_at": a.created_at,
            }
            for a in achievements
        ]

        stmt = (
            pg_insert(Achievement).values(rows).on_conflict_do_nothing(constraint="uq_achievement")
        )
        cursor = await self.session.execute(stmt)
        inserted = getattr(cursor, "rowcount", 0) or 0
        logger.debug("upsert_achievements: inserted=%d of %d", inserted, len(achievements))
        return inserted

    async def get_by_season(self, season_id: int) -> list[dict]:
        """Return all achievements for a season, joined with definitions."""
        stmt = (
            select(
                Achievement.id,
                Achievement.achievement_key,
                Achievement.tier,
                Achievement.participant_id,
                Achievement.matchday_id,
                Achievement.metadata_.label("metadata"),
                Achievement.created_at,
                AchievementDefinition.name_es.label("name"),
                AchievementDefinition.description_es.label("description"),
                AchievementDefinition.icon,
                AchievementDefinition.category,
                User.display_name,
                Matchday.number.label("matchday_number"),
            )
            .join(
                AchievementDefinition,
                Achievement.achievement_key == AchievementDefinition.achievement_key,
            )
            .join(SeasonParticipant, Achievement.participant_id == SeasonParticipant.id)
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(Matchday, Achievement.matchday_id == Matchday.id)
            .where(Achievement.season_id == season_id)
            .order_by(Achievement.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_by_participant(self, season_id: int, participant_id: int) -> list[dict]:
        """Return achievements for a single participant in a season."""
        stmt = (
            select(
                Achievement.id,
                Achievement.achievement_key,
                Achievement.tier,
                Achievement.participant_id,
                Achievement.matchday_id,
                Achievement.metadata_.label("metadata"),
                Achievement.created_at,
                AchievementDefinition.name_es.label("name"),
                AchievementDefinition.description_es.label("description"),
                AchievementDefinition.icon,
                AchievementDefinition.category,
                User.display_name,
                Matchday.number.label("matchday_number"),
            )
            .join(
                AchievementDefinition,
                Achievement.achievement_key == AchievementDefinition.achievement_key,
            )
            .join(SeasonParticipant, Achievement.participant_id == SeasonParticipant.id)
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(Matchday, Achievement.matchday_id == Matchday.id)
            .where(
                Achievement.season_id == season_id,
                Achievement.participant_id == participant_id,
            )
            .order_by(Achievement.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_by_matchday(self, season_id: int, matchday_id: int) -> list[dict]:
        """Return achievements granted for a specific matchday."""
        stmt = (
            select(
                Achievement.id,
                Achievement.achievement_key,
                Achievement.tier,
                Achievement.participant_id,
                Achievement.matchday_id,
                Achievement.metadata_.label("metadata"),
                Achievement.created_at,
                AchievementDefinition.name_es.label("name"),
                AchievementDefinition.description_es.label("description"),
                AchievementDefinition.icon,
                AchievementDefinition.category,
                User.display_name,
                Matchday.number.label("matchday_number"),
            )
            .join(
                AchievementDefinition,
                Achievement.achievement_key == AchievementDefinition.achievement_key,
            )
            .join(SeasonParticipant, Achievement.participant_id == SeasonParticipant.id)
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(Matchday, Achievement.matchday_id == Matchday.id)
            .where(
                Achievement.season_id == season_id,
                Achievement.matchday_id == matchday_id,
            )
            .order_by(Achievement.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_definitions(self) -> list[AchievementDefinition]:
        """Return all achievement definitions ordered by category and key."""
        stmt = select(AchievementDefinition).order_by(
            AchievementDefinition.category, AchievementDefinition.achievement_key
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_keys(self, season_id: int, participant_id: int) -> set[str]:
        """Return the set of achievement_keys already granted for this participant/season."""
        stmt = select(Achievement.achievement_key).where(
            Achievement.season_id == season_id,
            Achievement.participant_id == participant_id,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def delete_season_achievements(self, season_id: int) -> int:
        """Delete all achievements for a season (for re-evaluation).

        Returns the number of rows deleted.
        """
        stmt = delete(Achievement).where(Achievement.season_id == season_id)
        cursor = await self.session.execute(stmt)
        deleted = getattr(cursor, "rowcount", 0) or 0
        logger.info("delete_season_achievements: season_id=%d deleted=%d", season_id, deleted)
        return deleted
