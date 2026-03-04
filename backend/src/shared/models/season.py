from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base

if TYPE_CHECKING:
    from src.shared.models.competition import Competition
    from src.shared.models.draft import Draft
    from src.shared.models.matchday import Matchday
    from src.shared.models.participant import SeasonParticipant
    from src.shared.models.team import Team
    from src.shared.models.transaction import Transaction


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="setup", nullable=False)
    matchday_start: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    matchday_end: Mapped[int | None] = mapped_column(SmallInteger)
    matchday_current: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    matchday_winter: Mapped[int | None] = mapped_column(SmallInteger)
    matchday_scanned: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    draft_pool_size: Mapped[int] = mapped_column(SmallInteger, default=26, nullable=False)
    lineup_deadline_min: Mapped[int] = mapped_column(SmallInteger, default=30, nullable=False)
    total_participants: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    scoring_rules: Mapped[list[ScoringRule]] = relationship(back_populates="season", lazy="raise")
    payments: Mapped[list[SeasonPayment]] = relationship(back_populates="season", lazy="raise")
    participants: Mapped[list[SeasonParticipant]] = relationship(
        back_populates="season", lazy="raise"
    )
    teams: Mapped[list[Team]] = relationship(back_populates="season", lazy="raise")
    matchdays: Mapped[list[Matchday]] = relationship(back_populates="season", lazy="raise")
    drafts: Mapped[list[Draft]] = relationship(back_populates="season", lazy="raise")
    competitions: Mapped[list[Competition]] = relationship(back_populates="season", lazy="raise")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="season", lazy="raise")


class ScoringRule(Base):
    __tablename__ = "scoring_rules"
    __table_args__ = (
        UniqueConstraint("season_id", "rule_key", "position", name="uq_scoring_rule"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[str | None] = mapped_column(String(3))
    value: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))

    season: Mapped[Season] = relationship(back_populates="scoring_rules")


class SeasonPayment(Base):
    __tablename__ = "season_payments"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "payment_type",
            "position_rank",
            name="uq_season_payment",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    position_rank: Mapped[int | None] = mapped_column(SmallInteger)
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))

    season: Mapped[Season] = relationship(back_populates="payments")


class ValidFormation(Base):
    __tablename__ = "valid_formations"

    id: Mapped[int] = mapped_column(primary_key=True)
    formation: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    defenders: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    midfielders: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    forwards: Mapped[int] = mapped_column(SmallInteger, nullable=False)
