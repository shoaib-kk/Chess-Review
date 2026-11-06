"""Background "deep" scouting job: the engine-heavy and network-heavy analyses.

Three stages run in a worker thread per (opponent, filters) key:

1. **refutations**: Stockfish checks the moves the opponent habitually plays in
   their opening tree (``scout_refutations.find_refutations``).
2. **fingerprint**: full shallow analysis of their recent games to see how,
   when and where they go wrong (``scout_fingerprint.build_fingerprint``).
3. **lichess**: rating-banded Lichess explorer lookups for traps at their level
   (``scout_traps.find_trappy_lines``).

Each stage fails independently (a broken stage leaves its section empty plus a
logged warning) except a missing/crashed engine, which fails the job. At most
one job holds the engine at a time so interactive review keeps a free engine
slot; later jobs wait their turn. Results live in memory for ``RESULT_TTL_S``.
The JSON shape is ``ScoutDeepStatus`` in ``frontend/src/types.ts``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .chesscom_client import get_recent_games
from .opponent_scout import build_tree, parse_game

logger = logging.getLogger(__name__)

REFUTATION_DEPTH = 13
REFUTATION_POSITIONS = 40
FINGERPRINT_DEPTH = 10
FINGERPRINT_GAMES = 40
RESULT_TTL_S = 60 * 60
MAX_TRACKED_JOBS = 64

_lock = threading.Lock()
_jobs: dict[tuple, dict[str, Any]] = {}
# One deep job may hold the engine at a time; the pool has only a couple of
# engines and interactive /analyze must not starve.
_engine_slot = threading.Semaphore(1)


def _key(username: str, limit: int, time_class: str | None, rated_only: bool) -> tuple:
    return (username.strip().lower(), limit, time_class or "", bool(rated_only))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _idle() -> dict[str, Any]:
    return {
        "state": "idle",
        "stage": None,
        "progress": {"done": 0, "total": 0},
        "started_at": None,
        "error": None,
        "result": None,
    }


def _public(job: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def _expire_locked() -> None:
    now = time.monotonic()
    stale = [
        key for key, job in _jobs.items()
        if job["state"] in ("done", "error") and now - job.get("_finished", now) > RESULT_TTL_S
    ]
    for key in stale:
        del _jobs[key]
    if len(_jobs) > MAX_TRACKED_JOBS:
        finished = sorted(
            (k for k, j in _jobs.items() if j["state"] in ("done", "error")),
            key=lambda k: _jobs[k].get("_finished", 0),
        )
        for key in finished[: len(_jobs) - MAX_TRACKED_JOBS]:
            del _jobs[key]


def get_status(username: str, limit: int, time_class: str | None, rated_only: bool) -> dict[str, Any]:
    with _lock:
        _expire_locked()
        job = _jobs.get(_key(username, limit, time_class, rated_only))
        return _public(job) if job else _idle()


def start_job(username: str, limit: int, time_class: str | None, rated_only: bool) -> dict[str, Any]:
    """Start (or return the already-running) job for these filters."""
    key = _key(username, limit, time_class, rated_only)
    with _lock:
        _expire_locked()
        job = _jobs.get(key)
        if job and job["state"] == "running":
            return _public(job)
        job = {
            **_idle(),
            "state": "running",
            "stage": "fetching",
            "started_at": _now_iso(),
        }
        _jobs[key] = job
    thread = threading.Thread(
        target=_run, args=(key, username.strip(), limit, time_class, rated_only), daemon=True, name=f"scout-deep-{key[0]}"
    )
    thread.start()
    with _lock:
        return _public(_jobs[key])


def _update(key: tuple, **fields: Any) -> None:
    with _lock:
        job = _jobs.get(key)
        if job is not None:
            job.update(fields)


def _progress_cb(key: tuple):
    def report(done: int, total: int) -> None:
        _update(key, progress={"done": int(done), "total": int(total)})
    return report


def _main_rating(games) -> tuple[int | None, str | None]:
    """Their latest rating in the time class they play most."""
    classes = Counter(g.time_class for g in games if g.time_class)
    if not classes:
        return None, None
    main = classes.most_common(1)[0][0]
    for g in games:  # newest first
        if g.time_class == main and g.own_rating:
            return g.own_rating, main
    return None, main


def _run(key: tuple, username: str, limit: int, time_class: str | None, rated_only: bool) -> None:
    from stockfish_engine import EngineUnavailableError, StockfishEngine  # root-level module

    from .scout_fingerprint import build_fingerprint
    from .scout_refutations import find_refutations

    result: dict[str, Any] = {
        "refutations": [],
        "fingerprint": None,
        "lichess_traps": None,
        "lichess_error": None,
        "generated_at": None,
    }
    try:
        raw = get_recent_games(username, limit=limit)
        if time_class:
            raw = [g for g in raw if g.get("time_class") == time_class]
        if rated_only:
            raw = [g for g in raw if g.get("rated")]
        games = [g for g in (parse_game(r, username) for r in raw) if g is not None]
        games.sort(key=lambda g: -g.end_time)
        trees = {"white": build_tree(games, "white"), "black": build_tree(games, "black")}

        _update(key, stage="refutations", progress={"done": 0, "total": 0})
        with _engine_slot:
            try:
                with StockfishEngine(depth=REFUTATION_DEPTH) as engine:
                    result["refutations"] = find_refutations(
                        trees,
                        lambda board, multipv: engine.analyse_candidates(board, depth=REFUTATION_DEPTH, multipv=multipv),
                        max_positions=REFUTATION_POSITIONS,
                        progress=_progress_cb(key),
                    )
            except EngineUnavailableError:
                raise
            except Exception:
                logger.warning("Scout refutation stage failed for %s", username, exc_info=True)

            _update(key, stage="fingerprint", progress={"done": 0, "total": 0})
            try:
                with StockfishEngine(depth=FINGERPRINT_DEPTH) as engine:
                    result["fingerprint"] = build_fingerprint(
                        raw,
                        username,
                        lambda board: engine.analyse_position(board, depth=FINGERPRINT_DEPTH, include_pv=True),
                        depth=FINGERPRINT_DEPTH,
                        max_games=FINGERPRINT_GAMES,
                        progress=_progress_cb(key),
                    )
            except EngineUnavailableError:
                raise
            except Exception:
                logger.warning("Scout fingerprint stage failed for %s", username, exc_info=True)

        _update(key, stage="lichess", progress={"done": 0, "total": 0})
        try:
            from .lichess_explorer import fetch_explorer
            from .scout_traps import find_trappy_lines, lichess_rating_buckets, lichess_speeds, rating_band_label

            rating, main_class = _main_rating(games)
            buckets = lichess_rating_buckets(rating, time_class or main_class)
            speeds = lichess_speeds(time_class or main_class)
            band = rating_band_label(buckets) if buckets else "all ratings"
            result["lichess_traps"] = find_trappy_lines(
                trees,
                lambda fen: fetch_explorer(fen, ratings=buckets, speeds=speeds),
                rating_band=band,
                speeds=speeds,
                progress=_progress_cb(key),
            )
        except Exception as exc:  # LichessExplorerError and anything unexpected
            logger.warning("Scout Lichess stage failed for %s: %s", username, exc)
            result["lichess_error"] = str(exc)[:300] or "The Lichess opening explorer is unavailable right now."

        result["generated_at"] = _now_iso()
        _update(key, state="done", stage="done", result=result, _finished=time.monotonic())
    except EngineUnavailableError:
        logger.exception("Scout deep analysis: engine unavailable")
        _update(key, state="error", stage=None, error="The analysis engine is unavailable. Try again shortly.",
                _finished=time.monotonic())
    except Exception as exc:
        logger.exception("Scout deep analysis failed for %s", username)
        message = str(exc) if exc.__class__.__name__ == "ChessComClientError" else "Deep analysis failed."
        _update(key, state="error", stage=None, error=message, _finished=time.monotonic())
