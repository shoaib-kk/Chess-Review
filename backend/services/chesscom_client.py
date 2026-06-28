from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

BASE_URL = "https://api.chess.com/pub"

# Chess.com usernames are ASCII alphanumerics plus _ and -. Validate at the
# boundary so a crafted value can't inject extra path segments into the upstream
# URL, and so the user gets a clean error instead of a confusing upstream 404.
_VALID_USERNAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
HEADERS = {
    "User-Agent": "ChessGameReviewer/1.0 (local development)",
    "Accept": "application/json",
}
# Layered (connect, read) timeout: fail fast if we can't even open the socket,
# but allow a slow upstream a little longer to send the body. The old flat
# `TIMEOUT = 15` is kept as an alias so any external reference still resolves.
TIMEOUT = (5, 15)

# Bounded pool for fetching multiple monthly archives at once. Kept small so we
# stay polite to the upstream API (it rate-limits aggressive clients) while
# still collapsing a sequential wait of N months into roughly one round trip.
_MAX_WORKERS = 5

# A single module-level Session reuses the TCP/TLS connection across calls,
# which is markedly faster (and lighter on Chess.com) than a fresh connection
# per request. `requests.Session` is safe for concurrent GETs from multiple
# threads as long as we don't mutate it after setup, which we don't.
_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)


class ChessComClientError(RuntimeError):
    pass


def _get_json(url: str) -> dict[str, Any]:
    try:
        response = _SESSION.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ChessComClientError(f"Could not reach Chess.com: {exc}") from exc

    if response.status_code == 404:
        raise ChessComClientError("Chess.com player or games archive was not found.")
    if response.status_code >= 400:
        raise ChessComClientError(f"Chess.com returned HTTP {response.status_code}.")

    try:
        return response.json()
    except ValueError as exc:
        raise ChessComClientError("Chess.com returned malformed JSON.") from exc


def _format_date(end_time: int | None) -> str | None:
    if not end_time:
        return None
    return datetime.fromtimestamp(end_time, tz=timezone.utc).date().isoformat()


def _clean_game(game: dict[str, Any]) -> dict[str, Any] | None:
    pgn = game.get("pgn")
    white = game.get("white") or {}
    black = game.get("black") or {}
    if not pgn or not white.get("username") or not black.get("username"):
        return None

    # Chess.com only includes `accuracies` for games that were analysed via
    # Game Review, so these are real per-game accuracies (or absent).
    accuracies = game.get("accuracies") or {}

    return {
        "white_username": white.get("username", ""),
        "black_username": black.get("username", ""),
        "white_result": white.get("result"),
        "black_result": black.get("result"),
        "white_accuracy": accuracies.get("white"),
        "black_accuracy": accuracies.get("black"),
        "result": game.get("result") or _result_from_player_results(white.get("result"), black.get("result")),
        "end_time": game.get("end_time"),
        "date": _format_date(game.get("end_time")),
        "time_class": game.get("time_class"),
        "time_control": game.get("time_control"),
        "rated": bool(game.get("rated", False)),
        "rules": game.get("rules"),
        "url": game.get("url"),
        "pgn": pgn,
    }


def _result_from_player_results(white_result: str | None, black_result: str | None) -> str:
    if white_result in {"win", "checkmated", "resigned", "timeout"} and black_result == "win":
        return "0-1"
    if white_result == "win":
        return "1-0"
    if black_result == "win":
        return "0-1"
    if white_result and black_result:
        return "1/2-1/2"
    return "*"


def _normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not _VALID_USERNAME.match(normalized):
        raise ChessComClientError("Invalid Chess.com username.")
    return normalized


def get_player_archives(username: str) -> list[str]:
    normalized = _normalize_username(username)
    data = _get_json(f"{BASE_URL}/player/{quote(normalized, safe='')}/games/archives")
    return list(data.get("archives", []))


def get_month_games(username: str, year: int, month: int) -> list[dict[str, Any]]:
    normalized = _normalize_username(username)
    if month < 1 or month > 12:
        raise ChessComClientError("Month must be between 1 and 12.")

    data = _get_json(f"{BASE_URL}/player/{quote(normalized, safe='')}/games/{year:04d}/{month:02d}")
    games = []
    for game in data.get("games", []):
        clean = _clean_game(game)
        if clean:
            games.append(clean)
    return games


def _parse_archive_year_month(archive_url: str) -> tuple[int, int] | None:
    """Pull (year, month) out of an archive URL like `.../games/2024/03`.

    Returns None for any archive URL we can't parse, so callers can skip it
    instead of failing the whole fetch.
    """
    year_month = archive_url.rstrip("/").split("/")[-2:]
    if len(year_month) != 2:
        return None
    try:
        return int(year_month[0]), int(year_month[1])
    except ValueError:
        return None


def get_recent_games(username: str, limit: int = 20) -> list[dict[str, Any]]:
    # Listing the archives is the one fetch we can't proceed without, so a
    # failure here (404 / unreachable / HTTP error) still propagates as before.
    archives = get_player_archives(username)
    normalized = _normalize_username(username)

    # Newest month first, keeping only the archives we can actually parse.
    months: list[tuple[int, int]] = []
    for archive_url in reversed(archives):
        parsed = _parse_archive_year_month(archive_url)
        if parsed is not None:
            months.append(parsed)

    games: list[dict[str, Any]] = []
    last_error: ChessComClientError | None = None
    any_month_succeeded = False

    # Fetch newest months concurrently in bounded batches, stopping once we have
    # enough games. Doing it in batches (rather than firing every month at once)
    # avoids over-fetching the full archive for a `limit` that a couple of recent
    # months already satisfy, while still parallelising each batch's round trips.
    for start in range(0, len(months), _MAX_WORKERS):
        batch = months[start : start + _MAX_WORKERS]
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            # Map preserves batch (newest-first) order; we materialise results so
            # an exception in one month is raised here and handled per-month.
            futures = [
                executor.submit(get_month_games, normalized, year, month)
                for year, month in batch
            ]
            for future in futures:
                try:
                    games.extend(future.result())
                    any_month_succeeded = True
                except ChessComClientError as exc:
                    # A single bad month shouldn't 500 the whole request when
                    # other months returned games; remember the error in case
                    # every month ends up failing.
                    last_error = exc

        games.sort(key=lambda item: item.get("end_time") or 0, reverse=True)
        if len(games) >= limit:
            return games[:limit]

    # If we never managed to read a single month (and there were months to read),
    # surface the underlying error rather than a misleading empty result.
    if not any_month_succeeded and last_error is not None:
        raise last_error

    return games[:limit]
