"""Integration tests for the hardened Phase 7 API (envelope, auth, errors, cache).

Uses FastAPI's TestClient against a temporary SQLite DB. Redis is not required —
the cache layer degrades to a no-op. The Stockfish-dependent twin route is only
smoke-checked for auth/validation, not engine execution.
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pm_api_")
os.environ["PM_DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "api.db")
os.environ["PM_INDEX_DIR"] = os.path.join(_TMP, "indices")
os.environ["PM_MODELS_DIR"] = os.path.join(_TMP, "models")
os.environ["MASTER_API_KEY"] = "test-master-key"
os.environ["PM_REDIS_URL"] = "redis://127.0.0.1:6553/0"  # unreachable -> cache no-op

from fastapi.testclient import TestClient  # noqa: E402

from player_model.api import app  # noqa: E402
from player_model.api_common import ErrorCode  # noqa: E402

HEADERS = {"X-API-Key": "test-master-key"}
client = TestClient(app)


def _envelope_ok(body):
    assert set(body) == {"success", "data", "error", "meta"}
    assert set(body["meta"]) == {"computed_at", "model_version", "game_count"}


# --------------------------------------------------------------------------- #
def test_auth_required():
    r = client.get("/players/1")           # no key
    assert r.status_code == 401
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == ErrorCode.UNAUTHORIZED


def test_create_and_get_player_envelope():
    r = client.post("/players", json={"username": "magnus"}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    _envelope_ok(body)
    assert body["success"] is True
    pid = body["data"]["player_id"]

    r2 = client.get(f"/players/{pid}", headers=HEADERS)
    b2 = r2.json()
    _envelope_ok(b2)
    assert b2["data"]["username"] == "magnus"
    assert b2["data"]["profile_ready"] is False


def test_player_not_found():
    r = client.get("/players/999999", headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ErrorCode.PLAYER_NOT_FOUND


def test_profile_not_ready_error():
    pid = client.post("/players", json={"username": "noprofile"}, headers=HEADERS).json()["data"]["player_id"]
    r = client.get(f"/players/{pid}/profile", headers=HEADERS)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == ErrorCode.PROFILE_NOT_READY


def test_insufficient_games_error():
    from player_model.db import SessionLocal
    from player_model.models import PlayerProfile

    pid = client.post("/players", json={"username": "fewgames"}, headers=HEADERS).json()["data"]["player_id"]
    db = SessionLocal()
    db.add(PlayerProfile(player_id=pid, features={"accuracy": {"mean_cpl": 30}}, game_count=4))
    db.commit()
    db.close()

    r = client.get(f"/players/{pid}/profile", headers=HEADERS)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == ErrorCode.INSUFFICIENT_GAMES


def test_profile_success_with_enough_games():
    from player_model.db import SessionLocal
    from player_model.models import PlayerProfile

    pid = client.post("/players", json={"username": "ready"}, headers=HEADERS).json()["data"]["player_id"]
    db = SessionLocal()
    db.add(PlayerProfile(
        player_id=pid, features={"accuracy": {"mean_cpl": 25}}, game_count=30,
        archetype="Tactician",
    ))
    db.commit()
    db.close()

    r = client.get(f"/players/{pid}/profile", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    _envelope_ok(body)
    assert body["data"]["archetype"] == "Tactician"
    assert body["meta"]["game_count"] == 30


def test_invalid_fen_twin_move():
    pid = client.post("/players", json={"username": "twinp"}, headers=HEADERS).json()["data"]["player_id"]
    r = client.post(f"/players/{pid}/twin/move", json={"fen": "not-a-fen"}, headers=HEADERS)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == ErrorCode.INVALID_FEN


def test_patterns_empty_envelope():
    pid = client.post("/players", json={"username": "patp"}, headers=HEADERS).json()["data"]["player_id"]
    r = client.get(f"/players/{pid}/patterns", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    _envelope_ok(body)
    assert body["data"] == []


def test_delete_player():
    pid = client.post("/players", json={"username": "todelete"}, headers=HEADERS).json()["data"]["player_id"]
    r = client.delete(f"/players/{pid}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] == pid
    assert client.get(f"/players/{pid}", headers=HEADERS).status_code == 404


def test_health_unauthenticated():
    r = client.get("/health")              # no key required
    assert r.status_code == 200
    assert set(r.json()) == {"stockfish", "redis", "db"}
    assert r.json()["db"] == "ok"


def test_metrics():
    r = client.get("/metrics", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "total_players", "total_games_analysed", "queue_depth", "avg_job_time_seconds",
    }
    assert body["total_players"] >= 1


def test_compare_requires_both_players():
    pid = client.post("/players", json={"username": "cmpA"}, headers=HEADERS).json()["data"]["player_id"]
    r = client.get(f"/players/compare?a={pid}&b=999999", headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ErrorCode.PLAYER_NOT_FOUND


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            import traceback
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
