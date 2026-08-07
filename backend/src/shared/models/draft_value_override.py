from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base


class DraftValueOverride(Base):
    """Admin-set manual value + note for a player on the draft board.

    A ``manual_value`` (pts/match) replaces the automatic projection when set
    — the only way to value a brand-new player (no history) or one whose role
    changed. Shared across the season, keyed by (season_id, player_id).
    """

    __tablename__ = "draft_value_overrides"
    __table_args__ = (UniqueConstraint("season_id", "player_id", name="uq_draft_value_override"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    manual_value: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
