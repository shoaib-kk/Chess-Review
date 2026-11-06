from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import current_device
from ..services import scout_watch as svc
from ..services.chesscom_client import ChessComClientError
from ..services.rate_limit import lookup_rate_limiter

# Must be included BEFORE the /scout/{username} router so "watch" is not read as a username.
router = APIRouter(prefix="/scout/watch", tags=["scout"])


class WatchAddRequest(BaseModel):
    username: str = Field(..., max_length=64)


def _chesscom_http(exc: ChessComClientError) -> HTTPException:
    msg = str(exc)
    if "Invalid" in msg:
        return HTTPException(status_code=400, detail=msg)
    if "not found" in msg.lower():
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=502, detail=msg)


@router.get("")
def list_watch(device: str = Depends(current_device), _: None = Depends(lookup_rate_limiter)) -> dict:
    return svc.list_friends(device)


@router.post("")
def add_watch(
    request: WatchAddRequest,
    device: str = Depends(current_device),
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    try:
        return svc.add_friend(device, request.username)
    except svc.WatchLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ChessComClientError as exc:
        raise _chesscom_http(exc) from exc


@router.delete("/{username}")
def delete_watch(
    username: str, device: str = Depends(current_device), _: None = Depends(lookup_rate_limiter)
) -> dict:
    try:
        svc.remove_friend(device, username)
    except ChessComClientError as exc:
        raise _chesscom_http(exc) from exc
    return {"ok": True}


@router.post("/{username}/seen")
def seen_watch(
    username: str, device: str = Depends(current_device), _: None = Depends(lookup_rate_limiter)
) -> dict:
    try:
        return svc.mark_friend_seen(device, username)
    except svc.WatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not on your watchlist.") from exc
    except ChessComClientError as exc:
        raise _chesscom_http(exc) from exc
