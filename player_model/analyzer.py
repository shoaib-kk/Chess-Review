"""Stockfish analysis of a single position.

One engine instance is shared per worker process (see ``engine.py``). For each
position we request the top-N candidate moves at the configured depth, score the
move actually played, derive centipawn loss and classify the move.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chess
import chess.engine

from . import config

logger = logging.getLogger(__name__)


def find_stockfish() -> str:
    """Locate the Stockfish binary (env var, PATH, or a local ./stockfish dir)."""
    project_dir = Path(__file__).resolve().parents[1]
    local_candidates = sorted((project_dir / "stockfish").glob("stockfish*"))
    candidates = [
        config.STOCKFISH_PATH,
        *[str(p) for p in local_candidates],
        shutil.which("stockfish"),
        shutil.which("stockfish.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError(
        "Stockfish not found. Set STOCKFISH_PATH or place the binary on PATH."
    )


@dataclass
class CandidateMove:
    uci: str
    eval_cp: int  # centipawns, mover's POV


@dataclass
class PositionAnalysis:
    fen: str
    move_played: str  # UCI
    best_move: Optional[str]  # UCI
    eval_before: Optional[int]  # best eval at this position, mover POV
    eval_after: Optional[int]  # eval after the played move, mover POV
    cpl: Optional[int]  # centipawn loss, >= 0
    is_mistake: bool
    is_blunder: bool
    is_brilliant: bool
    depth_used: int
    candidates: list[CandidateMove]


# Rough material values for the brilliant/sacrifice heuristic.
_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 320,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _score_to_cp(score: chess.engine.PovScore, pov: chess.Color) -> int:
    """Convert a PovScore to an integer centipawn value from ``pov``'s side."""
    cp = score.pov(pov).score(mate_score=config.MATE_SCORE_CP)
    return int(cp) if cp is not None else 0


def _is_sacrifice(board: chess.Board, move: chess.Move) -> bool:
    """Heuristic: did the move give up material the opponent can immediately win?

    Not a full static-exchange evaluator — good enough to flag the eye-catching
    "Brilliant" sacrifices for the raw store. We compare the value placed en prise
    against what (if anything) was captured, and require the opponent to have a
    capturing move that nets material.
    """
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return False
    captured = board.piece_at(move.to_square)
    captured_value = _PIECE_VALUES.get(captured.piece_type, 0) if captured else 0

    after = board.copy(stack=False)
    after.push(move)

    # Cheapest opponent attacker of the square we just moved to.
    attackers = after.attackers(after.turn, move.to_square)
    if not attackers:
        return False
    moved_value = _PIECE_VALUES.get(moving_piece.piece_type, 0)
    # We are defended if friendly pieces also guard the square; a true sac still
    # nets the opponent material even after the recapture.
    defenders = after.attackers(not after.turn, move.to_square)
    net_for_opponent = moved_value - captured_value
    if defenders:
        # Opponent takes, we recapture: they gain our piece, lose their attacker.
        cheapest_attacker = min(
            _PIECE_VALUES.get(after.piece_at(sq).piece_type, 0) for sq in attackers
        )
        net_for_opponent = moved_value - captured_value - cheapest_attacker
    return net_for_opponent >= 200  # gave up ~2+ pawns of material


def _classify(cpl: int, *, is_best: bool, sacrifice: bool, eval_before: int) -> tuple[
    bool, bool, bool
]:
    """Return (is_mistake, is_blunder, is_brilliant) from centipawn loss."""
    is_blunder = cpl > config.BLUNDER_CPL
    is_mistake = (not is_blunder) and cpl > config.MISTAKE_CPL
    # Brilliant: engine's top move, a real material sacrifice, position not losing.
    is_brilliant = is_best and sacrifice and eval_before >= -50
    return is_mistake, is_blunder, is_brilliant


def analyse_position(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    move_played: chess.Move,
    *,
    depth: Optional[int] = None,
    multipv: Optional[int] = None,
) -> PositionAnalysis:
    """Analyse one position and score ``move_played``.

    All evaluations are integer centipawns from the mover's point of view, so a
    larger ``eval_before`` is always better for the side to move and CPL is a
    simple ``eval_before - eval_after`` (clamped at 0).
    """
    depth = depth or config.STOCKFISH_DEPTH
    multipv = multipv or config.STOCKFISH_MULTIPV
    mover = board.turn

    infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    if isinstance(infos, dict):  # multipv=1 returns a single dict
        infos = [infos]

    candidates: list[CandidateMove] = []
    eval_by_move: dict[str, int] = {}
    for info in infos:
        pv = info.get("pv")
        if not pv:
            continue
        uci = pv[0].uci()
        cp = _score_to_cp(info["score"], mover)
        candidates.append(CandidateMove(uci=uci, eval_cp=cp))
        eval_by_move[uci] = cp

    best_move = candidates[0].uci if candidates else None
    eval_before = candidates[0].eval_cp if candidates else None

    played_uci = move_played.uci()
    if played_uci in eval_by_move:
        eval_after = eval_by_move[played_uci]
    else:
        # Played move wasn't in the top-N: evaluate the resulting position once.
        after = board.copy(stack=False)
        after.push(move_played)
        info = engine.analyse(after, chess.engine.Limit(depth=depth))
        # After the push it's the opponent to move; flip back to the mover's POV.
        eval_after = _score_to_cp(info["score"], mover)

    if eval_before is None or eval_after is None:
        cpl = None
        flags = (False, False, False)
    else:
        cpl = max(0, eval_before - eval_after)
        is_best = played_uci == best_move
        sacrifice = is_best and _is_sacrifice(board, move_played)
        flags = _classify(cpl, is_best=is_best, sacrifice=sacrifice, eval_before=eval_before)

    return PositionAnalysis(
        fen=board.fen(),
        move_played=played_uci,
        best_move=best_move,
        eval_before=eval_before,
        eval_after=eval_after,
        cpl=cpl,
        is_mistake=flags[0],
        is_blunder=flags[1],
        is_brilliant=flags[2],
        depth_used=depth,
        candidates=candidates,
    )
