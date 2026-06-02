"""
services/board_renderer.py
Renders chess board positions as SVG using python-chess.
"""

import chess
import chess.svg
from typing import Optional


# Classification → square highlight colour (semi-transparent)
HIGHLIGHT_COLORS = {
    "Excellent":  "#4ade8044",
    "Inaccuracy": "#facc1566",
    "Mistake":    "#f9731666",
    "Blunder":    "#ef444466",
}


def render_board_svg(
    fen: str,
    last_move_uci: Optional[str] = None,
    best_move_uci: Optional[str] = None,
    classification: Optional[str] = None,
    flipped: bool = False,
    size: int = 420,
) -> str:
    """
    Render a chess board as an SVG string.

    Args:
        fen:              FEN string of the position.
        last_move_uci:    UCI string of the move played (highlighted in blue).
        best_move_uci:    UCI string of the best move (highlighted in green).
        classification:   Move classification for square highlighting.
        flipped:          Show board from Black's POV.
        size:             SVG pixel size.

    Returns:
        SVG string.
    """
    board = chess.Board(fen)

    arrows = []
    fill = {}

    if last_move_uci:
        try:
            move = chess.Move.from_uci(last_move_uci)
            arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color="#3b82f6cc"))
            if classification and classification in HIGHLIGHT_COLORS:
                fill[move.to_square] = HIGHLIGHT_COLORS[classification]
        except Exception:
            pass

    if best_move_uci and best_move_uci != last_move_uci:
        try:
            best = chess.Move.from_uci(best_move_uci)
            arrows.append(chess.svg.Arrow(best.from_square, best.to_square, color="#22c55eaa"))
        except Exception:
            pass

    svg = chess.svg.board(
        board,
        arrows=arrows,
        fill=fill,
        flipped=flipped,
        size=size,
        style="""
            .square.light { fill: #f0d9b5; }
            .square.dark  { fill: #b58863; }
        """,
    )
    return svg


def fen_to_last_move_uci(board_before_fen: str, san: str) -> Optional[str]:
    """Convert a SAN move to UCI given the FEN of the position before the move."""
    try:
        board = chess.Board(board_before_fen)
        move = board.parse_san(san)
        return move.uci()
    except Exception:
        return None


def san_to_uci(fen: str, san: str) -> Optional[str]:
    """Convert SAN to UCI for a given FEN."""
    try:
        board = chess.Board(fen)
        move = board.parse_san(san)
        return move.uci()
    except Exception:
        return None
