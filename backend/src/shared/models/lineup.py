from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.matchday import Matchday
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.player import Player


class Lineup(Base):
    __tablename__ = "lineups"
    __table_args__ = (
        UniqueConstraint(
            "participant_id", "matchday_id", name="uq_lineup_participant_matchday"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("season_participants.id"), nullable=False
    )
    matchday_id: Mapped[int] = mapped_column(ForeignKey("matchdays.id"), nullable=False)
    formation: Mapped[str] = mapped_column(String(10), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column()
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_sent_at: Mapped[datetime | None] = mapped_column()
    image_path: Mapped[str | None] = mapped_column(String(255))
    total_points: Mapped[int] = mapped_column(SmallInteger, default=0)

    participant: Mapped[SeasonParticipant] = relationship(back_populates="lineups")
    matchday: Mapped[Matchday] = relationship(back_populates="lineups")
    players: Mapped[list[LineupPlayer]] = relationship(
        back_populates="lineup",
        cascade="all, delete-orphan",
        order_by="LineupPlayer.display_order",
        lazy="selectin",
    )


class LineupPlayer(Base):
    __tablename__ = "lineup_players"
    __table_args__ = (
        UniqueConstraint("lineup_id", "player_id", name="uq_lineup_player"),
        UniqueConstraint("lineup_id", "display_order", name="uq_lineup_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lineup_id: Mapped[int] = mapped_column(
        ForeignKey("lineups.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    position_slot: Mapped[str] = mapped_column(String(3), nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    points: Mapped[int] = mapped_column(SmallInteger, default=0)

    lineup: Mapped[Lineup] = relationship(back_populates="players")
    player: Mapped[Player] = relationship(back_populates="lineup_entries")
