"""Probable starts, availability and team news read from external sources."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base


class PlayerAvailability(Base):
    """What one source says about one player for one matchday.

    One row per (season, matchday, source, team, name as the source writes it).
    Each refresh updates it in place, keeping the previous probability whenever
    it changes, so the screen can say "up from 50 % to 70 %". ``player_id`` is
    null when the name could not be matched with confidence: the row is kept
    and shown by its name rather than pinned on the wrong player.
    """

    __tablename__ = "player_availability"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "matchday_number",
            "source",
            "team_id",
            "raw_name",
            name="uq_player_availability",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matchday_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"))
    raw_name: Mapped[str] = mapped_column(String(120), nullable=False)
    probability: Mapped[int | None] = mapped_column(SmallInteger)
    previous_probability: Mapped[int | None] = mapped_column(SmallInteger)
    # In the source's probable eleven.
    starter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # duda | lesionado | sancionado | no_disponible | rotacion | apercibido
    status: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TeamNews(Base):
    """A news headline about a team, as a source lists it.

    Unique per team, not per URL: a match preview is listed on both teams'
    pages and belongs to both.
    """

    __tablename__ = "team_news"
    __table_args__ = (UniqueConstraint("team_id", "url", name="uq_team_news_team_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
