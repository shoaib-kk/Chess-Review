"""PGN parsing: split a multi-game PGN and extract per-game / per-move data.

Pure parsing only — no engine work and no DB writes happen here.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from typing import Iterator, Optional

import chess
import chess.pgn


@dataclass
class ParsedMove:
    ply: int  # 1-based half-move index
    fen_before: str  # FEN of the position *before* this move
    uci: str  # the move played, in UCI
    turn: str  # "white" / "black" — side to move at fen_before
    clock_seconds: Optional[int] = None  # remaining clock if present in PGN


@dataclass
class ParsedGame:
    pgn_raw: str
    pgn_hash: str
    time_control: Optional[str]
    date_played: Optional[str]
    result: Optional[str]
    color_played: Optional[str]  # target player's colour, "white"/"black"/None
    opponent: Optional[str]
    moves: list[ParsedMove] = field(default_factory=list)


def _hash_pgn(pgn_text: str) -> str:
    return hashlib.sha256(pgn_text.strip().encode("utf-8")).hexdigest()


def _detect_color(headers: chess.pgn.Headers, username: Optional[str]) -> tuple[
    Optional[str], Optional[str]
]:
    """Return (color_played, opponent) for the target username, case-insensitive."""
    white = headers.get("White", "") or ""
    black = headers.get("Black", "") or ""
    if not username:
        return None, None
    uname = username.strip().lower()
    if white.strip().lower() == uname:
        return "white", black or None
    if black.strip().lower() == uname:
        return "black", white or None
    return None, None


def _iter_moves(game: chess.pgn.Game) -> Iterator[ParsedMove]:
    board = game.board()
    ply = 0
    node = game
    while node.variations:
        node = node.variation(0)
        move = node.move
        ply += 1
        turn = "white" if board.turn == chess.WHITE else "black"
        clock = node.clock()  # seconds remaining, or None
        yield ParsedMove(
            ply=ply,
            fen_before=board.fen(),
            uci=move.uci(),
            turn=turn,
            clock_seconds=int(clock) if clock is not None else None,
        )
        board.push(move)


def parse_pgn(pgn_string: str, username: Optional[str] = None) -> list[ParsedGame]:
    """Parse every game in a (possibly multi-game) PGN string.

    ``username`` is used to tag each game with the target player's colour and the
    opponent. Games that can't be parsed are skipped rather than aborting the run.
    """
    stream = io.StringIO(pgn_string)
    games: list[ParsedGame] = []

    while True:
        try:
            game = chess.pgn.read_game(stream)
        except Exception:
            # A malformed game advances the stream; keep going with the next one.
            continue
        if game is None:
            break

        headers = game.headers
        color_played, opponent = _detect_color(headers, username)
        # Re-serialise so each game's pgn_raw is a single, self-contained game.
        pgn_raw = str(game).strip()

        games.append(
            ParsedGame(
                pgn_raw=pgn_raw,
                pgn_hash=_hash_pgn(pgn_raw),
                time_control=headers.get("TimeControl"),
                date_played=headers.get("UTCDate") or headers.get("Date"),
                result=headers.get("Result"),
                color_played=color_played,
                opponent=opponent,
                moves=list(_iter_moves(game)),
            )
        )

    return games
