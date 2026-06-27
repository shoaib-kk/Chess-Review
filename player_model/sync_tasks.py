"""Chess.com sync Celery tasks (Section 1).

Flow: list the player's monthly archives -> normalise + filter games (no daily,
no variants, optional time-class subset) -> dedup by ``chess_com_game_url`` ->
analyse each new game's positions with the same per-position pipeline used by PGN
upload -> advance the player's incremental-sync watermark -> recompute the
profile.

Heavy work (Stockfish) happens here, at ingestion time — never during gameplay.
A periodic beat task triggers an incremental resync every ``SYNC_INTERVAL_HOURS``.
"""

from __future__ import annotations

import logging
import traceback

import chess
import chess.engine

from . import config, repository as repo
from .celery_app import celery_app
from .chesscom_client import ChessComClientError, iter_new_games
from .db import SessionLocal
from .models import JobStatus, Player
from .pgn_ingest import parse_pgn
from .tasks import _analyse_game

logger = logging.getLogger(__name__)


def _collect_new_games(db, player, incremental: bool, time_classes):
    """Return the list of (ChessComGame, ParsedGame) still needing ingestion.

    Fetches every relevant archive up front so the job's ``total_games`` is known
    before analysis begins (good for a determinate progress bar). URL dedup is
    applied here; the unique index is the backstop.
    """
    since = player.last_game_end_time if incremental else None
    collected = []
    for game in iter_new_games(
        player.chess_com_username, since_end_time=since, time_classes=time_classes
    ):
        if not game.url or repo.game_url_exists(db, player.id, game.url):
            continue
        parsed_list = parse_pgn(game.pgn, username=player.chess_com_username)
        if not parsed_list:
            continue
        collected.append((game, parsed_list[0]))
    return collected


@celery_app.task(bind=True, name="player_model.sync_chess_com", max_retries=3)
def sync_chess_com(
    self,
    job_id: int,
    player_id: int,
    *,
    incremental: bool = False,
    time_classes: list[str] | None = None,
):
    """Sync a connected player's Chess.com games. Idempotent and resumable."""
    db = SessionLocal()
    job = repo.get_job(db, job_id)
    if job is None:
        db.close()
        raise ValueError(f"Sync job {job_id} not found")

    player = db.get(Player, player_id)
    if player is None or not player.chess_com_username:
        repo.set_job_status(db, job, JobStatus.FAILED, error="Player not connected to Chess.com.")
        db.close()
        return

    try:
        repo.set_job_status(db, job, JobStatus.RUNNING, total_games=0, processed_games=0)
        new_games = _collect_new_games(db, player, incremental, time_classes)
        repo.set_job_status(db, job, JobStatus.RUNNING, total_games=len(new_games))

        processed = 0
        max_end_time = player.last_game_end_time or 0
        for game, parsed in new_games:
            try:
                row = repo.create_chesscom_game(
                    db, player_id, parsed,
                    url=game.url, time_class=game.time_class, end_time=game.end_time,
                )
                db.commit()
                resume_from = repo.max_saved_ply(db, row.id)
                _analyse_game(db, row.id, parsed, resume_from)
                if game.end_time:
                    max_end_time = max(max_end_time, game.end_time)
            except chess.engine.EngineTerminatedError:
                db.rollback()
                repo.set_job_status(
                    db, job, JobStatus.RUNNING,
                    error=f"Stockfish crash on {game.url}; will retry.",
                )
                raise
            except Exception as exc:  # one bad game shouldn't kill the whole sync
                db.rollback()
                repo.set_job_status(
                    db, job, JobStatus.RUNNING, error=f"Game skipped ({game.url}): {exc}"
                )
            finally:
                processed += 1
                repo.set_job_status(db, job, JobStatus.RUNNING, processed_games=processed)

        repo.mark_player_synced(db, player_id, max_end_time or None)
        repo.set_job_status(db, job, JobStatus.COMPLETED, processed_games=processed)

        try:
            from .cache import invalidate_player

            invalidate_player(player_id)
        except Exception:  # noqa: BLE001
            logger.warning("Cache invalidation failed for player %s", player_id)

        # Only recompute the profile if we actually ingested new games.
        if new_games:
            from .profile_tasks import compute_profile

            compute_profile.delay(player_id)
    except ChessComClientError as exc:
        repo.set_job_status(db, job, JobStatus.FAILED, error=f"Chess.com error: {exc}")
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


@celery_app.task(name="player_model.enqueue_incremental_syncs")
def enqueue_incremental_syncs() -> int:
    """Beat task: resync every connected player whose last sync is >6h old."""
    db = SessionLocal()
    try:
        due = repo.players_due_for_resync(db, interval_hours=config.SYNC_INTERVAL_HOURS)
        for player in due:
            job = repo.create_job(db, player.id)
            db.commit()
            sync_chess_com.delay(job.id, player.id, incremental=True)
        return len(due)
    finally:
        db.close()
