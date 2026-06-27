"""Shared API plumbing: error codes, the ApiError exception, and the response
envelope (Phase 7)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Error codes
# --------------------------------------------------------------------------- #
class ErrorCode:
    PLAYER_NOT_FOUND = "PLAYER_NOT_FOUND"
    PROFILE_NOT_READY = "PROFILE_NOT_READY"
    INSUFFICIENT_GAMES = "INSUFFICIENT_GAMES"
    INVALID_FEN = "INVALID_FEN"
    INVALID_PGN = "INVALID_PGN"
    JOB_IN_PROGRESS = "JOB_IN_PROGRESS"
    STOCKFISH_ERROR = "STOCKFISH_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_FOUND = "NOT_FOUND"
    CHESSCOM_ERROR = "CHESSCOM_ERROR"


# HTTP status per code (client errors 400, Stockfish 503, auth 401, ...).
_STATUS = {
    ErrorCode.PLAYER_NOT_FOUND: 404,
    ErrorCode.PROFILE_NOT_READY: 400,
    ErrorCode.INSUFFICIENT_GAMES: 400,
    ErrorCode.INVALID_FEN: 400,
    ErrorCode.INVALID_PGN: 400,
    ErrorCode.JOB_IN_PROGRESS: 409,
    ErrorCode.STOCKFISH_ERROR: 503,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CHESSCOM_ERROR: 502,
}

# Minimum games before a profile is considered usable.
MIN_GAMES_FOR_PROFILE = 10


class ApiError(Exception):
    """Raised by route handlers; converted to an enveloped JSON error response."""

    def __init__(self, code: str, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code or _STATUS.get(code, 400)


# --------------------------------------------------------------------------- #
# Response envelope
# --------------------------------------------------------------------------- #
def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def build_meta(
    computed_at: Optional[datetime] = None,
    model_version: Optional[int] = None,
    game_count: Optional[int] = None,
) -> dict:
    return {
        "computed_at": _iso(computed_at),
        "model_version": model_version,
        "game_count": game_count,
    }


def success_envelope(data: Any, meta: Optional[dict] = None) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": meta or build_meta(),
    }


def error_envelope(code: str, message: str, meta: Optional[dict] = None) -> dict:
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message},
        "meta": meta or build_meta(),
    }
