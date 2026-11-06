"""Persistence for the per-device scouting watchlist. All SQL lives here."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from ..db import SessionLocal
from ..db_models import ScoutWatch


def _to_dict(row: ScoutWatch) -> dict[str, Any]:
    return {
        "username": row.username,
        "added_at": row.added_at,
        "last_seen_at": row.last_seen_at,
        "last_seen_end_time": row.last_seen_end_time,
        "last_seen_ratings": row.last_seen_ratings,
    }


def _one(session, owner_id: str, username: str) -> ScoutWatch | None:
    return session.execute(
        select(ScoutWatch).where(ScoutWatch.owner_id == owner_id, ScoutWatch.username == username)
    ).scalar_one_or_none()


def list_watch(owner_id: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ScoutWatch)
            .where(ScoutWatch.owner_id == owner_id)
            .order_by(ScoutWatch.added_at, ScoutWatch.id)
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def get_watch(owner_id: str, username: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = _one(session, owner_id, username)
        return _to_dict(row) if row else None


def count_watch(owner_id: str) -> int:
    with SessionLocal() as session:
        return int(
            session.execute(
                select(func.count()).select_from(ScoutWatch).where(ScoutWatch.owner_id == owner_id)
            ).scalar_one()
        )


def add_watch(
    owner_id: str,
    username: str,
    *,
    last_seen_end_time: int | None,
    last_seen_ratings: dict[str, int] | None,
) -> dict[str, Any]:
    """Insert a friend; if it already exists, return the existing row untouched."""
    with SessionLocal() as session:
        existing = _one(session, owner_id, username)
        if existing is not None:
            return _to_dict(existing)
        row = ScoutWatch(
            owner_id=owner_id,
            username=username,
            added_at=datetime.now(timezone.utc),
            last_seen_end_time=last_seen_end_time,
            last_seen_ratings=last_seen_ratings,
        )
        session.add(row)
        session.commit()
        return _to_dict(row)


def delete_watch(owner_id: str, username: str) -> bool:
    with SessionLocal() as session:
        result = session.execute(
            delete(ScoutWatch).where(ScoutWatch.owner_id == owner_id, ScoutWatch.username == username)
        )
        session.commit()
        return bool(result.rowcount)


def mark_seen(
    owner_id: str,
    username: str,
    *,
    last_seen_end_time: int | None,
    last_seen_ratings: dict[str, int] | None,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = _one(session, owner_id, username)
        if row is None:
            return None
        row.last_seen_at = datetime.now(timezone.utc)
        if last_seen_end_time is not None:
            row.last_seen_end_time = last_seen_end_time
        row.last_seen_ratings = last_seen_ratings
        session.commit()
        return _to_dict(row)
