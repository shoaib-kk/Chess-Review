"""Chess.com public API client (Section 1).

Self-contained — the engine is intentionally isolated from the main review app,
so it carries its own thin client rather than importing ``backend.services``.
Only the public ``api.chess.com/pub`` endpoints are used (no auth required).

Responsibilities:
- list a player's monthly game archives,
- fetch + normalise the games for a month,
- fetch the player's public profile (for the onboarding avatar step).

Filtering policy lives here so both the sync task and tests share it:
- ``daily`` games and non-standard variants (``rules != "chess"``) are excluded;
- ``bullet`` is kept but tagged so it can be weighted/queried separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

import requests

from . import config

BASE_URL = "https://api.chess.com/pub"
HEADERS = {
    "User-Agent": config.CHESSCOM_USER_AGENT,
    "Accept": "application/json",
}
TIMEOUT = 15

# Time classes we never model. ``daily`` (correspondence) is excluded per spec.
EXCLUDED_TIME_CLASSES = {"daily"}


class ChessComClientError(RuntimeError):
    """Raised on any failure to fetch or parse Chess.com data."""


@dataclass
class ChessComGame:
    """A normalised, ingest-ready Chess.com game."""

    url: str
    pgn: str
    time_class: str
    time_control: Optional[str]
    end_time: Optional[int]
    rated: bool
    rules: str


def _get_json(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ChessComClientError(f"Could not reach Chess.com: {exc}") from exc

    if response.status_code == 404:
        raise ChessComClientError("Chess.com player or archive was not found.")
    if response.status_code == 429:
        raise ChessComClientError("Chess.com rate limit hit; try again shortly.")
    if response.status_code >= 400:
        raise ChessComClientError(f"Chess.com returned HTTP {response.status_code}.")

    try:
        return response.json()
    except ValueError as exc:
        raise ChessComClientError("Chess.com returned malformed JSON.") from exc


def normalise_username(username: str) -> str:
    normalized = (username or "").strip().lower()
    if not normalized:
        raise ChessComClientError("Username is required.")
    return normalized


def get_player_profile(username: str) -> dict[str, Any]:
    """Public profile — used for the onboarding avatar-confirmation step."""
    data = _get_json(f"{BASE_URL}/player/{normalise_username(username)}")
    return {
        "username": data.get("username"),
        "avatar": data.get("avatar"),
        "name": data.get("name"),
        "url": data.get("url"),
        "followers": data.get("followers"),
        "country": data.get("country"),
    }


def get_archive_urls(username: str) -> list[str]:
    """Monthly archive URLs, oldest first (Chess.com already returns them sorted)."""
    data = _get_json(f"{BASE_URL}/player/{normalise_username(username)}/games/archives")
    return list(data.get("archives", []))


def _should_keep(game: dict[str, Any]) -> bool:
    if not game.get("pgn"):
        return False
    if (game.get("rules") or "chess") != "chess":
        return False  # variants (chess960, bughouse, ...) are not modelled
    if (game.get("time_class") or "").lower() in EXCLUDED_TIME_CLASSES:
        return False
    return True


def _normalise(game: dict[str, Any]) -> Optional[ChessComGame]:
    if not _should_keep(game):
        return None
    return ChessComGame(
        url=game.get("url") or "",
        pgn=game["pgn"],
        time_class=(game.get("time_class") or "").lower(),
        time_control=game.get("time_control"),
        end_time=game.get("end_time"),
        rated=bool(game.get("rated", False)),
        rules=game.get("rules") or "chess",
    )


def get_month_games(archive_url: str) -> list[ChessComGame]:
    """Fetch + normalise one monthly archive, keeping only modelled games."""
    data = _get_json(archive_url)
    games: list[ChessComGame] = []
    for raw in data.get("games", []):
        normalised = _normalise(raw)
        if normalised is not None:
            games.append(normalised)
    return games


def iter_new_games(
    username: str,
    *,
    since_end_time: Optional[int] = None,
    time_classes: Optional[Iterable[str]] = None,
) -> Iterable[ChessComGame]:
    """Yield modelled games newest archives first, oldest-within-month first.

    ``since_end_time`` powers incremental sync: games that finished at or before
    the watermark are skipped. ``time_classes`` optionally restricts to a chosen
    subset (e.g. the time control picked during onboarding); ``daily`` is always
    excluded regardless.
    """
    wanted = (
        {tc.lower() for tc in time_classes if tc.lower() not in EXCLUDED_TIME_CLASSES}
        if time_classes
        else None
    )
    archives = get_archive_urls(username)
    for archive_url in reversed(archives):
        for game in get_month_games(archive_url):
            if since_end_time is not None and (game.end_time or 0) <= since_end_time:
                continue
            if wanted is not None and game.time_class not in wanted:
                continue
            yield game
