from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base


class TournamentPrediction(Base):
    __tablename__ = "tournament_predictions"
    __table_args__ = (UniqueConstraint("season_id", "user_id", name="uq_tournament_prediction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    top_scorer_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    best_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    dark_horse_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    notes: Mapped[str | None] = mapped_column(String(500))
    bonus_points: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
