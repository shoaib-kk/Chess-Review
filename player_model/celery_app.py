"""Celery application and worker lifecycle hooks."""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from . import config
from .db import init_db
from .engine import shutdown_engine

logger = logging.getLogger(__name__)

celery_app = Celery(
    "player_model",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=[
        "player_model.tasks",
        "player_model.profile_tasks",
        "player_model.pattern_tasks",
        "player_model.sync_tasks",
    ],
)

celery_app.conf.update(
    task_acks_late=True,  # don't lose a job if a worker dies mid-task
    task_track_started=True,
    worker_prefetch_multiplier=1,  # one CPU-bound task at a time per child
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Incremental Chess.com resync every SYNC_INTERVAL_HOURS (Section 1). Runs
    # only when a beat scheduler is started (`celery ... beat`).
    beat_schedule={
        "incremental-chesscom-sync": {
            "task": "player_model.enqueue_incremental_syncs",
            "schedule": config.SYNC_INTERVAL_HOURS * 3600.0,
        },
    },
)

# Local (no-broker) mode: when the API runs tasks inline in a background thread,
# put Celery in eager mode so the chained ``.delay()`` calls inside tasks
# (ingest -> compute_profile -> compute_patterns) execute synchronously in that
# thread instead of trying to reach a Redis broker that isn't running.
from .runner import INLINE_TASKS  # noqa: E402  (avoid a circular import at top)

if INLINE_TASKS:
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=False,
        task_store_eager_result=False,
    )


@worker_process_init.connect
def _on_worker_start(**_kwargs):  # pragma: no cover - worker lifecycle
    # Ensure tables exist; the engine is launched lazily on first task.
    init_db()
    logger.info("Worker process initialised.")


@worker_process_shutdown.connect
def _on_worker_shutdown(**_kwargs):  # pragma: no cover - worker lifecycle
    shutdown_engine()
    logger.info("Worker process shut down; Stockfish stopped.")
