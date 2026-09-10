from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base


class ChatState(Base):
    __tablename__ = "draft_assistant_v2_chats"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("drafts.id", ondelete="CASCADE"), primary_key=True
    )
    exchanges: Mapped[list[dict[str, JsonValue]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    lease_id: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
