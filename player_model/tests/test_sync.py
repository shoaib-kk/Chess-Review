"""Tests for the Chess.com sync pipeline (Section 1).

The client filtering, incremental watermark and URL dedup are tested with a fake
``_get_json`` (no network). The integration test runs a real sync through
Stockfish and then plays 10 twin moves — exactly the spec's required end-to-end
check — and auto-skips when no engine is available.

Run with:  pytest player_model/tests/test_sync.py
       or:  python -m player_model.tests.test_sync
"""

from __future__ import annotations

import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "pm_sync_test.db")
for _suffix in ("", "-wal", "-shm"):
    try:
        os.remove(_TEST_DB + _suffix)
    except OSError:
        pass
os.environ["PM_DATABASE_URL"] = "sqlite:///" + _TEST_DB

import chess  # noqa: E402

from player_model import chesscom_client as cc  # noqa: E402
from player_model import repository as repo  # noqa: E402
from player_model.db import SessionLocal, init_db  # noqa: E402
from player_model.models import Player  # noqa: E402
from player_model.pgn_ingest import parse_pgn  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures: synthetic Chess.com archive data
# --------------------------------------------------------------------------- #
USER = "twinuser"


def _pgn(white: str, black: str, moves: str, result: str = "1-0") -> str:
    return (
        f'[Event "Live Chess"]\n[White "{white}"]\n[Black "{black}"]\n'
        f'[Result "{result}"]\n[TimeControl "600"]\n[UTCDate "2026.05.01"]\n\n'
        f"{moves} {result}\n"
    )


_BLITZ = _pgn(USER, "opp", "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7")
_BULLET = _pgn("opp", USER, "1. d4 d5 2. c4 e6 3. Nc3 Nf6", result="0-1")


def _raw(url, pgn, time_class, end_time, rules="chess"):
    return {
        "url": url, "pgn": pgn, "time_class": time_class,
        "time_control": "600", "end_time": end_time, "rated": True, "rules": rules,
    }


def _fake_get_json_factory(games):
    def _fake(url):
        if url.endswith("/games/archives"):
            return {"archives": [f"{cc.BASE_URL}/player/{USER}/games/2026/05"]}
        return {"games": games}
    return _fake


# --------------------------------------------------------------------------- #
# Client filtering policy
# --------------------------------------------------------------------------- #
def test_filtering_excludes_daily_and_variants_keeps_bullet():
    assert cc._should_keep(_raw("u1", _BLITZ, "blitz", 100)) is True
    assert cc._should_keep(_raw("u2", _BULLET, "bullet", 100)) is True  # bullet kept
    assert cc._should_keep(_raw("u3", _BLITZ, "daily", 100)) is False   # daily excluded
    assert cc._should_keep(_raw("u4", _BLITZ, "blitz", 100, rules="chess960")) is False
    assert cc._should_keep(_raw("u5", "", "blitz", 100)) is False        # no pgn

    bullet = cc._normalise(_raw("u2", _BULLET, "bullet", 100))
    assert bullet is not None and bullet.time_class == "bullet"  # tagged separately


def test_iter_new_games_incremental_and_timeclass(monkeypatch):
    games = [
        _raw("g_old", _BLITZ, "blitz", 1000),
        _raw("g_new", _BLITZ, "blitz", 2000),
        _raw("g_bullet", _BULLET, "bullet", 2500),
        _raw("g_daily", _BLITZ, "daily", 3000),
    ]
    monkeypatch.setattr(cc, "_get_json", _fake_get_json_factory(games))

    # No watermark, no filter: every non-daily game, daily dropped.
    urls = [g.url for g in cc.iter_new_games(USER)]
    assert urls == ["g_old", "g_new", "g_bullet"]

    # Incremental: only games that finished strictly after the watermark.
    urls = [g.url for g in cc.iter_new_games(USER, since_end_time=2000)]
    assert urls == ["g_bullet"]

    # Time-class subset restricts to the chosen control.
    urls = [g.url for g in cc.iter_new_games(USER, time_classes=["bullet"])]
    assert urls == ["g_bullet"]


# --------------------------------------------------------------------------- #
# Repository: URL dedup + resync scheduling
# --------------------------------------------------------------------------- #
def test_url_dedup_and_pgn_adoption():
    init_db()
    db = SessionLocal()
    try:
        player = repo.get_or_create_player(db, USER)
        db.commit()
        parsed = parse_pgn(_BLITZ, username=USER)[0]

        assert repo.game_url_exists(db, player.id, "https://x/1") is False
        g1 = repo.create_chesscom_game(
            db, player.id, parsed, url="https://x/1", time_class="blitz", end_time=2000
        )
        db.commit()
        assert repo.game_url_exists(db, player.id, "https://x/1") is True
        assert g1.source == "chesscom" and g1.time_class == "blitz"

        # Same PGN that was already stored is adopted, not duplicated.
        g2 = repo.create_chesscom_game(
            db, player.id, parsed, url="https://x/2", time_class="blitz", end_time=2100
        )
        db.commit()
        assert g2.id == g1.id and g2.chess_com_game_url == "https://x/2"
    finally:
        db.close()


def test_players_due_for_resync():
    init_db()
    db = SessionLocal()
    try:
        connected = repo.get_or_create_player(db, "due_user")
        repo.set_player_chesscom(db, connected, "due_user", None)  # never synced
        unconnected = repo.get_or_create_player(db, "pgn_only_user")
        db.commit()

        due_ids = {p.id for p in repo.players_due_for_resync(db, interval_hours=6)}
        assert connected.id in due_ids          # never synced -> due
        assert unconnected.id not in due_ids     # not connected -> never due

        repo.mark_player_synced(db, connected.id, 9999)  # just synced now
        due_ids = {p.id for p in repo.players_due_for_resync(db, interval_hours=6)}
        assert connected.id not in due_ids       # within the 6h window -> not due
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Integration: Chess.com sync -> twin plays 10 moves (needs Stockfish)
# --------------------------------------------------------------------------- #
def _engine_available() -> bool:
    try:
        from player_model.analyzer import find_stockfish

        find_stockfish()
        return True
    except Exception:
        return False


def test_integration_sync_then_twin_plays_ten_moves(monkeypatch):
    if not _engine_available():
        print("  (skipped: Stockfish not available)")
        return

    from player_model import profile_tasks, sync_tasks, twin
    from player_model.engine import shutdown_engine

    games = [
        _raw("https://chess.com/g/1", _BLITZ, "blitz", 1000),
        _raw("https://chess.com/g/2", _BULLET, "bullet", 2000),
        _raw("https://chess.com/g/skip", _BLITZ, "daily", 3000),  # excluded
    ]
    monkeypatch.setattr(cc, "_get_json", _fake_get_json_factory(games))
    # Keep the test focused on sync + gameplay: don't fan out to the profile job.
    monkeypatch.setattr(profile_tasks.compute_profile, "delay", lambda *a, **k: None)

    init_db()
    db = SessionLocal()
    try:
        player = repo.get_or_create_player(db, USER)
        repo.set_player_chesscom(db, player, USER, None)
        job = repo.create_job(db, player.id)
        db.commit()
        player_id = player.id

        # Run the sync task body synchronously (low depth keeps it quick).
        monkeypatch.setenv("STOCKFISH_DEPTH", "8")
        sync_tasks.sync_chess_com(job.id, player_id, incremental=False)

        # Two modelled games ingested (daily excluded); watermark advanced.
        from player_model.models import Game, JobStatus

        db.expire_all()
        n_games = db.query(Game).filter(Game.player_id == player_id).count()
        assert n_games == 2
        synced = db.get(Player, player_id)
        assert synced.last_game_end_time == 2000
        job_row = repo.get_job(db, job.id)
        assert job_row.status == JobStatus.COMPLETED

        # The twin (neutral profile is fine) plays 10 legal moves.
        board = chess.Board()
        for _ in range(10):
            decision = twin.decide_for_player(board.fen(), player_id, db, depth=8)
            assert decision is not None
            move = chess.Move.from_uci(decision.move_uci)
            assert move in board.legal_moves
            board.push(move)
        print("  (synced 2 games and played 10 twin moves)")
    finally:
        db.close()
        shutdown_engine()


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import inspect

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        kwargs = {}
        # Minimal monkeypatch shim so the file runs without pytest.
        if "monkeypatch" in inspect.signature(t).parameters:
            import contextlib

            class _MP:
                def __init__(self):
                    self._undo = []

                def setattr(self, obj, name, val):
                    old = getattr(obj, name)
                    self._undo.append((obj, name, old))
                    setattr(obj, name, val)

                def setenv(self, k, v):
                    self._undo.append((os.environ, k, os.environ.get(k)))
                    os.environ[k] = v

                def undo(self):
                    for obj, name, old in reversed(self._undo):
                        if isinstance(obj, os._Environ):
                            if old is None:
                                obj.pop(name, None)
                            else:
                                obj[name] = old
                        else:
                            setattr(obj, name, old)

            kwargs["monkeypatch"] = _MP()
        try:
            t(**kwargs)
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
        finally:
            if "monkeypatch" in kwargs:
                kwargs["monkeypatch"].undo()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
