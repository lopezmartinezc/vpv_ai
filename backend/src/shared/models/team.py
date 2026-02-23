from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.matchday import Match
    from src.shared.models.player import Player
    from src.shared.models.season import Season


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("season_id", "slug", name="uq_team_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(10))
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(255))

    season: Mapped[Season] = relationship(back_populates="teams")
    players: Mapped[list[Player]] = relationship(back_populates="team", lazy="selectin")
    home_matches: Mapped[list[Match]] = relationship(
        foreign_keys="[Match.home_team_id]", back_populates="home_team", lazy="selectin"
    )
    away_matches: Mapped[list[Match]] = relationship(
        foreign_keys="[Match.away_team_id]", back_populates="away_team", lazy="selectin"
    )
