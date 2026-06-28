from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from ..auth import current_device
from ..repositories.drills import get_drill, record_attempt
from ..schemas import DrillAttemptRequest, DrillVerdictResponse
from ..services.drills import MAX_USER_MOVES, compute_verdict, evaluate_final_position
from ..services.rate_limit import drill_attempt_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drills", tags=["drills"])


# All drills are scoped to the caller's device id (X-Device-Id), an unguessable
# random UUID — so a client only ever sees or grades its own drills.
@router.get("/{drill_id}")
def read_drill(drill_id: int = Path(..., ge=1), device: str = Depends(current_device)) -> dict:
    drill = get_drill(device, drill_id)
    if drill is None:
        raise HTTPException(status_code=404, detail="Drill not found.")
    drill["max_user_moves"] = MAX_USER_MOVES
    return drill


@router.post("/{drill_id}/attempt", response_model=DrillVerdictResponse)
def attempt_drill(
    request: DrillAttemptRequest,
    drill_id: int = Path(..., ge=1),
    device: str = Depends(current_device),
    _: None = Depends(drill_attempt_rate_limiter),
) -> DrillVerdictResponse:
    """Grade a finished play-out against the drill's objective via a live engine eval."""
    drill = get_drill(device, drill_id)
    if drill is None:
        raise HTTPException(status_code=404, detail="Drill not found.")

    try:
        final = evaluate_final_position(request.final_fen, drill["user_color"], depth=request.depth)
    except ValueError as exc:  # malformed FEN
        raise HTTPException(status_code=400, detail="Invalid final position.") from exc
    except Exception as exc:  # engine missing / crashed
        logger.exception("Drill evaluation failed")
        raise HTTPException(status_code=503, detail="Engine temporarily unavailable.") from exc

    result = compute_verdict(
        drill["objective"],
        drill["start_eval_cp"],
        final.final_eval_cp,
        mate_for_user=final.mate_for_user,
        is_draw=final.is_draw,
    )

    record_attempt(
        device,
        drill_id,
        verdict=result.verdict,
        final_eval_cp=result.final_eval,
        swing_cp=result.swing,
    )

    return DrillVerdictResponse(
        drill_id=drill_id,
        objective=drill["objective"],
        verdict=result.verdict,
        start_eval=result.start_eval,
        final_eval=result.final_eval,
        swing=result.swing,
        reason=result.reason,
    )
