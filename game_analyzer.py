"""
services/game_analyzer.py
Orchestrates PGN parsing → engine evaluation → GameSummary.
"""

import chess
from typing import Optional, Callable

from models import MoveAnalysis, GameSummary, classify_move
from pgn_parser import load_game_from_pgn_string, extract_headers, iter_positions
from stockfish_engine import StockfishEngine


ANALYSIS_MODES = {
    "fast": {"max_depth": 8, "pv_limit": 2},
    "normal": {"max_depth": 12, "pv_limit": 5},
    "deep": {"max_depth": 24, "pv_limit": 8},
}


def _cp_loss(eval_before: Optional[float], eval_after: Optional[float]) -> Optional[float]:
    if eval_before is None or eval_after is None:
        return None
    mover_eval_after = -eval_after
    loss = eval_before - mover_eval_after
    return max(0.0, loss)


def _mode_config(mode: str, requested_depth: int) -> dict:
    config = ANALYSIS_MODES.get(mode, ANALYSIS_MODES["normal"])
    return {
        "depth": min(requested_depth, config["max_depth"]),
        "pv_limit": config["pv_limit"],
    }


def _classification_counts(summary: GameSummary, color: str, classification) -> None:
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


def analyze_pgn(
    pgn_text: str,
    engine_path: Optional[str] = None,
    depth: int = 16,
    mode: str = "normal",
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> GameSummary:
    """
    Analyse a PGN string and return a GameSummary.

    Args:
        pgn_text:    Raw PGN content.
        engine_path: Optional path to Stockfish binary.
        depth:       Analysis depth. Fast/normal modes cap this for responsiveness.
        mode:        fast, normal, or deep.
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
    config = _mode_config(mode, depth)

    boards: list[chess.Board] = []
    if positions:
        boards.append(positions[0][0])
        for board_before, move, *_ in positions:
            board_after = board_before.copy()
            board_after.push(move)
            boards.append(board_after)

    analysis_cache: dict[str, dict] = {}
    position_results = []

    with StockfishEngine(path=engine_path, depth=depth) as engine:
        for idx, board in enumerate(boards):
            fen = board.fen()
            include_pv = idx < len(boards) - 1
            cached = analysis_cache.get(fen)

            if cached is None or (include_pv and not cached["has_pv"]):
                eval_cp, best_move_san, pv = engine.analyse_position(
                    board,
                    depth=config["depth"],
                    include_pv=include_pv,
                    pv_limit=config["pv_limit"],
                )
                cached = {
                    "eval": eval_cp,
                    "best_move": best_move_san,
                    "pv": pv,
                    "has_pv": include_pv,
                }
                analysis_cache[fen] = cached

            position_results.append(cached)

        for idx, (board_before, _move, move_number, color, san) in enumerate(positions, 1):
            if progress_cb:
                label = f"{move_number}{'.' if color == 'White' else '...'}{san}"
                progress_cb(idx, total, label)

            fen_before = board_before.fen()
            before = position_results[idx - 1]
            after = position_results[idx]

            cp_loss = _cp_loss(before["eval"], after["eval"])
            classification = classify_move(cp_loss if cp_loss is not None else 0)

            analysis = MoveAnalysis(
                move_number=move_number,
                color=color,
                move_played=san,
                eval_before=before["eval"],
                eval_after=after["eval"],
                best_move=before["best_move"],
                cp_loss=cp_loss,
                classification=classification,
                pv=before["pv"],
                fen_before=fen_before,
            )
            summary.move_analyses.append(analysis)
            _classification_counts(summary, color, classification)

    summary.total_moves = len(summary.move_analyses)
    return summary
