"""add games.owner_id (device-scoped ownership)

Revision ID: 0002_add_owner_id
Revises: 0001_initial
Create Date: 2026-06-28

Data is now scoped to an anonymous per-device id (a random UUID generated in the
browser on first visit), not the self-asserted Chess.com username. ``username``
stays on the row as the Chess.com player identity (used for color/accuracy
detection and display); ``owner_id`` is the new ownership key. The per-user
uniqueness constraint moves from ``(username, game_url)`` to
``(owner_id, game_url)`` so each device dedups its own copy of a game.

Existing rows keep ``owner_id = NULL`` (orphaned, invisible to any device); the
data is cheaply regenerable from public Chess.com games.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_owner_id"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("games", sa.Column("owner_id", sa.String(length=64), nullable=True))
    op.create_index("ix_games_owner_id", "games", ["owner_id"])
    op.drop_constraint("uq_games_username_game_url", "games", type_="unique")
    op.create_unique_constraint("uq_games_owner_game_url", "games", ["owner_id", "game_url"])


def downgrade() -> None:
    op.drop_constraint("uq_games_owner_game_url", "games", type_="unique")
    op.create_unique_constraint("uq_games_username_game_url", "games", ["username", "game_url"])
    op.drop_index("ix_games_owner_id", table_name="games")
    op.drop_column("games", "owner_id")
