from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


WIN_CHANCE_K = 0.00368208
MAX_CP_FOR_WIN_CHANCE = 4000.0


@dataclass(frozen=True)
class AccuracyComparison:
    move_number: int
    color: str
    cp_loss: float | None
    win_probability_loss: float | None
    legacy_accuracy: float | None
    new_accuracy: float | None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def cp_to_win_chance(cp: float | None) -> float | None:
    """Convert a centipawn score from the mover's POV to win chance percentage."""
    if cp is None:
        return None

    bounded_cp = clamp(float(cp), -MAX_CP_FOR_WIN_CHANCE, MAX_CP_FOR_WIN_CHANCE)
    win_chance = 50 + 50 * (2 / (1 + math.exp(-WIN_CHANCE_K * bounded_cp)) - 1)
    return clamp(win_chance, 0.0, 100.0)


def legacy_cp_loss_accuracy(cp_loss: float | None) -> float | None:
    """Previous CP-loss-only model, kept for comparison tooling."""
    if cp_loss is None:
        return None
    if cp_loss <= 0:
        return 100.0
    accuracy = 103.1668 * math.exp(-0.04354 * cp_loss) - 3.1669
    return clamp(accuracy, 0.0, 100.0)


def win_probability_loss(eval_before: float | None, eval_after: float | None) -> float | None:
    """
    Return lost win probability in percentage points.

    The analyzer stores eval_before from the side-to-move POV. After the move,
    Stockfish reports from the opponent's POV, so it is negated back to the
    original mover's POV.
    """
    if eval_before is None or eval_after is None:
        return None

    best_win_chance = cp_to_win_chance(eval_before)
    played_win_chance = cp_to_win_chance(-eval_after)
    if best_win_chance is None or played_win_chance is None:
        return None
    return max(0.0, best_win_chance - played_win_chance)


def move_accuracy(eval_before: float | None, eval_after: float | None, cp_loss: float | None = None) -> float | None:
    """
    Smooth move accuracy from win-probability loss.

    Perfect and near-perfect moves remain close to 100. Meaningful mistakes in
    equal positions fall faster because equal positions are win-prob sensitive,
    while CP loss in already-winning positions is naturally dampened.
    """
    loss = win_probability_loss(eval_before, eval_after)
    if loss is None:
        return legacy_cp_loss_accuracy(cp_loss)
    if loss <= 0:
        return 100.0

    accuracy = 100 * math.exp(-0.025 * (loss**1.35))
    return clamp(accuracy, 0.0, 100.0)


def phase_weight(ply_index: int, total_plies: int) -> float:
    if total_plies <= 0:
        return 1.0
    if ply_index <= 12:
        return 0.85
    if ply_index >= max(30, int(total_plies * 0.65)):
        return 1.05
    return 1.0


def weighted_average(values: Iterable[tuple[float, float]]) -> float | None:
    weighted_sum = 0.0
    total_weight = 0.0
    for value, weight in values:
        weighted_sum += value * weight
        total_weight += weight
    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 1)


def compare_accuracy_models(moves: Iterable[object]) -> list[AccuracyComparison]:
    """Utility for validating legacy CP-loss accuracy against the new model."""
    comparisons: list[AccuracyComparison] = []
    for move in moves:
        comparisons.append(
            AccuracyComparison(
                move_number=getattr(move, "move_number"),
                color=getattr(move, "color"),
                cp_loss=getattr(move, "cp_loss", None),
                win_probability_loss=win_probability_loss(
                    getattr(move, "eval_before", None),
                    getattr(move, "eval_after", None),
                ),
                legacy_accuracy=legacy_cp_loss_accuracy(getattr(move, "cp_loss", None)),
                new_accuracy=move_accuracy(
                    getattr(move, "eval_before", None),
                    getattr(move, "eval_after", None),
                    getattr(move, "cp_loss", None),
                ),
            )
        )
    return comparisons


def summarize_accuracy_comparison(moves: Iterable[object], chesscom_accuracy: float | None = None) -> dict:
    """Game-level validation summary for comparing the legacy and new models."""
    move_list = list(moves)
    comparisons = compare_accuracy_models(move_list)
    legacy_values = [item.legacy_accuracy for item in comparisons if item.legacy_accuracy is not None]
    cp_losses = [item.cp_loss for item in comparisons if item.cp_loss is not None]

    weighted_new_values = []
    total_plies = len(move_list)
    for index, item in enumerate(comparisons, start=1):
        if item.new_accuracy is not None:
            weighted_new_values.append((item.new_accuracy, phase_weight(index, total_plies)))

    return {
        "legacy_accuracy": round(sum(legacy_values) / len(legacy_values), 1) if legacy_values else None,
        "new_accuracy": weighted_average(weighted_new_values),
        "average_cp_loss": round(sum(cp_losses) / len(cp_losses), 1) if cp_losses else None,
        "chesscom_accuracy": chesscom_accuracy,
        "moves": [item.__dict__ for item in comparisons],
    }
