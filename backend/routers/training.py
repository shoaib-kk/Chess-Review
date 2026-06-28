from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import current_device
from ..repositories.games import count_inbox, get_inbox
from ..repositories.srs import get_streak
from ..schemas import InboxImportRequest
from ..services.auto_import import trigger_import
from ..services.chesscom_client import ChessComClientError
from ..services.progress import get_progress_summary, get_training_activity
from ..services.rate_limit import lookup_rate_limiter
from ..services.training_plan import get_training_plan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["training"])


@router.get("/training-plan")
def training_plan(
    username: str = Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    device: str = Depends(current_device),
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    """The device's weakness-derived training plan (categories + drill progress)."""
    try:
        return get_training_plan(device, username.strip())
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/progress")
def progress(
    username: str = Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    device: str = Depends(current_device),
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    """Progress-over-time deltas (cached) plus this device's streak and drill trend."""
    try:
        summary = get_progress_summary(username.strip())
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Streak and training activity are device-scoped, so they're computed outside
    # the username-keyed progress cache.
    return {
        **summary,
        "streak": get_streak(device),
        "training": get_training_activity(device),
    }


@router.get("/inbox")
def inbox(device: str = Depends(current_device)) -> dict:
    """Auto-imported games that are ready to review (not yet opened)."""
    return {"games": get_inbox(device), "count": count_inbox(device)}


@router.post("/inbox/refresh")
def inbox_refresh(
    request: InboxImportRequest,
    device: str = Depends(current_device),
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    """Kick off a background poll of the user's Chess.com archive for new games."""
    started = trigger_import(device, request.username.strip())
    return {"started": started}
