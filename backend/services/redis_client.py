from __future__ import annotations

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Shared, process-wide Redis client used by the rate limiter and the puzzle
# progress tracker so cross-instance state (rate-limit counters, in-flight
# mining runs) is correct when more than one backend instance is running.
#
# Design notes:
# - Connection is lazy: we only build the client on first use so importing this
#   module never touches the network (tests / local dev without Redis must not
#   crash on import).
# - We use a connection POOL (redis-py does this internally per client), and we
#   cache a single client per process behind a lock so every caller shares the
#   same pool rather than opening a socket per request.
# - The whole module is *fail-open*: if ``REDIS_URL`` is unset or the import of
#   the ``redis`` package fails, ``get_redis()`` returns ``None`` and callers
#   fall back to their in-memory / degraded path. Connection errors at call
#   time are the caller's responsibility to catch (they all do, and log a
#   warning + allow the request). A Redis blip must never take down the API.

REDIS_URL = os.getenv("REDIS_URL", "").strip()

_lock = threading.Lock()
_client = None  # type: ignore[var-annotated]
_init_attempted = False


def get_redis():
    """Return a process-wide pooled Redis client, or ``None`` if unavailable.

    Returns ``None`` (rather than raising) when ``REDIS_URL`` is not configured
    or the ``redis`` package isn't importable, so callers can transparently fall
    back to their in-memory path. We do *not* ping here — establishing a live
    connection happens lazily on the first command, and any error there is
    caught by the caller's fail-open handler.
    """
    global _client, _init_attempted

    if not REDIS_URL:
        # No Redis configured (local dev / tests): operate purely in-memory.
        return None

    # Fast path: already built.
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client
        if _init_attempted and _client is None:
            # We tried once and the redis package was missing; don't keep retrying
            # the import on every call.
            return None
        _init_attempted = True
        try:
            import redis  # imported lazily so the dependency is optional at runtime

            # decode_responses=True so we get str keys/values back (simpler for
            # the small hashes/counters we store). socket_connect_timeout keeps a
            # dead Redis from blocking request handling for long — combined with
            # the callers' try/except this gives fast fail-open.
            _client = redis.Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            logger.info("Redis client initialised for %s", _redacted_url(REDIS_URL))
        except Exception:  # pragma: no cover - exercised only without redis installed
            logger.warning(
                "Could not initialise Redis client; falling back to in-memory state.",
                exc_info=True,
            )
            _client = None
    return _client


def _redacted_url(url: str) -> str:
    """Hide any password in the URL before logging it."""
    if "@" in url and "//" in url:
        scheme, rest = url.split("//", 1)
        if "@" in rest:
            _creds, host = rest.split("@", 1)
            return f"{scheme}//***@{host}"
    return url


def reset_for_tests() -> None:
    """Drop the cached client so tests can re-evaluate configuration."""
    global _client, _init_attempted
    with _lock:
        _client = None
        _init_attempted = False
