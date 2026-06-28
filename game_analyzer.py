"""
services/game_analyzer.py
Orchestrates PGN parsing → engine evaluation → GameSummary.
"""

import chess
from typing import Optional, Callable

from models import MoveAnalysis, GameSummary, classify_move
from opening_recognition import recognise_opening
from pgn_parser import load_game_from_pgn_string, extract_headers, iter_positions
from stockfish_engine import StockfishEngine


# Depth caps per mode. "normal" is the default the UI uses; depth 12 was too
# shallow to see the short tactics amateurs actually blunder, so it would happily
# label a losing move "Excellent". 16 is a reasonable accuracy/speed balance.
#
# ``multipv`` is the number of candidate lines requested per position. The UI
# shows the top few choices with their evals, and the gap between the best and
# second-best line tells us how forced the position was (used to award "Great").
ANALYSIS_MODES = {
    "fast": {"max_depth": 10, "multipv": 2},
    "normal": {"max_depth": 16, "multipv": 3},
    "deep": {"max_depth": 24, "multipv": 4},
}

# How many plies of each principal variation we keep as SAN, so the best line is
# long enough to actually step through on the board.
PV_SAN_LENGTH = 10

# Hard ceiling on plies analysed. Every ply is a (slow) Stockfish call, so an
# oversized PGN is a CPU-exhaustion vector. Real games are well under this — a
# 300-move game is 600 plies — so legitimate input is never rejected, while a
# pathological multi-thousand-move PGN is refused before the engine loop.
MAX_ANALYSIS_PLIES = 600


def _cp_loss(eval_before: Optional[float], eval_after: Optional[float]) -> Optional[float]:
    if eval_before is None or eval_after is None:
        return None
    mover_eval_after = -eval_after
    loss = eval_before - mover_eval_after
    return max(0.0, loss)


_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _material(board: chess.Board, color: bool) -> int:
    return sum(
        _PIECE_VALUES[piece.piece_type]
        for piece in board.piece_map().values()
        if piece.color == color
    )


def _is_sacrifice(board_before: chess.Board, pv_san: list) -> bool:
    """Heuristic: does the best line give up material the mover never wins back?

    Only used to upgrade a "Best" move to "Brilliant". We replay the engine's
    principal variation (which begins with the played/best move) and check
    whether the mover ends up materially down. Conservative on purpose: a false
    "Brilliant" is worse than a missed one.
    """
    if not pv_san:
        return False
    mover = board_before.turn
    start_balance = _material(board_before, mover) - _material(board_before, not mover)

    board = board_before.copy()
    played = 0
    for san in pv_san:
        try:
            board.push_san(san)
        except (ValueError, AssertionError):
            break
        played += 1
        if played >= 8:
            break
    if played == 0:
        return False

    end_balance = _material(board, mover) - _material(board, not mover)
    # Mover ended at least a minor piece down relative to where they started.
    return (start_balance - end_balance) >= 2


def _offers_material(board_before: chess.Board, played_move: chess.Move) -> bool:
    """Does the played move hand the opponent a material-winning capture?

    One-ply check on the position after the move: if the opponent can capture for
    a net gain of at least a minor piece (accounting for an immediate recapture),
    the move offered material. Combined with engine approval this is what makes a
    move a *sacrifice* rather than a blunder — see ``classify_move``.
    """
    board = board_before.copy()
    try:
        board.push(played_move)
    except (ValueError, AssertionError):
        return False

    best_net = 0
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        if board.is_en_passant(move):
            captured_val = _PIECE_VALUES[chess.PAWN]
        else:
            victim = board.piece_at(move.to_square)
            if victim is None:
                continue
            captured_val = _PIECE_VALUES[victim.piece_type]
        attacker = board.piece_at(move.from_square)
        attacker_val = _PIECE_VALUES[attacker.piece_type] if attacker else 0

        board.push(move)
        can_recapture = any(
            reply.to_square == move.to_square and board.is_capture(reply)
            for reply in board.legal_moves
        )
        board.pop()

        net = captured_val - attacker_val if can_recapture else captured_val
        best_net = max(best_net, net)

    return best_net >= 2


def _mode_config(mode: str, requested_depth: int) -> dict:
    config = ANALYSIS_MODES.get(mode, ANALYSIS_MODES["normal"])
    return {
        "depth": min(requested_depth, config["max_depth"]),
        "multipv": config["multipv"],
    }


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
    opening = recognise_opening(game)

    summary = GameSummary(
        white_player=headers["white"],
        black_player=headers["black"],
        event=headers["event"],
        date=headers["date"],
        result=headers["result"],
        total_moves=0,
        initial_fen=game.board().fen(),
        opening_name=opening.name if opening else None,
        eco_code=opening.eco if opening else None,
        opening_matched_plies=opening.matched_plies if opening else 0,
    )

    positions = list(iter_positions(game))
    if len(positions) > MAX_ANALYSIS_PLIES:
        raise ValueError(
            f"PGN is too long to analyse ({len(positions)} plies; limit is {MAX_ANALYSIS_PLIES})."
        )
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
            if progress_cb:
                # Fire before the (slow) engine call so the UI reflects the
                # position being analysed now, not the one just finished.
                if idx < len(positions):
                    _, _, move_number, color, san = positions[idx]
                    label = f"{move_number}{'.' if color == 'White' else '...'}{san}"
                else:
                    label = "final position"
                progress_cb(idx + 1, len(boards), label)

            fen = board.fen()
            include_pv = idx < len(boards) - 1
            cached = analysis_cache.get(fen)

            if cached is None or (include_pv and not cached["has_pv"]):
                if include_pv:
                    candidates = engine.analyse_candidates(
                        board,
                        depth=config["depth"],
                        multipv=config["multipv"],
                        pv_limit=PV_SAN_LENGTH,
                    )
                    best = candidates[0] if candidates else None
                    cached = {
                        "eval": best["eval"] if best else None,
                        "best_move": best["move"] if best else None,
                        "pv": best["pv"] if best else [],
                        "top_moves": candidates,
                        "has_pv": True,
                    }
                else:
                    eval_cp, _best, _pv = engine.analyse_position(
                        board, depth=config["depth"], include_pv=False
                    )
                    cached = {
                        "eval": eval_cp,
                        "best_move": None,
                        "pv": [],
                        "top_moves": [],
                        "has_pv": False,
                    }
                analysis_cache[fen] = cached

            position_results.append(cached)

        for idx, (board_before, played_move, move_number, color, san) in enumerate(positions, 1):
            fen_before = board_before.fen()
            before = position_results[idx - 1]
            after = position_results[idx]

            cp_loss = _cp_loss(before["eval"], after["eval"])

            best_san = before["best_move"]
            is_best = best_san is not None and san == best_san
            is_book = idx <= summary.opening_matched_plies
            is_sacrifice = _is_sacrifice(board_before, before["pv"]) if is_best else False
            offers_material = _offers_material(board_before, played_move)

            top_moves = before["top_moves"]
            second_best_eval = top_moves[1]["eval"] if len(top_moves) > 1 else None

            classification = classify_move(
                eval_before=before["eval"],
                eval_after=after["eval"],
                cp_loss=cp_loss,
                is_book=is_book,
                is_best_move=is_best,
                is_sacrifice=is_sacrifice,
                offers_material=offers_material,
                second_best_eval=second_best_eval,
            )

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
                top_moves=[
                    {"move": cand["move"], "eval": cand["eval"]}
                    for cand in top_moves
                ],
            )
            summary.move_analyses.append(analysis)
            summary.record_classification(color, classification)

    summary.total_moves = len(summary.move_analyses)
    return summary
