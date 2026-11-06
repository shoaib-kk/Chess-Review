"""Opponent scouting: ``GET /scout/{username}``.

Builds a preparation report on another Chess.com player from their public games
(see ``backend/services/opponent_scout.py``). No per-device state is touched, so
no device scoping is needed; the optional ``me`` username only selects whose
public games the matchup section compares against.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..services.chesscom_client import ChessComClientError
from ..services.opponent_scout import get_scouting_report
from ..services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

# Each report can fetch up to two players' archives and (with engine=true) run a
# few hundred shallow Stockfish evals, so keep the cap tighter than plain lookups.
scout_rate_limiter = RateLimiter(max_requests=8, window_seconds=60, name="scout")

router = APIRouter(tags=["scout"])


@router.get("/scout/{username}", dependencies=[Depends(scout_rate_limiter)])
def scout(
    username: str,
    limit: int = Query(default=300, ge=20, le=500),
    time_class: str | None = Query(default=None, pattern="^(rapid|blitz|bullet|daily)$"),
    rated_only: bool = Query(default=False),
    engine: bool = Query(default=False),
    me: str | None = Query(default=None, max_length=64),
) -> dict:
    try:
        return get_scouting_report(
            username=username,
            limit=limit,
            time_class=time_class,
            rated_only=rated_only,
            engine=engine,
            me=me or None,
        )
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
