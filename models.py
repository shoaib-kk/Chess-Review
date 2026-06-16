"""
Data models for chess game analysis.
"""

import chess
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class MoveClassification(str, Enum):
    EXCELLENT = "Excellent"
    INACCURACY = "Inaccuracy"
    MISTAKE = "Mistake"
    BLUNDER = "Blunder"


CLASSIFICATION_EMOJIS = {
    MoveClassification.EXCELLENT: "✓",
    MoveClassification.INACCURACY: "?!",
    MoveClassification.MISTAKE: "?",
    MoveClassification.BLUNDER: "??",
}

CLASSIFICATION_COLORS = {
    MoveClassification.EXCELLENT: "#4ade80",
    MoveClassification.INACCURACY: "#facc15",
    MoveClassification.MISTAKE: "#f97316",
    MoveClassification.BLUNDER: "#ef4444",
}


def classify_move(cp_loss: float) -> MoveClassification:
    if cp_loss <= 30:
        return MoveClassification.EXCELLENT
    elif cp_loss <= 80:
        return MoveClassification.INACCURACY
    elif cp_loss <= 200:
        return MoveClassification.MISTAKE
    else:
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
        ("White" or "Black"). EXCELLENT moves are not counted. Intended to be
        called once per move while building the summary.
        """
        counters = {
            MoveClassification.INACCURACY: ("white_inaccuracies", "black_inaccuracies"),
            MoveClassification.MISTAKE: ("white_mistakes", "black_mistakes"),
            MoveClassification.BLUNDER: ("white_blunders", "black_blunders"),
        }
        attrs = counters.get(classification)
        if attrs is None:
            return
        attr = attrs[0] if color == "White" else attrs[1]
        setattr(self, attr, getattr(self, attr) + 1)
