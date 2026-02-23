from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.draft import DraftPick
    from src.shared.models.lineup import LineupPlayer
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.player_stat import PlayerStat
    from src.shared.models.team import Team


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("season_id", "slug", name="uq_player_slug"),
        Index("idx_players_season", "season_id"),
        Index("idx_players_owner", "owner_id"),
        Index("idx_players_team", "team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(3), nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(500))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("season_participants.id"))

    team: Mapped[Team] = relationship(back_populates="players")
    owner: Mapped[SeasonParticipant | None] = relationship(back_populates="players")
    stats: Mapped[list[PlayerStat]] = relationship(back_populates="player", lazy="selectin")
    draft_picks: Mapped[list[DraftPick]] = relationship(
        back_populates="player", lazy="selectin"
    )
    lineup_entries: Mapped[list[LineupPlayer]] = relationship(
        back_populates="player", lazy="selectin"
    )
