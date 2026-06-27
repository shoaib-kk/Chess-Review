"""initial schema: games and puzzles

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19

Creates the games table (each analysed game, reviewed or mined) and the puzzles
table (one row per generated puzzle, FK to games with ON DELETE CASCADE).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("game_url", sa.String(length=512), nullable=True),
        sa.Column("pgn_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="review"),
        sa.Column("mined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("game_date", sa.String(length=32), nullable=True),
        sa.Column("original_pgn", sa.Text(), nullable=False),
        sa.Column("white_player", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("black_player", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("white_elo", sa.Integer(), nullable=True),
        sa.Column("black_elo", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(length=255), nullable=True),
        sa.Column("site", sa.String(length=255), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column("opening", sa.String(length=255), nullable=True),
        sa.Column("eco_code", sa.String(length=8), nullable=True),
        sa.Column("analysis_version", sa.String(length=32), nullable=True),
        sa.Column("analysis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("average_accuracy", sa.Float(), nullable=True),
        sa.Column("total_blunders", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_mistakes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_inaccuracies", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("username", "game_url", name="uq_games_username_game_url"),
    )
    op.create_index("ix_games_username", "games", ["username"])
    op.create_index("ix_games_game_url", "games", ["game_url"])
    op.create_index("ix_games_pgn_hash", "games", ["pgn_hash"])

    op.create_table(
        "puzzles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("fen", sa.Text(), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=True),
        sa.Column("side_to_move", sa.String(length=8), nullable=True),
        sa.Column("best_move", sa.String(length=16), nullable=False),
        sa.Column("best_move_uci", sa.String(length=8), nullable=True),
        sa.Column("played_move", sa.String(length=16), nullable=True),
        sa.Column("continuation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evaluation_before", sa.Float(), nullable=True),
        sa.Column("evaluation_after", sa.Float(), nullable=True),
        sa.Column("cp_loss", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=True),
        sa.Column("solved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("game_id", "move_number", name="uq_puzzles_game_move"),
    )
    op.create_index("ix_puzzles_game_id", "puzzles", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_puzzles_game_id", table_name="puzzles")
    op.drop_table("puzzles")
    op.drop_index("ix_games_pgn_hash", table_name="games")
    op.drop_index("ix_games_game_url", table_name="games")
    op.drop_index("ix_games_username", table_name="games")
    op.drop_table("games")
