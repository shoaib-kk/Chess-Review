"""Local task execution without Redis or a separate Celery worker.

The engine is designed around Celery: the API enqueues background jobs with
``.delay()`` and a worker (``--concurrency=1``) runs them against a single
Stockfish process. That is the right shape for a deployment, but it is heavy for
running on a laptop — it needs a Redis broker and a second process.

When ``PM_INLINE_TASKS`` is enabled (the default), ``dispatch()`` instead runs
the task in a single background thread inside the API process:

* The HTTP handler returns immediately, so the onboarding UI's job-status
  polling keeps working exactly as it does against a real worker.
* A ``max_workers=1`` pool mirrors Celery's ``--concurrency=1`` so only one
  Stockfish-bound job runs at a time.
* Celery is put in eager mode (see ``celery_app``), so the chained ``.delay()``
  calls *inside* tasks (``compute_profile`` -> ``compute_patterns`` …) run
  synchronously within that same background thread.

Set ``PM_INLINE_TASKS=0`` to restore the real broker/worker behaviour (e.g. the
Docker Compose stack), in which case ``dispatch()`` is a thin ``.delay()`` wrapper.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


# Default ON: the common case for this repo is running locally without Redis.
INLINE_TASKS = _truthy(os.getenv("PM_INLINE_TASKS", "1"))

# One worker thread => at most one Stockfish-bound job at a time, matching the
# Celery worker's --concurrency=1. Jobs queue behind each other in submit order.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pm-inline")


def _run(task, args, kwargs) -> None:
    try:
        # ``.apply()`` executes the task body synchronously in this thread,
        # independent of Celery's eager flag, and never touches a broker.
        task.apply(args=list(args), kwargs=dict(kwargs))
    except Exception:  # noqa: BLE001  - background job: log, don't crash the pool
        logger.exception("Inline task %s failed", getattr(task, "name", task))


def dispatch(task, *args, **kwargs) -> None:
    """Enqueue a Celery task.

    Inline mode submits it to the background thread pool (non-blocking); otherwise
    it is handed to the Celery broker via ``.delay()``.
    """
    if INLINE_TASKS:
        _executor.submit(_run, task, args, kwargs)
    else:
        task.delay(*args, **kwargs)
