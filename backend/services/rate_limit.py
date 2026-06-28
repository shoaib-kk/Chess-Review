from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .redis_client import get_redis

logger = logging.getLogger(__name__)

# Only honour proxy-supplied client-IP headers when explicitly told we sit behind
# a trusted reverse proxy (the bundled nginx). When the backend is exposed
# directly, any client can forge these headers to dodge the limiter or poison
# another IP's bucket, so we ignore them and use the real peer address.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"


def client_ip(request: Request) -> str:
    """Best-effort real client IP.

    Behind the bundled nginx the backend only sees the proxy's address as
    ``request.client.host``. nginx sets ``X-Real-IP`` to the real ``$remote_addr``
    (overwriting any client-supplied value), so when ``TRUST_PROXY_HEADERS`` is
    set we honour that single trusted hop. We deliberately do *not* parse
    ``X-Forwarded-For`` — it's the easier header to spoof and X-Real-IP is
    sufficient. With no trusted proxy we fall back to the peer address.
    """
    if TRUST_PROXY_HEADERS:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Fixed-window rate limiter, keyed by client IP.

    When ``REDIS_URL`` is configured the counter lives in Redis, so the limit is
    shared across *all* backend instances (a single client can't dodge the cap by
    being load-balanced onto a different process, and the limit is no longer
    per-instance). Without Redis — local dev, tests, or a Redis outage — it falls
    back to an in-memory per-process counter that behaves exactly like the
    original implementation.

    FAIL-OPEN: if a Redis command raises (Redis down / unreachable), we log a
    warning and *allow* the request rather than 500-ing. A rate limiter that
    hard-fails would take the whole API down whenever Redis blips; degrading to
    "no limit for the duration of the outage" is the safer trade-off.

    The Redis scheme is a fixed-window counter:
        key   = ``ratelimit:{name}:{ip}:{window_bucket}``
        value = integer hit count, incremented atomically with INCR
        TTL   = the window length (set once, when the bucket is first created)
    ``window_bucket`` is ``floor(now / window_seconds)`` so each window gets its
    own key that Redis expires for us — no sweeping required server-side.
    """

    def __init__(self, max_requests: int, window_seconds: float, name: str):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # ``name`` namespaces the Redis keys so the five limiters never collide.
        self.name = name
        # In-memory fallback state (used when Redis is unconfigured/unreachable).
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()

    # ------------------------------------------------------------------ Redis
    def _allow_redis(self, redis_client, key: str) -> bool:
        """Atomically count this hit against the current window in Redis.

        Returns True if the request is under the cap. On *any* Redis error we
        re-raise so the caller's fail-open handler can allow the request.
        """
        bucket = int(time.time() // self.window_seconds)
        redis_key = f"ratelimit:{self.name}:{key}:{bucket}"
        # Pipeline INCR + EXPIRE so both run in one round trip. We always (re)set
        # EXPIRE; it's cheap and guarantees the key gets a TTL even if the process
        # died between INCR and EXPIRE on a prior call. ceil the TTL so a
        # fractional window still expires strictly after the window closes.
        pipe = redis_client.pipeline()
        pipe.incr(redis_key, 1)
        pipe.expire(redis_key, int(self.window_seconds) + 1)
        count, _ = pipe.execute()
        return int(count) <= self.max_requests

    # -------------------------------------------------------------- In-memory
    def _sweep(self, now: float) -> None:
        """Drop every key whose window has fully expired.

        ``defaultdict`` materialises an entry for each distinct IP, so without
        this a flood of spoofed/rotating addresses would grow the dict without
        bound. Runs at most once per window, so it's O(keys) amortised and caps
        memory at roughly the number of IPs active within one window.
        """
        if now - self._last_sweep < self.window_seconds:
            return
        self._last_sweep = now
        expired = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] > self.window_seconds
        ]
        for key in expired:
            del self._hits[key]

    def _allow_memory(self, key: str) -> bool:
        now = time.monotonic()
        self._sweep(now)
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    # ----------------------------------------------------------------- Caller
    def __call__(self, request: Request) -> None:
        key = client_ip(request)

        redis_client = get_redis()
        if redis_client is not None:
            try:
                allowed = self._allow_redis(redis_client, key)
            except Exception:
                # FAIL-OPEN: Redis is unreachable. Allow the request rather than
                # bringing the API down. We log at warning so the outage is
                # visible without spamming per-request stack traces.
                logger.warning(
                    "Rate limiter '%s' could not reach Redis; allowing request (fail-open).",
                    self.name,
                    exc_info=True,
                )
                return
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please slow down and try again shortly.",
                )
            return

        # No Redis configured: per-process in-memory limiting.
        if not self._allow_memory(key):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down and try again shortly.",
            )


# Stockfish analysis is CPU-heavy and synchronous per request.
analyze_rate_limiter = RateLimiter(max_requests=10, window_seconds=60, name="analyze")

# Chess.com lookups iterate over monthly archives upstream; lighter limit is enough.
lookup_rate_limiter = RateLimiter(max_requests=30, window_seconds=60, name="lookup")

# Triggering puzzle generation kicks off a background thread that runs Stockfish
# over up to ~200 of the user's games — by far the most expensive operation in
# the app. Keep it tight so a client can't queue many heavy runs back-to-back.
puzzle_analyze_rate_limiter = RateLimiter(max_requests=3, window_seconds=60, name="puzzle_analyze")

# Interactive "play out the position" makes one engine call per move; allow a
# brisk back-and-forth while still capping a runaway client.
play_rate_limiter = RateLimiter(max_requests=60, window_seconds=60, name="play")

# Grading a drill play-out runs one Stockfish eval of the final position. Less
# frequent than per-move play, so a tighter cap than play is plenty.
drill_attempt_rate_limiter = RateLimiter(max_requests=20, window_seconds=60, name="drill_attempt")
