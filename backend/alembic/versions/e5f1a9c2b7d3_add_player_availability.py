"""Probable starts, availability and team news from external sources."""

import sqlalchemy as sa

from alembic import op

revision: str = "e5f1a9c2b7d3"
down_revision: str = "d9e2a4b681f0"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_table(
        "player_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "season_id",
            sa.Integer(),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matchday_number", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("raw_name", sa.String(120), nullable=False),
        sa.Column("probability", sa.SmallInteger(), nullable=True),
        sa.Column("previous_probability", sa.SmallInteger(), nullable=True),
        sa.Column("starter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "season_id",
            "matchday_number",
            "source",
            "team_id",
            "raw_name",
            name="uq_player_availability",
        ),
    )
    op.create_index(
        "ix_player_availability_season_id", "player_availability", ["season_id"], unique=False
    )
    op.create_table(
        "team_news",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "season_id",
            sa.Integer(),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "url", name="uq_team_news_team_url"),
    )
    op.create_index("ix_team_news_season_id", "team_news", ["season_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_team_news_season_id", table_name="team_news")
    op.drop_table("team_news")
    op.drop_index("ix_player_availability_season_id", table_name="player_availability")
    op.drop_table("player_availability")
