"""add_stats_crc_to_matches

Revision ID: 501c85808658
Revises: 73fd1b04133b
Create Date: 2026-02-26 11:32:04.704092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '501c85808658'
down_revision: Union[str, None] = '73fd1b04133b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("stats_crc", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "stats_crc")
