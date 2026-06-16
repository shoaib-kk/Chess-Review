from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..services.puzzle_analyzer import get_progress, start_fresh
from ..services.puzzle_store import (
    ensure_tables,
    get_analyzed_count,
    get_phase_counts,
    get_puzzle_count,
    get_puzzles,
    mark_solved,
)
from ..services.rate_limit import lookup_rate_limiter

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


@router.get("/{username}")
def list_puzzles(
    username: str,
    limit: int = 100,
    offset: int = 0,
    phase: str | None = None,
    difficulty: str | None = None,
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    ensure_tables()
    normalized = username.strip()

    puzzles = get_puzzles(
        normalized, limit=limit, offset=offset, phase=phase, difficulty=difficulty
    )
    progress = get_progress(normalized)
    return {
        "username": normalized,
        "puzzles": puzzles,
        "total_puzzles": get_puzzle_count(normalized),
        "analyzed_games": get_analyzed_count(normalized),
        "phase_counts": get_phase_counts(normalized),
        "progress": progress,
    }


@router.post("/{username}/analyze")
def trigger_analysis(
    username: str,
    _: None = Depends(lookup_rate_limiter),
) -> dict:
    normalized = username.strip()
    ensure_tables()
    started = start_fresh(normalized)
    return {"started": started, "message": "Analysis already running." if not started else "Analysis started."}


@router.get("/{username}/progress")
def puzzle_progress(username: str) -> dict:
    ensure_tables()
    return get_progress(username.strip())


@router.post("/{username}/{puzzle_id}/solved")
def solved(username: str, puzzle_id: int) -> dict:
    ensure_tables()
    mark_solved(username.strip(), puzzle_id)
    return {"ok": True}
