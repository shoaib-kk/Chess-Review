from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """Fixed-window in-memory rate limiter, keyed by client IP.

    Per-process only: on multi-instance deployments each instance enforces
    its own limit. Good enough to stop a single client from hammering the
    Stockfish-backed endpoints.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[key]

        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down and try again shortly.")

        hits.append(now)


# Stockfish analysis is CPU-heavy and synchronous per request.
analyze_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

# Chess.com lookups iterate over monthly archives upstream; lighter limit is enough.
lookup_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

# Interactive "play out the position" makes one engine call per move; allow a
# brisk back-and-forth while still capping a runaway client.
play_rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
