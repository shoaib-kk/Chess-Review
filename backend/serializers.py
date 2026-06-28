from __future__ import annotations

import chess

from .services.accuracy import move_accuracy, phase_weight, weighted_average


def _enum_value(value):
    return getattr(value, "value", value)


def _move_derivatives(fen: str, played_san: str, best_san: str | None) -> dict:
    played_move_uci = None
    best_move_uci = None
    fen_after = fen

    try:
        board = chess.Board(fen)
        if best_san:
            try:
                best_move_uci = board.parse_san(best_san).uci()
            except Exception:
                best_move_uci = None

        played_move = board.parse_san(played_san)
        played_move_uci = played_move.uci()
        board.push(played_move)
        fen_after = board.fen()
    except Exception:
        pass

    return {
        "fen_after": fen_after,
        "played_move_uci": played_move_uci,
        "best_move_uci": best_move_uci,
    }


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _result_for_color(result: str, color: str | None) -> str | None:
    if not color:
        return None
    if result == "1/2-1/2":
        return "draw"
    if result == "1-0":
        return "win" if color == "White" else "loss"
    if result == "0-1":
        return "win" if color == "Black" else "loss"
    return "unknown"


def _user_color(summary, username: str | None) -> str | None:
    if not username:
        return None
    normalized = username.casefold()
    if summary.white_player.casefold() == normalized:
        return "White"
    if summary.black_player.casefold() == normalized:
        return "Black"
    return None


def _classification_counts(summary, color: str | None) -> tuple[int | None, int | None, int | None]:
    if color == "White":
        return summary.white_inaccuracies, summary.white_mistakes, summary.white_blunders
    if color == "Black":
        return summary.black_inaccuracies, summary.black_mistakes, summary.black_blunders
    return None, None, None


def serialize_game_summary(summary, username: str | None = None) -> dict:
    moves = []
    user_color = _user_color(summary, username)
    user_inaccuracies, user_mistakes, user_blunders = _classification_counts(summary, user_color)
    white_accuracies: list[tuple[float, float]] = []
    black_accuracies: list[tuple[float, float]] = []
    white_cp_losses: list[float] = []
    black_cp_losses: list[float] = []

    for ply_index, move in enumerate(summary.move_analyses, start=1):
        classification = _enum_value(move.classification)
        derived = _move_derivatives(move.fen_before, move.move_played, move.best_move)
        accuracy = move_accuracy(move.eval_before, move.eval_after, move.cp_loss)
        weight = phase_weight(ply_index, summary.total_moves)

        if move.color == "White":
            if accuracy is not None:
                white_accuracies.append((accuracy, weight))
            if move.cp_loss is not None:
                white_cp_losses.append(move.cp_loss)
        else:
            if accuracy is not None:
                black_accuracies.append((accuracy, weight))
            if move.cp_loss is not None:
                black_cp_losses.append(move.cp_loss)

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
                "move_accuracy": round(accuracy, 1) if accuracy is not None else None,
                "classification": classification,
                "pv": move.pv,
                "fen_before": move.fen_before,
                "top_moves": [
                    {"move": cand["move"], "eval": cand["eval"]}
                    for cand in getattr(move, "top_moves", [])
                ],
                **derived,
            }
        )

    user_accuracies = white_accuracies if user_color == "White" else black_accuracies if user_color == "Black" else []
    user_cp_losses = white_cp_losses if user_color == "White" else black_cp_losses if user_color == "Black" else []
    opponent = None
    if user_color == "White":
        opponent = summary.black_player
    elif user_color == "Black":
        opponent = summary.white_player

    return {
        "white_player": summary.white_player,
        "black_player": summary.black_player,
        "event": summary.event,
        "date": summary.date,
        "result": summary.result,
        "total_moves": summary.total_moves,
        "initial_fen": summary.initial_fen,
        "opening_name": summary.opening_name,
        "eco_code": summary.eco_code,
        "opening_matched_plies": summary.opening_matched_plies,
        "white_inaccuracies": summary.white_inaccuracies,
        "white_mistakes": summary.white_mistakes,
        "white_blunders": summary.white_blunders,
        "black_inaccuracies": summary.black_inaccuracies,
        "black_mistakes": summary.black_mistakes,
        "black_blunders": summary.black_blunders,
        "white_accuracy": weighted_average(white_accuracies),
        "black_accuracy": weighted_average(black_accuracies),
        "user_accuracy": weighted_average(user_accuracies),
        "average_cp_loss_white": _average(white_cp_losses),
        "average_cp_loss_black": _average(black_cp_losses),
        "average_cp_loss_user": _average(user_cp_losses),
        "user_color": user_color,
        "user_username": username if user_color else None,
        "opponent_username": opponent,
        "user_result": _result_for_color(summary.result, user_color),
        "user_inaccuracies": user_inaccuracies,
        "user_mistakes": user_mistakes,
        "user_blunders": user_blunders,
        "move_analyses": moves,
    }
