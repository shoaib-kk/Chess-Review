"""Fixed-length position feature encoding (Phase 5).

``encode_position(fen)`` turns a FEN into a 68-dim float32 vector using only
python-chess. The vector is homogeneous across the index and the query: every
component (including the evaluation context) is derived deterministically from the
FEN, so an L2 distance between two encodings is meaningful regardless of where the
position came from.

Layout (68 = 12 + 16 + 4 + 4 + 4 + 8 + 4 + 16):
  material(12) | pawn_structure(16) | king_safety(4) | mobility(4) |
  eval_context(4) | control(8) | castling_structure(4) | threats(16)
"""

from __future__ import annotations

from typing import Optional

import chess
import numpy as np

VECTOR_DIM = 68

_PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}
# Normalisation denominators for the 6 piece-type counts per colour.
_COUNT_DENOM = {
    chess.PAWN: 8,
    chess.KNIGHT: 2,
    chess.BISHOP: 2,
    chess.ROOK: 2,
    chess.QUEEN: 2,
    chess.KING: 1,
}
_PIECE_ORDER = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]
_MAX_SIDE_VALUE = 39.0  # 8 pawns + 2N + 2B + 2R + Q


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# --------------------------------------------------------------------------- #
# Segment builders
# --------------------------------------------------------------------------- #
def _material(board: chess.Board) -> list[float]:
    out = []
    for color in (chess.WHITE, chess.BLACK):
        for pt in _PIECE_ORDER:
            count = len(board.pieces(pt, color))
            out.append(_clamp01(count / _COUNT_DENOM[pt]))
    return out  # 12


def _pawn_structure(board: chess.Board) -> list[float]:
    wp = [0] * 8
    bp = [0] * 8
    for sq in board.pieces(chess.PAWN, chess.WHITE):
        wp[chess.square_file(sq)] += 1
    for sq in board.pieces(chess.PAWN, chess.BLACK):
        bp[chess.square_file(sq)] += 1
    out = []
    for f in range(8):
        out.append(_clamp01(wp[f] / 2))
        out.append(_clamp01(bp[f] / 2))
    return out  # 16


def _king_safety(board: chess.Board) -> list[float]:
    out = []
    for color in (chess.WHITE, chess.BLACK):
        ksq = board.king(color)
        if ksq is None:
            out.extend([0.0, 0.0])
        else:
            out.append(chess.square_file(ksq) / 7)
            out.append(chess.square_rank(ksq) / 7)
    return out  # 4


def _mobility(board: chess.Board) -> list[float]:
    def side_mobility(color: chess.Color) -> int:
        # Pseudo-legal count: a fast mobility proxy (skips the costly pin/check
        # filtering of full legality, which is unnecessary for a feature value).
        original = board.turn
        board.turn = color
        try:
            return board.pseudo_legal_moves.count()
        finally:
            board.turn = original

    def queen_mobility(color: chess.Color) -> int:
        return sum(len(board.attacks(sq)) for sq in board.pieces(chess.QUEEN, color))

    return [
        _clamp01(side_mobility(chess.WHITE) / 40),
        _clamp01(side_mobility(chess.BLACK) / 40),
        _clamp01(queen_mobility(chess.WHITE) / 27),
        _clamp01(queen_mobility(chess.BLACK) / 27),
    ]  # 4


def _static_eval_cp(board: chess.Board) -> int:
    """Material-only evaluation in centipawns, White's perspective."""
    white = sum(_PIECE_VALUE[p.piece_type] for p in board.piece_map().values() if p.color)
    black = sum(
        _PIECE_VALUE[p.piece_type] for p in board.piece_map().values() if not p.color
    )
    return (white - black) * 100


def _game_phase(board: chess.Board) -> float:
    total = sum(_PIECE_VALUE[p.piece_type] for p in board.piece_map().values())
    if total > 60:
        return 0.0
    if total < 24:
        return 1.0
    return 0.5


def _eval_context(board: chess.Board, eval_cp: Optional[int], ply: Optional[int]) -> list[float]:
    if eval_cp is None:
        eval_cp = _static_eval_cp(board)
    if ply is None:
        ply = (board.fullmove_number - 1) * 2 + (1 if board.turn == chess.BLACK else 0)

    eval_norm = max(-1.0, min(1.0, eval_cp / 1000))
    return [
        eval_norm,
        _game_phase(board),
        _clamp01(ply / 100),
        1.0 if board.turn == chess.WHITE else 0.0,
    ]  # 4


def _controlled_squares(board: chess.Board, color: chess.Color) -> set[int]:
    # Union of each piece's attack set — ~16 attacks() calls instead of 64
    # attackers() probes, and equivalent for "is this square controlled?".
    controlled: set[int] = set()
    for pt in _PIECE_ORDER:
        for sq in board.pieces(pt, color):
            controlled |= set(board.attacks(sq))
    return controlled


def _control(board: chess.Board) -> list[float]:
    out = []
    for color in (chess.WHITE, chess.BLACK):
        controlled = _controlled_squares(board, color)
        centre = sum(1 for sq in controlled if chess.square_rank(sq) in (3, 4))
        opp_ranks = (5, 6, 7) if color == chess.WHITE else (0, 1, 2)
        opp_territory = sum(1 for sq in controlled if chess.square_rank(sq) in opp_ranks)
        own_pawn_files = {
            chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)
        }
        open_files = 8 - len(own_pawn_files)
        out.extend([
            _clamp01(centre / 32),
            _clamp01(opp_territory / 32),
            _clamp01(len(controlled) / 32),
            _clamp01(open_files / 32),
        ])
    return out  # 8


def _castling_structure(board: chess.Board) -> list[float]:
    def has_castled(color: chess.Color) -> float:
        ksq = board.king(color)
        if ksq is None:
            return 0.0
        home = 0 if color == chess.WHITE else 7
        return 1.0 if (chess.square_file(ksq) in (2, 6) and chess.square_rank(ksq) == home) else 0.0

    def doubled(color: chess.Color) -> float:
        files = [chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)]
        return 1.0 if any(files.count(f) >= 2 for f in set(files)) else 0.0

    return [
        has_castled(chess.WHITE),
        has_castled(chess.BLACK),
        doubled(chess.WHITE),
        doubled(chess.BLACK),
    ]  # 4


def _threats(board: chess.Board) -> list[float]:
    out = []
    for color in (chess.WHITE, chess.BLACK):
        enemy = not color
        attacked, hanging = [], []
        attacker_squares: set[int] = set()
        defended = 0
        for sq, piece in board.piece_map().items():
            if piece.color != color or piece.piece_type == chess.KING:
                continue
            enemy_attackers = board.attackers(enemy, sq)
            if enemy_attackers:
                attacked.append(sq)
                attacker_squares |= set(enemy_attackers)
                if not board.attackers(color, sq):
                    hanging.append(sq)
                else:
                    defended += 1
        attacked_val = sum(_PIECE_VALUE[board.piece_at(sq).piece_type] for sq in attacked)
        hanging_val = sum(_PIECE_VALUE[board.piece_at(sq).piece_type] for sq in hanging)
        max_hanging = max(
            (_PIECE_VALUE[board.piece_at(sq).piece_type] for sq in hanging), default=0
        )
        out.extend([
            _clamp01(len(attacked) / 16),
            _clamp01(len(hanging) / 16),
            _clamp01(attacked_val / _MAX_SIDE_VALUE),
            _clamp01(hanging_val / _MAX_SIDE_VALUE),
            _clamp01(defended / 16),
            _clamp01(len(attacker_squares) / 16),
            _clamp01(max_hanging / 9),
            1.0 if board.is_check() and board.turn == color else 0.0,
        ])
    return out  # 16


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def encode_position(
    fen: str, eval_cp: Optional[int] = None, ply: Optional[int] = None
) -> np.ndarray:
    """Encode a FEN into a (68,) float32 feature vector.

    ``eval_cp`` / ``ply`` default to values derived from the FEN so the encoding is
    consistent between the stored index and ad-hoc queries; pass them only when you
    deliberately want engine-accurate context in both places.
    """
    board = chess.Board(fen)
    vec: list[float] = []
    vec += _material(board)
    vec += _pawn_structure(board)
    vec += _king_safety(board)
    vec += _mobility(board)
    vec += _eval_context(board, eval_cp, ply)
    vec += _control(board)
    vec += _castling_structure(board)
    vec += _threats(board)

    assert len(vec) == VECTOR_DIM, f"expected {VECTOR_DIM} dims, got {len(vec)}"
    return np.asarray(vec, dtype=np.float32)
