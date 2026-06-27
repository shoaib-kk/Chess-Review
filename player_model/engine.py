"""One Stockfish instance per worker process.

The constraint is exactly one engine per worker. We lazily launch a single
``SimpleEngine`` the first time it's needed and reuse it across tasks/positions.
If Stockfish crashes (``EngineTerminatedError``) we transparently relaunch it so
the caller can resume from the last saved ply.
"""

from __future__ import annotations

import logging
import threading

import chess.engine

from . import config
from .analyzer import find_stockfish

logger = logging.getLogger(__name__)

# Module-level singleton, one per OS process. Celery's prefork worker runs one
# task at a time per child, but the inline local runner (see ``runner.py``) shares
# this process with the API's twin-move requests. ``SimpleEngine`` is not
# thread-safe, so every consumer must hold ``ENGINE_LOCK`` while talking to it.
# Re-entrant so a single call path may acquire it more than once.
ENGINE_LOCK = threading.RLock()
_engine: chess.engine.SimpleEngine | None = None


def _launch() -> chess.engine.SimpleEngine:
    path = find_stockfish()
    eng = chess.engine.SimpleEngine.popen_uci(path)
    try:
        eng.configure(
            {"Hash": config.STOCKFISH_HASH_MB, "Threads": config.STOCKFISH_THREADS}
        )
    except chess.engine.EngineError as exc:  # pragma: no cover - exotic builds
        logger.warning("Could not set Hash/Threads: %s", exc)
    logger.info("Launched Stockfish from %s", path)
    return eng


def get_engine() -> chess.engine.SimpleEngine:
    """Return the process-wide engine, launching it on first use."""
    global _engine
    if _engine is None:
        _engine = _launch()
    return _engine


def restart_engine() -> chess.engine.SimpleEngine:
    """Force a fresh engine after a crash and return it."""
    global _engine
    shutdown_engine()
    _engine = _launch()
    return _engine


def shutdown_engine() -> None:
    """Quit the engine if running. Safe to call multiple times."""
    global _engine
    if _engine is not None:
        try:
            _engine.quit()
        except Exception:  # pragma: no cover - best effort on teardown
            pass
        _engine = None
