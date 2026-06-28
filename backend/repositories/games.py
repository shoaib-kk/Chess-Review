"""Persistence helpers for analysed games.

All SQL lives here (and in ``puzzles.py``) rather than in route handlers. A
``Game`` row is created the first time a game is reviewed interactively or mined
for puzzles; repeat reviews/mines of the same game are idempotent.
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

import chess.pgn
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..db_models import Game, ImportCursor

logger = logging.getLogger(__name__)


def pgn_hash(pgn: str) -> str:
    """Stable content hash used to dedup pasted PGNs (whitespace-normalised)."""
    normalized = " ".join(pgn.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_headers(pgn: str) -> dict[str, str]:
    """Pull the header tags (Elo/Site/Event/…) straight from the PGN text."""
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is not None:
            return dict(game.headers)
    except Exception:  # pragma: no cover - defensive: never block persistence
        logger.debug("Could not parse PGN headers for game persistence", exc_info=True)
    return {}


def _metrics_from_summary(summary: Any, analysis_json: dict[str, Any] | None) -> dict[str, Any]:
    """Derive the denormalised accuracy/error counters stored on the game row."""
    total_blunders = (getattr(summary, "white_blunders", 0) or 0) + (getattr(summary, "black_blunders", 0) or 0)
    total_mistakes = (getattr(summary, "white_mistakes", 0) or 0) + (getattr(summary, "black_mistakes", 0) or 0)
    total_inaccuracies = (getattr(summary, "white_inaccuracies", 0) or 0) + (getattr(summary, "black_inaccuracies", 0) or 0)

    average_accuracy = None
    if analysis_json:
        # Prefer the reviewing user's accuracy; otherwise average the two sides.
        average_accuracy = analysis_json.get("user_accuracy")
        if average_accuracy is None:
            sides = [analysis_json.get("white_accuracy"), analysis_json.get("black_accuracy")]
            present = [s for s in sides if s is not None]
            if present:
                average_accuracy = round(sum(present) / len(present), 1)

    return {
        "total_blunders": total_blunders,
        "total_mistakes": total_mistakes,
        "total_inaccuracies": total_inaccuracies,
        "average_accuracy": average_accuracy,
    }


def get_or_create_game(
    session: Session,
    *,
    owner_id: str | None,
    username: str | None,
    game_url: str | None,
    game_date: str | None,
    pgn: str,
    summary: Any,
    analysis_json: dict[str, Any] | None,
    source: str,
    depth: int | None = None,
    mode: str | None = None,
) -> Game:
    """Return the existing game row or insert a new one.

    Ownership/dedup is scoped to ``owner_id`` (the device id): the key is
    ``(owner_id, game_url)`` when a chess.com URL is present, otherwise
    ``(owner_id, pgn_hash)`` for pasted PGNs. ``username`` is stored as the
    Chess.com player identity (color/display), not for scoping. The caller is
    responsible for committing the surrounding transaction.
    """
    digest = pgn_hash(pgn)
    norm_owner = owner_id or None
    norm_user = username or None

    if game_url:
        stmt = select(Game).where(Game.owner_id == norm_owner, Game.game_url == game_url)
    else:
        stmt = select(Game).where(Game.owner_id == norm_owner, Game.pgn_hash == digest)
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing

    headers = _parse_headers(pgn)
    metrics = _metrics_from_summary(summary, analysis_json)
    analysis_version = f"{mode}-d{depth}" if mode and depth else None

    game = Game(
        owner_id=norm_owner,
        username=norm_user,
        game_url=game_url,
        pgn_hash=digest,
        source=source,
        mined=False,
        game_date=game_date or (analysis_json or {}).get("date") or headers.get("Date"),
        original_pgn=pgn,
        white_player=getattr(summary, "white_player", "") or headers.get("White", ""),
        black_player=getattr(summary, "black_player", "") or headers.get("Black", ""),
        white_elo=_to_int(headers.get("WhiteElo")),
        black_elo=_to_int(headers.get("BlackElo")),
        event=getattr(summary, "event", None) or headers.get("Event"),
        site=headers.get("Site"),
        result=getattr(summary, "result", None) or headers.get("Result"),
        opening=getattr(summary, "opening_name", None),
        eco_code=getattr(summary, "eco_code", None) or headers.get("ECO"),
        analysis_version=analysis_version,
        analysis_json=analysis_json,
        **metrics,
    )
    session.add(game)
    session.flush()  # assign game.id without ending the transaction
    return game


def save_reviewed_game(
    session: Session,
    *,
    owner_id: str | None,
    username: str | None,
    pgn: str,
    summary: Any,
    analysis_json: dict[str, Any] | None,
    game_url: str | None = None,
    depth: int | None = None,
    mode: str | None = None,
) -> None:
    """Persist an interactively reviewed game (idempotent). Commits on success."""
    game = get_or_create_game(
        session,
        owner_id=owner_id,
        username=username,
        game_url=game_url,
        game_date=(analysis_json or {}).get("date"),
        pgn=pgn,
        summary=summary,
        analysis_json=analysis_json,
        source="review",
        depth=depth,
        mode=mode,
    )
    # Opening a game in review clears it from the "ready to review" inbox.
    game.reviewed = True
    session.commit()


# ── auto-import inbox + Chess.com polling cursor ────────────────────────────

def get_inbox(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Auto-imported games this device has not yet opened in review."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Game)
            .where(
                Game.owner_id == owner_id,
                Game.source == "import",
                Game.reviewed.is_(False),
            )
            .order_by(Game.uploaded_at.desc())
            .limit(limit)
        ).scalars().all()
    return [
        {
            "id": game.id,
            "game_url": game.game_url,
            "game_date": game.game_date,
            "white_player": game.white_player,
            "black_player": game.black_player,
            "result": game.result,
            "opening": game.opening,
            "pgn": game.original_pgn,
        }
        for game in rows
    ]


def count_inbox(owner_id: str) -> int:
    with SessionLocal() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(Game)
                .where(
                    Game.owner_id == owner_id,
                    Game.source == "import",
                    Game.reviewed.is_(False),
                )
            ).scalar_one()
        )


def get_import_cursor(device_id: str, username: str) -> int | None:
    """Last auto-imported game's ``end_time`` for this (device, username)."""
    with SessionLocal() as session:
        return session.execute(
            select(ImportCursor.last_end_time).where(
                ImportCursor.device_id == device_id,
                ImportCursor.username == username,
            )
        ).scalar_one_or_none()


def set_import_cursor(device_id: str, username: str, last_end_time: int) -> None:
    with SessionLocal() as session:
        stmt = (
            pg_insert(ImportCursor)
            .values(device_id=device_id, username=username, last_end_time=last_end_time)
            .on_conflict_do_update(
                constraint="pk_import_cursors",
                set_={"last_end_time": last_end_time, "updated_at": func.now()},
            )
        )
        session.execute(stmt)
        session.commit()


def save_imported_game(
    *,
    owner_id: str,
    username: str,
    game_url: str | None,
    game_date: str | None,
    pgn: str,
) -> None:
    """Persist an auto-imported Chess.com game (not yet analysed/reviewed)."""
    session = SessionLocal()
    try:
        get_or_create_game(
            session,
            owner_id=owner_id,
            username=username,
            game_url=game_url,
            game_date=game_date,
            pgn=pgn,
            summary=None,
            analysis_json=None,
            source="import",
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
