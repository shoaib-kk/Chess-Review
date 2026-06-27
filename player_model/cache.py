"""Redis caching layer (Phase 7).

Provides a ``@cached(key_fn, ttl)`` decorator and invalidation helpers. Degrades
gracefully: if Redis is unreachable, the decorator simply calls through and the
invalidation helpers become no-ops (so the API still works without Redis, e.g. in
tests).
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Callable

from .config import REDIS_URL

logger = logging.getLogger(__name__)

# TTLs (seconds) per the spec.
TTL_PROFILE = 3600
TTL_STYLE = 3600
TTL_PATTERNS = 3600
TTL_TWIN_MOVE = 300
TTL_SIMILAR_PLAYERS = 6 * 3600

_redis = None
_unavailable = False


def get_redis():
    """Return a connected Redis client, or None if unreachable (sticky)."""
    global _redis, _unavailable
    if _unavailable:
        return None
    if _redis is None:
        try:
            import redis

            client = redis.Redis.from_url(
                REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5,
                decode_responses=True,
            )
            client.ping()
            _redis = client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            _unavailable = True
            return None
    return _redis


def reset_redis() -> None:
    """Reset the cached client/availability flag (used by tests)."""
    global _redis, _unavailable
    _redis = None
    _unavailable = False


def cached(key_fn: Callable[..., str], ttl: int):
    """Cache a function's (JSON-serialisable) return value in Redis under key_fn()."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            client = get_redis()
            key = key_fn(*args, **kwargs)
            if client is not None:
                try:
                    raw = client.get(key)
                    if raw is not None:
                        return json.loads(raw)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("cache get failed for %s: %s", key, exc)

            result = fn(*args, **kwargs)

            if client is not None and result is not None:
                try:
                    client.setex(key, ttl, json.dumps(result, default=str))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("cache set failed for %s: %s", key, exc)
            return result

        return wrapper

    return decorator


def _delete_matching(patterns: list[str]) -> None:
    client = get_redis()
    if client is None:
        return
    for pattern in patterns:
        try:
            for key in client.scan_iter(match=pattern, count=200):
                client.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cache delete failed for %s: %s", pattern, exc)


def invalidate_player(player_id: int) -> None:
    """Drop every cached key for a player (called on ingestion completion)."""
    _delete_matching([
        f"profile:{player_id}:*",
        f"style:{player_id}:*",
        f"patterns:{player_id}",
        f"twin_move:{player_id}:*",
        f"similar:{player_id}",
    ])


def invalidate_all_style() -> None:
    """Drop every cached style vector (called after a PCA refit)."""
    _delete_matching(["style:*"])
