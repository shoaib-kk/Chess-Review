from __future__ import annotations

import logging
import sys
from pathlib import Path

import chess
from fastapi import APIRouter, Depends, HTTPException

from ..auth import current_device
from ..schemas import EngineMoveRequest, EngineMoveResponse
from ..services.rate_limit import play_rate_limiter

# The Stockfish wrapper lives at the project root, not inside the backend
# package. Make sure it is importable regardless of how uvicorn is launched.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stockfish_engine import EngineUnavailableError, StockfishEngine  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/play", tags=["play"])


# This endpoint is stateless (it computes an engine reply for a FEN and stores
# nothing per device), so current_device here doesn't scope data — it just gates
# /play behind the same valid-X-Device-Id wall every sibling router enforces, for
# consistency and so the limiter/identity surface is uniform across the API.
@router.post(
    "/move",
    response_model=EngineMoveResponse,
    dependencies=[Depends(current_device), Depends(play_rate_limiter)],
)
def engine_move(request: EngineMoveRequest) -> EngineMoveResponse:
    """Return Stockfish's reply for a given position, for 'play out the position'."""
    try:
        board = chess.Board(request.fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid FEN.") from exc

    if board.is_game_over():
        return EngineMoveResponse(
            best_move_san=None,
            best_move_uci=None,
            fen=board.fen(),
            is_game_over=True,
            is_check=board.is_check(),
            eval_cp=None,
        )

    try:
        # The pool reuses a warm engine per checkout, so a play-out's many single-move
        # requests no longer pay the per-move spawn + NNUE-load cost. The Skill Level cap
        # set here is reset when the engine is returned, so it can't leak into analysis.
        with StockfishEngine(depth=request.depth) as engine:
            if request.skill_level is not None:
                engine.configure({"Skill Level": request.skill_level})
            eval_cp, best_move_san, _pv = engine.analyse_position(
                board, depth=request.depth, include_pv=True, pv_limit=1
            )
    except EngineUnavailableError as exc:  # engine missing / crashed / timed out
        logger.exception("Engine move failed")
        raise HTTPException(status_code=503, detail="Engine temporarily unavailable.") from exc
    except Exception as exc:  # unexpected engine fault — still a 503 to the client
        logger.exception("Engine move failed")
        raise HTTPException(status_code=503, detail="Engine temporarily unavailable.") from exc

    if not best_move_san:
        raise HTTPException(status_code=500, detail="Engine returned no move.")

    move = board.parse_san(best_move_san)
    best_move_uci = move.uci()
    board.push(move)

    return EngineMoveResponse(
        best_move_san=best_move_san,
        best_move_uci=best_move_uci,
        fen=board.fen(),
        is_game_over=board.is_game_over(),
        is_check=board.is_check(),
        eval_cp=eval_cp,
    )
