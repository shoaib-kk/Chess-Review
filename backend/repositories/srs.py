"""Persistence for the daily-puzzle SRS queue and the per-device streak.

All SQL for the daily/SRS subsystem lives here. Scheduling arithmetic (the
interval ladder, streak transitions) is the pure code in
:mod:`backend.services.daily`; this module only reads and writes rows.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db import SessionLocal
from ..db_models import Game, Puzzle, SrsCard, Streak

logger = logging.getLogger(__name__)


def _serialize_puzzle(puzzle: Puzzle, game: Game) -> dict[str, Any]:
    """Same JSON shape the puzzles router returns, so the frontend reuses its type."""
    return {
        "id": puzzle.id,
        "game_url": game.game_url,
        "game_date": game.game_date,
        "move_number": puzzle.move_number,
        "color": puzzle.side_to_move,
        "fen": puzzle.fen,
        "played_move": puzzle.played_move,
        "best_move": puzzle.best_move,
        "best_move_uci": puzzle.best_move_uci,
        "pv": puzzle.continuation or [],
        "cp_loss": puzzle.cp_loss,
        "classification": puzzle.classification,
        "solved": puzzle.solved,
    }


def get_daily_puzzles(device_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Today's set: the device's worst unsolved mistakes (falls back to any)."""
    base = (
        select(Puzzle, Game)
        .join(Game, Puzzle.game_id == Game.id)
        .where(Game.owner_id == device_id, Puzzle.evaluation_before >= 0)
    )
    with SessionLocal() as session:
        rows = session.execute(
            base.where(Puzzle.solved.is_(False)).order_by(Puzzle.cp_loss.desc()).limit(limit)
        ).all()
        if len(rows) < limit:
            extra = session.execute(
                base.order_by(Puzzle.cp_loss.desc()).limit(limit)
            ).all()
            seen = {p.id for p, _ in rows}
            for p, g in extra:
                if p.id not in seen and len(rows) < limit:
                    rows.append((p, g))
                    seen.add(p.id)
    return [_serialize_puzzle(p, g) for p, g in rows]


def get_due_cards(device_id: str, today: date) -> list[dict[str, Any]]:
    """SRS cards due on or before ``today``, oldest-due first, with their puzzle."""
    with SessionLocal() as session:
        rows = session.execute(
            select(SrsCard, Puzzle, Game)
            .join(Puzzle, SrsCard.puzzle_id == Puzzle.id)
            .join(Game, Puzzle.game_id == Game.id)
            .where(SrsCard.device_id == device_id, SrsCard.due_date <= today)
            .order_by(SrsCard.due_date)
        ).all()
    out = []
    for card, puzzle, game in rows:
        payload = _serialize_puzzle(puzzle, game)
        payload["srs"] = {
            "interval_stage": card.interval_stage,
            "due_date": card.due_date.isoformat(),
            "last_result": card.last_result,
        }
        out.append(payload)
    return out


def count_due_cards(device_id: str, today: date) -> int:
    with SessionLocal() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(SrsCard)
                .where(SrsCard.device_id == device_id, SrsCard.due_date <= today)
            ).scalar_one()
        )


def upsert_card(
    device_id: str,
    username: str | None,
    puzzle_id: int,
    *,
    interval_stage: int,
    due_date: date,
    last_result: str,
) -> None:
    """Insert or update a device's SRS card for a puzzle (unique device+puzzle)."""
    with SessionLocal() as session:
        stmt = (
            pg_insert(SrsCard)
            .values(
                device_id=device_id,
                username=username,
                puzzle_id=puzzle_id,
                interval_stage=interval_stage,
                due_date=due_date,
                last_result=last_result,
            )
            .on_conflict_do_update(
                constraint="uq_srs_device_puzzle",
                set_={
                    "interval_stage": interval_stage,
                    "due_date": due_date,
                    "last_result": last_result,
                    "updated_at": func.now(),
                },
            )
        )
        session.execute(stmt)
        session.commit()


def get_card_stage(device_id: str, puzzle_id: int) -> int | None:
    with SessionLocal() as session:
        return session.execute(
            select(SrsCard.interval_stage).where(
                SrsCard.device_id == device_id, SrsCard.puzzle_id == puzzle_id
            )
        ).scalar_one_or_none()


# ── streak ──────────────────────────────────────────────────────────────────

def get_streak(device_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        row = session.execute(
            select(Streak).where(Streak.device_id == device_id)
        ).scalar_one_or_none()
    if row is None:
        return {"current_streak": 0, "longest_streak": 0, "last_completed_date": None}
    return {
        "current_streak": row.current_streak,
        "longest_streak": row.longest_streak,
        "last_completed_date": row.last_completed_date.isoformat() if row.last_completed_date else None,
    }


def save_streak(
    device_id: str,
    *,
    current_streak: int,
    longest_streak: int,
    last_completed_date: date,
) -> None:
    with SessionLocal() as session:
        stmt = (
            pg_insert(Streak)
            .values(
                device_id=device_id,
                current_streak=current_streak,
                longest_streak=longest_streak,
                last_completed_date=last_completed_date,
            )
            .on_conflict_do_update(
                index_elements=[Streak.device_id],
                set_={
                    "current_streak": current_streak,
                    "longest_streak": longest_streak,
                    "last_completed_date": last_completed_date,
                    "updated_at": func.now(),
                },
            )
        )
        session.execute(stmt)
        session.commit()
