from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

BASE_URL = "https://api.chess.com/pub"
HEADERS = {
    "User-Agent": "ChessGameReviewer/1.0 (local development)",
    "Accept": "application/json",
}
TIMEOUT = 15


class ChessComClientError(RuntimeError):
    pass


def _get_json(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
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


def get_player_archives(username: str) -> list[str]:
    normalized = username.strip().lower()
    if not normalized:
        raise ChessComClientError("Username is required.")
    data = _get_json(f"{BASE_URL}/player/{normalized}/games/archives")
    return list(data.get("archives", []))


def get_month_games(username: str, year: int, month: int) -> list[dict[str, Any]]:
    normalized = username.strip().lower()
    if not normalized:
        raise ChessComClientError("Username is required.")
    if month < 1 or month > 12:
        raise ChessComClientError("Month must be between 1 and 12.")

    data = _get_json(f"{BASE_URL}/player/{normalized}/games/{year:04d}/{month:02d}")
    games = []
    for game in data.get("games", []):
        clean = _clean_game(game)
        if clean:
            games.append(clean)
    return games


def get_recent_games(username: str, limit: int = 20) -> list[dict[str, Any]]:
    archives = get_player_archives(username)
    games: list[dict[str, Any]] = []

    for archive_url in reversed(archives):
        year_month = archive_url.rstrip("/").split("/")[-2:]
        if len(year_month) != 2:
            continue
        try:
            year = int(year_month[0])
            month = int(year_month[1])
        except ValueError:
            continue

        games.extend(get_month_games(username, year, month))
        games.sort(key=lambda item: item.get("end_time") or 0, reverse=True)
        if len(games) >= limit:
            return games[:limit]

    return games[:limit]
