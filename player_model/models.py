"""SQLAlchemy ORM models for the ingestion pipeline.

Only *raw* analysis data is stored here. No aggregated player features are
computed in this phase — feature extraction is a later stage that reads these
tables.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Chess.com sync state (Section 1). Nullable so PGN-only players are unaffected.
    chess_com_username: Mapped[str | None] = mapped_column(String(128), index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    # Watermark for incremental sync: the end_time (unix seconds) of the most
    # recent game we have already ingested. Lets a 6-hour resync skip old games.
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_game_end_time: Mapped[int | None] = mapped_column(Integer)

    games: Mapped[list["Game"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        # Dedup guard: the same PGN for the same player should not be ingested twice.
        UniqueConstraint("player_id", "pgn_hash", name="uq_games_player_pgnhash"),
        # Primary dedup for Chess.com sync (Section 1 rule): a game URL is unique
        # per player. NULLs (PGN-upload games) are exempt — SQLite/Postgres both
        # allow multiple NULLs under a UNIQUE constraint.
        UniqueConstraint("player_id", "chess_com_game_url", name="uq_games_player_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pgn_raw: Mapped[str] = mapped_column(Text, nullable=False)
    # Hash of pgn_raw, kept only to enforce the dedup constraint above.
    pgn_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Where this game came from: "pgn" (uploaded) or "chesscom" (synced).
    source: Mapped[str] = mapped_column(String(16), default="pgn", nullable=False)
    # Canonical Chess.com game URL — the cross-archive dedup key (Section 1).
    chess_com_game_url: Mapped[str | None] = mapped_column(String(256), index=True)
    # bullet / blitz / rapid (daily is excluded at ingest; stored so bullet can be
    # queried / weighted separately per the spec).
    time_class: Mapped[str | None] = mapped_column(String(16), index=True)
    # End time of the game (unix seconds) — drives the incremental-sync watermark.
    end_time: Mapped[int | None] = mapped_column(Integer)
    time_control: Mapped[str | None] = mapped_column(String(64))
    date_played: Mapped[str | None] = mapped_column(String(32))
    color_played: Mapped[str | None] = mapped_column(String(8))  # "white" / "black"
    result: Mapped[str | None] = mapped_column(String(16))
    # Resume marker: highest ply already analysed and persisted for this game.
    last_analysed_ply: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analysis_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    player: Mapped["Player"] = relationship(back_populates="games")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        # One row per analysed ply in a game; also the resume idempotency key.
        UniqueConstraint("game_id", "ply", name="uq_positions_game_ply"),
        Index("ix_positions_game_ply", "game_id", "ply"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    fen: Mapped[str] = mapped_column(String(128), nullable=False)  # FEN before the move
    move_played: Mapped[str] = mapped_column(String(8), nullable=False)  # UCI
    best_move: Mapped[str | None] = mapped_column(String(8))  # UCI
    # Evaluations are stored as integer centipawns, mover's point of view.
    eval_before: Mapped[int | None] = mapped_column(Integer)
    eval_after: Mapped[int | None] = mapped_column(Integer)
    cpl: Mapped[int | None] = mapped_column(Integer)  # centipawn loss, >= 0
    is_mistake: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blunder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_brilliant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    depth_used: Mapped[int | None] = mapped_column(Integer)
    # Remaining clock (seconds) for the mover, if the PGN carried clock comments.
    # Nullable: rows ingested before this column existed stay null and the
    # time-based features degrade to null for them.
    clock_seconds: Mapped[int | None] = mapped_column(Integer)
    # Top-N candidate evals (integer cp, mover POV) from Phase 1's multipv search,
    # ordered best-first. Used by the complexity_preference feature.
    candidate_evals: Mapped[list | None] = mapped_column(JSON)

    game: Mapped["Game"] = relationship(back_populates="positions")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16),
        default=JobStatus.PENDING,
        nullable=False,
    )
    total_games: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_games: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    player: Mapped["Player"] = relationship(back_populates="jobs")


class PlayerProfile(Base):
    """The computed, structured profile for a player (Phase 2 output).

    ``features`` is the full feature blob whose shape is defined by
    ``player_model.features.compute_player_profile``. Stored as JSON so the
    schema can evolve without migrations; one row per player (player_id is PK).
    """

    __tablename__ = "player_profiles"

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    game_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    features: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Phase 6: human-readable style archetype from KMeans clustering.
    archetype: Mapped[str | None] = mapped_column(String(64))

    player: Mapped["Player"] = relationship()


class PlayerStyleVector(Base):
    """Compact PCA style embedding for a player (Phase 6).

    Stored as a JSON array so it stays portable to PostgreSQL. ``pca_version`` ties
    the vector to the PCA model that produced it; old vectors remain queryable
    until a refit recomputes them.
    """

    __tablename__ = "player_style_vectors"

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    vector: Mapped[list] = mapped_column(JSON, nullable=False)
    pca_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    player: Mapped["Player"] = relationship()


class ApiKey(Base):
    """API key for MVP authentication (Phase 7).

    Only the SHA-256 hash of the key is stored. ``player_id`` is optional: a key
    may be scoped to one player or be a general-purpose key.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BehaviouralPattern(Base):
    """A recurring behavioural pattern discovered from a player's mistakes (Phase 3).

    One row per detected pattern; patterns are recomputed (delete + reinsert) for a
    player each time, so there is no natural unique key beyond the surrogate ``id``.
    """

    __tablename__ = "behavioural_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Machine key, e.g. "repeated_queen_loss_in_middlegame".
    pattern_type: Mapped[str] = mapped_column(String(128), nullable=False)
    # Human-readable, UI-ready strings.
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1
    frequency_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supporting_game_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    player: Mapped["Player"] = relationship()
