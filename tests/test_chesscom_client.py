"""Tests for the Chess.com client's concurrent month-fetching.

These cover the parts that don't hit the network: monkeypatch the per-month
fetch and verify that `get_recent_games` still sorts by end_time desc, truncates
to `limit`, stops fetching once it has enough, and aggregates per-month errors
sensibly.
"""

from __future__ import annotations

import pytest

from backend.services import chesscom_client as cc
from backend.services.chesscom_client import ChessComClientError, get_recent_games


def _game(end_time: int) -> dict:
    """A minimal cleaned-game dict, identified by its end_time."""
    return {"end_time": end_time, "url": f"g{end_time}"}


def _patch_archives(monkeypatch, months: list[tuple[int, int]]) -> None:
    urls = [f"{cc.BASE_URL}/player/u/games/{y:04d}/{m:02d}" for (y, m) in months]
    monkeypatch.setattr(cc, "get_player_archives", lambda username: urls)


def test_recent_games_sorted_and_truncated(monkeypatch):
    # Two months, newest (2024/02) first in reverse order. Interleave end_times
    # so a correct sort can't be a coincidence of fetch order.
    _patch_archives(monkeypatch, [(2024, 1), (2024, 2)])

    data = {
        (2024, 2): [_game(50), _game(10)],
        (2024, 1): [_game(40), _game(30), _game(20)],
    }
    monkeypatch.setattr(cc, "get_month_games", lambda u, y, m: data[(y, m)])

    games = get_recent_games("u", limit=3)
    assert [g["end_time"] for g in games] == [50, 40, 30]


def test_recent_games_stops_at_batch_boundary(monkeypatch):
    # More months than one batch (_MAX_WORKERS). The first batch already
    # satisfies the limit, so the second batch's months must never be fetched.
    monkeypatch.setattr(cc, "_MAX_WORKERS", 2)
    _patch_archives(monkeypatch, [(2023, 11), (2023, 12), (2024, 1), (2024, 2)])

    fetched: list[tuple[int, int]] = []
    data = {
        (2024, 2): [_game(100), _game(95)],
        (2024, 1): [_game(90), _game(85)],
        (2023, 12): [_game(80)],
        (2023, 11): [_game(70)],
    }

    def fake(username, year, month):
        fetched.append((year, month))
        return data[(year, month)]

    monkeypatch.setattr(cc, "get_month_games", fake)

    games = get_recent_games("u", limit=3)
    assert [g["end_time"] for g in games] == [100, 95, 90]
    # Only the first batch (the two newest months) was fetched.
    assert set(fetched) == {(2024, 2), (2024, 1)}


def test_recent_games_one_bad_month_does_not_fail(monkeypatch):
    _patch_archives(monkeypatch, [(2024, 1), (2024, 2)])

    def fake(username, year, month):
        if (year, month) == (2024, 1):
            raise ChessComClientError("Chess.com returned HTTP 500.")
        return [_game(10)]

    monkeypatch.setattr(cc, "get_month_games", fake)

    games = get_recent_games("u", limit=20)
    assert [g["end_time"] for g in games] == [10]


def test_recent_games_all_months_fail_raises(monkeypatch):
    _patch_archives(monkeypatch, [(2024, 1), (2024, 2)])

    def fake(username, year, month):
        raise ChessComClientError("Chess.com returned HTTP 500.")

    monkeypatch.setattr(cc, "get_month_games", fake)

    with pytest.raises(ChessComClientError):
        get_recent_games("u", limit=20)


def test_recent_games_no_archives_returns_empty(monkeypatch):
    _patch_archives(monkeypatch, [])
    games = get_recent_games("u", limit=20)
    assert games == []
