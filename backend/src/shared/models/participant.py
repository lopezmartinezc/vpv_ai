from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.draft import DraftPick
    from src.shared.models.lineup import Lineup
    from src.shared.models.player import Player
    from src.shared.models.score import ParticipantMatchdayScore
    from src.shared.models.season import Season
    from src.shared.models.transaction import Transaction
    from src.shared.models.user import User


class SeasonParticipant(Base):
    __tablename__ = "season_participants"
    __table_args__ = (UniqueConstraint("season_id", "user_id", name="uq_season_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    draft_order: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    season: Mapped[Season] = relationship(back_populates="participants")
    user: Mapped[User] = relationship(back_populates="participations")
    players: Mapped[list[Player]] = relationship(back_populates="owner", lazy="raise")
    draft_picks: Mapped[list[DraftPick]] = relationship(back_populates="participant", lazy="raise")
    lineups: Mapped[list[Lineup]] = relationship(back_populates="participant", lazy="raise")
    matchday_scores: Mapped[list[ParticipantMatchdayScore]] = relationship(
        back_populates="participant", lazy="raise"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="participant", lazy="raise"
    )
