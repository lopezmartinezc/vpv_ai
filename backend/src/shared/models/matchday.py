from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.lineup import Lineup
    from src.shared.models.player_stat import PlayerStat
    from src.shared.models.score import ParticipantMatchdayScore
    from src.shared.models.season import Season
    from src.shared.models.team import Team


class Matchday(Base):
    __tablename__ = "matchdays"
    __table_args__ = (
        UniqueConstraint("season_id", "number", name="uq_matchday_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    counts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    first_match_at: Mapped[datetime | None] = mapped_column()
    deadline_at: Mapped[datetime | None] = mapped_column()
    stats_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    season: Mapped[Season] = relationship(back_populates="matchdays")
    matches: Mapped[list[Match]] = relationship(back_populates="matchday", lazy="selectin")
    player_stats: Mapped[list[PlayerStat]] = relationship(
        back_populates="matchday", lazy="selectin"
    )
    lineups: Mapped[list[Lineup]] = relationship(
        back_populates="matchday", lazy="selectin"
    )
    scores: Mapped[list[ParticipantMatchdayScore]] = relationship(
        back_populates="matchday", lazy="selectin"
    )


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint(
            "matchday_id", "home_team_id", "away_team_id",
            name="uq_match_teams",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    matchday_id: Mapped[int] = mapped_column(ForeignKey("matchdays.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    result: Mapped[str | None] = mapped_column(String(100))
    counts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stats_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_id: Mapped[int | None] = mapped_column()
    source_url: Mapped[str | None] = mapped_column(String(200))
    played_at: Mapped[datetime | None] = mapped_column()

    matchday: Mapped[Matchday] = relationship(back_populates="matches")
    home_team: Mapped[Team] = relationship(
        foreign_keys=[home_team_id], back_populates="home_matches"
    )
    away_team: Mapped[Team] = relationship(
        foreign_keys=[away_team_id], back_populates="away_matches"
    )
    player_stats: Mapped[list[PlayerStat]] = relationship(
        back_populates="match", lazy="selectin"
    )
