from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.competition import Competition
    from src.shared.models.matchday import Matchday
    from src.shared.models.participant import SeasonParticipant


class CompetitionMatchup(Base):
    """Head-to-head cruce between two VPV participants for a single VPV
    matchday inside a playoff competition.

    Shape is intentionally format-agnostic: the plugin that built the
    competition (see ``features/competitions/formats``) decides whether
    ``group_label``/``round_label``/``feeder_*`` are populated. The
    motor downstream only cares about ``score_a``, ``score_b`` and
    ``winner_participant_id``.
    """

    __tablename__ = "competition_matchups"
    __table_args__ = (
        CheckConstraint(
            "participant_a_id IS NULL OR participant_b_id IS NULL "
            "OR participant_a_id <> participant_b_id",
            name="chk_pair_distinct",
        ),
        Index("idx_matchups_competition", "competition_id"),
        Index("idx_matchups_matchday", "matchday_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False
    )
    phase: Mapped[str] = mapped_column(String(20), nullable=False)  # 'regular' | 'ko'
    group_label: Mapped[str | None] = mapped_column(String(10))
    round_label: Mapped[str | None] = mapped_column(String(20))
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    matchday_id: Mapped[int | None] = mapped_column(
        ForeignKey("matchdays.id", ondelete="SET NULL")
    )
    participant_a_id: Mapped[int | None] = mapped_column(
        ForeignKey("season_participants.id", ondelete="SET NULL")
    )
    participant_b_id: Mapped[int | None] = mapped_column(
        ForeignKey("season_participants.id", ondelete="SET NULL")
    )
    feeder_a_id: Mapped[int | None] = mapped_column(ForeignKey("competition_matchups.id"))
    feeder_b_id: Mapped[int | None] = mapped_column(ForeignKey("competition_matchups.id"))
    score_a: Mapped[int | None] = mapped_column(Integer)
    score_b: Mapped[int | None] = mapped_column(Integer)
    winner_participant_id: Mapped[int | None] = mapped_column(
        ForeignKey("season_participants.id", ondelete="SET NULL")
    )

    competition: Mapped[Competition] = relationship(back_populates="matchups")
    matchday: Mapped[Matchday | None] = relationship()
    participant_a: Mapped[SeasonParticipant | None] = relationship(foreign_keys=[participant_a_id])
    participant_b: Mapped[SeasonParticipant | None] = relationship(foreign_keys=[participant_b_id])
    winner: Mapped[SeasonParticipant | None] = relationship(foreign_keys=[winner_participant_id])
