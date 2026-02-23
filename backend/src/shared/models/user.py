from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.shared.models.participant import SeasonParticipant


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50))

    participations: Mapped[list[SeasonParticipant]] = relationship(
        back_populates="user", lazy="raise"
    )
