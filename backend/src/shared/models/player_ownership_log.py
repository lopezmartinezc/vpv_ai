from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.player import Player
    from src.shared.models.season import Season


class PlayerOwnershipLog(Base):
    """Tracks player ownership changes across a season.

    Each row records that *participant_id* owns *player_id* starting from
    *from_matchday* (inclusive).  A NULL participant_id means the player was
    released (no owner from that matchday onward).

    To find the owner of a player at a given matchday N:
        SELECT * FROM player_ownership_log
        WHERE player_id = :pid AND season_id = :sid AND from_matchday <= N
        ORDER BY from_matchday DESC LIMIT 1
    """

    __tablename__ = "player_ownership_log"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "player_id",
            "from_matchday",
            name="uq_ownership_log_player_matchday",
        ),
        Index("idx_ownership_log_season", "season_id"),
        Index("idx_ownership_log_participant", "participant_id"),
        Index("idx_ownership_log_player", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    participant_id: Mapped[int | None] = mapped_column(
        ForeignKey("season_participants.id"),
        nullable=True,
    )
    from_matchday: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    season: Mapped[Season] = relationship()
    player: Mapped[Player] = relationship()
    participant: Mapped[SeasonParticipant | None] = relationship()
