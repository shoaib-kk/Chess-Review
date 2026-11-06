"""Thin client for the Lichess opening explorer (``/lichess`` database endpoint).

Findings when this was written (Nov 2026): both ``explorer.lichess.org`` and the
older ``explorer.lichess.ovh`` answer ``401 Authorization Required`` without a
token, so a personal Lichess API token (no scopes needed) is expected in the
``LICHESS_TOKEN`` env var and is sent as ``Authorization: Bearer``. Without it
we raise a clear ``LichessExplorerError`` rather than hitting the network.

Politeness: at most one request per second across all threads, a day-long
cache, and a single 60 s back-off on HTTP 429 before giving up.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import requests

from .cache import ttl_lru_cache

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("LICHESS_EXPLORER_URL", "https://explorer.lichess.org").rstrip("/")
HEADERS = {
    "User-Agent": "ChessGameReviewer/1.0 (opponent scouting)",
    "Accept": "application/json",
}
TIMEOUT = (5, 15)
MIN_INTERVAL = 1.0        # seconds between requests (all threads)
RATE_LIMIT_WAIT = 60.0    # back-off after a 429
CACHE_TTL_SECONDS = 24 * 3600
MOVES_PER_POSITION = 12

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)

_throttle_lock = threading.Lock()
_last_request = 0.0
_sleep = time.sleep
_now = time.monotonic


class LichessExplorerError(RuntimeError):
    pass


def _throttle() -> None:
    """Block until at least ``MIN_INTERVAL`` has passed since the previous request."""
    global _last_request
    with _throttle_lock:
        wait = _last_request + MIN_INTERVAL - _now()
        if wait > 0:
            _sleep(wait)
        _last_request = _now()


def _request(params: dict[str, Any], headers: dict[str, str]) -> requests.Response:
    _throttle()
    try:
        return _SESSION.get(f"{BASE_URL}/lichess", params=params, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise LichessExplorerError(f"Could not reach the Lichess explorer: {exc}") from exc


@ttl_lru_cache(maxsize=4096, ttl_seconds=CACHE_TTL_SECONDS)
def _fetch_cached(fen: str, ratings: tuple[int, ...], speeds: tuple[str, ...]) -> dict[str, Any]:
    token = os.environ.get("LICHESS_TOKEN", "").strip()
    if not token:
        raise LichessExplorerError(
            "The Lichess opening explorer needs an API token. Set the LICHESS_TOKEN environment variable."
        )
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "variant": "standard",
        "fen": fen,
        "speeds": ",".join(speeds),
        "ratings": ",".join(str(r) for r in ratings),
        "moves": MOVES_PER_POSITION,
        "topGames": 0,
        "recentGames": 0,
    }

    response = _request(params, headers)
    if response.status_code == 429:
        logger.warning("Lichess explorer rate limited; waiting %.0fs", RATE_LIMIT_WAIT)
        _sleep(RATE_LIMIT_WAIT)
        response = _request(params, headers)
        if response.status_code == 429:
            raise LichessExplorerError("The Lichess explorer is rate limiting us. Try again in a few minutes.")
    if response.status_code in (401, 403):
        raise LichessExplorerError(f"The Lichess explorer rejected the API token (HTTP {response.status_code}).")
    if response.status_code >= 400:
        raise LichessExplorerError(f"The Lichess explorer returned HTTP {response.status_code}.")

    try:
        data = response.json()
    except ValueError as exc:
        raise LichessExplorerError("The Lichess explorer returned malformed JSON.") from exc
    if not isinstance(data, dict):
        raise LichessExplorerError("The Lichess explorer returned an unexpected response.")
    return data


def fetch_explorer(fen: str, *, ratings: list[int], speeds: list[str]) -> dict[str, Any]:
    """Explorer stats for ``fen`` (cached ~1 day, throttled to 1 req/s)."""
    return _fetch_cached(fen, tuple(sorted(ratings)), tuple(sorted(speeds)))
