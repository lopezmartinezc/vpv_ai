from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
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
    # Extended predictions stored as JSONB:
    #   {
    #     "groups": {"A": [team_id_1st, team_id_2nd, team_id_3rd, team_id_4th], ...},
    #     "best_thirds": ["A", "C", "E", "F", "I", "J", "K", "L"],
    #     "match_winners": {"M73": team_id, "M74": team_id, ...}
    #   }
    bracket_predictions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
