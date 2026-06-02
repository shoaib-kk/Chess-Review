"""
services/game_analyzer.py
Orchestrates PGN parsing → engine evaluation → GameSummary.
"""

import chess
from typing import Optional, Callable

from analysis.models import MoveAnalysis, GameSummary, classify_move
from analysis.pgn_parser import load_game_from_pgn_string, extract_headers, iter_positions
from analysis.stockfish_engine import StockfishEngine


def _cp_loss(eval_before: Optional[float], eval_after: Optional[float]) -> Optional[float]:
    if eval_before is None or eval_after is None:
        return None
    mover_eval_after = -eval_after
    loss = eval_before - mover_eval_after
    return max(0.0, loss)


def analyze_pgn(
    pgn_text: str,
    engine_path: Optional[str] = None,
    depth: int = 16,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> GameSummary:
    """
    Analyse a PGN string and return a GameSummary.

    Args:
        pgn_text:    Raw PGN content.
        engine_path: Optional path to Stockfish binary.
        depth:       Analysis depth.
        progress_cb: Optional callback(current, total, label) for progress reporting.
    """
    game = load_game_from_pgn_string(pgn_text)
    headers = extract_headers(game)

    summary = GameSummary(
        white_player=headers["white"],
        black_player=headers["black"],
        event=headers["event"],
        date=headers["date"],
        result=headers["result"],
        total_moves=0,
        initial_fen=game.board().fen(),
    )

    positions = list(iter_positions(game))
    total = len(positions)

    with StockfishEngine(path=engine_path, depth=depth) as engine:
        for idx, (board_before, move, move_number, color, san) in enumerate(positions, 1):
            if progress_cb:
                label = f"{move_number}{'.' if color == 'White' else '…'}{san}"
                progress_cb(idx, total, label)

            fen_before = board_before.fen()
            eval_before, best_move_san, pv = engine.analyse_position(board_before)

            board_after = board_before.copy()
            board_after.push(move)
            eval_after, _, _ = engine.analyse_position(board_after)

            cp_loss = _cp_loss(eval_before, eval_after)
            classification = classify_move(cp_loss if cp_loss is not None else 0)

            analysis = MoveAnalysis(
                move_number=move_number,
                color=color,
                move_played=san,
                eval_before=eval_before,
                eval_after=eval_after,
                best_move=best_move_san,
                cp_loss=cp_loss,
                classification=classification,
                pv=pv,
                fen_before=fen_before,
            )
            summary.move_analyses.append(analysis)

            if classification.value == "Inaccuracy":
                if color == "White":
                    summary.white_inaccuracies += 1
                else:
                    summary.black_inaccuracies += 1
            elif classification.value == "Mistake":
                if color == "White":
                    summary.white_mistakes += 1
                else:
                    summary.black_mistakes += 1
            elif classification.value == "Blunder":
                if color == "White":
                    summary.white_blunders += 1
                else:
                    summary.black_blunders += 1

    summary.total_moves = len(summary.move_analyses)
    return summary
