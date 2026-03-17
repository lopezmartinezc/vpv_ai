from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.matchday import Matchday
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.season import Season


class AchievementDefinition(Base):
    __tablename__ = "achievement_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    achievement_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name_es: Mapped[str] = mapped_column(String(100), nullable=False)
    description_es: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    max_tier: Mapped[int] = mapped_column(SmallInteger, default=1)
    repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "participant_id",
            "matchday_id",
            "achievement_key",
            name="uq_achievement",
        ),
        Index("idx_achievements_season", "season_id"),
        Index("idx_achievements_participant", "participant_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("season_participants.id"), nullable=False
    )
    matchday_id: Mapped[int | None] = mapped_column(ForeignKey("matchdays.id"), nullable=True)
    achievement_key: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, default=1)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    season: Mapped[Season] = relationship(foreign_keys=[season_id])
    participant: Mapped[SeasonParticipant] = relationship(foreign_keys=[participant_id])
    matchday: Mapped[Matchday | None] = relationship(foreign_keys=[matchday_id])
