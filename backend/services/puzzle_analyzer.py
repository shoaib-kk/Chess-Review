from __future__ import annotations

import logging
import threading
from typing import Any

import chess

from ..repositories.puzzles import (
    get_analyzed_count,
    get_analyzed_urls,
    get_puzzle_count,
    save_mined_puzzles,
)
from ..serializers import serialize_game_summary
from .chesscom_client import get_recent_games
from .redis_client import get_redis

logger = logging.getLogger(__name__)

# Run state is keyed by ``owner_id`` (the device), so each device gets its own
# progress and at most one concurrent mining run.
#
# When ``REDIS_URL`` is set, progress lives in a Redis hash per device
# (``puzzleprogress:{device}``) so that an instance polling ``get_progress`` sees
# a job that was started on a *different* instance — counters and the "running"
# flag are shared. The background worker thread still runs in-process (the
# Stockfish work is local), but every progress read/write goes through Redis.
#
# FAIL-OPEN: if Redis is unconfigured or unreachable, we transparently fall back
# to the in-memory dicts below, exactly like the original single-instance
# behaviour. A Redis blip must never crash the worker thread or the GET handler.
_lock = threading.Lock()
_running: set[str] = set()
_progress: dict[str, dict] = {}

# Progress keys carry a TTL so abandoned/finished runs don't accumulate in Redis
# forever. Comfortably longer than the slowest plausible 200-game mining run;
# every write refreshes it.
PROGRESS_TTL_SECONDS = 6 * 60 * 60  # 6 hours

# Atomic "claim a run" for a device. Sets running=1 and refreshes the TTL only
# when no run is currently in flight (field missing or "0"), returning 1 if it
# claimed and 0 otherwise. KEYS[1] = progress hash key, ARGV[1] = TTL seconds.
_CLAIM_LUA = """
local cur = redis.call('HGET', KEYS[1], 'running')
if cur == false or cur == '0' then
  redis.call('HSET', KEYS[1], 'running', '1')
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  return 1
end
return 0
"""

GAME_LIMIT = 200

# Depth used when mining puzzles from past games. Decoupled from the interactive
# review default so puzzle quality doesn't silently track the UI's "normal"
# setting. Higher = fewer bogus puzzles from shallow misreads, but slower over
# the (up to 200) games analysed in the background.
PUZZLE_ANALYSIS_DEPTH = 14


def _progress_key(owner_id: str) -> str:
    return f"puzzleprogress:{owner_id}"


def _read_progress(owner_id: str) -> dict:
    """Read the raw progress state for a device (Redis if available, else memory).

    Returns a dict with ``analyzed`` / ``total`` / ``puzzle_count`` (ints) and
    ``running`` (bool); missing fields default to 0 / False. Never raises — Redis
    errors fall back to the in-memory copy.
    """
    redis_client = get_redis()
    if redis_client is not None:
        try:
            raw = redis_client.hgetall(_progress_key(owner_id))
        except Exception:
            logger.warning("Could not read puzzle progress from Redis; using in-memory.", exc_info=True)
            raw = None
        if raw is not None:
            return {
                "analyzed": int(raw.get("analyzed", 0) or 0),
                "total": int(raw.get("total", 0) or 0),
                "puzzle_count": int(raw.get("puzzle_count", 0) or 0),
                "running": (raw.get("running") == "1"),
            }
    with _lock:
        mem = dict(_progress.get(owner_id, {}))
    return {
        "analyzed": int(mem.get("analyzed", 0)),
        "total": int(mem.get("total", 0)),
        "puzzle_count": int(mem.get("puzzle_count", 0)),
        "running": bool(mem.get("running", False)),
    }


def get_progress(owner_id: str) -> dict:
    state = _read_progress(owner_id)
    db_analyzed = get_analyzed_count(owner_id)
    db_puzzles = get_puzzle_count(owner_id)
    return {
        "analyzed": max(state["analyzed"], db_analyzed),
        # ``total`` is only meaningful once a run has set it; before that, fall
        # back to the count already in the DB so the bar isn't stuck at 0/0.
        "total": state["total"] or db_analyzed,
        "running": state["running"],
        "puzzle_count": max(state["puzzle_count"], db_puzzles),
    }


def _try_claim_run(owner_id: str) -> bool:
    """Atomically mark a run as in-flight for this device. Returns False if one
    is already running.

    With Redis, ``running`` lives in the device's progress hash and is claimed
    with an atomic check-and-set Lua script (see ``_CLAIM_LUA``) so two instances
    can't both start a run for the same device. Without Redis we fall back to the
    in-process ``_running`` set. On a Redis error we degrade to the in-memory
    claim so the request still proceeds (fail-open).
    """
    redis_client = get_redis()
    if redis_client is not None:
        try:
            key = _progress_key(owner_id)
            # Claim atomically only when no run is in flight. HSETNX alone is
            # insufficient because a *finished* run leaves the field set to "0",
            # which would then block every future run. This tiny Lua script
            # claims when the field is absent OR equal to "0", so it's reusable
            # across runs while still being a single atomic check-and-set.
            claimed = redis_client.eval(_CLAIM_LUA, 1, key, str(PROGRESS_TTL_SECONDS))
            return bool(claimed)
        except Exception:
            logger.warning("Could not claim puzzle run in Redis; using in-memory claim.", exc_info=True)
    with _lock:
        if owner_id in _running:
            return False
        _running.add(owner_id)
    return True


def _release_run(owner_id: str) -> None:
    """Clear the in-flight flag for this device (best-effort)."""
    redis_client = get_redis()
    if redis_client is not None:
        try:
            redis_client.hset(_progress_key(owner_id), "running", "0")
            redis_client.expire(_progress_key(owner_id), PROGRESS_TTL_SECONDS)
        except Exception:
            logger.warning("Could not release puzzle run flag in Redis.", exc_info=True)
    with _lock:
        _running.discard(owner_id)
        if owner_id in _progress:
            _progress[owner_id]["running"] = False


def start_if_needed(owner_id: str, player_username: str) -> bool:
    """Start background analysis if there are un-analyzed games and nothing is running."""
    # Check the cheap precondition before claiming the run lock.
    if get_analyzed_count(owner_id) >= GAME_LIMIT:
        return False
    if not _try_claim_run(owner_id):
        return False

    t = threading.Thread(target=_run, args=(owner_id, player_username), daemon=True)
    t.start()
    return True


def start_fresh(owner_id: str, player_username: str) -> bool:
    """Force a (re-)analysis run regardless of how many games are already in DB."""
    if not _try_claim_run(owner_id):
        return False

    t = threading.Thread(target=_run, args=(owner_id, player_username), daemon=True)
    t.start()
    return True


def _set_progress(owner_id: str, **kwargs: Any) -> None:
    """Write progress fields (Redis hash if available, else in-memory).

    Always mirrors into the in-memory dict so the fallback path stays warm even
    when Redis is the primary store. Redis errors degrade silently to memory.
    """
    with _lock:
        current = _progress.setdefault(owner_id, {})
        current.update(kwargs)

    redis_client = get_redis()
    if redis_client is None:
        return
    mapping: dict[str, str] = {}
    for field, value in kwargs.items():
        if field == "running":
            mapping["running"] = "1" if value else "0"
        else:
            mapping[field] = str(value)
    try:
        key = _progress_key(owner_id)
        redis_client.hset(key, mapping=mapping)
        redis_client.expire(key, PROGRESS_TTL_SECONDS)
    except Exception:
        logger.warning("Could not write puzzle progress to Redis.", exc_info=True)


def _incr_progress(owner_id: str, field: str, amount: int = 1) -> None:
    """Atomically bump a numeric progress field (Redis HINCRBY, else in-memory).

    Using HINCRBY keeps the counter correct even though the worker runs in one
    process — it avoids a read-modify-write race and keeps Redis as the source of
    truth that other instances poll.
    """
    with _lock:
        prog = _progress.setdefault(owner_id, {})
        prog[field] = int(prog.get(field, 0)) + amount

    redis_client = get_redis()
    if redis_client is None:
        return
    try:
        key = _progress_key(owner_id)
        redis_client.hincrby(key, field, amount)
        redis_client.expire(key, PROGRESS_TTL_SECONDS)
    except Exception:
        logger.warning("Could not increment puzzle progress in Redis.", exc_info=True)


def _run(owner_id: str, player_username: str) -> None:
    try:
        _set_progress(owner_id, running=True, analyzed=0, total=0, puzzle_count=0)
        games = get_recent_games(player_username, limit=GAME_LIMIT)
        analyzed_urls = get_analyzed_urls(owner_id)
        pending = [g for g in games if g.get("url") and g["url"] not in analyzed_urls]

        db_analyzed = get_analyzed_count(owner_id)
        _set_progress(owner_id, total=db_analyzed + len(pending), analyzed=db_analyzed)

        for raw in pending:
            _analyze_one(owner_id, player_username, raw)
            _incr_progress(owner_id, "analyzed", 1)

    except Exception:
        logger.exception("Puzzle analysis failed for device %s (player %s)", owner_id, player_username)
    finally:
        _release_run(owner_id)


def _analyze_one(owner_id: str, player_username: str, raw: dict[str, Any]) -> None:
    # Defer import to avoid circular dependency with top-level game_analyzer.
    try:
        from game_analyzer import analyze_pgn
    except ModuleNotFoundError:
        from services.game_analyzer import analyze_pgn  # type: ignore[no-redef]

    url = raw.get("url", "")
    date = raw.get("date", "")
    pgn_text = raw.get("pgn", "")
    user_color = _user_color(raw, player_username)

    if not pgn_text or not user_color:
        _persist(owner_id, player_username, url, date, pgn_text, summary=None, puzzles=[])
        return

    try:
        summary = analyze_pgn(pgn_text=pgn_text, depth=PUZZLE_ANALYSIS_DEPTH, mode="normal")
    except Exception:
        logger.warning("Could not analyze game %s", url)
        _persist(owner_id, player_username, url, date, pgn_text, summary=None, puzzles=[])
        return

    puzzles: list[dict[str, Any]] = []
    for move in summary.move_analyses:
        if move.color != user_color:
            continue
        cls = getattr(move.classification, "value", str(move.classification))
        if cls not in ("Blunder", "Mistake"):
            continue
        if not move.best_move:
            continue
        # Evaluations are from the mover's POV. Only create puzzles where the
        # player is equal or better before their mistake.
        if move.eval_before is None or move.eval_before < 0:
            continue

        puzzles.append(
            {
                "move_number": move.move_number,
                "color": move.color,
                "fen": move.fen_before,
                "played_move": move.move_played,
                "best_move": move.best_move,
                "best_move_uci": _to_uci(move.fen_before, move.best_move),
                "pv": move.pv,
                "cp_loss": move.cp_loss or 0.0,
                "eval_before": move.eval_before,
                "eval_after": move.eval_after,
                "classification": cls,
            }
        )

    _persist(owner_id, player_username, url, date, pgn_text, summary=summary, puzzles=puzzles)
    if puzzles:
        _incr_progress(owner_id, "puzzle_count", len(puzzles))


def _persist(
    owner_id: str,
    player_username: str,
    url: str,
    date: str,
    pgn_text: str,
    *,
    summary: Any,
    puzzles: list[dict[str, Any]],
) -> None:
    """Store the mined game + its puzzles, marking the game analysed.

    A game with no usable PGN/colour, or that failed analysis, is still recorded
    (with an empty PGN guarded) so it is not re-mined on the next run. The game is
    owned by ``owner_id`` (device); ``player_username`` is the Chess.com identity
    used for color detection and stored for display.
    """
    analysis_json = serialize_game_summary(summary, username=player_username) if summary is not None else None
    save_mined_puzzles(
        owner_id=owner_id,
        username=player_username,
        game_url=url,
        game_date=date,
        pgn=pgn_text or url or f"{player_username}:{date}",
        summary=summary,
        analysis_json=analysis_json,
        puzzles=puzzles,
        depth=PUZZLE_ANALYSIS_DEPTH,
        mode="normal",
    )


def _user_color(raw: dict[str, Any], username: str) -> str | None:
    normalized = username.casefold()
    if raw.get("white_username", "").casefold() == normalized:
        return "White"
    if raw.get("black_username", "").casefold() == normalized:
        return "Black"
    return None


def _to_uci(fen: str, san: str) -> str | None:
    try:
        board = chess.Board(fen)
        return board.parse_san(san).uci()
    except Exception:
        return None
