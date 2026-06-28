"""Tests for the Redis-backed rate limiter and puzzle progress.

The CI/dev environment usually has NO live Redis. These tests therefore focus on
two things that must hold without a server:

1. Fail-open: with REDIS_URL unset (or pointing at a dead server), the rate
   limiter still enforces limits via its in-memory fallback and never 500s, and
   the puzzle-progress helpers still read/write without crashing.
2. Import safety: the modules import cleanly with no Redis around.

Anything that needs a real server is guarded by ``redis_available()`` and skips
gracefully when Redis can't be reached.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "dev")


class _FakeRequest:
    """Minimal stand-in for fastapi.Request that client_ip() understands."""

    def __init__(self, ip: str = "1.2.3.4"):
        self.headers = {}
        self.client = type("C", (), {"host": ip})()


def redis_available() -> bool:
    url = os.getenv("REDIS_URL")
    if not url:
        return False
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=1)
        client.ping()
        return True
    except Exception:
        return False


def test_rate_limit_module_imports_without_redis():
    # Force the no-Redis path for this module-load.
    os.environ.pop("REDIS_URL", None)
    from backend.services import redis_client

    redis_client.reset_for_tests()
    redis_client.REDIS_URL = ""
    assert redis_client.get_redis() is None


def test_in_memory_limiter_enforces_and_fails_open():
    from fastapi import HTTPException

    from backend.services import redis_client
    from backend.services.rate_limit import RateLimiter

    # Ensure the in-memory path (no Redis).
    redis_client.reset_for_tests()
    redis_client.REDIS_URL = ""

    limiter = RateLimiter(max_requests=2, window_seconds=60, name="test")
    req = _FakeRequest("9.9.9.9")

    limiter(req)  # 1st OK
    limiter(req)  # 2nd OK
    with pytest.raises(HTTPException) as exc:
        limiter(req)  # 3rd over the cap
    assert exc.value.status_code == 429


def test_limiter_fails_open_on_redis_error(monkeypatch):
    """A broken Redis client must allow the request, not raise."""
    from backend.services import rate_limit

    class _BoomClient:
        def pipeline(self):
            raise RuntimeError("redis down")

    monkeypatch.setattr(rate_limit, "get_redis", lambda: _BoomClient())

    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=60, name="boom")
    req = _FakeRequest("8.8.8.8")
    # Even well past the cap, fail-open means no exception is raised.
    for _ in range(5):
        limiter(req)


def test_puzzle_progress_reads_without_redis(monkeypatch):
    from backend.services import puzzle_analyzer

    # Stub out the DB-backed counts so this stays a pure unit test.
    monkeypatch.setattr(puzzle_analyzer, "get_analyzed_count", lambda owner: 0)
    monkeypatch.setattr(puzzle_analyzer, "get_puzzle_count", lambda owner: 0)
    monkeypatch.setattr(puzzle_analyzer, "get_redis", lambda: None)

    puzzle_analyzer._set_progress("dev-xyz", total=10, analyzed=3)
    puzzle_analyzer._incr_progress("dev-xyz", "analyzed", 1)
    prog = puzzle_analyzer.get_progress("dev-xyz")
    assert prog["total"] == 10
    assert prog["analyzed"] == 4
    assert prog["running"] is False


def test_progress_fails_open_on_redis_error(monkeypatch):
    from backend.services import puzzle_analyzer

    class _BoomClient:
        def hgetall(self, *a):
            raise RuntimeError("redis down")

        def hset(self, *a, **k):
            raise RuntimeError("redis down")

        def hincrby(self, *a):
            raise RuntimeError("redis down")

        def expire(self, *a):
            raise RuntimeError("redis down")

    monkeypatch.setattr(puzzle_analyzer, "get_analyzed_count", lambda owner: 0)
    monkeypatch.setattr(puzzle_analyzer, "get_puzzle_count", lambda owner: 0)
    monkeypatch.setattr(puzzle_analyzer, "get_redis", lambda: _BoomClient())

    # None of these should raise despite Redis blowing up.
    puzzle_analyzer._set_progress("dev-boom", total=5)
    puzzle_analyzer._incr_progress("dev-boom", "analyzed", 1)
    prog = puzzle_analyzer.get_progress("dev-boom")
    assert prog["analyzed"] >= 1  # served from the in-memory mirror


@pytest.mark.skipif(not redis_available(), reason="No live Redis available")
def test_redis_limiter_shares_counter():
    """Integration: with a real Redis, the counter is enforced atomically."""
    from fastapi import HTTPException

    from backend.services import redis_client
    from backend.services.rate_limit import RateLimiter

    redis_client.reset_for_tests()
    limiter = RateLimiter(max_requests=2, window_seconds=60, name="itest")
    req = _FakeRequest("7.7.7.7")
    limiter(req)
    limiter(req)
    with pytest.raises(HTTPException):
        limiter(req)
