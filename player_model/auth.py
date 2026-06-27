"""Simple API-key authentication for the MVP (Phase 7).

Keys are random tokens; only their SHA-256 hash is stored. A ``MASTER_API_KEY``
env var (if set) is always accepted — useful for bootstrapping the first players
and for admin/monitoring tooling.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from .api_common import ApiError, ErrorCode

MASTER_API_KEY = os.getenv("MASTER_API_KEY")


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_api_key(db, player_id: Optional[int] = None) -> str:
    """Generate, store and return a new raw API key (shown to the caller once)."""
    from .models import ApiKey

    raw = secrets.token_urlsafe(32)
    db.add(ApiKey(key_hash=hash_key(raw), player_id=player_id))
    db.commit()
    return raw


def authenticate(db, raw_key: Optional[str]):
    """Validate a key. Returns a marker on success; raises ApiError(401) otherwise.

    Returns the string ``"master"`` for the master key, otherwise the ApiKey row.
    """
    if not raw_key:
        raise ApiError(ErrorCode.UNAUTHORIZED, "Missing X-API-Key header.")

    if MASTER_API_KEY and secrets.compare_digest(raw_key, MASTER_API_KEY):
        return "master"

    from sqlalchemy import select

    from .models import ApiKey

    row = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key)))
    if row is None:
        raise ApiError(ErrorCode.UNAUTHORIZED, "Invalid API key.")
    row.last_used = datetime.now(timezone.utc)
    db.commit()
    return row
