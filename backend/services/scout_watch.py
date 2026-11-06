"""Friends watchlist: pure alert logic plus orchestration over Chess.com fetches."""

from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from ..repositories import scout_watch as repo
from .cache import ttl_lru_cache
from .chesscom_client import ChessComClientError, _normalize_username, get_recent_games
from .opponent_scout import ScoutGame, parse_game

logger = logging.getLogger(__name__)

MAX_FRIENDS = 20
MAX_GAMES = 100
NEW_OPENING_MAX_SHARE = 0.05
DROPPED_OPENING_MIN_SHARE = 0.25
MIN_OLDER_GAMES = 10
RECENT_FALLBACK = 10
DROPPED_WINDOW = 12
RATING_DELTA = 30


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def current_ratings(games: list[ScoutGame]) -> dict[str, int]:
    """Most recent own rating per time class."""
    out: dict[str, int] = {}
    for g in sorted(games, key=lambda g: g.end_time, reverse=True):
        if g.time_class and g.own_rating is not None and g.time_class not in out:
            out[g.time_class] = int(g.own_rating)
    return out


def compute_alerts(
    games: list[ScoutGame],
    *,
    last_seen_end_time: int | None,
    last_seen_ratings: dict[str, int] | None,
) -> tuple[int, list[dict]]:
    ordered = sorted(games, key=lambda g: g.end_time, reverse=True)
    alerts: list[dict] = []

    if last_seen_end_time is None:
        new: list[ScoutGame] = []
        older = ordered
    else:
        new = [g for g in ordered if g.end_time > last_seen_end_time]
        older = [g for g in ordered if g.end_time <= last_seen_end_time]
    new_games = len(new)

    if new_games > 0:
        alerts.append({
            "kind": "new_games", "color": None, "family": None, "games": new_games,
            "message": f"Played {_plural(new_games, 'new game')} since you last checked",
        })

    if new:
        recent, baseline = new, older
    else:
        recent, baseline = ordered[:RECENT_FALLBACK], ordered[RECENT_FALLBACK:]

    for color in ("white", "black"):
        base_c = [g for g in baseline if g.color == color]
        if len(base_c) < MIN_OLDER_GAMES:
            continue
        base_counts = Counter(g.family for g in base_c)
        label = color.capitalize()

        recent_counts = Counter(g.family for g in recent if g.color == color and g.family)
        for family, n in recent_counts.most_common():
            if base_counts.get(family, 0) / len(base_c) < NEW_OPENING_MAX_SHARE:
                alerts.append({
                    "kind": "new_opening", "color": color, "family": family, "games": n,
                    "message": f"New as {label}: the {family} ({_plural(n, 'game')})",
                })

        latest = [g for g in ordered if g.color == color][:DROPPED_WINDOW]
        latest_fams = {g.family for g in latest}
        for family, n in base_counts.most_common():
            if family and n / len(base_c) >= DROPPED_OPENING_MIN_SHARE and family not in latest_fams:
                alerts.append({
                    "kind": "dropped_opening", "color": color, "family": family, "games": n,
                    "message": (
                        f"Stopped playing the {family} as {label} "
                        f"(was {round(100 * n / len(base_c))}% of their games)"
                    ),
                })

    if last_seen_ratings:
        for tc, cur in current_ratings(ordered).items():
            prev = last_seen_ratings.get(tc)
            if prev is not None and abs(cur - prev) >= RATING_DELTA:
                diff = cur - prev
                alerts.append({
                    "kind": "rating_change", "color": None, "family": None, "games": 0,
                    "message": (
                        f"{tc.capitalize()} rating {'up' if diff > 0 else 'down'} "
                        f"{abs(diff)} ({prev} -> {cur})"
                    ),
                })

    return new_games, alerts


# -- Chess.com fetch (cached ~5 min) -----------------------------------------

def _fetch_uncached(username: str) -> list[ScoutGame]:
    raw = get_recent_games(username, limit=MAX_GAMES)
    games = [parse_game(r, username) for r in raw]
    return [g for g in games if g is not None]


fetch_scout_games = ttl_lru_cache(maxsize=128, ttl_seconds=300)(_fetch_uncached)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _newest(games: list[ScoutGame]) -> int | None:
    return max((g.end_time for g in games), default=None)


def build_friend(row: dict[str, Any], games: list[ScoutGame] | None, error: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "username": row["username"],
        "added_at": _iso(row["added_at"]),
        "last_seen_at": _iso(row["last_seen_at"]),
        "last_game_at": None,
        "new_games": 0,
        "ratings": {},
        "alerts": [],
        "error": error,
    }
    if games is None:
        return out
    newest = _newest(games)
    if newest:
        out["last_game_at"] = datetime.fromtimestamp(newest, tz=timezone.utc).isoformat()
    out["ratings"] = current_ratings(games)
    out["new_games"], out["alerts"] = compute_alerts(
        games,
        last_seen_end_time=row["last_seen_end_time"],
        last_seen_ratings=row["last_seen_ratings"],
    )
    return out


def _load(row: dict[str, Any]) -> dict[str, Any]:
    try:
        return build_friend(row, fetch_scout_games(row["username"]))
    except ChessComClientError as exc:
        return build_friend(row, None, str(exc))
    except Exception:  # noqa: BLE001 - one friend must never fail the list
        logger.exception("Watch fetch failed for %s", row["username"])
        return build_friend(row, None, "Could not load this player's games.")


def list_friends(owner_id: str) -> dict[str, Any]:
    rows = repo.list_watch(owner_id)
    if not rows:
        return {"friends": []}
    with ThreadPoolExecutor(max_workers=min(4, len(rows))) as pool:
        friends = list(pool.map(_load, rows))
    return {"friends": friends}


class WatchLimitError(Exception):
    pass


class WatchNotFoundError(Exception):
    pass


def add_friend(owner_id: str, raw_username: str) -> dict[str, Any]:
    """Raises ChessComClientError (bad format / unknown player) or WatchLimitError."""
    username = _normalize_username(raw_username)
    existing = repo.get_watch(owner_id, username)
    if existing is not None:
        return _load(existing)
    if repo.count_watch(owner_id) >= MAX_FRIENDS:
        raise WatchLimitError(f"You can watch at most {MAX_FRIENDS} players.")
    games: list[ScoutGame] | None
    try:
        games = fetch_scout_games(username)
    except ChessComClientError as exc:
        if "not found" in str(exc).lower():
            raise
        games = None
    row = repo.add_watch(
        owner_id,
        username,
        last_seen_end_time=_newest(games) if games else None,
        last_seen_ratings=current_ratings(games) if games else None,
    )
    return build_friend(row, games, None if games is not None else "Could not reach Chess.com.")


def remove_friend(owner_id: str, raw_username: str) -> None:
    repo.delete_watch(owner_id, _normalize_username(raw_username))


def mark_friend_seen(owner_id: str, raw_username: str) -> dict[str, Any]:
    username = _normalize_username(raw_username)
    if repo.get_watch(owner_id, username) is None:
        raise WatchNotFoundError(username)
    games = fetch_scout_games(username)
    row = repo.mark_seen(
        owner_id,
        username,
        last_seen_end_time=_newest(games),
        last_seen_ratings=current_ratings(games),
    )
    if row is None:
        raise WatchNotFoundError(username)
    return build_friend(row, games)
