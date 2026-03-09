from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.player import Player
    from src.shared.models.season import Season


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    draft_type: Mapped[str] = mapped_column(String(20), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    current_round: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    current_pick: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    season: Mapped[Season] = relationship(back_populates="drafts")
    picks: Mapped[list[DraftPick]] = relationship(
        back_populates="draft", order_by="DraftPick.pick_number", lazy="raise"
    )


class DraftPick(Base):
    __tablename__ = "draft_picks"
    __table_args__ = (
        UniqueConstraint("draft_id", "pick_number", name="uq_draft_pick_number"),
        UniqueConstraint("draft_id", "player_id", name="uq_draft_player"),
        Index("idx_draft_picks_participant", "participant_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), nullable=False)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("season_participants.id"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pick_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    picked_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    dropped_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)

    draft: Mapped[Draft] = relationship(back_populates="picks")
    participant: Mapped[SeasonParticipant] = relationship(back_populates="draft_picks")
    player: Mapped[Player] = relationship(foreign_keys=[player_id], back_populates="draft_picks")
    dropped_player: Mapped[Player | None] = relationship(foreign_keys=[dropped_player_id])
