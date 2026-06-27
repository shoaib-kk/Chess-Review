"""Database access helpers. All SQL for the pipeline lives here."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .analyzer import PositionAnalysis
from .models import Game, IngestionJob, JobStatus, Player, Position
from .pgn_ingest import ParsedGame


def get_or_create_player(db: Session, username: str) -> Player:
    username = username.strip()
    player = db.scalar(select(Player).where(Player.username == username))
    if player is None:
        player = Player(username=username)
        db.add(player)
        db.flush()
    return player


def create_job(db: Session, player_id: int) -> IngestionJob:
    job = IngestionJob(player_id=player_id, status=JobStatus.PENDING)
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: int) -> Optional[IngestionJob]:
    return db.get(IngestionJob, job_id)


def set_job_status(
    db: Session,
    job: IngestionJob,
    status: JobStatus,
    *,
    total_games: Optional[int] = None,
    processed_games: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    job.status = status
    if total_games is not None:
        job.total_games = total_games
    if processed_games is not None:
        job.processed_games = processed_games
    if error is not None:
        # Append rather than overwrite so multiple failures are retained.
        job.error_log = ((job.error_log + "\n") if job.error_log else "") + error
    db.add(job)
    db.commit()


def get_or_create_game(db: Session, player_id: int, parsed: ParsedGame) -> Game:
    """Dedup by (player_id, pgn_hash). Returns the existing row if present.

    The existing row carries ``last_analysed_ply``, which lets the worker resume
    a game that was only partially analysed before a crash.
    """
    game = db.scalar(
        select(Game).where(
            Game.player_id == player_id, Game.pgn_hash == parsed.pgn_hash
        )
    )
    if game is not None:
        return game

    game = Game(
        player_id=player_id,
        pgn_raw=parsed.pgn_raw,
        pgn_hash=parsed.pgn_hash,
        time_control=parsed.time_control,
        date_played=parsed.date_played,
        color_played=parsed.color_played,
        result=parsed.result,
    )
    db.add(game)
    db.flush()
    return game


def game_url_exists(db: Session, player_id: int, url: str) -> bool:
    """Section 1 dedup check: has this Chess.com game URL already been ingested?"""
    return db.scalar(
        select(Game.id).where(
            Game.player_id == player_id, Game.chess_com_game_url == url
        )
    ) is not None


def create_chesscom_game(
    db: Session,
    player_id: int,
    parsed: ParsedGame,
    *,
    url: str,
    time_class: str | None,
    end_time: int | None,
) -> Game:
    """Insert a freshly-synced Chess.com game, tagged with its source metadata.

    Callers must first check ``game_url_exists`` (the unique (player_id, url) index
    is the hard backstop). Falls back to the PGN-hash row if the same PGN was
    already uploaded manually, so a game is never analysed twice.
    """
    existing = db.scalar(
        select(Game).where(
            Game.player_id == player_id, Game.pgn_hash == parsed.pgn_hash
        )
    )
    if existing is not None:
        # Same game arrived earlier via PGN upload — adopt the URL metadata.
        existing.source = "chesscom"
        existing.chess_com_game_url = url
        existing.time_class = time_class
        existing.end_time = end_time
        db.flush()
        return existing

    game = Game(
        player_id=player_id,
        pgn_raw=parsed.pgn_raw,
        pgn_hash=parsed.pgn_hash,
        source="chesscom",
        chess_com_game_url=url,
        time_class=time_class,
        end_time=end_time,
        time_control=parsed.time_control,
        date_played=parsed.date_played,
        color_played=parsed.color_played,
        result=parsed.result,
    )
    db.add(game)
    db.flush()
    return game


def set_player_chesscom(
    db: Session, player: Player, chess_com_username: str, avatar_url: str | None
) -> None:
    player.chess_com_username = chess_com_username
    player.avatar_url = avatar_url
    db.add(player)
    db.commit()


def mark_player_synced(db: Session, player_id: int, last_game_end_time: int | None) -> None:
    """Advance the incremental-sync watermark after a successful sync."""
    player = db.get(Player, player_id)
    if player is None:
        return
    player.last_synced_at = datetime.now(timezone.utc)
    if last_game_end_time is not None:
        player.last_game_end_time = max(player.last_game_end_time or 0, last_game_end_time)
    db.add(player)
    db.commit()


def players_due_for_resync(db: Session, *, interval_hours: int) -> list[Player]:
    """Connected players whose last sync is older than ``interval_hours`` (or never)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=interval_hours)
    return list(
        db.scalars(
            select(Player).where(
                Player.chess_com_username.is_not(None),
                or_(Player.last_synced_at.is_(None), Player.last_synced_at < cutoff),
            )
        )
    )


def max_saved_ply(db: Session, game_id: int) -> int:
    """Highest ply already persisted for a game (0 if none) — the resume point."""
    return db.scalar(
        select(func.coalesce(func.max(Position.ply), 0)).where(
            Position.game_id == game_id
        )
    ) or 0


def flush_positions(
    db: Session,
    game_id: int,
    analyses: list[tuple[int, PositionAnalysis, Optional[int]]],
) -> None:
    """Persist a batch of (ply, analysis, clock_seconds) and advance the resume marker."""
    if not analyses:
        return
    db.add_all(
        Position(
            game_id=game_id,
            ply=ply,
            fen=a.fen,
            move_played=a.move_played,
            best_move=a.best_move,
            eval_before=a.eval_before,
            eval_after=a.eval_after,
            cpl=a.cpl,
            is_mistake=a.is_mistake,
            is_blunder=a.is_blunder,
            is_brilliant=a.is_brilliant,
            depth_used=a.depth_used,
            clock_seconds=clock,
            candidate_evals=[c.eval_cp for c in a.candidates] or None,
        )
        for ply, a, clock in analyses
    )
    game = db.get(Game, game_id)
    if game is not None:
        game.last_analysed_ply = max(game.last_analysed_ply, analyses[-1][0])
    db.commit()


def mark_game_complete(db: Session, game_id: int) -> None:
    game = db.get(Game, game_id)
    if game is not None:
        game.analysis_complete = True
        db.commit()
