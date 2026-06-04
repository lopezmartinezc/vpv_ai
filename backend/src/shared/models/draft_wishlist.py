from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, SmallInteger, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.draft import Draft
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.player import Player


class DraftWishlist(Base):
    __tablename__ = "draft_wishlists"
    __table_args__ = (
        UniqueConstraint("draft_id", "participant_id", name="uq_wishlist_draft_participant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("season_participants.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    draft: Mapped[Draft] = relationship()
    participant: Mapped[SeasonParticipant] = relationship()
    players: Mapped[list[DraftWishlistPlayer]] = relationship(
        back_populates="wishlist",
        order_by="DraftWishlistPlayer.priority",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DraftWishlistPlayer(Base):
    __tablename__ = "draft_wishlist_players"
    __table_args__ = (
        UniqueConstraint("wishlist_id", "player_id", name="uq_wishlist_player"),
        UniqueConstraint("wishlist_id", "priority", name="uq_wishlist_priority"),
        Index("idx_wishlist_players_wishlist", "wishlist_id", "priority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wishlist_id: Mapped[int] = mapped_column(
        ForeignKey("draft_wishlists.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    wishlist: Mapped[DraftWishlist] = relationship(back_populates="players")
    player: Mapped[Player] = relationship(lazy="joined")
