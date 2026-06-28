"""training layer: drills, drill attempts, SRS queue, streaks, import cursors

Revision ID: 0003_training
Revises: 0002_add_owner_id
Create Date: 2026-06-28

Adds the habit-forming training subsystem. All new per-user data is scoped to the
anonymous per-device id (``device_id``), the same key ``games.owner_id`` uses; the
Chess.com ``username`` is stored only for display/regeneration, never for scoping.

- ``drills`` / ``drill_attempts`` — weakness-targeted "play-out" drills mined from
  the user's own games (a critical position + an objective to convert/hold/defend)
  and the verdicts of each attempt.
- ``srs_queue`` — spaced-repetition schedule over the user's puzzles.
- ``streaks`` — one row per device: daily-set completion streak.
- ``import_cursors`` — per (device, username) high-water mark of the last
  auto-imported Chess.com game, so polling only fetches genuinely new games.

A ``games.reviewed`` flag is added so the "ready to review" inbox can list
auto-imported games that the user has not yet opened.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_training"
down_revision: Union[str, None] = "0002_add_owner_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "drills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("source_game_id", sa.Integer(), nullable=False),
        sa.Column("fen", sa.Text(), nullable=False),
        sa.Column("user_color", sa.String(length=8), nullable=False),
        sa.Column("start_eval_cp", sa.Integer(), nullable=False),
        sa.Column("objective", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_game_id"], ["games.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("device_id", "source_game_id", "fen", name="uq_drills_device_game_fen"),
    )
    op.create_index("ix_drills_device_id", "drills", ["device_id"])
    op.create_index("ix_drills_source_game_id", "drills", ["source_game_id"])

    op.create_table(
        "drill_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drill_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("verdict", sa.String(length=8), nullable=False),
        sa.Column("final_eval_cp", sa.Integer(), nullable=True),
        sa.Column("swing_cp", sa.Integer(), nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["drill_id"], ["drills.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_drill_attempts_drill_id", "drill_attempts", ["drill_id"])
    op.create_index("ix_drill_attempts_device_id", "drill_attempts", ["device_id"])

    op.create_table(
        "srs_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("puzzle_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("interval_stage", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_result", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["puzzle_id"], ["puzzles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("device_id", "puzzle_id", name="uq_srs_device_puzzle"),
    )
    op.create_index("ix_srs_queue_device_id", "srs_queue", ["device_id"])
    op.create_index("ix_srs_queue_puzzle_id", "srs_queue", ["puzzle_id"])

    op.create_table(
        "streaks",
        sa.Column("device_id", sa.String(length=64), primary_key=True),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_completed_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "import_cursors",
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("last_end_time", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("device_id", "username", name="pk_import_cursors"),
    )


def downgrade() -> None:
    op.drop_table("import_cursors")
    op.drop_table("streaks")
    op.drop_index("ix_srs_queue_puzzle_id", table_name="srs_queue")
    op.drop_index("ix_srs_queue_device_id", table_name="srs_queue")
    op.drop_table("srs_queue")
    op.drop_index("ix_drill_attempts_device_id", table_name="drill_attempts")
    op.drop_index("ix_drill_attempts_drill_id", table_name="drill_attempts")
    op.drop_table("drill_attempts")
    op.drop_index("ix_drills_source_game_id", table_name="drills")
    op.drop_index("ix_drills_device_id", table_name="drills")
    op.drop_table("drills")
    op.drop_column("games", "reviewed")
