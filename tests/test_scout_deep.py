"""Tests for the deep scouting job runner (stages stubbed; no engine, no network)."""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("APP_ENV", "dev")

import stockfish_engine  # noqa: E402
from backend.services import (  # noqa: E402
    lichess_explorer,
    scout_deep,
    scout_fingerprint,
    scout_refutations,
    scout_traps,
)
from test_opponent_scout import _opponent_games  # noqa: E402  (tests/ is on sys.path under pytest)


class _FakeEngine:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wait(key_args, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = scout_deep.get_status(*key_args)
        if status["state"] in ("done", "error"):
            return status
        time.sleep(0.02)
    raise AssertionError("deep job did not finish")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    scout_deep._jobs.clear()
    monkeypatch.setattr(scout_deep, "get_recent_games", lambda username, limit: _opponent_games())
    monkeypatch.setattr(stockfish_engine, "StockfishEngine", _FakeEngine)
    yield
    scout_deep._jobs.clear()


def test_idle_before_start():
    assert scout_deep.get_status("target", 300, None, False)["state"] == "idle"


def test_runs_all_stages_and_reports_result(monkeypatch):
    seen = {}

    def fake_refutations(trees, analyse, progress=None, **kw):
        seen["trees"] = sorted(trees)
        progress(1, 1)
        return [{"line": "1. e4"}]

    def fake_fingerprint(raw, username, evaluate, *, depth, max_games, progress=None, **kw):
        seen["fp"] = (username, depth, max_games, len(raw))
        return {"games_analyzed": 3}

    def fake_traps(trees, fetch, *, rating_band, speeds, progress=None, **kw):
        seen["band"] = rating_band
        return [{"trap_move": "Nf6"}]

    monkeypatch.setattr(scout_refutations, "find_refutations", fake_refutations)
    monkeypatch.setattr(scout_fingerprint, "build_fingerprint", fake_fingerprint)
    monkeypatch.setattr(scout_traps, "find_trappy_lines", fake_traps)

    started = scout_deep.start_job("Target", 300, "blitz", False)
    assert started["state"] == "running"
    status = _wait(("target", 300, "blitz", False))
    assert status["state"] == "done", status
    result = status["result"]
    assert result["refutations"] == [{"line": "1. e4"}]
    assert result["fingerprint"] == {"games_analyzed": 3}
    assert result["lichess_traps"] == [{"trap_move": "Nf6"}]
    assert result["lichess_error"] is None
    assert seen["trees"] == ["black", "white"]
    assert seen["fp"][0] == "Target" and seen["fp"][1] == scout_deep.FINGERPRINT_DEPTH


def test_stage_failures_are_isolated(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("stage broke")

    def lichess_down(*a, **k):
        raise lichess_explorer.LichessExplorerError("explorer down")

    monkeypatch.setattr(scout_refutations, "find_refutations", boom)
    monkeypatch.setattr(scout_fingerprint, "build_fingerprint", lambda *a, **k: {"games_analyzed": 1})
    monkeypatch.setattr(scout_traps, "find_trappy_lines", lichess_down)

    scout_deep.start_job("target", 300, None, False)
    status = _wait(("target", 300, None, False))
    assert status["state"] == "done"
    assert status["result"]["refutations"] == []
    assert status["result"]["fingerprint"] == {"games_analyzed": 1}
    assert status["result"]["lichess_traps"] is None
    assert "explorer down" in status["result"]["lichess_error"]


def test_engine_unavailable_fails_job(monkeypatch):
    def no_engine(*a, **k):
        raise stockfish_engine.EngineUnavailableError("gone")

    monkeypatch.setattr(scout_refutations, "find_refutations", no_engine)
    scout_deep.start_job("target", 300, None, False)
    status = _wait(("target", 300, None, False))
    assert status["state"] == "error"
    assert "engine" in status["error"].lower()


def test_second_start_while_running_returns_same_job(monkeypatch):
    import threading

    gate = threading.Event()

    def slow(trees, analyse, progress=None, **kw):
        gate.wait(5)
        return []

    monkeypatch.setattr(scout_refutations, "find_refutations", slow)
    monkeypatch.setattr(scout_fingerprint, "build_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(scout_traps, "find_trappy_lines", lambda *a, **k: [])
    first = scout_deep.start_job("target", 300, None, False)
    second = scout_deep.start_job("target", 300, None, False)
    assert first["started_at"] == second["started_at"]
    gate.set()
    assert _wait(("target", 300, None, False))["state"] == "done"
