"""Private V2 chat history and expiring per-user/draft leases."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d9e2a4b681f0"
down_revision: str = "c8a1f3e72d91"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_table(
        "draft_assistant_v2_chats",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "draft_id",
            sa.Integer(),
            sa.ForeignKey("drafts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("exchanges", postgresql.JSONB(), nullable=False),
        sa.Column("lease_id", sa.String(36), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("draft_assistant_v2_chats")
