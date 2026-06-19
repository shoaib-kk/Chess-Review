from __future__ import annotations

import logging
import threading
from typing import Any

import chess

from .chesscom_client import get_recent_games
from .puzzle_store import (
    ensure_tables,
    get_analyzed_count,
    get_analyzed_urls,
    get_puzzle_count,
    mark_game_analyzed,
    save_puzzle,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running: set[str] = set()
_progress: dict[str, dict] = {}

GAME_LIMIT = 200

# Depth used when mining puzzles from past games. Decoupled from the interactive
# review default so puzzle quality doesn't silently track the UI's "normal"
# setting. Higher = fewer bogus puzzles from shallow misreads, but slower over
# the (up to 200) games analysed in the background.
PUZZLE_ANALYSIS_DEPTH = 14


def get_progress(username: str) -> dict:
    with _lock:
        mem = _progress.get(username, {})
    db_analyzed = get_analyzed_count(username)
    db_puzzles = get_puzzle_count(username)
    return {
        "analyzed": max(mem.get("analyzed", 0), db_analyzed),
        "total": mem.get("total", db_analyzed),
        "running": mem.get("running", False),
        "puzzle_count": max(mem.get("puzzle_count", 0), db_puzzles),
    }


def start_if_needed(username: str) -> bool:
    """Start background analysis if there are un-analyzed games and nothing is running."""
    ensure_tables()
    with _lock:
        if username in _running:
            return False
        analyzed = get_analyzed_count(username)
        if analyzed >= GAME_LIMIT:
            return False
        _running.add(username)

    t = threading.Thread(target=_run, args=(username,), daemon=True)
    t.start()
    return True


def start_fresh(username: str) -> bool:
    """Force a (re-)analysis run regardless of how many games are already in DB."""
    ensure_tables()
    with _lock:
        if username in _running:
            return False
        _running.add(username)

    t = threading.Thread(target=_run, args=(username,), daemon=True)
    t.start()
    return True


def _set_progress(username: str, **kwargs: Any) -> None:
    with _lock:
        current = _progress.setdefault(username, {})
        current.update(kwargs)


def _run(username: str) -> None:
    try:
        _set_progress(username, running=True, analyzed=0, total=0, puzzle_count=0)
        games = get_recent_games(username, limit=GAME_LIMIT)
        analyzed_urls = get_analyzed_urls(username)
        pending = [g for g in games if g.get("url") and g["url"] not in analyzed_urls]

        db_analyzed = get_analyzed_count(username)
        _set_progress(username, total=db_analyzed + len(pending), analyzed=db_analyzed)

        for raw in pending:
            _analyze_one(username, raw)
            with _lock:
                prog = _progress.setdefault(username, {})
                prog["analyzed"] = prog.get("analyzed", 0) + 1

    except Exception:
        logger.exception("Puzzle analysis failed for %s", username)
    finally:
        with _lock:
            _running.discard(username)
            if username in _progress:
                _progress[username]["running"] = False


def _analyze_one(username: str, raw: dict[str, Any]) -> None:
    # Defer import to avoid circular dependency with top-level game_analyzer.
    try:
        from game_analyzer import analyze_pgn
    except ModuleNotFoundError:
        from services.game_analyzer import analyze_pgn  # type: ignore[no-redef]

    url = raw.get("url", "")
    date = raw.get("date", "")
    pgn_text = raw.get("pgn", "")
    user_color = _user_color(raw, username)

    if not pgn_text or not user_color:
        mark_game_analyzed(username, url, 0)
        return

    try:
        summary = analyze_pgn(pgn_text=pgn_text, depth=PUZZLE_ANALYSIS_DEPTH, mode="normal")
    except Exception:
        logger.warning("Could not analyze game %s", url)
        mark_game_analyzed(username, url, 0)
        return

    count = 0
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

        best_move_uci = _to_uci(move.fen_before, move.best_move)

        save_puzzle(
            username=username,
            game_url=url,
            game_date=date,
            move_number=move.move_number,
            color=move.color,
            fen=move.fen_before,
            played_move=move.move_played,
            best_move=move.best_move,
            best_move_uci=best_move_uci,
            pv=move.pv,
            cp_loss=move.cp_loss or 0.0,
            eval_before=move.eval_before,
            classification=cls,
        )
        count += 1
        with _lock:
            prog = _progress.setdefault(username, {})
            prog["puzzle_count"] = prog.get("puzzle_count", 0) + 1

    mark_game_analyzed(username, url, count)


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
