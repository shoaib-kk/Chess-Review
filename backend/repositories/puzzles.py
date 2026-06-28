"""Persistence helpers for generated puzzles (PostgreSQL-backed).

Replaces the old SQLite ``services/puzzle_store.py``. Puzzles are scoped to a
user through their parent ``games`` row (``games.username``); deleting a game
cascades to its puzzles. The JSON shape returned by :func:`get_puzzles` is kept
identical to the previous implementation so the frontend needs no changes.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..db_models import Game, Puzzle
from .games import get_or_create_game

logger = logging.getLogger(__name__)

# Phase is derived from the full-move number on the board (not stored):
#   Opening    = move_number <= 12
#   Middlegame = 13..30
#   Endgame    = > 30
_PHASE_RANGES: dict[str, tuple[int | None, int | None]] = {
    "opening": (None, 12),
    "middlegame": (13, 30),
    "endgame": (31, None),
}

# Difficulty filter maps onto the stored `classification` column.
_DIFFICULTY_CLASSIFICATION: dict[str, str] = {
    "blunders": "Blunder",
    "mistakes": "Mistake",
}


# ── read helpers used by the puzzles router / progress ──────────────────────

def get_analyzed_urls(owner_id: str) -> set[str]:
    """URLs of games already mined for this device (so they aren't re-analysed)."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Game.game_url).where(
                Game.owner_id == owner_id,
                Game.mined.is_(True),
                Game.game_url.is_not(None),
            )
        ).all()
    return {row[0] for row in rows if row[0]}


def get_analyzed_count(owner_id: str) -> int:
    with SessionLocal() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(Game)
                .where(Game.owner_id == owner_id, Game.mined.is_(True))
            ).scalar_one()
        )


def get_puzzle_count(owner_id: str) -> int:
    with SessionLocal() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(Puzzle)
                .join(Game, Puzzle.game_id == Game.id)
                .where(Game.owner_id == owner_id, Puzzle.evaluation_before >= 0)
            ).scalar_one()
        )


def get_phase_counts(owner_id: str) -> dict[str, int]:
    """Count available puzzles per phase (for the lobby), ignoring difficulty."""
    counts = {"all": 0, "opening": 0, "middlegame": 0, "endgame": 0}
    with SessionLocal() as session:
        rows = session.execute(
            select(Puzzle.move_number)
            .join(Game, Puzzle.game_id == Game.id)
            .where(Game.owner_id == owner_id, Puzzle.evaluation_before >= 0)
        ).all()
    for (move_number,) in rows:
        move_number = move_number or 0
        counts["all"] += 1
        if move_number <= 12:
            counts["opening"] += 1
        elif move_number <= 30:
            counts["middlegame"] += 1
        else:
            counts["endgame"] += 1
    return counts


def _apply_phase(stmt, phase: str | None):
    if not phase:
        return stmt
    bounds = _PHASE_RANGES.get(phase.strip().lower())
    if not bounds:
        return stmt
    low, high = bounds
    if low is not None:
        stmt = stmt.where(Puzzle.move_number >= low)
    if high is not None:
        stmt = stmt.where(Puzzle.move_number <= high)
    return stmt


def _apply_difficulty(stmt, difficulty: str | None):
    if not difficulty:
        return stmt
    cls = _DIFFICULTY_CLASSIFICATION.get(difficulty.strip().lower())
    if not cls:
        return stmt
    return stmt.where(Puzzle.classification == cls)


def _serialize(puzzle: Puzzle, game: Game) -> dict[str, Any]:
    """Map ORM rows back to the JSON shape the frontend `Puzzle` type expects."""
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


def get_puzzles(
    owner_id: str,
    limit: int = 100,
    offset: int = 0,
    phase: str | None = None,
    difficulty: str | None = None,
) -> list[dict]:
    stmt = (
        select(Puzzle, Game)
        .join(Game, Puzzle.game_id == Game.id)
        .where(Game.owner_id == owner_id, Puzzle.evaluation_before >= 0)
    )
    stmt = _apply_phase(stmt, phase)
    stmt = _apply_difficulty(stmt, difficulty)
    stmt = stmt.order_by(Puzzle.cp_loss.desc()).limit(limit).offset(offset)
    with SessionLocal() as session:
        rows = session.execute(stmt).all()
    return [_serialize(puzzle, game) for puzzle, game in rows]


def mark_solved(owner_id: str, puzzle_id: int) -> None:
    with SessionLocal() as session:
        puzzle = session.execute(
            select(Puzzle)
            .join(Game, Puzzle.game_id == Game.id)
            .where(Puzzle.id == puzzle_id, Game.owner_id == owner_id)
        ).scalar_one_or_none()
        if puzzle is not None:
            puzzle.solved = True
            session.commit()


# ── write path used by the background puzzle miner ──────────────────────────

def save_mined_puzzles(
    *,
    owner_id: str,
    username: str,
    game_url: str,
    game_date: str,
    pgn: str,
    summary: Any,
    analysis_json: dict | None,
    puzzles: list[dict],
    depth: int | None = None,
    mode: str | None = None,
) -> None:
    """Persist a mined game and its puzzles in one transaction (idempotent).

    Creates (or reuses) the parent ``games`` row owned by ``owner_id`` (the
    device), marks it ``mined`` — so even a game that yields zero puzzles is not
    re-analysed — and bulk-inserts puzzles, skipping any that already exist for
    the game (unique ``game_id, move_number``). ``username`` is the Chess.com
    player identity stored for color/display.
    """
    session: Session = SessionLocal()
    try:
        game = get_or_create_game(
            session,
            owner_id=owner_id,
            username=username,
            game_url=game_url or None,
            game_date=game_date,
            pgn=pgn,
            summary=summary,
            analysis_json=analysis_json,
            source="mine",
            depth=depth,
            mode=mode,
        )
        game.mined = True
        session.flush()

        if puzzles:
            rows = [
                {
                    "game_id": game.id,
                    "fen": p["fen"],
                    "move_number": p.get("move_number"),
                    "side_to_move": p.get("color"),
                    "best_move": p["best_move"],
                    "best_move_uci": p.get("best_move_uci"),
                    "played_move": p.get("played_move"),
                    "continuation": p.get("pv") or [],
                    "evaluation_before": p.get("eval_before"),
                    "evaluation_after": p.get("eval_after"),
                    "cp_loss": p.get("cp_loss"),
                    "classification": p.get("classification"),
                }
                for p in puzzles
            ]
            stmt = pg_insert(Puzzle).values(rows).on_conflict_do_nothing(
                constraint="uq_puzzles_game_move"
            )
            session.execute(stmt)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
