"""
Data models for chess game analysis.
"""

import math
import chess
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class MoveClassification(str, Enum):
    BOOK = "Book"
    BRILLIANT = "Brilliant"
    BEST = "Best"
    EXCELLENT = "Excellent"
    GOOD = "Good"
    INACCURACY = "Inaccuracy"
    MISTAKE = "Mistake"
    MISS = "Miss"
    BLUNDER = "Blunder"


CLASSIFICATION_EMOJIS = {
    MoveClassification.BOOK: "",
    MoveClassification.BRILLIANT: "!!",
    MoveClassification.BEST: "★",
    MoveClassification.EXCELLENT: "!",
    MoveClassification.GOOD: "",
    MoveClassification.INACCURACY: "?!",
    MoveClassification.MISTAKE: "?",
    MoveClassification.MISS: "✗",
    MoveClassification.BLUNDER: "??",
}

CLASSIFICATION_COLORS = {
    MoveClassification.BOOK: "#94a3b8",
    MoveClassification.BRILLIANT: "#22d3ee",
    MoveClassification.BEST: "#34d399",
    MoveClassification.EXCELLENT: "#4ade80",
    MoveClassification.GOOD: "#a3e635",
    MoveClassification.INACCURACY: "#facc15",
    MoveClassification.MISTAKE: "#f97316",
    MoveClassification.MISS: "#f59e0b",
    MoveClassification.BLUNDER: "#ef4444",
}


# --- Win-probability helpers -------------------------------------------------
# Kept here (rather than importing from backend.services.accuracy) so the
# root-level analysis modules have no dependency on the backend package and to
# avoid import-order issues. The constant matches accuracy.py intentionally.
_WIN_CHANCE_K = 0.00368208
_MAX_CP_FOR_WIN_CHANCE = 4000.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def cp_to_win_chance(cp: Optional[float]) -> Optional[float]:
    """Centipawns (mover POV) -> win chance percentage (0-100)."""
    if cp is None:
        return None
    bounded = _clamp(float(cp), -_MAX_CP_FOR_WIN_CHANCE, _MAX_CP_FOR_WIN_CHANCE)
    win_chance = 50 + 50 * (2 / (1 + math.exp(-_WIN_CHANCE_K * bounded)) - 1)
    return _clamp(win_chance, 0.0, 100.0)


def win_probability_loss(eval_before: Optional[float], eval_after: Optional[float]) -> Optional[float]:
    """Win-probability lost by the move, in percentage points.

    ``eval_before`` is from the mover's POV; ``eval_after`` is reported from the
    opponent's POV by the engine, so it is negated back to the mover's POV.
    """
    if eval_before is None or eval_after is None:
        return None
    best = cp_to_win_chance(eval_before)
    played = cp_to_win_chance(-eval_after)
    if best is None or played is None:
        return None
    return max(0.0, best - played)


def _classify_by_cp_loss(cp_loss: Optional[float]) -> MoveClassification:
    """Fallback used only when evaluations are unavailable (e.g. mate-cut PVs)."""
    loss = cp_loss if cp_loss is not None else 0.0
    if loss <= 20:
        return MoveClassification.EXCELLENT
    if loss <= 50:
        return MoveClassification.GOOD
    if loss <= 100:
        return MoveClassification.INACCURACY
    if loss <= 200:
        return MoveClassification.MISTAKE
    return MoveClassification.BLUNDER


def classify_move(
    eval_before: Optional[float] = None,
    eval_after: Optional[float] = None,
    cp_loss: Optional[float] = None,
    *,
    is_book: bool = False,
    is_best_move: bool = False,
    is_sacrifice: bool = False,
) -> MoveClassification:
    """Classify a move using win-probability loss (consistent with accuracy).

    The labels mirror the vocabulary players already know from Chess.com/Lichess:
    Book, Brilliant, Best, Excellent, Good, Inaccuracy, Mistake, Miss, Blunder.
    Thresholds are in win-probability points lost, so a small slip in an equal
    position is treated as more serious than the same centipawn loss when already
    winning.
    """
    if is_book:
        return MoveClassification.BOOK

    if is_best_move:
        # Playing the engine's top move. A sound sacrifice that keeps the
        # position at least equal earns "Brilliant"; otherwise just "Best".
        if is_sacrifice and (cp_to_win_chance(eval_before) or 0.0) >= 50.0:
            return MoveClassification.BRILLIANT
        return MoveClassification.BEST

    wpl = win_probability_loss(eval_before, eval_after)
    if wpl is None:
        return _classify_by_cp_loss(cp_loss)

    best_win_chance = cp_to_win_chance(eval_before) or 0.0
    played_win_chance = cp_to_win_chance(-eval_after) if eval_after is not None else 0.0

    # "Miss": a clearly winning continuation was available and thrown away, but
    # the position is not yet lost (that would be a Blunder).
    if wpl >= 10.0 and best_win_chance >= 85.0 and (played_win_chance or 0.0) >= 50.0:
        return MoveClassification.MISS

    if wpl <= 2.0:
        return MoveClassification.EXCELLENT
    if wpl <= 5.0:
        return MoveClassification.GOOD
    if wpl <= 10.0:
        return MoveClassification.INACCURACY
    if wpl <= 20.0:
        return MoveClassification.MISTAKE
    return MoveClassification.BLUNDER


@dataclass
class MoveAnalysis:
    move_number: int
    color: str
    move_played: str
    eval_before: Optional[float]
    eval_after: Optional[float]
    best_move: Optional[str]
    cp_loss: Optional[float]
    classification: MoveClassification
    pv: list = field(default_factory=list)
    fen_before: str = ""

    @property
    def eval_white_pov(self) -> Optional[float]:
        """Evaluation from White's POV in pawns (for graph)."""
        if self.eval_before is None:
            return None
        val = self.eval_before / 100
        return val if self.color == "White" else -val

    @property
    def display_label(self) -> str:
        dot = "." if self.color == "White" else "…"
        return f"{self.move_number}{dot} {self.move_played}"


@dataclass
class GameSummary:
    white_player: str
    black_player: str
    event: str
    date: str
    result: str
    total_moves: int
    opening_name: Optional[str] = None
    eco_code: Optional[str] = None
    opening_matched_plies: int = 0
    white_inaccuracies: int = 0
    white_mistakes: int = 0
    white_blunders: int = 0
    black_inaccuracies: int = 0
    black_mistakes: int = 0
    black_blunders: int = 0
    move_analyses: list = field(default_factory=list)
    initial_fen: str = chess.STARTING_FEN

    def record_classification(self, color: str, classification: MoveClassification) -> None:
        """Tally one analysed move into this game's per-side error counters.

        Increments the inaccuracy/mistake/blunder count for ``color``
        ("White" or "Black"). A "Miss" (thrown-away winning chance) is counted
        as a mistake. Non-error classifications are not counted. Intended to be
        called once per move while building the summary.
        """
        counters = {
            MoveClassification.INACCURACY: ("white_inaccuracies", "black_inaccuracies"),
            MoveClassification.MISTAKE: ("white_mistakes", "black_mistakes"),
            MoveClassification.MISS: ("white_mistakes", "black_mistakes"),
            MoveClassification.BLUNDER: ("white_blunders", "black_blunders"),
        }
        attrs = counters.get(classification)
        if attrs is None:
            return
        attr = attrs[0] if color == "White" else attrs[1]
        setattr(self, attr, getattr(self, attr) + 1)
