"""
PGN loading helpers for the chess reviewer.
"""

import io

import chess.pgn


def load_game_from_pgn_string(pgn_text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("No valid PGN game found.")
    return game


def extract_headers(game: chess.pgn.Game) -> dict[str, str]:
    headers = game.headers
    return {
        "white": headers.get("White", "White"),
        "black": headers.get("Black", "Black"),
        "event": headers.get("Event", "Unknown event"),
        "date": headers.get("Date", "Unknown date"),
        "result": headers.get("Result", "*"),
    }


def iter_positions(game: chess.pgn.Game):
    board = game.board()
    for node in game.mainline():
        move = node.move
        san = board.san(move)
        move_number = board.fullmove_number
        color = "White" if board.turn == chess.WHITE else "Black"
        yield board.copy(), move, move_number, color, san
        board.push(move)
