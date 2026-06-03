from __future__ import annotations

import re
from dataclasses import dataclass

import chess.pgn


@dataclass(frozen=True)
class OpeningInfo:
    eco: str | None
    name: str
    matched_plies: int = 0


@dataclass(frozen=True)
class OpeningLine:
    eco: str
    name: str
    moves: tuple[str, ...]


OPENING_LINES: tuple[OpeningLine, ...] = (
    OpeningLine("A00", "Polish Opening", ("b4",)),
    OpeningLine("A01", "Nimzowitsch-Larsen Attack", ("b3",)),
    OpeningLine("A02", "Bird Opening", ("f4",)),
    OpeningLine("A04", "Reti Opening", ("Nf3",)),
    OpeningLine("A10", "English Opening", ("c4",)),
    OpeningLine("A20", "English Opening", ("c4", "e5")),
    OpeningLine("A30", "English Opening, Symmetrical Variation", ("c4", "c5")),
    OpeningLine("A40", "Queen's Pawn Game", ("d4",)),
    OpeningLine("A45", "Trompowsky Attack", ("d4", "Nf6", "Bg5")),
    OpeningLine("A46", "London System", ("d4", "Nf6", "Nf3", "d5", "Bf4")),
    OpeningLine("A80", "Dutch Defense", ("d4", "f5")),
    OpeningLine("B00", "King's Pawn Game", ("e4",)),
    OpeningLine("B01", "Scandinavian Defense", ("e4", "d5")),
    OpeningLine("B02", "Alekhine Defense", ("e4", "Nf6")),
    OpeningLine("B06", "Modern Defense", ("e4", "g6")),
    OpeningLine("B07", "Pirc Defense", ("e4", "d6", "d4", "Nf6", "Nc3", "g6")),
    OpeningLine("B10", "Caro-Kann Defense", ("e4", "c6")),
    OpeningLine("B12", "Caro-Kann Defense, Advance Variation", ("e4", "c6", "d4", "d5", "e5")),
    OpeningLine("B13", "Caro-Kann Defense, Exchange Variation", ("e4", "c6", "d4", "d5", "exd5", "cxd5")),
    OpeningLine("B15", "Caro-Kann Defense, Tartakower Variation", ("e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Nf6", "Nxf6+", "gxf6")),
    OpeningLine("B20", "Sicilian Defense", ("e4", "c5")),
    OpeningLine("B22", "Sicilian Defense, Alapin Variation", ("e4", "c5", "c3")),
    OpeningLine("B23", "Sicilian Defense, Closed Variation", ("e4", "c5", "Nc3")),
    OpeningLine("B27", "Sicilian Defense, Hyperaccelerated Dragon", ("e4", "c5", "Nf3", "g6")),
    OpeningLine("B30", "Sicilian Defense, Rossolimo Variation", ("e4", "c5", "Nf3", "Nc6", "Bb5")),
    OpeningLine("B32", "Sicilian Defense, Open", ("e4", "c5", "Nf3", "Nc6", "d4", "cxd4", "Nxd4")),
    OpeningLine("B40", "Sicilian Defense, Kan Variation", ("e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "a6")),
    OpeningLine("B50", "Sicilian Defense, Moscow Variation", ("e4", "c5", "Nf3", "d6", "Bb5+")),
    OpeningLine("B70", "Sicilian Defense, Dragon Variation", ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6")),
    OpeningLine("B76", "Sicilian Defense, Dragon Variation, Yugoslav Attack", ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6", "Be3", "Bg7", "f3")),
    OpeningLine("B90", "Sicilian Defense, Najdorf Variation", ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6")),
    OpeningLine("B92", "Sicilian Defense, Najdorf Variation, Opocensky Variation", ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Be2")),
    OpeningLine("B96", "Sicilian Defense, Najdorf Variation, English Attack", ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Be3")),
    OpeningLine("C00", "French Defense", ("e4", "e6")),
    OpeningLine("C02", "French Defense, Advance Variation", ("e4", "e6", "d4", "d5", "e5")),
    OpeningLine("C10", "French Defense, Classical Variation", ("e4", "e6", "d4", "d5", "Nc3", "Nf6")),
    OpeningLine("C15", "French Defense, Winawer Variation", ("e4", "e6", "d4", "d5", "Nc3", "Bb4")),
    OpeningLine("C20", "King's Pawn Game", ("e4", "e5")),
    OpeningLine("C22", "Center Game", ("e4", "e5", "d4", "exd4")),
    OpeningLine("C23", "Bishop's Opening", ("e4", "e5", "Bc4")),
    OpeningLine("C25", "Vienna Game", ("e4", "e5", "Nc3")),
    OpeningLine("C30", "King's Gambit", ("e4", "e5", "f4")),
    OpeningLine("C41", "Philidor Defense", ("e4", "e5", "Nf3", "d6")),
    OpeningLine("C42", "Petrov's Defense", ("e4", "e5", "Nf3", "Nf6")),
    OpeningLine("C44", "Ponziani Opening", ("e4", "e5", "Nf3", "Nc6", "c3")),
    OpeningLine("C45", "Scotch Game", ("e4", "e5", "Nf3", "Nc6", "d4")),
    OpeningLine("C46", "Four Knights Game", ("e4", "e5", "Nf3", "Nc6", "Nc3", "Nf6")),
    OpeningLine("C50", "Italian Game", ("e4", "e5", "Nf3", "Nc6", "Bc4")),
    OpeningLine("C53", "Italian Game, Giuoco Piano", ("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5")),
    OpeningLine("C55", "Italian Game, Two Knights Defense", ("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6")),
    OpeningLine("C60", "Ruy Lopez", ("e4", "e5", "Nf3", "Nc6", "Bb5")),
    OpeningLine("C65", "Ruy Lopez, Berlin Defense", ("e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6")),
    OpeningLine("C78", "Ruy Lopez, Morphy Defense", ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6")),
    OpeningLine("C80", "Ruy Lopez, Open Variation", ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Nxe4")),
    OpeningLine("C88", "Ruy Lopez, Closed", ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7")),
    OpeningLine("D00", "Queen's Pawn Game", ("d4", "d5")),
    OpeningLine("D02", "Queen's Pawn Game, London System", ("d4", "d5", "Nf3", "Nf6", "Bf4")),
    OpeningLine("D06", "Queen's Gambit", ("d4", "d5", "c4")),
    OpeningLine("D08", "Queen's Gambit, Albin Countergambit", ("d4", "d5", "c4", "e5")),
    OpeningLine("D10", "Queen's Gambit Declined, Slav Defense", ("d4", "d5", "c4", "c6")),
    OpeningLine("D20", "Queen's Gambit Accepted", ("d4", "d5", "c4", "dxc4")),
    OpeningLine("D30", "Queen's Gambit Declined", ("d4", "d5", "c4", "e6")),
    OpeningLine("D37", "Queen's Gambit Declined, Three Knights Variation", ("d4", "d5", "c4", "e6", "Nf3", "Nf6", "Nc3")),
    OpeningLine("D43", "Semi-Slav Defense", ("d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3", "e6")),
    OpeningLine("D80", "Grunfeld Defense", ("d4", "Nf6", "c4", "g6", "Nc3", "d5")),
    OpeningLine("E00", "Queen's Pawn Game", ("d4", "Nf6", "c4", "e6")),
    OpeningLine("E10", "Blumenfeld Countergambit", ("d4", "Nf6", "c4", "e6", "Nf3", "c5", "d5", "b5")),
    OpeningLine("E11", "Bogo-Indian Defense", ("d4", "Nf6", "c4", "e6", "Nf3", "Bb4+")),
    OpeningLine("E12", "Queen's Indian Defense", ("d4", "Nf6", "c4", "e6", "Nf3", "b6")),
    OpeningLine("E20", "Nimzo-Indian Defense", ("d4", "Nf6", "c4", "e6", "Nc3", "Bb4")),
    OpeningLine("E60", "King's Indian Defense", ("d4", "Nf6", "c4", "g6")),
    OpeningLine("E70", "King's Indian Defense", ("d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4")),
    OpeningLine("E90", "King's Indian Defense, Classical Variation", ("d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O")),
)


def recognise_opening(game: chess.pgn.Game, max_plies: int = 30) -> OpeningInfo | None:
    """Return the deepest known opening match for the first max_plies moves."""
    header_opening = _opening_from_headers(game.headers)
    played = _normalised_mainline(game, max_plies=max_plies)

    best = None
    for line in OPENING_LINES:
        if len(line.moves) <= len(played) and played[: len(line.moves)] == line.moves:
            if best is None or len(line.moves) > len(best.moves):
                best = line

    if best and (not header_opening or len(best.moves) >= 4):
        return OpeningInfo(eco=best.eco, name=best.name, matched_plies=len(best.moves))

    return header_opening


def _normalised_mainline(game: chess.pgn.Game, max_plies: int) -> tuple[str, ...]:
    board = game.board()
    moves: list[str] = []
    for node in game.mainline():
        if len(moves) >= max_plies:
            break
        san = board.san(node.move)
        moves.append(_normalise_san(san))
        board.push(node.move)
    return tuple(moves)


def _normalise_san(san: str) -> str:
    return san.replace("0-0-0", "O-O-O").replace("0-0", "O-O").rstrip("!?")


def _opening_from_headers(headers: chess.pgn.Headers) -> OpeningInfo | None:
    eco = _clean_header(headers.get("ECO"))
    opening = _clean_header(headers.get("Opening"))
    variation = _clean_header(headers.get("Variation"))

    if opening and variation and variation.casefold() not in opening.casefold():
        opening = f"{opening}, {variation}"

    if opening:
        return OpeningInfo(eco=eco, name=opening, matched_plies=0)

    eco_url = _clean_header(headers.get("ECOUrl"))
    if eco_url:
        name = _name_from_eco_url(eco_url)
        if name:
            return OpeningInfo(eco=eco, name=name, matched_plies=0)

    return None


def _clean_header(value: str | None) -> str | None:
    if not value or value == "?":
        return None
    return value.strip()


def _name_from_eco_url(url: str) -> str | None:
    slug = url.rstrip("/").split("/")[-1]
    if not slug:
        return None
    name = re.sub(r"[-_]+", " ", slug)
    name = re.sub(r"\s+", " ", name).strip()
    return name.title() if name else None
