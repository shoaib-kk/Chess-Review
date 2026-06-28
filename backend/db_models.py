"""SQLAlchemy ORM models for persisted games and puzzles.

Named ``db_models`` to avoid clashing with the root-level ``models.py`` (the
analysis dataclasses). A ``Game`` is any analysed game — reviewed interactively
or mined for puzzles in the background; a ``Puzzle`` always belongs to exactly
one game and is deleted with it.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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
        # per owner are allowed while chess.com games dedup on their URL.
        UniqueConstraint("owner_id", "game_url", name="uq_games_owner_game_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Ownership key: an anonymous per-device id (random UUID from the browser).
    # All reads are scoped to this; it is NOT the Chess.com username.
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # The Chess.com player identity for this game — used for color/accuracy
    # detection and display, not for ownership.
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    game_url: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    pgn_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "review" (interactive) or "mine" (background puzzle pipeline).
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="review")
    # True once the puzzle miner has processed this game (incl. 0-puzzle games),
    # so it is not re-analysed. Replaces the old `analyzed_games` table.
    mined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True once the user has opened this game in interactive review. Drives the
    # "ready to review" inbox: an auto-imported game stays unreviewed until then.
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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


class Drill(Base):
    """A weakness-targeted play-out position drawn from the user's own game.

    Unlike a :class:`Puzzle` (find the single best move), a drill is a *full
    play-out*: the user plays ``fen`` against Stockfish and is graded on whether
    they met the ``objective`` (convert a winning position / hold an equal one /
    defend a worse one) rather than on finding one move. Scoped to ``device_id``;
    ``username`` is the Chess.com identity used to detect the user's side.
    """

    __tablename__ = "drills"
    __table_args__ = (
        UniqueConstraint("device_id", "source_game_id", "fen", name="uq_drills_device_game_fen"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fen: Mapped[str] = mapped_column(Text, nullable=False)
    # "White" / "Black" — the side the user plays out.
    user_color: Mapped[str] = mapped_column(String(8), nullable=False)
    # Engine eval at the critical moment, in centipawns from the user's POV.
    start_eval_cp: Mapped[int] = mapped_column(Integer, nullable=False)
    # "convert" (winning) | "hold" (equal) | "defend" (worse).
    objective: Mapped[str] = mapped_column(String(16), nullable=False)
    # Human training-category label, e.g. "Converting winning middlegames".
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    attempts: Mapped[list["DrillAttempt"]] = relationship(
        back_populates="drill", cascade="all, delete-orphan", passive_deletes=True
    )


class DrillAttempt(Base):
    """One graded play-out of a drill: the server-computed verdict + evals."""

    __tablename__ = "drill_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    drill_id: Mapped[int] = mapped_column(
        ForeignKey("drills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "pass" / "fail".
    verdict: Mapped[str] = mapped_column(String(8), nullable=False)
    final_eval_cp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    swing_cp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    drill: Mapped["Drill"] = relationship(back_populates="attempts")


class SrsCard(Base):
    """A puzzle scheduled for spaced repetition on a device.

    Interval ladder is +1 / +3 / +7 days (``interval_stage`` 0→1→2). A pass
    advances the stage; a fail resets it to 0 and re-shows the card tomorrow.
    """

    __tablename__ = "srs_queue"
    __table_args__ = (
        UniqueConstraint("device_id", "puzzle_id", name="uq_srs_device_puzzle"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    puzzle_id: Mapped[int] = mapped_column(
        ForeignKey("puzzles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    interval_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Streak(Base):
    """Per-device daily-set completion streak (intrinsic motivation, not secured)."""

    __tablename__ = "streaks"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ImportCursor(Base):
    """High-water mark of auto-imported Chess.com games, per (device, username)."""

    __tablename__ = "import_cursors"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_end_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
