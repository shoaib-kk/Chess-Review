"""The Celery ingestion task.

Flow: parse all games -> for each game, analyse every position where it's the
target player's turn -> write positions in batches of 50 -> update job progress.
A Stockfish crash relaunches the engine and resumes from the last saved ply.
"""

from __future__ import annotations

import logging
import traceback

import chess
import chess.engine

from . import config, repository as repo
from .analyzer import analyse_position
from .celery_app import celery_app
from .db import SessionLocal
from .engine import ENGINE_LOCK, get_engine, restart_engine
from .models import JobStatus
from .pgn_ingest import ParsedGame, ParsedMove, parse_pgn

logger = logging.getLogger(__name__)


def _analyse_game(db, game_id: int, parsed: ParsedGame, resume_from_ply: int) -> None:
    """Analyse one game's positions, batching writes and resuming if needed.

    Only positions where it is the *target player's* turn are analysed (we model
    the player, not the opponent). Already-saved plies (<= ``resume_from_ply``)
    are skipped so a re-run after a crash is idempotent.
    """
    target_color = parsed.color_played  # "white"/"black"/None
    batch: list[tuple[int, "PositionAnalysis", int | None]] = []  # noqa: F821

    for move in parsed.moves:
        if move.ply <= resume_from_ply:
            continue
        # Skip positions that aren't the target player's move.
        if target_color is not None and move.turn != target_color:
            continue

        board = chess.Board(move.fen_before)
        played = chess.Move.from_uci(move.uci)

        analysis = _analyse_with_recovery(board, played)
        batch.append((move.ply, analysis, move.clock_seconds))

        if len(batch) >= config.BATCH_SIZE:
            repo.flush_positions(db, game_id, batch)
            batch = []

    if batch:
        repo.flush_positions(db, game_id, batch)
    repo.mark_game_complete(db, game_id)


def _analyse_with_recovery(board: chess.Board, played: chess.Move):
    """Analyse one position, relaunching Stockfish once if it has crashed.

    Holds the shared ``ENGINE_LOCK`` for the duration so a concurrent twin-move
    request in the same process (inline local runner) cannot use Stockfish at the
    same time. The lock is released between positions, keeping twin moves snappy.
    """
    with ENGINE_LOCK:
        try:
            return analyse_position(get_engine(), board, played)
        except chess.engine.EngineTerminatedError:
            logger.warning("Stockfish crashed; relaunching and retrying position.")
            restart_engine()
            return analyse_position(get_engine(), board, played)


@celery_app.task(bind=True, name="player_model.ingest_pgn", max_retries=3)
def ingest_pgn(self, job_id: int, player_id: int, pgn_string: str, username: str | None = None):
    """Ingest a PGN string for a player. Idempotent and resumable per game."""
    db = SessionLocal()
    job = repo.get_job(db, job_id)
    if job is None:
        db.close()
        raise ValueError(f"Ingestion job {job_id} not found")

    try:
        games = parse_pgn(pgn_string, username=username)
        repo.set_job_status(
            db, job, JobStatus.RUNNING, total_games=len(games), processed_games=0
        )

        processed = 0
        for parsed in games:
            try:
                game = repo.get_or_create_game(db, player_id, parsed)
                db.commit()
                resume_from = repo.max_saved_ply(db, game.id)
                _analyse_game(db, game.id, parsed, resume_from)
            except chess.engine.EngineTerminatedError:
                # Engine could not be kept alive — surface and let Celery retry,
                # which will resume from the last saved ply of each game.
                db.rollback()
                repo.set_job_status(
                    db, job, JobStatus.RUNNING,
                    error=f"Stockfish crash on game {parsed.date_played}; will retry.",
                )
                raise
            except Exception as exc:  # one bad game shouldn't kill the whole job
                db.rollback()
                repo.set_job_status(
                    db, job, JobStatus.RUNNING,
                    error=f"Game skipped ({parsed.date_played}): {exc}",
                )
            finally:
                processed += 1
                repo.set_job_status(db, job, JobStatus.RUNNING, processed_games=processed)

        repo.set_job_status(db, job, JobStatus.COMPLETED, processed_games=processed)
        # Job complete -> drop all cached responses for this player (Phase 7).
        try:
            from .cache import invalidate_player

            invalidate_player(player_id)
        except Exception:  # noqa: BLE001
            logger.warning("Cache invalidation failed for player %s", player_id)
        # Ingestion done -> automatically kick off Phase 2 feature extraction.
        # Imported lazily to avoid a circular import at module load.
        from .profile_tasks import compute_profile

        compute_profile.delay(player_id)
    except chess.engine.EngineTerminatedError as exc:
        try:
            self.retry(countdown=10, exc=exc)
        except self.MaxRetriesExceededError:
            repo.set_job_status(db, job, JobStatus.FAILED, error="Max retries exceeded.")
    except Exception as exc:
        repo.set_job_status(
            db, job, JobStatus.FAILED, error=f"{exc}\n{traceback.format_exc()}"
        )
        raise
    finally:
        db.close()
