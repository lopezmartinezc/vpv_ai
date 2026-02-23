from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.matchday import Matchday
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.season import Season


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_participant", "participant_id"),
        Index("idx_transactions_season", "season_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("season_participants.id"), nullable=False
    )
    matchday_id: Mapped[int | None] = mapped_column(ForeignKey("matchdays.id"))
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    season: Mapped[Season] = relationship(back_populates="transactions")
    participant: Mapped[SeasonParticipant] = relationship(back_populates="transactions")
    matchday: Mapped[Matchday | None] = relationship()
