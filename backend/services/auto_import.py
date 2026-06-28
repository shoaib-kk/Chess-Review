"""Auto-import new Chess.com games into the per-device "ready to review" inbox.

Polls the user's public archive (reuses :func:`get_recent_games`) for games newer
than the last imported ``end_time`` and persists them via
:func:`save_imported_game` (which dedups through ``get_or_create_game``). Runs in a
background thread per device so the request returns immediately; the frontend then
sees the new games via ``GET /inbox``.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from ..repositories.games import get_import_cursor, save_imported_game, set_import_cursor
from .chesscom_client import get_recent_games

logger = logging.getLogger(__name__)

GAME_LIMIT = 50

_lock = threading.Lock()
_running: set[str] = set()


def trigger_import(device_id: str, username: str) -> bool:
    """Kick off a background poll for this device, unless one is already running."""
    key = f"{device_id}:{username.casefold()}"
    with _lock:
        if key in _running:
            return False
        _running.add(key)
    t = threading.Thread(target=_run, args=(device_id, username, key), daemon=True)
    t.start()
    return True


def _run(device_id: str, username: str, key: str) -> None:
    try:
        poll_new_games(device_id, username)
    except Exception:  # pragma: no cover - background best-effort
        logger.exception("Auto-import failed for device %s (player %s)", device_id, username)
    finally:
        with _lock:
            _running.discard(key)


def poll_new_games(device_id: str, username: str) -> int:
    """Import games newer than the stored cursor. Returns how many were imported."""
    normalized = username.strip()
    if not normalized:
        return 0

    cursor = get_import_cursor(device_id, normalized.casefold()) or 0
    games = get_recent_games(normalized, limit=GAME_LIMIT)

    imported = 0
    highest = cursor
    for raw in games:
        end_time = raw.get("end_time") or 0
        if end_time <= cursor:
            continue
        pgn = raw.get("pgn")
        if not pgn:
            continue
        save_imported_game(
            owner_id=device_id,
            username=normalized,
            game_url=raw.get("url") or None,
            game_date=raw.get("date"),
            pgn=pgn,
        )
        imported += 1
        highest = max(highest, end_time)

    if highest > cursor:
        set_import_cursor(device_id, normalized.casefold(), highest)
    return imported


def status() -> dict[str, Any]:  # pragma: no cover - trivial
    with _lock:
        return {"running": sorted(_running)}
