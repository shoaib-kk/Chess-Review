"""Tests for the scouting watchlist: pure alert logic + repo/router on temp SQLite."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "dev")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.services.opponent_scout import ScoutGame  # noqa: E402
from backend.services.scout_watch import compute_alerts  # noqa: E402


@compiles(JSONB, "sqlite")
def _jsonb_as_json(element, compiler, **kw):  # noqa: ANN001
    return "JSON"


def game(t, color="white", family="Italian Game", tc="rapid", rating=1500):
    return ScoutGame(
        color=color, score=1.0, expected=None, own_rating=rating, foe_rating=1500, foe="x",
        sans=[], fens=[], ply_count=40, family=family, variation=None, eco="", time_class=tc,
        end_time=t, date=None, url=None, accuracy=None, result_reason="win:resignation",
    )


def kinds(alerts):
    return [a["kind"] for a in alerts]


def test_new_games_count_and_message():
    games = [game(t) for t in range(1, 11)]
    n, alerts = compute_alerts(games, last_seen_end_time=6, last_seen_ratings=None)
    assert n == 4
    assert alerts[0]["kind"] == "new_games"
    assert alerts[0]["message"] == "Played 4 new games since you last checked"


def test_no_new_games_no_alert():
    n, alerts = compute_alerts([game(1), game(2)], last_seen_end_time=5, last_seen_ratings=None)
    assert n == 0 and "new_games" not in kinds(alerts)


def test_unset_cursor_means_zero_new():
    n, _ = compute_alerts([game(1)], last_seen_end_time=None, last_seen_ratings=None)
    assert n == 0


def test_new_opening_detected():
    old = [game(t, "black", "Sicilian Defense") for t in range(1, 21)]
    new = [game(101, "black", "Pirc Defense"), game(102, "black", "Pirc Defense")]
    _, alerts = compute_alerts(old + new, last_seen_end_time=50, last_seen_ratings=None)
    a = next(a for a in alerts if a["kind"] == "new_opening")
    assert a["color"] == "black" and a["family"] == "Pirc Defense" and a["games"] == 2
    assert a["message"] == "New as Black: the Pirc Defense (2 games)"


def test_new_opening_threshold_5pct_and_min_games():
    # 1 of 20 older = exactly 5% -> not new.
    old = [game(t, "black", "Sicilian Defense") for t in range(1, 20)] + [game(20, "black", "Pirc Defense")]
    _, alerts = compute_alerts(old + [game(101, "black", "Pirc Defense")], last_seen_end_time=50, last_seen_ratings=None)
    assert "new_opening" not in kinds(alerts)
    # Fewer than 10 older games of that colour -> no baseline.
    few = [game(t, "black", "Sicilian Defense") for t in range(1, 9)]
    _, alerts = compute_alerts(few + [game(101, "black", "Pirc Defense")], last_seen_end_time=50, last_seen_ratings=None)
    assert "new_opening" not in kinds(alerts)


def test_new_opening_falls_back_to_last_10_when_nothing_new():
    old = [game(t, "white", "Italian Game") for t in range(1, 31)]
    recent = [game(100 + t, "white", "Vienna Game") for t in range(3)]
    _, alerts = compute_alerts(old + recent, last_seen_end_time=1000, last_seen_ratings=None)
    assert any(a["kind"] == "new_opening" and a["family"] == "Vienna Game" and a["games"] == 3 for a in alerts)


def test_dropped_opening():
    old = [game(t, "white", "King's Gambit") for t in range(1, 6)] + [game(t, "white", "Italian Game") for t in range(6, 16)]
    latest = [game(100 + t, "white", "Italian Game") for t in range(12)]
    _, alerts = compute_alerts(old + latest, last_seen_end_time=1000, last_seen_ratings=None)
    d = [a for a in alerts if a["kind"] == "dropped_opening"]
    assert [a["family"] for a in d] == ["King's Gambit"]
    assert d[0]["color"] == "white"


def test_dropped_opening_not_when_still_played_or_small_share():
    old = [game(t, "white", "King's Gambit") for t in range(1, 4)] + [game(t, "white", "Italian Game") for t in range(4, 20)]
    latest = [game(100 + t, "white", "Italian Game") for t in range(12)]
    _, alerts = compute_alerts(old + latest, last_seen_end_time=1000, last_seen_ratings=None)
    assert "dropped_opening" not in kinds(alerts)  # 3/19 < 25%
    old2 = [game(t, "white", "King's Gambit") for t in range(1, 8)] + [game(t, "white", "Italian Game") for t in range(8, 20)]
    latest2 = [game(100 + t, "white", "King's Gambit" if t == 11 else "Italian Game") for t in range(12)]
    _, alerts = compute_alerts(old2 + latest2, last_seen_end_time=1000, last_seen_ratings=None)
    assert "dropped_opening" not in kinds(alerts)


def test_rating_change_threshold():
    games = [game(1, rating=1500), game(2, rating=1530)]
    _, alerts = compute_alerts(games, last_seen_end_time=5, last_seen_ratings={"rapid": 1500})
    assert [a["kind"] for a in alerts] == ["rating_change"]
    assert "up 30" in alerts[0]["message"]
    _, alerts = compute_alerts([game(2, rating=1529)], last_seen_end_time=5, last_seen_ratings={"rapid": 1500})
    assert alerts == []
    _, alerts = compute_alerts([game(2, rating=1450, tc="blitz")], last_seen_end_time=5, last_seen_ratings={"blitz": 1500})
    assert "down 50" in alerts[0]["message"]


# ── repository + router on a temp SQLite DB ─────────────────────────────────

DEVICE_A = "11111111-1111-4111-8111-111111111111"
DEVICE_B = "22222222-2222-4222-8222-222222222222"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from backend import db_models
    from backend.auth import current_device
    from backend.db import Base
    from backend.repositories import scout_watch as repo
    from backend.routers import scout_watch as router_mod
    from backend.services import scout_watch as svc
    from backend.services.rate_limit import lookup_rate_limiter

    engine = create_engine(f"sqlite:///{tmp_path / 'w.db'}", future=True)
    Base.metadata.create_all(engine, tables=[db_models.ScoutWatch.__table__])
    monkeypatch.setattr(repo, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False, future=True))

    data = {"alice": [game(100, rating=1500)], "bob": [game(50, rating=1400)]}

    def fake_fetch(username):
        if username == "broken":
            from backend.services.chesscom_client import ChessComClientError
            raise ChessComClientError("Chess.com returned HTTP 500.")
        return list(data.get(username, [game(10)]))

    monkeypatch.setattr(svc, "fetch_scout_games", fake_fetch)

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[lookup_rate_limiter] = lambda: None
    current = {"id": DEVICE_A}
    app.dependency_overrides[current_device] = lambda: current["id"]
    c = TestClient(app)
    c.data, c.current = data, current
    return c


def test_add_list_seen_delete_flow(client):
    r = client.post("/scout/watch", json={"username": "Alice"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice" and body["new_games"] == 0
    assert body["ratings"] == {"rapid": 1500} and body["error"] is None
    assert client.post("/scout/watch", json={"username": "alice"}).status_code == 200  # idempotent
    assert len(client.get("/scout/watch").json()["friends"]) == 1

    client.data["alice"] = [game(100), game(200, rating=1540), game(201, rating=1545)]
    f = client.get("/scout/watch").json()["friends"][0]
    assert f["new_games"] == 2
    assert {"new_games", "rating_change"} <= {a["kind"] for a in f["alerts"]}

    seen = client.post("/scout/watch/alice/seen").json()
    assert seen["new_games"] == 0 and seen["last_seen_at"] is not None and seen["alerts"] == []

    assert client.delete("/scout/watch/alice").json() == {"ok": True}
    assert client.get("/scout/watch").json() == {"friends": []}
    assert client.post("/scout/watch/alice/seen").status_code == 404


def test_validation_limit_and_isolation(client):
    assert client.post("/scout/watch", json={"username": "bad name!"}).status_code == 400
    for i in range(20):
        assert client.post("/scout/watch", json={"username": f"user{i}"}).status_code == 200
    assert client.post("/scout/watch", json={"username": "extra"}).status_code == 409
    assert client.post("/scout/watch", json={"username": "user0"}).status_code == 200  # existing still ok
    client.current["id"] = DEVICE_B
    assert client.get("/scout/watch").json() == {"friends": []}


def test_one_failing_friend_sets_error(client):
    client.post("/scout/watch", json={"username": "alice"})
    from backend.repositories import scout_watch as repo
    repo.add_watch(DEVICE_A, "broken", last_seen_end_time=None, last_seen_ratings=None)
    friends = {f["username"]: f for f in client.get("/scout/watch").json()["friends"]}
    assert friends["alice"]["error"] is None
    assert "HTTP 500" in friends["broken"]["error"]
