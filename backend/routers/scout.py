"""Opponent scouting: ``GET /scout/{username}`` plus the deep (engine) job.

Builds a preparation report on another Chess.com player from their public games
(see ``backend/services/opponent_scout.py``). No per-device state is touched, so
no device scoping is needed; the optional ``me`` username only selects whose
games the matchup / head-to-head sections compare against. The friends
watchlist (device-scoped) lives in ``routers/scout_watch.py``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..services.chesscom_client import ChessComClientError
from ..services.opponent_scout import get_scouting_report
from ..services.rate_limit import RateLimiter
from ..services.scout_deep import get_status, start_job

logger = logging.getLogger(__name__)

# Each report can fetch up to two players' archives and (with engine=true) run a
# few hundred shallow Stockfish evals, so keep the cap tighter than plain lookups.
scout_rate_limiter = RateLimiter(max_requests=8, window_seconds=60, name="scout")
# Starting a deep job queues minutes of engine work.
scout_deep_rate_limiter = RateLimiter(max_requests=4, window_seconds=60, name="scout_deep")
# The page polls job status every few seconds while a job runs; give polling its
# own budget so it can't eat the shared lookup limit the rest of the app uses.
scout_deep_status_rate_limiter = RateLimiter(max_requests=60, window_seconds=60, name="scout_deep_status")

USERNAME = Path(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")
TIME_CLASS = Query(default=None, pattern="^(rapid|blitz|bullet|daily)$")

router = APIRouter(tags=["scout"])


@router.get("/scout/{username}", dependencies=[Depends(scout_rate_limiter)])
def scout(
    username: str = USERNAME,
    limit: int = Query(default=300, ge=20, le=500),
    time_class: str | None = TIME_CLASS,
    rated_only: bool = Query(default=False),
    engine: bool = Query(default=False),
    me: str | None = Query(default=None, max_length=64),
    tz_offset: int = Query(default=0, ge=-840, le=840),
) -> dict:
    try:
        return get_scouting_report(
            username=username,
            limit=limit,
            time_class=time_class,
            rated_only=rated_only,
            engine=engine,
            me=me or None,
            tz_offset=tz_offset,
        )
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scout/{username}/deep", dependencies=[Depends(scout_deep_rate_limiter)])
def start_deep(
    username: str = USERNAME,
    limit: int = Query(default=300, ge=20, le=500),
    time_class: str | None = TIME_CLASS,
    rated_only: bool = Query(default=False),
) -> dict:
    return start_job(username, limit, time_class, rated_only)


@router.get("/scout/{username}/deep", dependencies=[Depends(scout_deep_status_rate_limiter)])
def deep_status(
    username: str = USERNAME,
    limit: int = Query(default=300, ge=20, le=500),
    time_class: str | None = TIME_CLASS,
    rated_only: bool = Query(default=False),
) -> dict:
    return get_status(username, limit, time_class, rated_only)
