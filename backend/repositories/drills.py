"""Persistence for weakness-targeted play-out drills.

All SQL for the drills subsystem lives here (never in routers). Drills are scoped
to ``device_id`` (the anonymous per-device id); the verdict logic itself is the
pure code in :mod:`backend.services.drills`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db import SessionLocal
from ..db_models import Drill, DrillAttempt, Game, Puzzle
from ..services.drills import CategorySpec, drill_from_puzzle

logger = logging.getLogger(__name__)

# Per-category target: passing this many drills "masters" the category.
MASTERY_TARGET = 5
# How many candidate positions to assemble per category when generating drills.
DRILLS_PER_CATEGORY = 8

_PHASE_BOUNDS: dict[str, tuple[int | None, int | None]] = {
    "Opening": (None, 12),
    "Middlegame": (13, 30),
    "Endgame": (31, None),
}


def _phase_filtered(stmt, phase: str | None):
    bounds = _PHASE_BOUNDS.get(phase or "")
    if not bounds:
        return stmt
    low, high = bounds
    if low is not None:
        stmt = stmt.where(Puzzle.move_number >= low)
    if high is not None:
        stmt = stmt.where(Puzzle.move_number <= high)
    return stmt


def _matching_puzzles(device_id: str, spec: CategorySpec, limit: int) -> list[dict[str, Any]]:
    """Candidate mined positions for a category (worst mistakes first)."""
    stmt = (
        select(Puzzle, Game)
        .join(Game, Puzzle.game_id == Game.id)
        .where(Game.owner_id == device_id, Puzzle.evaluation_before >= 0)
    )
    stmt = _phase_filtered(stmt, spec.phase)
    if spec.opening_family:
        like = f"%{spec.opening_family}%"
        stmt = stmt.where(or_(Game.opening.ilike(like), Game.eco_code.ilike(like)))
    stmt = stmt.order_by(Puzzle.cp_loss.desc()).limit(limit)

    with SessionLocal() as session:
        rows = session.execute(stmt).all()
    return [
        {
            "fen": puzzle.fen,
            "color": puzzle.side_to_move,
            "evaluation_before": puzzle.evaluation_before,
            "move_number": puzzle.move_number,
            "game_id": game.id,
        }
        for puzzle, game in rows
    ]


def ensure_drills_for_category(device_id: str, username: str | None, spec: CategorySpec) -> int:
    """Generate (idempotently) the drill set for a category from mined puzzles.

    Returns the number of drills now available for the category. Re-running is a
    no-op for positions that already became drills (unique on device+game+fen).
    """
    candidates = _matching_puzzles(device_id, spec, DRILLS_PER_CATEGORY)
    rows = []
    for cand in candidates:
        drill = drill_from_puzzle(cand, spec.name)
        if drill is None:
            continue
        rows.append(
            {
                "device_id": device_id,
                "username": username,
                "source_game_id": cand["game_id"],
                "fen": drill["fen"],
                "user_color": drill["user_color"],
                "start_eval_cp": drill["start_eval_cp"],
                "objective": drill["objective"],
                "category": drill["category"],
                "phase": drill["phase"],
            }
        )

    if rows:
        with SessionLocal() as session:
            stmt = pg_insert(Drill).values(rows).on_conflict_do_nothing(
                constraint="uq_drills_device_game_fen"
            )
            session.execute(stmt)
            session.commit()

    return count_drills(device_id, spec.name)


def count_drills(device_id: str, category: str) -> int:
    with SessionLocal() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(Drill)
                .where(Drill.device_id == device_id, Drill.category == category)
            ).scalar_one()
        )


def get_category_progress(device_id: str, category: str) -> dict[str, Any]:
    """Drills total/passed and the next unsolved drill id for a category."""
    passed_subq = (
        select(DrillAttempt.drill_id)
        .where(DrillAttempt.verdict == "pass")
        .distinct()
        .subquery()
    )
    with SessionLocal() as session:
        total = int(
            session.execute(
                select(func.count())
                .select_from(Drill)
                .where(Drill.device_id == device_id, Drill.category == category)
            ).scalar_one()
        )
        passed = int(
            session.execute(
                select(func.count(func.distinct(Drill.id)))
                .select_from(Drill)
                .join(passed_subq, passed_subq.c.drill_id == Drill.id)
                .where(Drill.device_id == device_id, Drill.category == category)
            ).scalar_one()
        )
        next_id = session.execute(
            select(Drill.id)
            .where(
                Drill.device_id == device_id,
                Drill.category == category,
                Drill.id.notin_(select(passed_subq.c.drill_id)),
            )
            .order_by(Drill.id)
            .limit(1)
        ).scalar_one_or_none()

    mastery_pct = round(min(100.0, (passed / MASTERY_TARGET) * 100), 1) if MASTERY_TARGET else 0.0
    return {
        "drills_total": total,
        "drills_passed": passed,
        "mastery_pct": mastery_pct,
        "mastered": passed >= MASTERY_TARGET,
        "next_drill_id": next_id,
    }


def get_drill(device_id: str, drill_id: int) -> dict[str, Any] | None:
    with SessionLocal() as session:
        drill = session.execute(
            select(Drill).where(Drill.id == drill_id, Drill.device_id == device_id)
        ).scalar_one_or_none()
        if drill is None:
            return None
        return _serialize(drill)


def _serialize(drill: Drill) -> dict[str, Any]:
    return {
        "id": drill.id,
        "category": drill.category,
        "fen": drill.fen,
        "user_color": drill.user_color,
        "start_eval_cp": drill.start_eval_cp,
        "objective": drill.objective,
        "phase": drill.phase,
        "source_game_id": drill.source_game_id,
        # max_user_moves is added by the router from the service constant.
    }


def get_recent_attempts(device_id: str, since: datetime) -> list[dict[str, Any]]:
    """Graded play-out attempts on or after ``since``, with each drill's phase.

    Powers the training-activity trend on the progress dashboard. Returns raw
    rows; the windowing/headline logic is the pure code in
    :func:`backend.services.progress.summarize_training_activity`.
    """
    with SessionLocal() as session:
        rows = session.execute(
            select(
                DrillAttempt.verdict,
                DrillAttempt.played_at,
                DrillAttempt.swing_cp,
                Drill.phase,
                Drill.category,
            )
            .join(Drill, DrillAttempt.drill_id == Drill.id)
            .where(DrillAttempt.device_id == device_id, DrillAttempt.played_at >= since)
        ).all()
    return [
        {
            "verdict": verdict,
            "played_at": played_at,
            "swing_cp": swing_cp,
            "phase": phase,
            "category": category,
        }
        for verdict, played_at, swing_cp, phase, category in rows
    ]


def record_attempt(
    device_id: str,
    drill_id: int,
    *,
    verdict: str,
    final_eval_cp: int | None,
    swing_cp: int | None,
) -> None:
    with SessionLocal() as session:
        session.add(
            DrillAttempt(
                drill_id=drill_id,
                device_id=device_id,
                verdict=verdict,
                final_eval_cp=final_eval_cp,
                swing_cp=swing_cp,
            )
        )
        session.commit()
