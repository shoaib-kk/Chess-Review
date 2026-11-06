"""scout watchlist: friends a device watches for new games / opening changes

Revision ID: 0004_scout_watch
Revises: 0003_training
Create Date: 2026-07-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_scout_watch"
down_revision: Union[str, None] = "0003_training"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scout_watch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_end_time", sa.BigInteger(), nullable=True),
        sa.Column("last_seen_ratings", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("owner_id", "username", name="uq_scout_watch_owner_username"),
    )
    op.create_index("ix_scout_watch_owner_id", "scout_watch", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_scout_watch_owner_id", table_name="scout_watch")
    op.drop_table("scout_watch")
