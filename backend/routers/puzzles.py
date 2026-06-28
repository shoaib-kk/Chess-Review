from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from ..auth import current_device
from ..repositories.puzzles import (
    get_analyzed_count,
    get_phase_counts,
    get_puzzle_count,
    get_puzzles,
    mark_solved,
)
from ..schemas import PuzzleAnalyzeRequest
from ..services.puzzle_analyzer import get_progress, start_fresh
from ..services.rate_limit import lookup_rate_limiter, puzzle_analyze_rate_limiter

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


# All puzzle data is scoped to the caller's device id (X-Device-Id), which is an
# unguessable random UUID — so a client only ever sees or mutates its own
# puzzles. The Chess.com username is never part of the ownership key.
@router.get("/")
def list_puzzles(
    device: str = Depends(current_device),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    phase: str | None = Query(default=None, pattern="^(opening|middlegame|endgame)$"),
    difficulty: str | None = Query(default=None, pattern="^(blunders|mistakes)$"),
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    puzzles = get_puzzles(device, limit=limit, offset=offset, phase=phase, difficulty=difficulty)
    return {
        "puzzles": puzzles,
        "total_puzzles": get_puzzle_count(device),
        "analyzed_games": get_analyzed_count(device),
        "phase_counts": get_phase_counts(device),
        "progress": get_progress(device),
    }


@router.post("/analyze")
def trigger_analysis(
    request: PuzzleAnalyzeRequest,
    device: str = Depends(current_device),
    _: None = Depends(puzzle_analyze_rate_limiter),
) -> dict:
    # Mine the given Chess.com account's public games; the resulting puzzles are
    # owned by this device.
    started = start_fresh(device, request.username.strip().lower())
    return {"started": started, "message": "Analysis already running." if not started else "Analysis started."}


@router.get("/progress")
def puzzle_progress(device: str = Depends(current_device)) -> dict:
    return get_progress(device)


@router.post("/{puzzle_id}/solved")
def solved(puzzle_id: int = Path(..., ge=1), device: str = Depends(current_device)) -> dict:
    mark_solved(device, puzzle_id)
    return {"ok": True}
