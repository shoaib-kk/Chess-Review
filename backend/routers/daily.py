from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path

from ..auth import current_device
from ..schemas import DailyResultRequest
from ..services.daily import get_daily, record_result
from ..services.rate_limit import lookup_rate_limiter

router = APIRouter(prefix="/daily", tags=["daily"])


# Daily set, due SRS cards, and streak are all scoped to the device id.
@router.get("/")
def daily(device: str = Depends(current_device), _: None = Depends(lookup_rate_limiter)) -> dict:
    return get_daily(device, date.today())


@router.post("/{puzzle_id}/result")
def daily_result(
    request: DailyResultRequest,
    puzzle_id: int = Path(..., ge=1),
    device: str = Depends(current_device),
) -> dict:
    username = (request.username or "").strip() or None
    return record_result(device, username, puzzle_id, request.result, date.today())
