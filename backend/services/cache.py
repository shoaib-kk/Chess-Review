from __future__ import annotations

import time
from functools import wraps
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def ttl_lru_cache(maxsize: int = 32, ttl_seconds: int = 300) -> Callable[[F], F]:
    """Like functools.lru_cache, but entries expire after ttl_seconds.

    Needed for chess.com-backed lookups: a plain lru_cache never refreshes,
    so a user who plays new games keeps seeing stale insights until the
    process restarts.
    """

    def decorator(func: F) -> F:
        cache: dict[tuple, tuple[float, object]] = {}
        order: list[tuple] = []

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()

            cached = cache.get(key)
            if cached is not None:
                timestamp, value = cached
                if now - timestamp < ttl_seconds:
                    return value
                del cache[key]
                order.remove(key)

            value = func(*args, **kwargs)
            cache[key] = (now, value)
            order.append(key)
            if len(order) > maxsize:
                oldest = order.pop(0)
                cache.pop(oldest, None)
            return value

        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
