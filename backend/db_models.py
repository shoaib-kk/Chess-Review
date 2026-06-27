"""SQLAlchemy ORM models for persisted games and puzzles.

Named ``db_models`` to avoid clashing with the root-level ``models.py`` (the
analysis dataclasses). A ``Game`` is any analysed game — reviewed interactively
or mined for puzzles in the background; a ``Puzzle`` always belongs to exactly
one game and is deleted with it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        # Postgres treats NULLs as distinct, so many null-url (pasted PGN) rows
        # per user are allowed while chess.com games dedup on their URL.
        UniqueConstraint("username", "game_url", name="uq_games_username_game_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    game_url: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    pgn_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "review" (interactive) or "mine" (background puzzle pipeline).
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="review")
    # True once the puzzle miner has processed this game (incl. 0-puzzle games),
    # so it is not re-analysed. Replaces the old `analyzed_games` table.
    mined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    game_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original_pgn: Mapped[str] = mapped_column(Text, nullable=False)

    white_player: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    black_player: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    white_elo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    black_elo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    opening: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eco_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

    analysis_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analysis_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    average_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_blunders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_mistakes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_inaccuracies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    puzzles: Mapped[list["Puzzle"]] = relationship(
        back_populates="game", cascade="all, delete-orphan", passive_deletes=True
    )


class Puzzle(Base):
    __tablename__ = "puzzles"
    __table_args__ = (
        UniqueConstraint("game_id", "move_number", name="uq_puzzles_game_move"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )

    fen: Mapped[str] = mapped_column(Text, nullable=False)
    move_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "White" / "Black" — the side that was to move (was `color`).
    side_to_move: Mapped[str | None] = mapped_column(String(8), nullable=True)
    best_move: Mapped[str] = mapped_column(String(16), nullable=False)
    best_move_uci: Mapped[str | None] = mapped_column(String(8), nullable=True)
    played_move: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Principal variation as a JSON array of SAN strings (was `pv`).
    continuation: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    evaluation_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    cp_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "Blunder" / "Mistake" — also serves as the difficulty bucket.
    classification: Mapped[str | None] = mapped_column(String(16), nullable=True)

    solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    game: Mapped["Game"] = relationship(back_populates="puzzles")
