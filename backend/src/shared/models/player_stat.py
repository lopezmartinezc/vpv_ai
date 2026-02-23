from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.matchday import Match, Matchday
    from src.shared.models.player import Player


class PlayerStat(Base):
    __tablename__ = "player_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "matchday_id", name="uq_player_matchday"),
        Index("idx_player_stats_matchday", "matchday_id"),
        Index("idx_player_stats_player", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    matchday_id: Mapped[int] = mapped_column(ForeignKey("matchdays.id"), nullable=False)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))

    # Estado
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Posicion en esta jornada (FUENTE DE VERDAD para calculo de puntos)
    position: Mapped[str] = mapped_column(String(3), nullable=False)

    # Participacion
    played: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    event: Mapped[str | None] = mapped_column(String(60))
    event_minute: Mapped[int | None] = mapped_column(SmallInteger)
    minutes_played: Mapped[int | None] = mapped_column(SmallInteger)

    # Resultado del equipo
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    result: Mapped[int | None] = mapped_column(SmallInteger)
    goals_for: Mapped[int | None] = mapped_column(SmallInteger)
    goals_against: Mapped[int | None] = mapped_column(SmallInteger)

    # Datos crudos del scraping
    goals: Mapped[int] = mapped_column(SmallInteger, default=0)
    penalty_goals: Mapped[int] = mapped_column(SmallInteger, default=0)
    penalties_missed: Mapped[int] = mapped_column(SmallInteger, default=0)
    own_goals: Mapped[int] = mapped_column(SmallInteger, default=0)
    assists: Mapped[int] = mapped_column(SmallInteger, default=0)
    penalties_saved: Mapped[int] = mapped_column(SmallInteger, default=0)
    yellow_card: Mapped[bool] = mapped_column(Boolean, default=False)
    yellow_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    double_yellow: Mapped[bool] = mapped_column(Boolean, default=False)
    red_card: Mapped[bool] = mapped_column(Boolean, default=False)
    woodwork: Mapped[int] = mapped_column(SmallInteger, default=0)
    penalties_won: Mapped[int] = mapped_column(SmallInteger, default=0)
    penalties_committed: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Valoracion mediatica
    marca_rating: Mapped[str | None] = mapped_column(String(10))
    as_picas: Mapped[str | None] = mapped_column(String(10))

    # Puntos calculados
    pts_play: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_starter: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_result: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_clean_sheet: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_goals: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_penalty_goals: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_assists: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_penalties_saved: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_woodwork: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_penalties_won: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_penalties_missed: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_own_goals: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_yellow: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_red: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_pen_committed: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_marca: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_as: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_marca_as: Mapped[int] = mapped_column(SmallInteger, default=0)
    pts_total: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Relationships
    player: Mapped[Player] = relationship(back_populates="stats")
    matchday: Mapped[Matchday] = relationship(back_populates="player_stats")
    match: Mapped[Match | None] = relationship(back_populates="player_stats")
