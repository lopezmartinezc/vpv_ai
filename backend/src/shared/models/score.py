from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.matchday import Matchday
    from src.shared.models.participant import SeasonParticipant


class ParticipantMatchdayScore(Base):
    __tablename__ = "participant_matchday_scores"
    __table_args__ = (
        UniqueConstraint(
            "participant_id", "matchday_id",
            name="uq_participant_matchday_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("season_participants.id"), nullable=False
    )
    matchday_id: Mapped[int] = mapped_column(ForeignKey("matchdays.id"), nullable=False)
    total_points: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    ranking: Mapped[int | None] = mapped_column(SmallInteger)

    participant: Mapped[SeasonParticipant] = relationship(
        back_populates="matchday_scores"
    )
    matchday: Mapped[Matchday] = relationship(back_populates="scores")
