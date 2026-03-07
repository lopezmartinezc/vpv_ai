"""add_player_ownership_log

Revision ID: c8a1f3e72d91
Revises: b4526c391b2d
Create Date: 2026-03-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a1f3e72d91'
down_revision: Union[str, None] = 'b4526c391b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_ownership_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("from_matchday", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["season_participants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season_id", "player_id", "from_matchday",
            name="uq_ownership_log_player_matchday",
        ),
    )
    op.create_index("idx_ownership_log_season", "player_ownership_log", ["season_id"])
    op.create_index("idx_ownership_log_participant", "player_ownership_log", ["participant_id"])
    op.create_index("idx_ownership_log_player", "player_ownership_log", ["player_id"])


def downgrade() -> None:
    op.drop_index("idx_ownership_log_player", table_name="player_ownership_log")
    op.drop_index("idx_ownership_log_participant", table_name="player_ownership_log")
    op.drop_index("idx_ownership_log_season", table_name="player_ownership_log")
    op.drop_table("player_ownership_log")
