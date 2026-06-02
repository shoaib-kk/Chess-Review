from __future__ import annotations

import chess


def _enum_value(value):
    return getattr(value, "value", value)


def _san_to_uci(fen: str, san: str | None) -> str | None:
    if not san:
        return None
    try:
        board = chess.Board(fen)
        return board.parse_san(san).uci()
    except Exception:
        return None


def _fen_after(fen: str, san: str) -> str:
    try:
        board = chess.Board(fen)
        board.push(board.parse_san(san))
        return board.fen()
    except Exception:
        return fen


def serialize_game_summary(summary) -> dict:
    moves = []

    for move in summary.move_analyses:
        classification = _enum_value(move.classification)
        fen_after = _fen_after(move.fen_before, move.move_played)

        moves.append(
            {
                "move_number": move.move_number,
                "color": move.color,
                "move_played": move.move_played,
                "eval_before": move.eval_before,
                "eval_after": move.eval_after,
                "eval_white_pov": move.eval_white_pov,
                "best_move": move.best_move,
                "cp_loss": move.cp_loss,
                "classification": classification,
                "pv": move.pv,
                "fen_before": move.fen_before,
                "fen_after": fen_after,
                "played_move_uci": _san_to_uci(move.fen_before, move.move_played),
                "best_move_uci": _san_to_uci(move.fen_before, move.best_move),
            }
        )

    return {
        "white_player": summary.white_player,
        "black_player": summary.black_player,
        "event": summary.event,
        "date": summary.date,
        "result": summary.result,
        "total_moves": summary.total_moves,
        "initial_fen": summary.initial_fen,
        "white_inaccuracies": summary.white_inaccuracies,
        "white_mistakes": summary.white_mistakes,
        "white_blunders": summary.white_blunders,
        "black_inaccuracies": summary.black_inaccuracies,
        "black_mistakes": summary.black_mistakes,
        "black_blunders": summary.black_blunders,
        "move_analyses": moves,
    }
